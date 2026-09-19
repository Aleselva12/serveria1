import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv('/Users/devanshkedia/JARVIS/.env')
except ImportError:
    print("Please install python-dotenv: pip install python-dotenv")

try:
    from langchain_core.messages import HumanMessage
except ImportError:
    print("Please install required packages: pip install langchain-core langchain-google-genai langgraph tavily-python")
    sys.exit(1)

from search_agent.search_graph import create_search_graph
from search_agent.search_render import render_message, console

def main():
    # Check for required environment variables before starting
    if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
        print("WARNING: Neither GEMINI_API_KEY nor GOOGLE_API_KEY environment variable is set. You need this to run Gemini.")
    if not os.environ.get("TAVILY_API_KEY"):
        print("WARNING: TAVILY_API_KEY environment variable is not set. You need this to use the search tool.")
        
    print("Initializing Agent Graph...")
    app = create_search_graph()
    
    print("=====================================================")
    print("Welcome to the Tavily Search Agent Chat!")
    print("Type 'quit', 'exit', or 'q' to stop the conversation.")
    print("=====================================================")
    
    while True:
        try:
            user_input = input("\nYou: ")
            
            if user_input.strip().lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break
                
            if not user_input.strip():
                continue
                
            # Prepare the input state for the graph
            inputs = {"messages": [HumanMessage(content=user_input)]}
            
            # Stream the execution updates from the graph
            for output in app.stream(inputs, stream_mode="updates"):
                for node_name, node_state in output.items():
                    messages = node_state.get("messages", [])
                    if messages:
                        last_message = messages[-1]
                        render_message(last_message, node_name)
                        
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    main()
