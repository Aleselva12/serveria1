from __future__ import annotations

from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from core.context_budget import fit_messages
from core.governance import bind_capabilities
from core.models import get_chat_model
from core.prompt_context import with_permanent_context
from core.runtime_context import ensure_runtime_active
from audio_agent.audio_prompt import AUDIO_AGENT_PROMPT
from audio_agent.audio_tools import AUDIO_TOOLS


class AgentState(MessagesState):
    system_prompt: str


bind_capabilities("audio_agent", AUDIO_TOOLS)
# Optional injected model for integration tests; production resolves each call.
model_with_tools = None


def prepare_prompt(state: AgentState):
    return {"system_prompt": with_permanent_context(AUDIO_AGENT_PROMPT)}


def call_llm(state: AgentState):
    ensure_runtime_active()
    messages = [SystemMessage(content=state["system_prompt"])] + list(state["messages"])
    model = model_with_tools if model_with_tools is not None else get_chat_model("audio", temperature=0.0).bind_tools(AUDIO_TOOLS)
    response = model.invoke(fit_messages(messages, tools=AUDIO_TOOLS))
    return {"messages": [response]}


def should_continue(state: AgentState):
    ensure_runtime_active()
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return END


def create_audio_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("prepare", prepare_prompt)
    workflow.add_node("call_llm", call_llm)
    workflow.add_node("tools", ToolNode(AUDIO_TOOLS, handle_tool_errors=True))
    workflow.add_edge(START, "prepare")
    workflow.add_edge("prepare", "call_llm")
    workflow.add_conditional_edges(
        "call_llm",
        should_continue,
        {"tools": "tools", END: END},
    )
    workflow.add_edge("tools", "call_llm")
    return workflow.compile()


graph = create_audio_graph()


if __name__ == "__main__":
    print("Audio Agent graph ready.")
