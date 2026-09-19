from langgraph.graph import END, StateGraph, START, MessagesState
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage
from datetime import datetime
import pytz
import os
from dotenv import load_dotenv

from calendar_agent.calendar_tools import calendar_tools
from calendar_agent.calendar_prompt import SYSTEM_PROMPT
from langchain_groq import ChatGroq

load_dotenv()

GROQ_API_KEY2 = os.getenv("GROQ_API_KEY2")
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=GROQ_API_KEY2
)

# Bind our tools to the LLM
model_with_tools = llm.bind_tools(calendar_tools)

# Define the node that calls the LLM
def call_model(state: MessagesState):
    messages = state["messages"]
    
    # Calculate dynamic current time for the LLM
    timezone = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(timezone)
    current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S %Z')
    dynamic_system_prompt = f"The current date and time is {current_time_str}.\n\n{SYSTEM_PROMPT}"
    
    # Prepend the system message before sending to the LLM
    messages_for_llm = [SystemMessage(content=dynamic_system_prompt)] + messages
    
    # The LLM will either respond with an answer OR request a tool call
    response = model_with_tools.invoke(messages_for_llm)
    
    return {"messages": [response]}

# Define the conditional edge that decides what to do next
def should_continue(state: MessagesState):
    messages = state["messages"]
    last_message = messages[-1]
    
    # If the LLM requested a tool call, go to the tool node
    if last_message.tool_calls:
        return "tools"
    
    # If there are no tool calls, it means the LLM gave a final answer, so we END
    return END

# We use LangGraph's pre-built ToolNode to execute the tools
tool_node = ToolNode(calendar_tools)

# Build the graph exactly as you described!
builder = StateGraph(MessagesState)

# 1. Call LLM node from where everything will start
builder.add_node("call_model", call_model)

# 2. There will be then a tool node
builder.add_node("tools", tool_node)

# 3. Everything starts at call_model
builder.add_edge(START, "call_model")

# 4. From call_model, there will be a should_continue
# If it has tool calls, go to "tools". If not, go to END.
builder.add_conditional_edges("call_model", should_continue, ["tools", END])

# 5. After tool node finishes, the result goes back to call_model
builder.add_edge("tools", "call_model")

# We add MemorySaver so the agent remembers conversation history across turns
memory = MemorySaver()
graph = builder.compile(checkpointer=memory)
