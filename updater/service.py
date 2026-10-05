"""Private host service; browser requests go through Cora's owner authentication."""
import argparse
import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from updater.engine import Engine


def handler(engine, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def reply(self, code, value):
            data=json.dumps(value,ensure_ascii=False).encode()
            self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def dispatch(self):
            if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):
                return self.reply(401,{'detail':'Accesso non autorizzato.'})
            try:
                parts=self.path.strip('/').split('/')
                if self.command=='GET':
                    if parts==['status']: return self.reply(200,{'available':True,'active_commit':engine.current()['commit'],'jobs':engine.list_jobs()})
                    if len(parts)==2 and parts[0]=='jobs': return self.reply(200,engine.public(engine.load(parts[1])))
                elif self.command=='POST':
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=20000: raise ValueError('Richiesta troppo grande o vuota.')
                    data=json.loads(self.rfile.read(length))
                    if not isinstance(data,dict): raise ValueError('Richiesta non valida.')
                    if parts==['workspaces'] and set(data)=={'title'}: return self.reply(201,engine.create_workspace(data['title']))
                    if len(parts)==3 and parts[0]=='workspaces' and parts[2]=='commit' and set(data)=={'message'}:
                        return self.reply(200,engine.commit_workspace(parts[1],data['message']))
                    if parts==['jobs'] and set(data)<= {'kind','workspace_id','commit','release_id'}:
                        return self.reply(202,engine.submit(data['kind'],data.get('workspace_id',''),data.get('commit',''),data.get('release_id','')))
                self.reply(404,{'detail':'Operazione non disponibile.'})
            except FileNotFoundError: self.reply(404,{'detail':'Risorsa non trovata.'})
            except (ValueError,KeyError,TypeError,UnicodeError): self.reply(409,{'detail':'Richiesta non valida o stato cambiato: ricontrolla workspace e commit.'})
            except Exception: self.reply(503,{'detail':'Servizio aggiornamenti non disponibile. Controllare il log host.'})
        do_GET=dispatch
        do_POST=dispatch
    return Handler


def main():
    import fcntl
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);args=parser.parse_args()
    root=Path(args.root).resolve()
    with (root/'service.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        engine=Engine(root);engine.start()
        server=ThreadingHTTPServer((engine.config['listen'],engine.config['port']),handler(engine,(root/'bridge.token').read_text().strip()))
        import threading
        serving=threading.Thread(target=server.serve_forever,daemon=True);serving.start()
        try:
            while engine.worker.is_alive():threading.Event().wait(1)
            raise RuntimeError('Worker updater terminato; il supervisore deve riavviare il servizio.')
        finally:server.shutdown();server.server_close()


if __name__=='__main__': main()
