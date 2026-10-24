import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError
from unittest.mock import patch
from worker import worker


class WorkerChatTests(unittest.TestCase):
    def test_native_chat_tools_auth_installed_model_and_busy_slot(self):
        reply = {'model': 'small', 'message': {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {'name': 'note', 'arguments': {'content': 'ok'}}}]}, 'done': True}
        with patch.object(worker, 'TOKEN', 's' * 40), patch.object(worker, 'installed_models', return_value=[{'name': 'small'}]), patch.object(worker, 'ollama', return_value=reply) as ollama:
            server = ThreadingHTTPServer(('127.0.0.1', 0), worker.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            def post(body, auth=True):
                request = Request(f'http://127.0.0.1:{server.server_port}/chat', data=json.dumps(body).encode(), headers={'X-Cora-Worker-Token': 's' * 40 if auth else 'wrong', 'Content-Type': 'application/json'})
                return build_opener(ProxyHandler({})).open(request, timeout=2)
            body = {'model': 'small', 'messages': [{'role': 'user', 'content': 'hello'}], 'tools': [{'type': 'function', 'function': {'name': 'note'}}], 'stream': True}
            try:
                with post(body) as response: self.assertEqual(json.load(response), reply)
                self.assertEqual(ollama.call_args.args[0], '/api/chat')
                self.assertEqual(ollama.call_args.args[1]['tools'], body['tools'])
                self.assertFalse(ollama.call_args.args[1]['stream'])
                for data, auth, code in [(body, False, 403), ({**body, 'model': 'absent'}, True, 422), ({**body, 'messages': []}, True, 422)]:
                    with self.assertRaises(HTTPError) as error: post(data, auth)
                    self.assertEqual(error.exception.code, code)
                worker._inference_slot.acquire()
                try:
                    with self.assertRaises(HTTPError) as error: post(body)
                    self.assertEqual(error.exception.code, 429)
                finally: worker._inference_slot.release()
            finally:
                server.shutdown(); server.server_close(); thread.join()


    def test_model_metadata_requires_auth_and_never_exposes_prompt_or_runs_inference(self):
        metadata = {'capabilities':['completion','tools'], 'thinking':{'values':[False],'default':False},
                    'model_info':{'x.context_length':4096}, 'template':'private template', 'system':'private prompt'}
        with patch.object(worker,'TOKEN','s'*40), patch.object(worker,'installed_models',return_value=[{'name':'small'}]), patch.object(worker,'ollama',return_value=metadata) as ollama:
            server = ThreadingHTTPServer(('127.0.0.1',0),worker.Handler)
            thread = threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            def request(token,model='small'):
                req = Request(f'http://127.0.0.1:{server.server_port}/model-info',data=json.dumps({'model':model}).encode(),headers={'X-Cora-Worker-Token':token,'Content-Type':'application/json'})
                return build_opener(ProxyHandler({})).open(req,timeout=2)
            try:
                with self.assertRaises(HTTPError) as error:request('wrong')
                self.assertEqual(error.exception.code,403)
                with request('s'*40) as response:info=json.load(response)
                self.assertEqual(info['model_info']['x.context_length'],4096)
                self.assertNotIn('system',info);self.assertNotIn('template',info)
                self.assertEqual(ollama.call_args.args,('/api/show',{'model':'small'}))
                self.assertEqual(ollama.call_count,1)
                with self.assertRaises(HTTPError) as error:request('s'*40,'absent')
                self.assertEqual(error.exception.code,422)
                self.assertEqual(ollama.call_count,1)
            finally:
                server.shutdown();server.server_close();thread.join()
