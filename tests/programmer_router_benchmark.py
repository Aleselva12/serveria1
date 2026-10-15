"""Explicit read-only live routing check: python tests/programmer_router_benchmark.py --live.
Only classifications are sent to the configured local Ollama. No tools execute.
"""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from langchain_core.messages import HumanMessage, AIMessage
from programmer_agent.request_router import classify
from programmer_agent.context_manager import semantic_tools, metrics
from programmer_agent.programmer_tools import PROGRAMMER_TOOLS

CASES = [
    ('language_preference', ['Preferisci scrivere in italiano o inglese?'], 'current', set()),
    ('programming_preference', ['Preferisci Python o C++?'], 'current', set()),
    ('english_preference', ['Would you rather write in Italian or English?'], 'current', set()),
    ('explanation', ['Spiegami il paradosso del mentitore'], 'current', set()),
    ('history', ['Chiamiamo il progetto Cora', 'Va bene', 'Come abbiamo deciso di chiamarlo?'], 'history', set()),
    ('file_edit', ['Rinomina la funzione load in load_config in config.py'], 'files', {'edit'}),
    ('repository_read', ['Controlla nel repository dove viene costruito il prompt'], 'files', {'read'}),
    ('release', ['Prepara il rilascio delle modifiche nel workspace'], 'files', {'release'}),
]

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', required=True)
    parser.parse_args()
    rows = []
    for name, texts, context, groups in CASES:
        messages = [(HumanMessage if i % 2 == 0 else AIMessage)(text) for i, text in enumerate(texts)]
        decision = classify(messages)
        selected, reason = semantic_tools(messages, PROGRAMMER_TOOLS, decision)
        route = decision.get('route') or {}
        matches = (decision['status'] == 'classified' and context in route.get('context', [])
                   and groups <= set(route.get('tool_groups', [])))
        if context == 'current':
            matches = matches and set(route.get('context', [])) == {'current'} and not route.get('tool_groups')
        rows.append({'case':name, 'expectation_met':bool(matches), 'decision':decision,
                     'selection_reason':reason, **metrics([], selected)})
    print(json.dumps({'mode':'live_classification_only', 'cases':rows}, ensure_ascii=False, indent=2))
