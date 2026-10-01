from __future__ import annotations

from core.system_context import get_system_context


def with_permanent_context(base_prompt: str) -> str:
    """Append user-controlled permanent context to any agent system prompt."""
    try:
        context = get_system_context()
        content = (context.get("content") or "").strip()
    except Exception:
        content = ""

    if not content:
        return base_prompt.strip()

    return (
        base_prompt.strip()
        + "\n\nPERMANENT USER-CONFIGURED CONTEXT\n"
        + "This context is explicitly maintained by the user, is common to all "
          "Cora models, has high priority, and must not be modified as learned memory.\n"
        + content
    )
