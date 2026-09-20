from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from audio_agent.audio_graph import graph


def main():
    load_dotenv()

    print("=====================================================")
    print("Cora Audio Agent")
    print("Trascrizione e analisi di file audio locali.")
    print("Type 'quit', 'exit', or 'q' to stop.")
    print("=====================================================")

    config = {
        "configurable": {
            "thread_id": "audio_agent_session"
        }
    }

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
            print("\nAudio Agent:")
            print(result["messages"][-1].content)

        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break
        except Exception as error:
            print(f"\nAn error occurred: {error}")


if __name__ == "__main__":
    main()
