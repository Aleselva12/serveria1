from datetime import datetime
import os

import pytz
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from calendar_agent.calendar_prompt import SYSTEM_PROMPT
from calendar_agent.calendar_tools import calendar_tools

load_dotenv()

llm = ChatOllama(
    model=os.getenv("OLLAMA_MODEL", "gpt-oss:20b"),
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11435"),
    temperature=0.0,
)

model_with_tools = llm.bind_tools(calendar_tools)


def call_model(state: MessagesState):
    messages = state["messages"]

    timezone = pytz.timezone("Europe/Rome")
    current_time = datetime.now(timezone)
    current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S %Z")
    dynamic_system_prompt = (
        f"The current date and time is {current_time_str}.\n\n{SYSTEM_PROMPT}"
    )

    messages_for_llm = [SystemMessage(content=dynamic_system_prompt)] + messages
    response = model_with_tools.invoke(messages_for_llm)
    return {"messages": [response]}


def should_continue(state: MessagesState):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return END


tool_node = ToolNode(calendar_tools)
builder = StateGraph(MessagesState)
builder.add_node("call_model", call_model)
builder.add_node("tools", tool_node)
builder.add_edge(START, "call_model")
builder.add_conditional_edges("call_model", should_continue, ["tools", END])
builder.add_edge("tools", "call_model")

graph = builder.compile(checkpointer=MemorySaver())
