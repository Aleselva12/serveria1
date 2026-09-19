from graph import graph
import sys
from rich.console import Console

console = Console()

def main():
    print("===================================================")
    print("                 JARVIS IS ONLINE                  ")
    print("   Your personal AI assistant at your service.     ")
    print("===================================================")
    print("Type 'exit' or 'quit' to stop.")
    print("===================================================")

    # We use a specific thread ID so the supervisor checkpointer 
    # maintains your conversation history throughout the session.
    thread_id = "jarvis_supervisor_session"
    config = {"configurable": {"thread_id": thread_id}}
    
    while True:
        try:
            # Safely get user input synchronously
            user_input = input("\nYou: ")
        except (KeyboardInterrupt, EOFError):
            break
            
        if user_input.lower() in ['exit', 'quit']:
            print("\nJARVIS: Powering down. Goodbye!")
            break
            
        if not user_input.strip():
            continue
            
        try:
            # Run the graph synchronously
            final_state = graph.invoke(
                {"messages": [{"role": "user", "content": user_input}]},
                config=config
            )
            
            final_message = final_state["messages"][-1]
            print(f"\nJARVIS: {final_message.content}\n")
            
        except Exception as e:
            print(f"\nJARVIS Error: {e}")

if __name__ == "__main__":
    main()