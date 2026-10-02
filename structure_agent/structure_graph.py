from __future__ import annotations

from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from core.models import get_chat_model
from core.prompt_context import with_permanent_context
from structure_agent.structure_prompt import STRUCTURE_AGENT_PROMPT
from structure_agent.structure_tools import STRUCTURE_TOOLS


class AgentState(MessagesState):
    system_prompt: str


llm = get_chat_model("structure", temperature=0.0)
model_with_tools = llm.bind_tools(STRUCTURE_TOOLS)


def prepare_prompt(state: AgentState):
    return {"system_prompt": with_permanent_context(STRUCTURE_AGENT_PROMPT)}


def call_llm(state: AgentState):
    messages = [SystemMessage(content=state["system_prompt"])] + list(state["messages"])
    response = model_with_tools.invoke(messages)
    return {"messages": [response]}


def should_continue(state: AgentState):
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return END


def create_structure_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("prepare", prepare_prompt)
    workflow.add_node("call_llm", call_llm)
    workflow.add_node("tools", ToolNode(STRUCTURE_TOOLS))
    workflow.add_edge(START, "prepare")
    workflow.add_edge("prepare", "call_llm")
    workflow.add_conditional_edges(
        "call_llm",
        should_continue,
        {"tools": "tools", END: END},
    )
    workflow.add_edge("tools", "call_llm")
    return workflow.compile()


graph = create_structure_graph()


if __name__ == "__main__":
    print("Structure Agent graph ready.")
