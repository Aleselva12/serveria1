from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from email_agent.email_graph import graph


def main():
    load_dotenv()
    config = {"configurable": {"thread_id": "email_agent_session"}}

    print("=====================================================")
    print("Cora Email & Quotes Agent")
    print("Archivio mail, digest giornaliero e preventivi PDF.")
    print("Type 'quit', 'exit', or 'q' to stop.")
    print("=====================================================")

    while True:
        try:
            user_input = input("\nYou: ")

            if user_input.strip().lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break

            if not user_input.strip():
                continue

            result = graph.invoke(
                {"messages": [HumanMessage(content=user_input)]},
                config=config,
            )
            print("\nEmail Agent:")
            print(result["messages"][-1].content)

        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break
        except Exception as error:
            print(f"\nAn error occurred: {error}")


if __name__ == "__main__":
    main()
