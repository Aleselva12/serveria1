"""Generate the historical 17 steps and the current Home project status."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def render():
    rows=json.loads((ROOT/'docs/roadmap.json').read_text(encoding='utf-8'))
    header=('17 PASSI — DECISIONI STORICHE\nDecisioni del proprietario, 18 ottobre 2026\n\n'
            'Fonte dei 17 passi storici: docs/roadmap.json. La Home attuale usa docs/project-status.json.\n'
            'Il documento originale è una fotografia storica, non un elenco di attività autorizzate.\n'
            'La numerazione resta stabile: i collaudi sono riuniti al 17; il 16 prepara la baseline.\n'
            'I test di sviluppo verificano il codice e non sostituiscono il collaudo finale sul server.\n\n')
    return header+'\n\n'.join(row['label']+'\nStato: '+row['state']+'\n'+row['detail'] for row in rows)+'\n'


if __name__=='__main__':
    (ROOT/'17 passi.txt').write_text(render(),encoding='utf-8')
    # Frontend Docker/check builds receive only frontend/, never the sibling docs/.
    target=ROOT/'frontend/src/roadmap.generated.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text((ROOT/'docs/roadmap.json').read_text(encoding='utf-8'),encoding='utf-8')

    # Current project goals are separate from the owner's historical 17 decisions.
    (ROOT/'frontend/src/project-status.generated.json').write_text(
        (ROOT/'docs/project-status.json').read_text(encoding='utf-8'),encoding='utf-8')
