import uuid

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from local_tools import (
    calculator_tool,
    list_project_files,
    read_project_file,
    system_status_tool,
)


@tool
def search_agent_tool(query: str, thread_id: str = "") -> str:
    """
    Usa il Local Research Agent per trovare, leggere, confrontare e analizzare
    informazioni contenute nei documenti locali autorizzati. Non usa Internet.
    """
    from search_agent.search_graph import create_search_graph

    search_app = create_search_graph()
    effective_thread_id = thread_id or f"search_{uuid.uuid4()}"
    config = {"configurable": {"thread_id": effective_thread_id}}
    state = {"messages": [HumanMessage(content=query)]}
    result = search_app.invoke(state, config=config)
    return result["messages"][-1].content


@tool
def audio_agent_tool(query: str, thread_id: str = "") -> str:
    """
    Usa l'Audio Agent per trovare e trascrivere file audio locali e,
    quando richiesto, riassumere o analizzare la trascrizione.
    """
    from audio_agent.audio_graph import graph as audio_app

    effective_thread_id = thread_id or f"audio_{uuid.uuid4()}"
    config = {"configurable": {"thread_id": effective_thread_id}}
    state = {"messages": [HumanMessage(content=query)]}
    result = audio_app.invoke(state, config=config)
    return result["messages"][-1].content


@tool
def email_agent_tool(query: str, thread_id: str = "") -> str:
    """
    Usa l'Email & Quotes Agent per cercare nell'archivio mail, riassumere
    la posta di una giornata, preparare bozze e generare preventivi PDF.
    """
    from email_agent.email_graph import graph as email_app

    effective_thread_id = thread_id or f"email_{uuid.uuid4()}"
    config = {"configurable": {"thread_id": effective_thread_id}}
    state = {"messages": [HumanMessage(content=query)]}
    result = email_app.invoke(state, config=config)
    return result["messages"][-1].content


supervisor_tools = [
    calculator_tool,
    system_status_tool,
    list_project_files,
    read_project_file,
    search_agent_tool,
    audio_agent_tool,
    email_agent_tool,
]
