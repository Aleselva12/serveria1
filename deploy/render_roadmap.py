"""Generate the human-readable roadmap from the same data displayed on Home."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def render():
    rows=json.loads((ROOT/'docs/roadmap.json').read_text(encoding='utf-8'))
    header=('17 PASSI — ROADMAP CANONICA\nDecisioni del proprietario, 18 ottobre 2026\n\n'
            'Fonte unica degli stati: docs/roadmap.json (usata anche dalla Home).\n'
            'Il documento originale è una fotografia storica, non un elenco di attività autorizzate.\n'
            'La numerazione resta stabile: i collaudi sono riuniti al 17; il 16 prepara la baseline.\n'
            'I test di sviluppo verificano il codice e non sostituiscono il collaudo finale sul server.\n\n')
    return header+'\n\n'.join(row['label']+'\nStato: '+row['state']+'\n'+row['detail'] for row in rows)+'\n'


if __name__=='__main__':
    (ROOT/'17 passi.txt').write_text(render(),encoding='utf-8')
    # Frontend Docker/check builds receive only frontend/, never the sibling docs/.
    target=ROOT/'frontend/src/data/roadmap.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text((ROOT/'docs/roadmap.json').read_text(encoding='utf-8'),encoding='utf-8')
