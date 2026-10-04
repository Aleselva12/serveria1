"""Static inspection of generated adapters; no import of generated Python."""
import ast
import json
from programmer_agent import workspace as ws
from core.runtime import checkpoint


def contracts(identifier):
    from programmer_agent.components import _load
    from core.automation_drafts import validate_graph
    from core.tool_inventory import inventory
    rows = _load(identifier)
    targets = {p for row in rows for p in row['files'] if row['kind'] == 'tool' and p.endswith('.py') or row['kind'] == 'automation' and p.endswith('.json')}
    targets.update(p for p in ws.list_files(identifier) if p.startswith(('generated_tools/', 'generated_automations/')))
    errors, warnings, checked, ids = [], [], 0, set()
    entries = [e for e in inventory()['entries'] if e['kind'] == 'tool']
    live = {e['id'] for e in entries}
    capabilities = {c['id'] for e in entries for c in e.get('capabilities', [])}
    def error(path, message): errors.append({'path': path, 'error': message})
    for path in sorted(targets):
        checkpoint()
        content = ws.file_path(identifier, path).read_text(encoding='utf-8')
        if path.endswith('.json'):
            checked += 1
            try:
                validated = validate_graph(json.loads(content), tool_ids=live)
                for warning in validated.get('warnings', []):
                    error(path, 'Bozza incompleta: '+warning)
            except (ValueError, TypeError, KeyError) as exc:
                error(path, str(exc)[:300])
        elif path.endswith('.py'):
            try:
                tree = ast.parse(content)
            except SyntaxError as exc:
                error(path, str(exc)); continue
            for fn in ast.walk(tree):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for decorator in fn.decorator_list:
                    if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Name) or decorator.func.id != 'agent_tool':
                        continue
                    checked += 1
                    try:
                        args = [ast.literal_eval(a) for a in decorator.args]
                        kw = {k.arg: ast.literal_eval(k.value) for k in decorator.keywords}
                        actor = args[0] if args else kw.get('actor')
                        actions = kw.get('actions')
                        if not isinstance(actor, str) or not actor or not isinstance(actions, (tuple, list)) or not actions or any(not isinstance(a,str) or not a for a in actions):
                            raise ValueError('actor e actions devono essere stringhe esplicite.')
                        if kw.get('effect') not in {'read', 'compute', 'write', 'delegate'} or kw.get('retry') not in {'safe', 'never'}:
                            raise ValueError('effect e retry devono essere espliciti e validi.')
                        if kw['effect'] in {'write', 'delegate'} and kw['retry'] == 'safe':
                            raise ValueError('Non dichiarare retry safe per scritture/deleghe senza revisione di idempotenza.')
                        arguments = [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]
                        if any(a.annotation is None for a in arguments) or fn.returns is None or fn.args.vararg or fn.args.kwarg:
                            raise ValueError('Input e output devono avere tipi espliciti, senza argomenti variadici.')
                        key = kw.get('capability', fn.name)
                        if not isinstance(key, str) or not key or actor+'.'+key in ids or actor+'.'+key in capabilities:
                            raise ValueError('ID capability duplicato o già presente: revisionare il collegamento.')
                        ids.add(actor+'.'+key)
                        warnings.append({'path': path, 'warning': 'Verificare manualmente permessi, binding, semantica dei tipi e integrazione di '+key})
                    except (ValueError, TypeError, IndexError) as exc:
                        error(path, str(exc)[:300])
    if not checked:
        error('', 'Nessun adapter agent_tool o bozza automazione da verificare. Registra il componente o usa generated_tools/generated_automations.')
    return {'profile': 'contracts', 'passed': not errors, 'checked': checked, 'errors': errors[:50],
            'total_errors': len(errors), 'warnings': warnings[:50], 'executes_code': False,
            'scope': 'Ispezione statica di adapter e validazione bozze; non prova comportamento o registrazione nel runtime.'}
