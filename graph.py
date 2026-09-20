from dotenv import load_dotenv

from langchain_core.messages import SystemMessage, AIMessage
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from core.models import get_chat_model
from tools import supervisor_tools
from prompt import SUPERVISOR_PROMPT

load_dotenv()

llm = get_chat_model("supervisor", temperature=0.0)
model_with_tools = llm.bind_tools(supervisor_tools)


def call_model(state: MessagesState):
    """Call Cora's supervisor model."""
    messages = state["messages"]
    messages_for_llm = [SystemMessage(content=SUPERVISOR_PROMPT)] + messages

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

memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)
