import os
from langchain_ollama import ChatOllama

def ChatGroq(*args, model=None, api_key=None, temperature=0, **kwargs):
    return ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "gpt-oss:20b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11435"),
        temperature=temperature,
    )
