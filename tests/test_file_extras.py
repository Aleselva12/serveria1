import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.server_files import router
from core.ia_library import router as library_router

class FileExtrasTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.base=Path(self.temp.name)
        self.data=self.base/'files';self.library=self.base/'library';self.originals=self.base/'originals'
        for p in [self.data,self.library,self.originals]:p.mkdir()
        self.env=patch.dict(os.environ,{'CORA_FILES_TOKEN':'owner','CORA_FILE_ROOTS':json.dumps([{'id':'files','path':str(self.data),'writable':True},{'id':'ro','path':str(self.data),'writable':False}]),'CORA_KNOWLEDGE_ROOT':str(self.library),'CORA_LIBRARY_ORIGINALS_ROOT':str(self.originals),'CORA_FILES_MAX_UPLOAD_BYTES':'100'})
        self.env.start();app=FastAPI();app.include_router(router);app.include_router(library_router)
        self.client=TestClient(app,headers={'Authorization':'Bearer owner'});self.prefix='/api/v1/server/files'
    def tearDown(self):self.client.close();self.env.stop();self.temp.cleanup()
    def start(self,name='hello.txt',data=b'hello world',area='server',root='files'):
        prefix='/api/v1/'+area+'/files'
        r=self.client.post(prefix+'/uploads',json={'root_id':root,'filename':name,'size':len(data),'sha256':hashlib.sha256(data).hexdigest()})
        self.assertEqual(r.status_code,201,r.text);return r.json()['id']
    def chunk(self,ident,data,offset=0,prefix=None,root='files'):
        return self.client.post((prefix or self.prefix)+'/uploads/'+ident+'/chunks',data={'root_id':root,'offset':offset},files={'file':('chunk',data)})
    def complete(self,ident,prefix=None,root='files'):
        return self.client.post((prefix or self.prefix)+'/uploads/'+ident+'/complete',params={'root_id':root})
    def test_resume_checks_offset_digest_and_receipt_without_overwrite(self):
        ident=self.start();self.assertEqual(self.chunk(ident,b'hello').json()['offset'],5)
        self.assertEqual(self.chunk(ident,b'duplicate',0).status_code,409)
        self.assertEqual(self.complete(ident).status_code,409)
        self.assertEqual(self.client.get(self.prefix+'/uploads/'+ident,params={'root_id':'files'}).json()['offset'],5)
        self.assertEqual(self.chunk(ident,b' world',5).status_code,200)
        self.assertEqual(self.complete(ident).status_code,200)
        self.assertEqual((self.data/'hello.txt').read_bytes(),b'hello world')
        self.assertEqual(self.complete(ident).status_code,200)
        self.assertEqual(self.client.get(self.prefix+'/uploads/'+ident,params={'root_id':'files'}).json()['offset'],11)
        self.assertEqual(self.client.get(self.prefix+'/children',params={'root_id':'files'}).json()['total'],1)
    def test_wrong_digest_and_readonly_root_never_publish(self):
        ident=self.start(data=b'right');self.chunk(ident,b'wrong')
        self.assertEqual(self.complete(ident).status_code,422)
        self.assertFalse((self.data/'hello.txt').exists())
        r=self.client.post(self.prefix+'/uploads',json={'root_id':'ro','filename':'x','size':1,'sha256':'0'*64})
        self.assertEqual(r.status_code,403)
        self.assertEqual(self.client.get(self.prefix+'/uploads/../secret',params={'root_id':'files'}).status_code,404)
    def test_library_resume_preserves_distinct_original_and_limits_scope(self):
        ident=self.start(area='library',root='library',data=b'copy')
        lp='/api/v1/library/files'
        self.assertEqual(self.chunk(ident,b'copy',prefix=lp,root='library').status_code,200)
        self.assertEqual(self.complete(ident,prefix=lp,root='library').status_code,200)
        original=list(self.originals.glob('*/hello.txt'))[0]
        self.assertEqual(original.read_bytes(),b'copy');self.assertNotEqual(original.stat().st_ino,(self.library/'hello.txt').stat().st_ino)
        self.assertEqual(self.client.get(self.prefix+'/uploads/'+ident,params={'root_id':'files'}).status_code,404)
    def test_conflicting_destination_is_not_replaced(self):
        ident=self.start(data=b'new');self.chunk(ident,b'new');(self.data/'hello.txt').write_bytes(b'old')
        self.assertEqual(self.complete(ident).status_code,409);self.assertEqual((self.data/'hello.txt').read_bytes(),b'old')
    def test_expiry_and_cancel_remove_partial_upload(self):
        ident=self.start();self.chunk(ident,b'hello')
        self.assertEqual(self.client.delete(self.prefix+'/uploads/'+ident,params={'root_id':'files'}).status_code,200)
        self.assertFalse((self.data/'hello.txt').exists())
        ident=self.start();meta=self.data/'.cora-staging'/('upload-'+ident)/'meta.json';data=json.loads(meta.read_text());data['created']=0;meta.write_text(json.dumps(data))
        self.assertEqual(self.client.get(self.prefix+'/uploads/'+ident,params={'root_id':'files'}).status_code,410)
    def test_preview_escapes_html_and_search_ignores_links_and_reserved_areas(self):
        (self.data/'deep').mkdir();(self.data/'deep'/'report.txt').write_text('<script>do not execute</script>')
        (self.data/'.cora-staging').mkdir();(self.data/'.cora-staging'/'report.txt').write_text('hidden')
        outside=self.base/'external';outside.mkdir();(outside/'report.txt').write_text('secret');(self.data/'link').symlink_to(outside)
        r=self.client.get(self.prefix+'/search',params={'root_id':'files','query':'report'}).json()
        self.assertEqual([i['path'] for i in r['items']],['deep/report.txt'])
        r=self.client.get(self.prefix+'/preview',params={'root_id':'files','path':'deep/report.txt'})
        self.assertEqual(r.json()['kind'],'text');self.assertIn('<script>',r.json()['text']);self.assertEqual(r.headers['x-content-type-options'],'nosniff')
        (self.data/'bad.html').write_text('<script/>')
        self.assertEqual(self.client.get(self.prefix+'/preview',params={'root_id':'files','path':'bad.html'}).status_code,415)
        self.assertEqual(self.client.get(self.prefix+'/preview',params={'root_id':'files','path':'link/report.txt'}).status_code,403)
    def test_no_auth_no_extras(self):
        self.assertEqual(self.client.get(self.prefix+'/search',params={'root_id':'files','query':'x'},headers={'Authorization':''}).status_code,401)

    def test_resumable_metadata_cannot_redirect_publication_outside_root(self):
        ident=self.start(data=b'new');self.chunk(ident,b'new')
        metadata=self.data/'.cora-staging'/('upload-'+ident)/'meta.json'
        original=json.loads(metadata.read_text())
        for field,value in [('path','../outside'),('filename','../escape.txt'),('size','not-a-number'),('created','bad')]:
            meta={**original,field:value};metadata.write_text(json.dumps(meta))
            result=self.complete(ident)
            self.assertIn(result.status_code,(400,409),(field,result.text))
            self.assertFalse((self.base/'escape.txt').exists())
        metadata.write_text(json.dumps(original))
        self.assertEqual(self.complete(ident).status_code,200)
        self.assertEqual(self.chunk(ident,b'x',3).status_code,409)

    def test_upload_content_and_metadata_symlinks_never_access_external_files(self):
        for name in ('meta.json','content'):
            ident=self.start();slot=self.data/'.cora-staging'/('upload-'+ident)
            external=self.base/('external-'+name);external.write_text('keep private')
            (slot/name).unlink();(slot/name).symlink_to(external)
            self.assertEqual(self.client.get(self.prefix+'/uploads/'+ident,params={'root_id':'files'}).status_code,403)
            self.assertEqual(self.chunk(ident,b'bad').status_code,403)
            self.assertEqual(self.complete(ident).status_code,403)
            self.assertEqual(self.client.delete(self.prefix+'/uploads/'+ident,params={'root_id':'files'}).status_code,403)
            self.assertEqual(external.read_text(),'keep private')

    def test_stale_session_scan_does_not_read_symlinked_metadata(self):
        slot=self.data/'.cora-staging'/('upload-'+'a'*32);slot.mkdir(parents=True)
        external=self.base/'expired.json';external.write_text(json.dumps({'created':0}))
        (slot/'meta.json').symlink_to(external)
        self.start()
        self.assertTrue(slot.exists());self.assertTrue(external.exists())
