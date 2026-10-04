import json
import tempfile
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock,patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core import audio_api

class AudioUITests(unittest.TestCase):
    def test_worker_uses_shared_engine_and_saves_transcript_with_compare_and_swap(self):
        ident=uuid.uuid4();row={'id':ident,'source_path':'call.wav','speaker_names':['Ale','Cliente'],'version':1,'transcript':None}
        conn=MagicMock();conn.execute.return_value.fetchone.return_value={'id':ident}
        @contextmanager
        def db():yield conn
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);(base/'call.wav').write_bytes(b'audio')
            tools=SimpleNamespace(AUDIO_ROOT=base,transcribe_path=MagicMock(return_value={'transcript':'[00:00] Interlocutore 1: ciao\n[00:01] Interlocutore 2: salve','diarization_status':'applied'}))
            fake_run=SimpleNamespace(id=str(uuid.uuid4()),snapshot=lambda:{'id':'run','status':'queued'})
            def submit(thread,work,**kw):
                self.assertEqual(thread,'audio:'+str(ident));work(fake_run);return fake_run
            with patch.object(audio_api,'audio_status',return_value={'ready':True}),patch.object(audio_api,'get_record',return_value=row),patch.object(audio_api,'engine',return_value=tools),patch.object(audio_api,'db_connection',db),patch.object(audio_api.runtime,'submit',side_effect=submit):
                result=audio_api.transcribe(ident,audio_api.TranscriptionRequest(expected_version=1,diarize=True))
                self.assertEqual(result['status'],'queued');tools.transcribe_path.assert_called_once_with(base/'call.wav','it',True,2)
                args=conn.execute.call_args_list[1].args[1]
                self.assertIn('Ale: ciao',args[0]);self.assertIn('Cliente: salve',args[0]);self.assertEqual(args[2:],(ident,1))
    def test_existing_transcript_or_stale_version_does_not_submit(self):
        ident=uuid.uuid4()
        with patch.object(audio_api.runtime,'submit') as submit:
            for row in [{'version':2,'transcript':None},{'version':1,'transcript':'saved'}]:
                with patch.object(audio_api,'get_record',return_value=row):
                    with self.assertRaises(Exception) as error:audio_api.transcribe(ident,audio_api.TranscriptionRequest(expected_version=1))
                    self.assertEqual(error.exception.status_code,409)
            submit.assert_not_called()
    def test_edit_conflict_does_not_report_success(self):
        conn=MagicMock();conn.execute.return_value.fetchone.return_value=None
        @contextmanager
        def db():yield conn
        with patch.object(audio_api,'db_connection',db):
            with self.assertRaises(Exception) as error:audio_api.edit(uuid.uuid4(),audio_api.TranscriptEdit(transcript='correction',expected_version=1))
            self.assertEqual(error.exception.status_code,409)
    def test_library_export_keeps_versioned_filename_and_original(self):
        ident=uuid.uuid4()
        with patch.object(audio_api,'get_record',return_value={'transcript':'testo corretto','version':3}),patch('core.ia_library.upload_copy') as upload:
            audio_api.copy_to_library(ident)
            _,file=upload.call_args.args
            self.assertIn('-v3.txt',file.filename);self.assertEqual(file.file.read(),b'testo corretto')
