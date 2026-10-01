from __future__ import annotations

import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT_ROOT = Path(
    os.getenv(
        "CORA_CHAT_TRANSCRIPT_ROOT",
        str(PROJECT_ROOT / "data" / "chat-transcripts"),
    )
).expanduser().resolve()


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9àèéìòùÀÈÉÌÒÙ_-]+", "-", value.strip())
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return normalized[:80] or "chat"


def transcript_path(conversation: dict) -> Path:
    created = conversation["created_at"]
    if isinstance(created, str):
        created = datetime.fromisoformat(created)
    directory = TRANSCRIPT_ROOT / f"{created.year:04d}" / f"{created.month:02d}"
    filename = f"{created.date().isoformat()}_{_slug(conversation['title'])}_{conversation['id']}.md"
    return directory / filename


def render_transcript(conversation: dict, messages: Iterable[dict]) -> str:
    lines = [
        f"# {conversation['title']}",
        "",
        f"- Conversation ID: {conversation['id']}",
        f"- Created: {conversation['created_at']}",
        f"- Updated: {conversation['updated_at']}",
        "",
        "---",
        "",
    ]
    labels = {"user": "Utente", "assistant": "Cora", "system": "Sistema"}
    for message in messages:
        role = labels.get(message["role"], message["role"])
        timestamp = message["created_at"]
        agent = message.get("agent_id")
        model = message.get("model_id")
        suffix = ""
        if agent or model:
            details = [value for value in [agent, model] if value]
            suffix = " · " + " / ".join(details)
        lines.extend(
            [
                f"## {role} — {timestamp}{suffix}",
                "",
                message["content"],
                "",
                "---",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_transcript(conversation: dict, messages: Iterable[dict]) -> Path:
    path = transcript_path(conversation)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = render_transcript(conversation, messages)

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        suffix=".tmp",
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)
    return path
