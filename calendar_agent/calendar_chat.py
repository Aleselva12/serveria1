from calendar_agent.calendar_graph import graph

def main():
    print("========================================")
    print("  Welcome to JARVIS Calendar Assistant! ")
    print("  Type 'exit' or 'quit' to stop.        ")
    print("========================================")

    # Use a definite thread ID so memory persists as long as the script runs,
    # or across script runs if a persistent checkpointer is used later.
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
            # We pass the user's input to the graph. 
            # Because we pass `config` with our thread_id, LangGraph automatically 
            # retrieves the past messages for this thread and saves the new ones!
            result = graph.invoke(
                {"messages": [{"role": "user", "content": user_input}]},
                config=config
            )
            
            # The result contains the entire message history. 
            # We just want to print the last message from the AI.
            final_message = result["messages"][-1]
            print(f"\nJARVIS: {final_message.content}")
            
        except Exception as e:
            print(f"\nJARVIS Error: {e}")

if __name__ == "__main__":
    main()
