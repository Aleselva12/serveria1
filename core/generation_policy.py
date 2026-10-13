"""Generation policy, separate from the finite context window and tool safeguards."""
import os
from typing import Literal

ResponseLength = Literal["short", "medium", "long"]

def unlimited():
    # Explicit opt-out preserves configurable budgets for other installations.
    return os.getenv("CORA_UNLIMITED_GENERATION", "true").lower() in {"true", "1", "yes"}

def run_timeout():
    return 0.0 if unlimited() else max(0, float(os.getenv("CORA_RUN_TIMEOUT_SECONDS", "300")))

def output_tokens():
    return -1 if unlimited() else int(os.getenv("CORA_OUTPUT_TOKENS", "1024"))

def model_timeout():
    value = 0.0 if unlimited() else float(os.getenv("CORA_MODEL_TIMEOUT_SECONDS", "120"))
    return value if value > 0 else None

def response_instruction(length: ResponseLength):
    style = {"short": "breve e diretta", "medium": "di lunghezza media, con le spiegazioni utili", "long": "dettagliata, con spiegazioni ed esempi pertinenti"}[length]
    return "Preferenza di presentazione: risposta " + style + ". Completa sempre il compito e il codice necessario; questa preferenza non limita il lavoro o i test."
