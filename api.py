import os
import uuid
from urllib.error import URLError
from urllib.request import urlopen

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.registry import get_agents, get_registry
from graph import graph


load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11435").rstrip("/")

app = FastAPI(
    title="Cora API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    thread_id: str


def _ollama_online() -> bool:
    try:
        with urlopen(f"{OLLAMA_BASE_URL}/api/tags", timeout=1.5):
            return True
    except (URLError, TimeoutError, OSError):
        return False


@app.get("/health")
def health():
    return {
        "status": "ok",
        "ollama_online": _ollama_online(),
        "model": OLLAMA_MODEL,
        "agents": [agent["name"] for agent in get_agents()],
    }


@app.get("/capabilities")
def capabilities():
    return get_registry()


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    message = request.message.strip()
    if not message:
        return ChatResponse(
            response="Scrivi un messaggio per iniziare.",
            thread_id=request.thread_id or str(uuid.uuid4()),
        )

    thread_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    result = graph.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": message,
                }
            ]
        },
        config=config,
    )

    response = result["messages"][-1].content
    return ChatResponse(
        response=response,
        thread_id=thread_id,
    )
