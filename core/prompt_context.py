from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def with_permanent_context(base_prompt: str) -> str:
    """Append only universal runtime context.

    The owner-maintained system context is no longer injected automatically.
    It is available on demand through owner_context_tool/context pages.
    The historical function name is kept for specialist compatibility.
    """
    now = datetime.now(ZoneInfo("Europe/Rome"))
    base_prompt += (
        "\n\nTOOL GOVERNANCE: Un risultato con status pending è una proposta, non un'azione eseguita. "
        "Non dichiarare riuscita un'operazione con status error. "
        "Le approvazioni autorizzano solo l'azione mostrata."
    )
    return base_prompt.strip() + "\n\nCURRENT SERVER TIME (Europe/Rome): " + now.isoformat(timespec="seconds")
