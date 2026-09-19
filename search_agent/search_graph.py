import os
import operator
from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

# Use Groq instead of OpenAI
try:
    from langchain_groq import ChatGroq
except ImportError:
    raise ImportError("Please install the required package: pip install langchain-groq")

from search_agent.search_tools import tavily_search
from search_agent.search_prompt import SEARCH_AGENT_PROMPT

# Define the state structure for our graph
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]

# Define the node that calls the LLM
def call_llm(state: AgentState):
    messages = state['messages']
    
    # Inject the system prompt if it's not already at the beginning of the context
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SEARCH_AGENT_PROMPT)] + list(messages)
        
    # Initialize the Groq LLM
    api_key = os.environ.get("GROQ_API_KEY1")
    
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0,
        api_key=api_key
    )
    
    # Bind the tools to the LLM
    llm_with_tools = llm.bind_tools([tavily_search])
    
    # Invoke the LLM with the current conversation history
    response = llm_with_tools.invoke(messages)
    
    # Return the new message to append to the state
    return {"messages": [response]}

# Define the conditional logic to decide what to do after the LLM responds
def should_continue(state: AgentState):
    messages = state['messages']
    last_message = messages[-1]
    
    # If the LLM decided to call a tool, route to the "tools" node
    if last_message.tool_calls:
        return "tools"
    # Otherwise, we're done and can route to END
    return END

def create_search_graph():
    # 1. Initialize the graph with our state schema
    workflow = StateGraph(AgentState)
    
    # 2. Add nodes
    workflow.add_node("call_llm", call_llm)
    
    # Use LangGraph's prebuilt ToolNode which automatically executes the tool calls
    tool_node = ToolNode([tavily_search])
    workflow.add_node("tools", tool_node)
    
    # 3. Set the entry point
    workflow.set_entry_point("call_llm")
    
    # 4. Add conditional edges from the LLM node
    workflow.add_conditional_edges(
        "call_llm",
        should_continue,
        {
            "tools": "tools",  # Go to tool node if tool calls exist
            END: END           # End execution if no tool calls exist
        }
    )
    
    # 5. Add a normal edge: always go back to the LLM after tools execute
    workflow.add_edge("tools", "call_llm")
    
    # 6. Set up Checkpointer and Compile the graph
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    return app

if __name__ == "__main__":
    # Test building the graph
    app = create_search_graph()
    print("Successfully built the search agent graph with Groq!")
