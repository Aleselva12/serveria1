import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock,patch
from audio_agent.audio_tools import _load_whisper_model,transcribe_audio_file
from audio_agent.model_setup import digest,verify,prepare
from deploy.doctor import model_available,inspect


class AudioDeploymentTests(unittest.TestCase):
    def tearDown(self):_load_whisper_model.cache_clear()

    def test_missing_offline_model_never_calls_engine_or_download(self):
        factory=Mock()
        with patch.dict(os.environ,{'CORA_WHISPER_MODEL':'/missing-cora-model','CORA_WHISPER_LOCAL_ONLY':'true'}),patch.dict(sys.modules,{'faster_whisper':types.SimpleNamespace(WhisperModel=factory)}):
            with self.assertRaisesRegex(RuntimeError,'locale assente'):_load_whisper_model()
        factory.assert_not_called()

    def test_cpu_engine_is_offline_bounded_and_reused(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)
            for name in ('model.bin','config.json','tokenizer.json'):(path/name).write_bytes(b'fixture')
            factory=Mock()
            with patch.dict(os.environ,{'CORA_WHISPER_MODEL':temporary,'CORA_WHISPER_LOCAL_ONLY':'true','CORA_WHISPER_DEVICE':'cpu','CORA_WHISPER_COMPUTE_TYPE':'int8','CORA_WHISPER_CPU_THREADS':'3'}),patch.dict(sys.modules,{'faster_whisper':types.SimpleNamespace(WhisperModel=factory)}):
                _load_whisper_model();_load_whisper_model()
            factory.assert_called_once_with(temporary,device='cpu',compute_type='int8',cpu_threads=3,num_workers=1,local_files_only=True)

    def test_model_manifest_detects_corruption_and_path_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)
            for name in ('model.bin','config.json','tokenizer.json'):(path/name).write_bytes(b'fixture')
            manifest={'version':1,'revision':'a'*40,'sha256':{name:digest(path/name) for name in ('model.bin','config.json','tokenizer.json')}}
            (path/'cora-model.json').write_text(json.dumps(manifest));verify(path)
            manifest['sha256']['../escape']='bad';(path/'cora-model.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'Invalid model file path'):verify(path)
            del manifest['sha256']['../escape'];(path/'cora-model.json').write_text(json.dumps(manifest))
            (path/'model.bin').write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):verify(path)

    def test_cancel_during_segment_iteration_escapes_without_partial_transcript(self):
        from core.runtime import RunStopped
        from core.governance import find_capability
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary);(path/'sample.wav').write_bytes(b'fixture')
            model=Mock();model.transcribe.return_value=([SimpleNamespace(text='partial',start=0,end=1)],SimpleNamespace(language='it'))
            fn=find_capability('audio_agent.transcribe_audio_file')[1]['fn']
            with patch('audio_agent.audio_tools.AUDIO_ROOT',path),patch('audio_agent.audio_tools._require_permission'),patch('audio_agent.audio_tools._load_whisper_model',return_value=model),patch('core.runtime.checkpoint',side_effect=[None,None,RunStopped('cancelled')]):
                with self.assertRaises(RunStopped):fn('sample.wav')

    def test_model_preparation_pins_public_revision_and_cleans_partial_download(self):
        api=Mock();api.model_info.return_value.sha='a'*40
        download=Mock(side_effect=OSError('download interrupted'))
        utils=types.SimpleNamespace(available_models=lambda:['small'],download_model=download,_MODELS={'small':'public/model'})
        with tempfile.TemporaryDirectory() as temporary:
            destination=Path(temporary)/'whisper'
            with patch.dict(sys.modules,{'faster_whisper':types.ModuleType('faster_whisper'),'faster_whisper.utils':utils,'huggingface_hub':types.SimpleNamespace(HfApi=Mock(return_value=api))}):
                with self.assertRaises(OSError):prepare('small',destination)
            self.assertFalse(destination.exists());self.assertEqual(list(Path(temporary).iterdir()),[])
            self.assertEqual(download.call_args.kwargs['revision'],'a'*40)
            self.assertIs(download.call_args.kwargs['use_auth_token'],False)

    def test_doctor_reports_failed_dependency_without_credentials_or_exception_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(os.environ,{'CORA_API_BUILD_TARGET':'api'},clear=True),patch('core.database.db_connection') as db,patch('core.server_files.roots',return_value=[{'id':'test','path':temporary,'writable':True}]),patch('deploy.doctor.urlopen',side_effect=OSError('private password in error')):
                conn=db.return_value.__enter__.return_value
                conn.execute.return_value.fetchone.side_effect=[{'vector':True},{'n':1}]
                result=inspect()
            self.assertFalse(result['ok']);self.assertFalse(result['checks']['ollama']['ok'])
            self.assertNotIn('private password',json.dumps(result))

    def test_ollama_names_allow_only_default_latest_alias(self):
        self.assertTrue(model_available('local-model',{'local-model:latest'}))
        self.assertFalse(model_available('local-model:custom',{'local-model:latest'}))
