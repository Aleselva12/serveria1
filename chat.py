from graph import graph


def main():
    print("===================================================")
    print("                  CORA IS ONLINE                   ")
    print("         Assistente multi-agente locale.           ")
    print("===================================================")
    print("Type 'exit' or 'quit' to stop.")
    print("===================================================")

    thread_id = "cora_supervisor_session"
    config = {"configurable": {"thread_id": thread_id}}

    while True:
        try:
            user_input = input("\nYou: ")
        except (KeyboardInterrupt, EOFError):
            break

        if user_input.strip().lower() in ["exit", "quit"]:
            print("\nCora: arresto della sessione. A presto.")
            break

        if not user_input.strip():
            continue

        try:
            final_state = graph.invoke(
                {"messages": [{"role": "user", "content": user_input}]},
                config=config,
            )
            final_message = final_state["messages"][-1]
            print(f"\nCora: {final_message.content}\n")
        except Exception as error:
            print(f"\nCora Error: {error}")


if __name__ == "__main__":
    main()
