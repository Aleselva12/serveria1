import operator
from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from core.models import get_chat_model
from email_agent.email_prompt import EMAIL_AGENT_PROMPT
from email_agent.email_tools import EMAIL_TOOLS


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]


def call_llm(state: AgentState):
    messages = state["messages"]

    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=EMAIL_AGENT_PROMPT)] + list(messages)

    llm = get_chat_model("email", temperature=0.0)
    response = llm.bind_tools(EMAIL_TOOLS).invoke(messages)
    return {"messages": [response]}


def should_continue(state: AgentState):
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return END


def create_email_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("call_llm", call_llm)
    workflow.add_node("tools", ToolNode(EMAIL_TOOLS))
    workflow.set_entry_point("call_llm")
    workflow.add_conditional_edges(
        "call_llm",
        should_continue,
        {"tools": "tools", END: END},
    )
    workflow.add_edge("tools", "call_llm")
    return workflow.compile(checkpointer=MemorySaver())


graph = create_email_graph()


if __name__ == "__main__":
    print("Email & Quotes Agent graph ready.")
