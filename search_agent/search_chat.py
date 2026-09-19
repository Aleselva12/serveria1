from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from search_agent.search_graph import create_search_graph
from search_agent.search_render import render_message


def main():
    load_dotenv()
    app = create_search_graph()

    print("=====================================================")
    print("Cora Local Research Agent")
    print("Ricerca e analisi esclusivamente su documenti locali.")
    print("Type 'quit', 'exit', or 'q' to stop.")
    print("=====================================================")

    thread_id = "local_research_session"
    config = {"configurable": {"thread_id": thread_id}}

    while True:
        try:
            user_input = input("\nYou: ")

            if user_input.strip().lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break

            if not user_input.strip():
                continue

            inputs = {"messages": [HumanMessage(content=user_input)]}

            for output in app.stream(
                inputs,
                config=config,
                stream_mode="updates",
            ):
                for node_name, node_state in output.items():
                    messages = node_state.get("messages", [])
                    if messages:
                        render_message(messages[-1], node_name)

        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break
        except Exception as error:
            print(f"\nAn error occurred: {error}")


if __name__ == "__main__":
    main()
