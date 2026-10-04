"""Real relational integration tests, enabled only for the disposable CI database."""
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID,uuid4
from fastapi.testclient import TestClient
from core.database import db_connection,close_pool
from core.auth import provision
from core.runtime import Runtime

@unittest.skipUnless(os.getenv('CORA_RUNTIME_TEST_DATABASE_URL'), 'Requires disposable PostgreSQL+pgvector')
class MediaPostgresTests(unittest.TestCase):
    def setUp(self):
        import api
        import core.audio_api as audio_api
        import core.runtime_api as runtime_api
        from audio_agent import audio_tools
        self.api=api;self.audio_api=audio_api;self.temp=tempfile.TemporaryDirectory();base=Path(self.temp.name)
        self.files=base/'files';self.library=base/'library';self.originals=base/'originals';self.audio=base/'audio'
        for path in [self.files,self.library,self.originals,self.audio]:path.mkdir()
        import json
        self.patches=[patch.dict(os.environ,{'CORA_CHAT_ATTACHMENTS_ROOT':str(base/'attachments'),'CORA_FILE_ROOTS':json.dumps([{'id':'files','path':str(self.files),'writable':True}]),'CORA_KNOWLEDGE_ROOT':str(self.library),'CORA_LIBRARY_ORIGINALS_ROOT':str(self.originals),'CORA_EMBEDDING_MODEL':''}),patch.object(audio_tools,'AUDIO_ROOT',self.audio)]
        self.runtime=Runtime()
        self.patches += [patch.object(api,'runtime',self.runtime),patch.object(audio_api,'runtime',self.runtime),patch.object(runtime_api,'runtime',self.runtime),patch.object(api.postprocess,'submit')]
        for p in self.patches:p.start()
        with db_connection() as conn:
            conn.execute('TRUNCATE app_sessions,app_users,chat_attachments,audio_records,file_shares CASCADE')
        provision('media-owner','a-long-media-test-password')
        self.client=TestClient(api.app,headers={'X-Cora-Client':'ui'})
        self.assertEqual(self.client.post('/auth/login',json={'username':'media-owner','password':'a-long-media-test-password'}).status_code,200)
    def tearDown(self):
        self.runtime.shutdown();self.client.close()
        for p in reversed(self.patches):p.stop()
        close_pool();self.temp.cleanup()
    def wait(self,ident):
        run=self.runtime.get(ident);self.assertTrue(run.done.wait(5));self.assertEqual(run.status,'completed',run.snapshot());return run
    def test_chat_upload_is_persisted_scoped_and_reaches_model_context(self):
        cid=str(uuid4());uploaded=self.client.post('/api/v1/chat/attachments',data={'conversation_id':cid},files={'file':('report.txt',b'Vendite: 42')})
        self.assertEqual(uploaded.status_code,201,uploaded.text);attachment=uploaded.json()
        seen=[]
        def fake_stream(data,**kwargs):
            seen.extend(data['messages']);yield 'values',{'messages':[SimpleNamespace(content='Letto') ]}
        with patch.object(self.api.graph,'stream',side_effect=fake_stream):
            response=self.client.post('/api/v1/chat/runs',json={'message':'Riassumi','thread_id':cid,'attachment_ids':[attachment['id']]})
            self.assertEqual(response.status_code,202,response.text);self.wait(response.json()['id'])
        self.assertTrue(any('Vendite: 42' in str(getattr(m,'content',m)) for m in seen))
        messages=self.client.get('/conversations/'+cid+'/messages').json()
        self.assertEqual(messages[0]['content'],'Riassumi');self.assertEqual(messages[0]['metadata']['attachments'][0]['id'],attachment['id'])
        self.assertEqual(self.client.get(attachment['downloadUrl']).content,b'Vendite: 42')
        invalid=self.client.post('/api/v1/chat/runs',json={'message':'Riassumi','thread_id':str(uuid4()),'attachment_ids':[attachment['id']]})
        self.assertEqual(invalid.status_code,404)
    def test_private_share_requires_login_expires_and_is_revocable(self):
        (self.files/'document.txt').write_text('private')
        prefix='/api/v1/server/files'
        created=self.client.post(prefix+'/shares',json={'root_id':'files','path':'document.txt','hours':24})
        self.assertEqual(created.status_code,201,created.text);share=created.json()
        guest=TestClient(self.api.app)
        try: self.assertEqual(guest.get(share['url']).status_code,401)
        finally: guest.close()
        self.assertEqual(self.client.get(share['url']).text,'private')
        self.assertEqual(self.client.delete(prefix+'/shares/'+share['id']).status_code,200)
        self.assertEqual(self.client.get(share['url']).status_code,404)
        share=self.client.post(prefix+'/shares',json={'root_id':'files','path':'document.txt','hours':1}).json()
        with db_connection() as conn:conn.execute("UPDATE file_shares SET expires_at=NOW()-INTERVAL '1 second' WHERE id=%s",(UUID(share['id']),))
        self.assertEqual(self.client.get(share['url']).status_code,404)
    def test_changed_shared_file_is_not_served_as_the_original(self):
        (self.files/'document.txt').write_text('private')
        share=self.client.post('/api/v1/server/files/shares',json={'root_id':'files','path':'document.txt'}).json()
        (self.files/'document.txt').write_text('changed bytes')
        self.assertEqual(self.client.get(share['url']).status_code,409)
    def test_audio_runtime_persistence_correction_conflict_and_library_export(self):
        from audio_agent import audio_tools
        uploaded=self.client.post('/api/v1/audio',data={'title':'Telefonata','recorded_at':'2026-10-04T19:30','speaker_one':'Ale'},files={'file':('call.wav',b'fake audio')})
        self.assertEqual(uploaded.status_code,201,uploaded.text);record=uploaded.json();ident=record['id']
        engine_result={'transcript':'[00:00] Interlocutore 1: ciao','diarization_status':'applied','diarization_warning':None,'duration_seconds':1,'detected_language':'it'}
        with patch.object(self.audio_api,'audio_status',return_value={'ready':True}),patch.object(audio_tools,'transcribe_path',return_value=engine_result):
            run=self.client.post('/api/v1/audio/'+ident+'/transcribe',json={'expected_version':1,'diarize':True})
            self.assertEqual(run.status_code,202,run.text);self.wait(run.json()['id'])
        details=self.client.get('/api/v1/audio/'+ident).json();self.assertIn('Ale: ciao',details['transcript']);self.assertEqual(details['version'],2)
        edited=self.client.put('/api/v1/audio/'+ident+'/transcript',json={'transcript':'corretto','expected_version':2})
        self.assertEqual(edited.status_code,200,edited.text)
        conflict=self.client.put('/api/v1/audio/'+ident+'/transcript',json={'transcript':'stale','expected_version':2})
        self.assertEqual(conflict.status_code,409)
        self.assertEqual(self.client.get('/api/v1/audio/'+ident+'/transcript/download').text,'corretto')
        copied=self.client.post('/api/v1/audio/'+ident+'/library')
        self.assertEqual(copied.status_code,201,copied.text)
        original=self.originals/copied.json()['original']['path'];copy=self.library/copied.json()['copy']['path']
        self.assertEqual(original.read_text(),'corretto');self.assertNotEqual(original.stat().st_ino,copy.stat().st_ino)
        with db_connection() as conn:row=conn.execute('SELECT kind,target FROM runtime_runs WHERE id=%s',(UUID(run.json()['id']),)).fetchone()
        self.assertEqual((row['kind'],row['target']),('audio','audio_agent'))
