from dotenv import load_dotenv

from langchain_core.messages import SystemMessage, AIMessage
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode

from core.memory import search_memories
from core.models import get_chat_model
from core.prompt_context import with_permanent_context
from tools import supervisor_tools
from prompt import SUPERVISOR_PROMPT

load_dotenv()

llm = get_chat_model("supervisor", temperature=0.0)
model_with_tools = llm.bind_tools(supervisor_tools)


def _latest_user_text(messages) -> str:
    for message in reversed(messages):
        role = getattr(message, "type", None)
        if role in {"human", "user"}:
            return str(getattr(message, "content", ""))
        if isinstance(message, dict) and message.get("role") == "user":
            return str(message.get("content", ""))
    return ""


def _runtime_system_prompt(messages) -> str:
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


def call_model(state: MessagesState):
    """Call Cora's supervisor model with persistent context and relevant memories."""
    messages = state["messages"]
    messages_for_llm = [
        SystemMessage(content=_runtime_system_prompt(messages))
    ] + messages

    response = model_with_tools.invoke(messages_for_llm)

    # Execute at most one tool call per graph cycle.
    if hasattr(response, "tool_calls") and len(response.tool_calls) > 1:
        response = AIMessage(
            content=response.content,
            additional_kwargs=response.additional_kwargs,
            response_metadata=response.response_metadata,
            tool_calls=[response.tool_calls[0]],
            id=response.id,
        )

    return {"messages": [response]}


def should_continue(state: MessagesState):
    """Route to tools when the supervisor requested one; otherwise stop."""
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and len(last_message.tool_calls) > 0:
        return "tools"

    return END


tool_node = ToolNode(supervisor_tools)

workflow = StateGraph(MessagesState)
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        END: END,
    },
)
workflow.add_edge("tools", "agent")

graph = workflow.compile()
