"""Reproduce fresh desktop access and missing mounts without Ollama or live data."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from core import file_paths
from core.governance import CapabilityExecutionError
from core.library_preflight import preload
from search_agent import search_tools


class LibraryWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        for setting in (patch.object(file_paths,'BASE',self.base),
                        patch.dict(os.environ,{'CORA_KNOWLEDGE_ROOT':'','CORA_LIBRARY_ORIGINALS_ROOT':''}),
                        patch('core.permissions.policy_overrides',return_value={}),
                        patch('core.operation_journal.begin',return_value=None),
                        patch('core.operation_journal.finish',return_value=None)):
            setting.start();self.addCleanup(setting.stop)

    def test_first_agent_access_initializes_same_default_as_ui_without_opening_files(self):
        from core.ia_library import library_base
        import tools
        self.assertFalse((self.base/'knowledge').exists())
        data=json.loads(tools.library_list.invoke({}))
        self.assertEqual(data['documents'],[])
        self.assertEqual(library_base(),self.base/'knowledge')
        (library_base()/'note.txt').write_text('workspace note',encoding='utf-8')
        self.assertIn('workspace note',tools.library_read.invoke({'relative_path':'note.txt'}))

    def test_agents_and_ui_follow_current_configuration_not_an_import_time_path(self):
        from core.ia_library import library_base
        import tools
        for folder in ('first','second'):
            root=self.base/folder;root.mkdir();(root/'note.txt').write_text(folder,encoding='utf-8')
            with patch.dict(os.environ,{'CORA_KNOWLEDGE_ROOT':str(root)}):
                self.assertEqual(library_base(),root)
                self.assertIn(folder,tools.library_read.invoke({'relative_path':'note.txt'}))

    def test_missing_configured_mount_is_not_created_or_replaced_with_default(self):
        from core.ia_library import library_roots
        import tools
        missing=self.base/'not-mounted'
        with patch.dict(os.environ,{'CORA_KNOWLEDGE_ROOT':str(missing)}):
            self.assertEqual(Path(library_roots()[0]['path']),missing)
            with self.assertRaises(CapabilityExecutionError) as failure:
                tools.library_search.invoke({'query':'note'})
            self.assertEqual(failure.exception.code,'LibraryRootMissing')
            text=preload('Il file "note" è nella Libreria IA',['library_search','library_read'])
            self.assertIn('NON RIUSCITA',text)
            self.assertIn('mount',text)
            self.assertNotIn(str(missing),text)
            self.assertEqual(file_paths.library_workspace_status()['code'],'LibraryRootMissing')
            self.assertFalse(missing.exists())
            self.assertFalse((self.base/'knowledge').exists())
            # A repaired mount becomes visible without reloading the Python module.
            missing.mkdir();(missing/'note.txt').write_text('recovered',encoding='utf-8')
            self.assertIn('recovered',tools.library_read.invoke({'relative_path':'note.txt'}))

    def test_non_directory_overlap_and_permissions_are_distinct(self):
        target=self.base/'file';target.write_text('not a directory')
        with patch.dict(os.environ,{'CORA_KNOWLEDGE_ROOT':str(target)}):
            self.assertEqual(file_paths.library_workspace_status()['code'],'LibraryRootNotDirectory')
        with patch.dict(os.environ,{'CORA_KNOWLEDGE_ROOT':str(self.base/'data/library_originals')}):
            self.assertEqual(file_paths.library_workspace_status()['code'],'LibraryRootsOverlap')
        with patch.dict(os.environ,{'CORA_KNOWLEDGE_ROOT':str(self.base/'denied')}),patch.object(Path,'stat',side_effect=PermissionError('private host detail')):
            status=file_paths.library_workspace_status()
            self.assertEqual(status['code'],'LibraryPermissionDenied')
            self.assertNotIn('private host detail',json.dumps(status))

    def test_unreadable_walk_is_an_error_instead_of_an_empty_success(self):
        import tools
        def inaccessible(*args,**kwargs):
            kwargs['onerror'](PermissionError('private path'))
            yield
        with patch.object(search_tools.os,'walk',side_effect=inaccessible):
            with self.assertRaises(CapabilityExecutionError) as failure:
                tools.library_search.invoke({'query':'note'})
        self.assertEqual(failure.exception.code,'LibraryPermissionDenied')

    def test_invalid_path_and_temporary_storage_failure_are_reported_without_details(self):
        for cause,expected in ((ValueError('private detail'),'LibraryRootInvalid'),
                               (OSError('private detail'),'LibraryStorageUnavailable')):
            with patch.object(file_paths,'knowledge_root',side_effect=cause):
                result=file_paths.library_workspace_status()
                self.assertEqual(result['code'],expected)
                self.assertNotIn('private detail',json.dumps(result))

    def test_full_chat_graph_survives_real_missing_root_and_lists_without_a_model(self):
        import graph
        from langchain_core.messages import AIMessage,HumanMessage
        model=Mock();model.invoke.return_value=AIMessage('La Libreria IA non è disponibile; non ho letto il file.')
        with patch.dict(os.environ,{'CORA_KNOWLEDGE_ROOT':str(self.base/'missing')}),patch.object(graph,'model_with_tools',model):
            request='Leggi il file "note" nella Libreria IA'
            response=graph.graph.invoke({'messages':[HumanMessage(request)],'request_text':request})
            self.assertIn('non è disponibile',response['messages'][-1].content)
            model.invoke.assert_called_once()
            context=' '.join(str(m.content) for m in model.invoke.call_args.args[0])
            self.assertIn('CONSULTAZIONE LIBRERIA IA NON RIUSCITA',context)
            model.reset_mock()
            request='Elenca i file nella Libreria IA'
            response=graph.graph.invoke({'messages':[HumanMessage(request)],'request_text':request})
            self.assertIn('Impossibile consultare',response['messages'][-1].content)
            model.invoke.assert_not_called()


class PreflightFailureTests(unittest.TestCase):
    @patch('tools.library_search')
    @patch('tools.library_read')
    def test_search_error_does_not_abort_prepare_or_attempt_a_read(self,read,search):
        from graph import prepare_turn
        search.invoke.side_effect=CapabilityExecutionError('LibraryRootMissing','private details')
        result=prepare_turn({'messages':[],'request_text':'Il file "note" è nella Libreria IA'})
        self.assertIn('NON RIUSCITA',result['memory_context'])
        self.assertNotIn('private details',result['memory_context'])
        read.invoke.assert_not_called()
        search.invoke.assert_called_once()

    @patch('tools.library_search')
    @patch('tools.library_read')
    def test_malformed_search_and_read_failures_never_claim_document_was_read(self,read,search):
        for response in ('not json','[]','{}','{"results":null}','{"results":[{}]}'):
            search.invoke.return_value=response
            self.assertIn('NON RIUSCITA',preload('/libreria/note',['library_search','library_read']))
        read.invoke.assert_not_called()
        search.invoke.return_value='{"results":[{"path":"note.txt"}]}'
        for response in ('',None,'{"status" : "error"}', '{"status":"pending"}'):
            read.invoke.return_value=response
            result=preload('/libreria/note',['library_search','library_read'])
            self.assertIn('NON RIUSCITA',result)
            self.assertNotIn('DOCUMENTO LIBRERIA IA LETTO',result)

    @patch('tools.library_search')
    def test_cancellation_timeout_and_uncertain_effects_are_never_converted_into_warnings(self,search):
        from core.runtime_context import RunTimedOut
        from core.run_lifecycle import RunCancelled
        from core.run_states import EffectUncertain,DurabilityLost
        for stop in (RunTimedOut('stop'),RunCancelled('stop'),EffectUncertain(),DurabilityLost()):
            search.invoke.side_effect=stop
            with self.assertRaises(type(stop)):preload('/libreria/note',['library_search','library_read'])

    @patch('tools.library_list')
    def test_direct_listing_handles_unavailability_and_malformed_results(self,listing):
        from core.library_routing import list_documents_direct
        listing.invoke.side_effect=CapabilityExecutionError('LibraryRootMissing','private details')
        self.assertIn('Impossibile consultare',list_documents_direct())
        listing.invoke.side_effect=None;listing.invoke.return_value='{}'
        self.assertIn('Impossibile consultare',list_documents_direct())
        listing.invoke.return_value='{"documents":[]}'
        self.assertIn('Non risultano documenti',list_documents_direct())
