from __future__ import annotations

from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from core.context_budget import fit_messages
from core.governance import bind_capabilities
from core.models import get_chat_model
from core.prompt_context import with_permanent_context
from core.runtime_context import ensure_runtime_active
from search_agent.search_prompt import SEARCH_AGENT_PROMPT
from search_agent.search_tools import LOCAL_RESEARCH_TOOLS


class AgentState(MessagesState):
    system_prompt: str


bind_capabilities("local_research_agent", LOCAL_RESEARCH_TOOLS)
# Optional injected model for integration tests; production resolves each call.
model_with_tools = None


def prepare_prompt(state: AgentState):
    return {"system_prompt": with_permanent_context(SEARCH_AGENT_PROMPT)}


def call_llm(state: AgentState):
    ensure_runtime_active()
    messages = [SystemMessage(content=state["system_prompt"])] + list(state["messages"])
    model = model_with_tools if model_with_tools is not None else get_chat_model("research", temperature=0.0).bind_tools(LOCAL_RESEARCH_TOOLS)
    response = model.invoke(fit_messages(messages, tools=LOCAL_RESEARCH_TOOLS))
    return {"messages": [response]}


def should_continue(state: AgentState):
    ensure_runtime_active()
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return END


def create_search_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("prepare", prepare_prompt)
    workflow.add_node("call_llm", call_llm)
    workflow.add_node("tools", ToolNode(LOCAL_RESEARCH_TOOLS, handle_tool_errors=True))
    workflow.add_edge(START, "prepare")
    workflow.add_edge("prepare", "call_llm")
    workflow.add_conditional_edges(
        "call_llm",
        should_continue,
        {"tools": "tools", END: END},
    )
    workflow.add_edge("tools", "call_llm")
    return workflow.compile()


graph = create_search_graph()


if __name__ == "__main__":
    print("Local Research Agent graph ready.")
