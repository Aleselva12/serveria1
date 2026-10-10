"""Request-scoped tool availability; selection never grants execution permissions."""


def validate_selection(names, tools):
    if names is None:
        return None
    allowed = {tool.name for tool in tools}
    if len(names) > len(allowed) or len(set(names)) != len(names) or any(n not in allowed for n in names):
        raise ValueError("Selezione tools non valida: usa solo strumenti disponibili della chat, senza duplicati.")
    return list(names)


def validate_manual_calls(names, calls):
    if names is not None and any(call.get("name") not in names for call in calls):
        raise ValueError("Il modello ha richiesto un tool non abilitato per questa richiesta.")


def chat_tool_options():
    from tools import supervisor_tools
    from core.governance import tool_contract, capability_manifest, executables
    result = []
    for tool in supervisor_tools:
        contract = tool_contract(tool)
        entry = next(e for e in executables.values() if e["tool"] is tool)
        result.append(dict(name=tool.name, description=contract.description,
                           group="Agenti specializzati" if contract.effect == "delegate" else
                           "Calendario" if tool.name.startswith("calendar_") else
                           "Memoria" if "memory" in tool.name or tool.name == "remember_tool" else "Sistema e file",
                           permissions=capability_manifest(entry)["permissions"]))
    return {"tools": result}
