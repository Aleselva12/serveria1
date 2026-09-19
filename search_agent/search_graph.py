import os
import operator
from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from search_agent.search_tools import tavily_search
from search_agent.search_prompt import SEARCH_AGENT_PROMPT


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]


def call_llm(state: AgentState):
    messages = state["messages"]

    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SEARCH_AGENT_PROMPT)] + list(messages)

    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "gpt-oss:20b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11435"),
        temperature=0,
    )
    llm_with_tools = llm.bind_tools([tavily_search])
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def should_continue(state: AgentState):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return END


def create_search_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("call_llm", call_llm)
    workflow.add_node("tools", ToolNode([tavily_search]))
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
    print("Successfully built the search agent graph with local Ollama.")
