import time
from core.runtime import current_run
from dotenv import load_dotenv

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode

from core.context_budget import fit_messages
from core.governance import bind_capabilities, tool_contract
from core.models import get_chat_model
from core.context_pages import resolve_context_pages, selected_tool_names, render_pages, preload_context
from core.prompt_context import with_permanent_context
from core.runtime_context import ensure_runtime_active
from tools import supervisor_tools
from prompt import SUPERVISOR_BOOTSTRAP

load_dotenv()


class CoraState(MessagesState):
    system_prompt: str
    memory_context: str
    context_pages: list[str]
    selected_tool_names: list[str]


llm = get_chat_model("supervisor", temperature=0.0)
# "Connected" means the graph may expose these capabilities dynamically.
# This does not bind all schemas to every model call.
bind_capabilities("supervisor", supervisor_tools)
# Compatibility hook for tests/instrumentation that replace the supervisor model.
# Production keeps this None and uses the task-scoped binding below.
model_with_tools = None
PARALLEL_READ_TOOLS = {t.name for t in supervisor_tools if tool_contract(t).effect in {"read","compute"} and tool_contract(t).retry == "safe"}
TERMINAL_DELEGATION_TOOLS = {t.name for t in supervisor_tools if tool_contract(t).response_mode == "final"}


def _latest_user_text(messages) -> str:
    for message in reversed(messages):
        role = getattr(message, "type", None)
        if role in {"human", "user"}:
            return str(getattr(message, "content", ""))
        if isinstance(message, dict) and message.get("role") == "user":
            return str(message.get("content", ""))
    return ""


def _runtime_system_prompt(messages) -> tuple[str, str, list[str], list[str]]:
    """Assemble only task-relevant context; owner/memory data is loaded on call."""
    user_text = _latest_user_text(messages)
    selected = resolve_context_pages(user_text)
    page_text = render_pages(selected)
    prompt = with_permanent_context(SUPERVISOR_BOOTSTRAP)
    if page_text:
        prompt += "\n\nTASK CONTEXT\n" + page_text

    preload_started = time.perf_counter()
    preloaded_context, preload_providers = preload_context(selected)
    tool_names = selected_tool_names(selected)

    run = current_run.get()
    if run:
        run.timings["memory_ms"] = 0.0
        run.timings["memory_available"] = 1
        run.timings["context_pages"] = [page.id for page in selected]
        run.timings["preloaded_context"] = preload_providers
        run.timings["preloaded_context_chars"] = len(preloaded_context)
        run.timings["preload_ms"] = round((time.perf_counter() - preload_started) * 1000, 2)
        run.timings["selected_tools"] = tool_names
        run.timings["selected_tool_count"] = len(tool_names)
        from core.event_bus import bus
        bus.publish(
            "context.pages_selected",
            "context",
            run_id=run.id,
            thread_id=run.thread_id,
            payload={
                "pages": [page.id for page in selected],
                "preloaded": preload_providers,
                "tools": tool_names,
            },
        )
    return prompt, preloaded_context, [page.id for page in selected], tool_names


def prepare_turn(state: CoraState):
    started = time.perf_counter()
    prompt, memory_context, context_pages, tool_names = _runtime_system_prompt(state["messages"])
    run = current_run.get()
    if run: run.timings["prompt_ms"] = round((time.perf_counter()-started)*1000,2)
    return {"system_prompt": prompt, "memory_context":memory_context, "context_pages":context_pages, "selected_tool_names":tool_names}


def _tool_name(call) -> str:
    if isinstance(call, dict):
        return str(call.get("name", ""))
    return str(getattr(call, "name", ""))


def _bounded_tool_calls(response: AIMessage) -> AIMessage:
    calls = list(getattr(response, "tool_calls", []) or [])
    if len(calls) <= 1:
        return response

    names = {_tool_name(call) for call in calls}
    selected = calls[:4] if names and names <= PARALLEL_READ_TOOLS else calls[:1]
    return AIMessage(
        content=response.content,
        additional_kwargs=response.additional_kwargs,
        response_metadata=response.response_metadata,
        tool_calls=selected,
        id=response.id,
        usage_metadata=getattr(response, "usage_metadata", None),
    )


def call_model(state: CoraState):
    ensure_runtime_active()
    messages_for_llm = [
        SystemMessage(content=state["system_prompt"])
    ]
    if state.get('memory_context'):
        messages_for_llm.append(HumanMessage(content=state['memory_context'],name='context_data'))
    messages_for_llm += list(state["messages"])

    tool_map = {tool.name: tool for tool in supervisor_tools}
    selected_tools = [tool_map[name] for name in state.get("selected_tool_names", []) if name in tool_map]

    # Tests/instrumentation can inject a model that already owns its tool binding.
    # In production model_with_tools is None and only selected schemas are bound.
    if model_with_tools is not None:
        response = model_with_tools.invoke(
            fit_messages(messages_for_llm, tools=selected_tools if selected_tools else None, reserve=128)
        )
    elif selected_tools:
        model = llm.bind_tools(selected_tools)
        response = model.invoke(fit_messages(messages_for_llm, tools=selected_tools))
    else:
        response = llm.invoke(fit_messages(messages_for_llm, reserve=128))
    return {"messages": [_bounded_tool_calls(response)]}


def should_continue(state: CoraState):
    ensure_runtime_active()
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return END


def after_tools(state: CoraState):
    """
    A delegated specialist already returns user-facing natural language.
    End the run there instead of paying for a redundant Supervisor rewrite.
    """
    ensure_runtime_active()
    tool_failed = False
    for message in reversed(state["messages"]):
        if getattr(message, "type", None) == "tool" and getattr(message, "status", None) == "error":
            tool_failed = True
        calls = getattr(message, "tool_calls", None)
        if calls:
            names = {_tool_name(call) for call in calls}
            if len(calls) == 1 and names <= TERMINAL_DELEGATION_TOOLS and not tool_failed:
                return END
            break
    return "agent"


tool_node = ToolNode(supervisor_tools, handle_tool_errors=True)

workflow = StateGraph(CoraState)
workflow.add_node("prepare", prepare_turn)
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

workflow.add_edge(START, "prepare")
workflow.add_edge("prepare", "agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        END: END,
    },
)
workflow.add_conditional_edges(
    "tools",
    after_tools,
    {
        "agent": "agent",
        END: END,
    },
)

graph = workflow.compile()
