from __future__ import annotations

import uuid

from langchain_core.messages import HumanMessage

from structure_agent.structure_graph import graph


def ask_structure_agent(query: str, thread_id: str = "") -> str:
    effective_thread_id = thread_id or f"structure_{uuid.uuid4()}"
    result = graph.invoke(
        {"messages": [HumanMessage(content=query)]},
        config={"configurable": {"thread_id": effective_thread_id}},
    )
    return result["messages"][-1].content


if __name__ == "__main__":
    print("Structure Agent ready.")
