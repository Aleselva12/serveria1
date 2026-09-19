import os
from typing import Dict, Any

try:
    from tavily import TavilyClient
except ImportError:
    raise ImportError(
        "Could not import tavily python package. "
        "Please install it with `pip install tavily-python`."
    )

from langchain_core.tools import tool

@tool
def tavily_search(query: str, search_depth: str = "basic", max_results: int = 5) -> str:
    """
    Search the web using the Tavily API for recent or real-time information.
    
    Args:
        query (str): The search query to execute.
        search_depth (str): The depth of the search. Can be "basic" or "advanced". Default is "basic".
        max_results (int): The maximum number of results to return. Default is 5.

    Returns:
        str: A formatted string containing the titles, URLs, and content of the search results.
    """
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return "Error: TAVILY_API_KEY environment variable is not set."

    client = TavilyClient(api_key=api_key)
    
    try:
        response = client.search(
            query=query,
            search_depth=search_depth,
            max_results=max_results,
        )
        
        formatted_results = []
        for result in response.get("results", []):
            title = result.get("title", "No Title")
            url = result.get("url", "No URL")
            content = result.get("content", "No Content")
            formatted_results.append(f"Title: {title}\nURL: {url}\nContent: {content}\n")
        
        return "\n".join(formatted_results) if formatted_results else "No results found."
    except Exception as e:
        return f"An error occurred while searching Tavily: {str(e)}"
