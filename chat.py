import uuid

from core.chat_store import ensure_conversation, recent_context, save_message
from core.models import get_model_name
from graph import graph


def main():
    print("===================================================")
    print("                  CORA IS ONLINE                   ")
    print("         Assistente multi-agente locale.           ")
    print("===================================================")
    print("Type 'exit' or 'quit' to stop.")
    print("===================================================")

    thread_id = str(uuid.uuid4())
    ensure_conversation(thread_id, metadata={"interface": "cli"})

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
            user_message = save_message(
                conversation_id=thread_id,
                role="user",
                content=user_input,
                agent_id="user",
                metadata={"source": "cli"},
            )
            final_state = graph.invoke({"messages": recent_context(thread_id)})
            response = final_state["messages"][-1].content
            save_message(
                conversation_id=thread_id,
                role="assistant",
                content=response,
                agent_id="supervisor",
                model_id=get_model_name("supervisor"),
                parent_message_id=str(user_message["id"]),
                metadata={"source": "cli"},
            )
            print(f"\nCora: {response}\n")
        except Exception as error:
            print(f"\nCora Error: {error}")


if __name__ == "__main__":
    main()
