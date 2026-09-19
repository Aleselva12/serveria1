import os
import sys

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from email_agent.email_connector import fetch_emails
from email_agent.agent.email_graph import graph
from langchain_core.messages import HumanMessage

def main():
    print("========================================")
    print("   Welcome to JARVIS Email Assistant!   ")
    print("   Fetching your latest emails...       ")
    print("========================================")
    # Fetch exactly once
    recent_emails = fetch_emails()
    print(f"Fetched {len(recent_emails)} recent emails.")
    print("Type 'exit' or 'quit' to stop.")
    print("========================================")
    
    thread_id = "default_user_session"
    config = {"configurable": {"thread_id": thread_id}}
    
    while True:
        try:
            user_input = input("\nYou: ")
        except (KeyboardInterrupt, EOFError):
            break
            
        if user_input.lower() in ['exit', 'quit']:
            print("\nJARVIS: Goodbye!")
            break
            
        if not user_input.strip():
            continue
            
        try:
            print("JARVIS is thinking...")
            
            # Provide emails on every request. In LangGraph, providing it merges it into the state.
            invoke_payload = {
                "emails": recent_emails,
                "messages": [HumanMessage(content=user_input)],
                "revision_count": 0  # Always reset to 0 so future email drafts also trigger the review!
            }
                
            result = graph.invoke(invoke_payload, config=config)
            
            if result and "messages" in result:
                final_message = result["messages"][-1]
                print(f"\nJARVIS:\n{final_message.content}")
            
        except Exception as e:
            print(f"\nJARVIS Error: {e}")

if __name__ == "__main__":
    main()
