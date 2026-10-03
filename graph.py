import time
from core.runtime import current_run
from dotenv import load_dotenv

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode

from core.memory import search_memories
from core.context_budget import fit_messages
from core.governance import bind_capabilities, tool_contract
from core.models import get_chat_model
from core.prompt_context import with_permanent_context
from core.runtime_context import ensure_runtime_active
from tools import supervisor_tools
from prompt import SUPERVISOR_PROMPT

load_dotenv()


class CoraState(MessagesState):
    system_prompt: str


llm = get_chat_model("supervisor", temperature=0.0)
model_with_tools = llm.bind_tools(bind_capabilities('supervisor', supervisor_tools))

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


def _runtime_system_prompt(messages) -> str:
    """Build expensive turn context exactly once before the first model call."""
    user_text = _latest_user_text(messages)

    relevant = []
    retrieval_started = time.perf_counter()
    if user_text.strip():
        try:
            relevant = search_memories(user_text, limit=6)
        except Exception:
            relevant = []

    run = current_run.get()
    if run: run.timings["memory_ms"] = round((time.perf_counter()-retrieval_started)*1000,2)
    sections = [with_permanent_context(SUPERVISOR_PROMPT)]
    if relevant:
        lines = []
        for memory in relevant:
            lines.append(
                f"- [{memory.get('memory_type', 'memory')}] "
                f"{memory.get('key', '')}: {memory.get('content', '')}"
            )
        sections.append(
            "RELEVANT PERSISTENT MEMORIES\n"
            "These are retrieved memories, not absolute truth. Prefer newer explicit "
            "user information when conflicts exist.\n" + "\n".join(lines)
        )
    return "\n\n".join(sections)


def prepare_turn(state: CoraState):
    started = time.perf_counter()
    prompt = _runtime_system_prompt(state["messages"])
    run = current_run.get()
    if run: run.timings["prompt_ms"] = round((time.perf_counter()-started)*1000,2)
    return {"system_prompt": prompt}


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
    ] + list(state["messages"])

    response = model_with_tools.invoke(fit_messages(messages_for_llm, tools=supervisor_tools))
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
