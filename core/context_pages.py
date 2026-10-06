"""Small, task-scoped context pages for the Supervisor.

Pages are plain Markdown with TOML frontmatter. Selection is deterministic in
this prototype: no additional LLM call is spent deciding which context to load.
"""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "context_pages"


@dataclass(frozen=True)
class ContextPage:
    id: str
    title: str
    triggers: tuple[str, ...]
    tools: tuple[str, ...]
    body: str
    priority: int = 50


def _parse(path: Path) -> ContextPage:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("+++\n"):
        raise ValueError(f"Context page without TOML frontmatter: {path}")
    _, frontmatter, body = text.split("+++\n", 2)
    meta = tomllib.loads(frontmatter)
    return ContextPage(
        id=str(meta["id"]),
        title=str(meta.get("title", meta["id"])),
        triggers=tuple(str(item).casefold() for item in meta.get("triggers", [])),
        tools=tuple(str(item) for item in meta.get("tools", [])),
        body=body.strip(),
        priority=int(meta.get("priority", 50)),
    )


def pages() -> tuple[ContextPage, ...]:
    if not ROOT.exists():
        return ()
    result = []
    for path in sorted(ROOT.glob("*.md")):
        # Documentation may live beside pages; only files with TOML frontmatter
        # are executable context definitions.
        if not path.read_text(encoding="utf-8").startswith("+++\n"):
            continue
        result.append(_parse(path))
    return tuple(result)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[\wÀ-ÿ]+", text.casefold()))


def resolve_context_pages(user_text: str, *, max_pages: int = 3) -> list[ContextPage]:
    """Select only pages with explicit lexical evidence.

    A casual/unknown message intentionally selects no page and no tool schema.
    """
    normalized = user_text.casefold()
    words = _tokens(user_text)
    scored: list[tuple[int, int, ContextPage]] = []
    for page in pages():
        score = 0
        for trigger in page.triggers:
            if " " in trigger:
                if trigger in normalized:
                    score += 4
            elif trigger in words:
                score += 3
            elif len(trigger) >= 5 and trigger in normalized:
                score += 1
        if score:
            scored.append((score, page.priority, page))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [page for _, _, page in scored[:max_pages]]


def selected_tool_names(selected: list[ContextPage]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for page in selected:
        for name in page.tools:
            if name not in seen:
                result.append(name)
                seen.add(name)
    return result


def render_pages(selected: list[ContextPage]) -> str:
    if not selected:
        return ""
    rendered = []
    for page in selected:
        rendered.append(f"## Context Page: {page.title} [{page.id}]\n{page.body}")
    return "\n\n".join(rendered)
