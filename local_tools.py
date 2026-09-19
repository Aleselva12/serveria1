import ast
import json
import operator
from pathlib import Path

import psutil
from langchain_core.tools import tool


PROJECT_ROOT = Path(__file__).resolve().parent

BLOCKED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
}

BLOCKED_NAMES = {
    ".env",
    "credentials.json",
    "token.json",
}

TEXT_EXTENSIONS = {
    ".py", ".md", ".txt", ".json",
    ".yaml", ".yml", ".toml",
    ".html", ".css", ".js",
}


def _safe_path(relative_path: str) -> Path:
    candidate = (PROJECT_ROOT / relative_path).resolve()

    if candidate != PROJECT_ROOT and PROJECT_ROOT not in candidate.parents:
        raise ValueError("Accesso esterno alla cartella del progetto vietato.")

    if any(part in BLOCKED_PARTS for part in candidate.parts):
        raise ValueError("Cartella protetta.")

    if candidate.name.lower() in BLOCKED_NAMES:
        raise ValueError("File contenente possibili credenziali protetto.")

    return candidate


BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}

UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _calculate(node):
    if isinstance(node, ast.Expression):
        return _calculate(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Sono ammessi soltanto numeri.")

    if isinstance(node, ast.BinOp) and type(node.op) in BINARY_OPERATORS:
        left = _calculate(node.left)
        right = _calculate(node.right)
        return BINARY_OPERATORS[type(node.op)](left, right)

    if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY_OPERATORS:
        return UNARY_OPERATORS[type(node.op)](_calculate(node.operand))

    raise ValueError("Espressione matematica non consentita.")


@tool
def calculator_tool(expression: str) -> str:
    """Calcola in sicurezza un'espressione con +, -, *, /, // e %."""
    print(f"[TOOL] calculator_tool: {expression}")

    try:
        tree = ast.parse(expression, mode="eval")
        result = _calculate(tree)
        return str(result)
    except Exception as error:
        return f"Errore nel calcolo: {error}"


@tool
def system_status_tool() -> str:
    """Restituisce utilizzo reale di CPU, RAM e disco del computer."""
    print("[TOOL] system_status_tool")

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(str(PROJECT_ROOT.anchor))

    result = {
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "ram_total_gb": round(memory.total / 1024**3, 2),
        "ram_used_gb": round(memory.used / 1024**3, 2),
        "ram_available_gb": round(memory.available / 1024**3, 2),
        "ram_percent": memory.percent,
        "disk_total_gb": round(disk.total / 1024**3, 2),
        "disk_used_gb": round(disk.used / 1024**3, 2),
        "disk_free_gb": round(disk.free / 1024**3, 2),
        "disk_percent": disk.percent,
    }

    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def list_project_files(
    directory: str = ".",
    extension: str = "",
    recursive: bool = True,
) -> str:
    """Elenca file reali esclusivamente dentro il progetto Cora."""
    print(
        f"[TOOL] list_project_files: "
        f"directory={directory}, extension={extension}, recursive={recursive}"
    )

    try:
        base = _safe_path(directory)

        if not base.exists() or not base.is_dir():
            return "La cartella richiesta non esiste."

        iterator = base.rglob("*") if recursive else base.glob("*")
        results = []

        normalized_extension = extension.strip()
        if normalized_extension and not normalized_extension.startswith("."):
            normalized_extension = "." + normalized_extension

        for path in iterator:
            relative = path.relative_to(PROJECT_ROOT)

            if any(part in BLOCKED_PARTS for part in relative.parts):
                continue

            if path.name.lower() in BLOCKED_NAMES:
                continue

            if path.is_file():
                if normalized_extension and path.suffix.lower() != normalized_extension.lower():
                    continue

                results.append(str(relative))

            if len(results) >= 100:
                break

        if not results:
            return "Nessun file trovato."

        return "\n".join(sorted(results))

    except Exception as error:
        return f"Errore durante l'elenco dei file: {error}"


@tool
def read_project_file(relative_path: str) -> str:
    """Legge un file di testo esclusivamente dentro il progetto Cora."""
    print(f"[TOOL] read_project_file: {relative_path}")

    try:
        path = _safe_path(relative_path)

        if not path.exists() or not path.is_file():
            return "Il file richiesto non esiste."

        if path.suffix.lower() not in TEXT_EXTENSIONS:
            return "Questo tipo di file non è autorizzato."

        if path.stat().st_size > 100_000:
            return "Il file supera il limite di 100 KB."

        return path.read_text(encoding="utf-8", errors="replace")

    except Exception as error:
        return f"Errore durante la lettura: {error}"
