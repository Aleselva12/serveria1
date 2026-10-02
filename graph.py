from dotenv import load_dotenv

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode

from core.memory import search_memories
from core.models import get_chat_model
from core.prompt_context import with_permanent_context
from tools import supervisor_tools
from prompt import SUPERVISOR_PROMPT

load_dotenv()


class CoraState(MessagesState):
    system_prompt: str


llm = get_chat_model("supervisor", temperature=0.0)
model_with_tools = llm.bind_tools(supervisor_tools)

PARALLEL_READ_TOOLS = {
    "calculator_tool",
    "system_status_tool",
    "list_project_files",
    "read_project_file",
    "structure_registry_tool",
    "recent_system_events_tool",
    "recall_memory_tool",
    "calendar_list_events",
    "calendar_get_event",
}
TERMINAL_DELEGATION_TOOLS = {
    "structure_agent_tool",
    "search_agent_tool",
    "audio_agent_tool",
    "email_agent_tool",
}


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
    if user_text.strip():
        try:
            relevant = search_memories(user_text, limit=6)
        except Exception:
            relevant = []

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
    return {"system_prompt": _runtime_system_prompt(state["messages"])}


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
    messages_for_llm = [
        SystemMessage(content=state["system_prompt"])
    ] + list(state["messages"])

    response = model_with_tools.invoke(messages_for_llm)
    return {"messages": [_bounded_tool_calls(response)]}


def should_continue(state: CoraState):
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return END


def after_tools(state: CoraState):
    """
    A delegated specialist already returns user-facing natural language.
    End the run there instead of paying for a redundant Supervisor rewrite.
    """
    for message in reversed(state["messages"]):
        calls = getattr(message, "tool_calls", None)
        if calls:
            names = {_tool_name(call) for call in calls}
            if names & TERMINAL_DELEGATION_TOOLS:
                return END
            break
    return "agent"


tool_node = ToolNode(supervisor_tools)

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
