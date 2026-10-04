from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from core.system_context import get_system_context


def with_permanent_context(base_prompt: str) -> str:
    """Append user-controlled permanent context to any agent system prompt."""
    # Relative calendar dates must be anchored to the server's current Italian time.
    now = datetime.now(ZoneInfo("Europe/Rome"))
    base_prompt += "\n\nTOOL GOVERNANCE: Un risultato con status pending è una proposta, non un'azione eseguita. Indica che l'utente deve approvarla nella pagina Attività (le proposte calendario sono anche nel Calendario). Non dichiarare riuscita un'operazione con status error. Dopo l'approvazione si esegue solo l'azione confermata, senza continuazione automatica del ragionamento."
    base_prompt = base_prompt.strip() + "\n\nCURRENT SERVER TIME (Europe/Rome): " + now.isoformat(timespec="seconds")
    from core.runtime import current_run
    run = current_run.get()
    # One owner context snapshot per root run, shared by all delegated agents.
    if run:
        with run.lock:
            context = getattr(run,"permanent_context",None)
            if context is None:
                context = get_system_context()
                run.permanent_context = context
                run.timings['permanent_context_version'] = context['version']
    else:
        context = get_system_context()
    content = (context.get("content") or "").strip()

    if not content:
        return base_prompt.strip()

    return (
        base_prompt.strip()
        + "\n\nPERMANENT USER-CONFIGURED CONTEXT\n"
        + "This context is explicitly maintained by the user, is common to all "
          "Cora models, has high priority, and must not be modified as learned memory.\n"
        + content
    )
