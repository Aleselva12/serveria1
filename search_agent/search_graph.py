import operator
from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from core.models import get_chat_model
from search_agent.search_prompt import SEARCH_AGENT_PROMPT
from search_agent.search_tools import LOCAL_RESEARCH_TOOLS


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]


def call_llm(state: AgentState):
    messages = state["messages"]

    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SEARCH_AGENT_PROMPT)] + list(messages)

    llm = get_chat_model("research", temperature=0.0)
    response = llm.bind_tools(LOCAL_RESEARCH_TOOLS).invoke(messages)
    return {"messages": [response]}


def should_continue(state: AgentState):
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return END


def create_search_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("call_llm", call_llm)
    workflow.add_node("tools", ToolNode(LOCAL_RESEARCH_TOOLS))
    workflow.set_entry_point("call_llm")
    workflow.add_conditional_edges(
        "call_llm",
        should_continue,
        {"tools": "tools", END: END},
    )
    workflow.add_edge("tools", "call_llm")
    return workflow.compile(checkpointer=MemorySaver())


if __name__ == "__main__":
    app = create_search_graph()
    print("Local Research Agent graph ready.")
