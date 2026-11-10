"""Reviewed isolated suites and their explicitly bounded tree coverage."""

SUITES = {'automation_draft_regression': {'title': 'Automazioni: bozze, validazione e versioni',
                                 'component': 'cora',
                                 'tests': ('tests.test_automation_drafts.DraftTests',
                                           'tests.test_automation_api.DraftApiTests'),
                                 'nodes': ['T13.p1', 'T13.p1.m2'],
                                 'scope': 'Persistenza e validazione bozze su cartella temporanea; editor '
                                          'browser, trigger ed esecuzione esclusi.'},
 'capability_permissions_regression': {'title': 'Capability: contratti, permessi e risultati',
                                       'component': 'cora',
                                       'tests': ('tests.test_capability_contracts.ContractTests',),
                                       'nodes': ['T2.p2',
                                                 'T2.p2.m1',
                                                 'T2.p2.m2',
                                                 'R6.2.p1',
                                                 'R6.2.p1.m1',
                                                 'R6.2.p1.m2',
                                                 'R6.2.p2.m1',
                                                 'T13.p2.m1'],
                                       'scope': 'Input/output, autorizzazioni e identità con journal '
                                                'simulato; effetti e database reali esclusi.'},
 'coordinator_regression': {'title': 'Coordinator: ownership e panoramica',
                            'component': 'cora',
                            'tests': ('tests.test_system_coordinator.SystemCoordinatorTests',),
                            'nodes': ['T3.p1', 'T3.p1.m1', 'T3.p1.m2', 'T3.p2', 'T3.p2.m1'],
                            'scope': 'Ownership e snapshot non esecutiva; disponibilità dei servizi reali '
                                     'esclusa.'},
 'runtime_state_regression': {'title': 'Runtime: transizioni, coda e annullamento',
                              'component': 'cora',
                              'tests': ('tests.test_runtime_foundations.RuntimeTests',),
                              'nodes': ['T4.p2', 'T4.p2.m1', 'T4.p2.m2', 'T5.p1', 'T5.p1.m1', 'T13.p2.m2'],
                              'scope': 'Runtime in memoria, FIFO, cancellazione, budget e isolamento bus; '
                                       'persistenza e ripresa dopo crash escluse.'},
 'component_protocol_regression': {'title': 'Componenti: protocollo e destinatari',
                                   'component': 'cora',
                                   'tests': ('tests.test_core_protocol.ProtocolBusTests',),
                                   'nodes': ['T5.p2', 'T5.p2.m1', 'T5.p2.m2'],
                                   'scope': 'Messaggi tipizzati e dispatch locale; rete distribuita '
                                            'esclusa.'},
 'context_packet_regression': {'title': 'Contesto: fonti, interpretazioni e conflitti',
                               'component': 'cora',
                               'tests': ('tests.test_context_contracts.ContextContractTests',),
                               'nodes': ['T6.p3', 'T6.p3.m1', 'T6.p3.m2'],
                               'scope': 'Contratti del pacchetto e distinzione tra letterale e sintesi; '
                                        'qualità del recupero reale esclusa.'},
 'agent_bindings_regression': {'title': 'Agenti: modelli, salvataggio e profili',
                               'component': 'worker',
                               'tests': ('tests.test_agent_models.AssignmentTests',),
                               'nodes': ['T8.p2', 'T8.p2.m1', 'T8.p2.m2'],
                               'scope': 'Configurazione in file temporanei e trasporto simulato; inferenza e '
                                        'GPU reali escluse.'},
 'diagnostic_trace_regression': {'title': 'Diagnostica: isolamento, errori e tempi',
                                 'component': 'cora',
                                 'tests': ('tests.test_events_observability.DiagnosticUnitTests',),
                                 'nodes': ['T10.p3.m1', 'T5.p1.m2'],
                                 'scope': 'Metadati, token timing e guasti del sink simulati; storico '
                                          'PostgreSQL e misure prestazionali reali esclusi.'},
 'auth_guard_regression': {'title': 'Accessi: password, cookie e protezioni scrittura',
                           'component': 'cora',
                           'tests': ('tests.test_runtime_foundations.AuthTests',),
                           'nodes': ['R6.1.p2', 'R6.1.p2.m1', 'R6.1.p2.m2'],
                           'scope': 'Autenticazione su app di prova, password e richieste browser; account e '
                                    'dispositivi reali esclusi.'},
 'tailscale_identity_regression': {'title': 'Tailscale: identità e header non attendibili',
                                   'component': 'cora',
                                   'tests': ('tests.test_tailscale_auth.TailscaleAuthTests',),
                                   'nodes': ['R6.1.p1', 'R6.1.p1.m1'],
                                   'scope': 'Proxy e identità simulati; connettività remota e rete tra nodi '
                                            'escluse.'},
 'library_copy_regression': {'title': 'Libreria: copie indipendenti e originali',
                             'component': 'files',
                             'tests': ('tests.test_ia_library.LibraryCopiesTests',),
                             'nodes': ['B2.p1', 'B2.p1.m1'],
                             'scope': 'Import, upload e modifiche su directory temporanee; indicizzazione '
                                      'semantica e mount reali esclusi.'},
 'library_edit_regression': {'title': 'Libreria: conferme, versioni e conflitti',
                             'component': 'files',
                             'tests': ('tests.test_library_writes.LibraryWriteTests',
                                       'tests.test_library_document_editing.DocumentEditingUnitTests'),
                             'nodes': ['B2.p3', 'B2.p3.m1', 'B2.p3.m2', 'B3.p4', 'B3.p4.m2'],
                             'scope': 'Proposte e scritture su fixture, hash, backup e ripristino; browser e '
                                      'storage produttivo esclusi.'},
 'library_search_regression': {'title': 'Local Reader: ricerca, fonti e errori',
                               'component': 'files',
                               'tests': ('tests.test_library_research.LibraryResearchTests',),
                               'nodes': ['B2.p2', 'B2.p2.m1'],
                               'scope': 'Ricerca su documenti temporanei e riferimenti alle fonti; '
                                        'attendibilità semantica non certificata.'},
 'file_preview_regression': {'title': 'File: anteprime, ricerca e ripresa upload',
                             'component': 'files',
                             'tests': ('tests.test_file_extras.FileExtrasTests',),
                             'nodes': ['B1.p1.m2'],
                             'scope': 'Anteprime sanificate, ricerca e upload riprendibile su fixture; '
                                      'browser reale escluso.'},
 'push_payload_regression': {'title': 'Notifiche: chiavi e richiesta cifrata',
                             'component': 'calendar',
                             'tests': ('tests.test_webpush.WebPushTests',),
                             'nodes': ['C1c'],
                             'scope': 'Payload e chiavi su fixture con invio simulato; ricezione sul '
                                      'telefono esclusa.'},
 'tool_registry_regression': {'title': 'Registry: strumenti esposti e collegamenti',
                              'component': 'cora',
                              'tests': ('tests.test_tool_inventory.InventoryTest',),
                              'nodes': ['T2.p1', 'T2.p1.m1', 'T2.p1.m2', 'T8.p1', 'T8.p1.m1', 'T8.p1.m2'],
                              'scope': 'Catalogo eseguibile e binding; completamento di deleghe reali '
                                       'escluso.'},
 'health_registry_regression': {'title': 'Registro salute: esiti, cache e letture',
                                'component': 'cora',
                                'tests': ('tests.test_project_checks.ProjectChecksTests',),
                                'nodes': ['T11.p1',
                                          'T11.p1.m1',
                                          'T11.p1.m2',
                                          'T11.p2',
                                          'T11.p2.m1',
                                          'T11.p2.m2'],
                                'scope': 'Registro e isolamento delle prove con dipendenze simulate; '
                                         'persistenza dopo riavvio esclusa.'},
 'shadow_route_regression': {'title': 'Router shadow: proposta e instradamento',
                             'component': 'cora',
                             'tests': ('tests.test_shadow_router.ShadowRouterTests',),
                             'nodes': ['T1.p2', 'T1.p2.m1'],
                             'scope': 'Classificazione delle chiamate tool su messaggi campione; routing '
                                      'reale del modello escluso.'},
 'larva_observer_regression': {'title': 'Larva: osservazione senza azioni',
                               'component': 'cora',
                               'tests': ('tests.test_system_larva.SystemLarvaTests',),
                               'nodes': ['T1.p3', 'T1.p3.m1', 'T1.p3.m2'],
                               'scope': 'Snapshot campione nominali e guasti: classificazione deterministica '
                                        'senza effetti esterni.'},
 'model_profile_regression': {'title': 'Modelli: profili e compatibilità tool',
                              'component': 'worker',
                              'tests': ('tests.test_model_profiles.ModelProfileTests',),
                              'nodes': ['R3.2.p1', 'R3.2.p1.m1', 'R1.3.p1.m2', 'worker.p3'],
                              'scope': 'Profili e cache simulati; disponibilità RAM/VRAM, benchmark e '
                                       'inferenza reale esclusi.'},
 'machine_registry_regression': {'title': 'Macchine: identità, stato e attivazione',
                                 'component': 'worker',
                                 'tests': ('tests.test_machines_api.MachinesTests',),
                                 'nodes': ['installare.m1',
                                           'installare.m2',
                                           'R1.2.p2.m1',
                                           'R1.3.p2.m1',
                                           'worker.p3.m2'],
                                 'scope': 'Registrazione su fixture, probe simulati e impostazioni '
                                          'proprietario; connessione reale esclusa.'},
 'model_selection_regression': {'title': 'Modelli: selezione persistente e pubblicazione atomica',
                                'component': 'worker',
                                'tests': ('tests.test_runtime_models.RuntimeModelTests',),
                                'nodes': ['assegnare.m1'],
                                'scope': 'Configurazione temporanea dei ruoli e override; esecuzione sul '
                                         'worker esclusa.'},
 'provider_diagnostics_regression': {'title': 'Errori provider: diagnosi e dati sicuri',
                                     'component': 'cora',
                                     'tests': ('tests.test_provider_errors.ProviderErrorTests',),
                                     'nodes': ['T10.p2', 'T10.p2.m1', 'T12.p4.m2'],
                                     'scope': 'Classificazione e propagazione di errori campione; guasti '
                                              'reali e UI browser esclusi.'},
 'adaptive_context_regression': {'title': 'Contesto: recupero e budget progressivo',
                                 'component': 'cora',
                                 'tests': ('tests.test_adaptive_context.AdaptiveContextTests',
                                           'tests.test_programmer_context.ContextTests'),
                                 'nodes': ['T6.p2', 'T6.p2.m1', 'T6.p2.m2', 'A2.p3.m1'],
                                 'scope': 'Messaggi e modello simulati; preservazione intenzione, espansione '
                                          'catalogo e cancellazione. Qualità IA reale esclusa.'},
 'library_monitor_regression': {'title': 'Libreria: modifiche e scansioni fallite',
                                'component': 'files',
                                'tests': ('tests.test_library_monitor.LibraryMonitorTests',),
                                'nodes': ['B2.p3.m1'],
                                'scope': 'Directory temporanee, rilevamento variazioni e conservazione '
                                         'snapshot dopo errori. Mount reali esclusi.'},
 'audio_engine_regression': {'title': 'Audio: modelli offline e cancellazione',
                             'component': 'audio',
                             'tests': ('tests.test_audio_deployment.AudioDeploymentTests',),
                             'nodes': ['R3.1.p2.m1', 'C3.p2.m1'],
                             'scope': 'Manifest e motore simulato; nessuna certificazione della trascrizione '
                                      'reale.'},
 'programmer_workspace_regression': {'title': 'Programmatore: file protetti e risultati verificabili',
                                     'component': 'cora',
                                     'tests': ('tests.test_programmer_agent.ProgrammerTests.test_filtered_snapshot_and_optimistic_write_leave_live_source_untouched',
                                               'tests.test_programmer_agent.ProgrammerTests.test_manual_editor_reads_full_file_and_rejects_stale_save',
                                               'tests.test_programmer_agent.ProgrammerTests.test_static_checks_do_not_execute_generated_code_and_detect_invalid_json',
                                               'tests.test_programmer_agent.ProgrammerTests.test_failed_check_supersedes_prior_success_for_identical_source',
                                               'tests.test_programmer_agent.ProgrammerTests.test_unavailable_checks_are_recorded_and_revoke_verified_state',
                                               'tests.test_programmer_agent.ProgrammerTests.test_tool_registration_requires_tests_and_all_skipped_is_not_success'),
                                     'nodes': ['G1.p2.m1', 'G1.p3', 'G1.p3.m1', 'G1.p3.m2'],
                                     'scope': 'Workspace temporanei, conflitti e invalidazione degli esiti; '
                                              'esecuzione di codice e rilascio reale esclusi.'},
 'programmer_graph_regression': {'title': 'Programmatore: grafo e provenienza repository',
                                 'component': 'cora',
                                 'tests': ('tests.test_programmer_agent.ProgrammerTests.test_graph_queries_preserve_provenance_and_signal_modified_snapshot',
                                           'tests.test_programmer_agent.ProgrammerTests.test_graphify_unresolved_imports_are_explicit_and_edges_remain_queryable'),
                                 'nodes': ['G1.p1', 'G1.p1.m1', 'G1.p1.m2'],
                                 'scope': 'Repository campione e grafo locale; analisi completa di '
                                          'repository produttive esclusa.'},
 'migration_contract_regression': {'title': 'Database: contratto migrazioni',
                                   'component': 'cora',
                                   'tests': ('tests.test_database_migration_contract.DatabaseMigrationContractTests',),
                                   'nodes': ['R2.1.p3.m1'],
                                   'scope': 'Immutabilità baseline e collocazione migrazioni; applicazione '
                                            'reale su PostgreSQL esclusa.'}}


# T11 owns the inventory itself: this suite proves that every repository unittest
# module is visible once and that new live E2E checks stay inside the owner-
# selected problems.xlsx scope. It does not execute the entire repository suite.
SUITES["test_inventory_regression"] = {
    "title": "T11: inventario completo test e perimetro nuovi E2E",
    "component": "cora",
    "tests": ("tests.test_test_inventory.TestInventoryTests",),
    "nodes": [
        "T11.p1", "T11.p1.m1", "T11.p1.m2",
        "T11.p2", "T11.p2.m1", "T11.p2.m2",
    ],
    "scope": (
        "Inventario statico di tutti i moduli unittest della repository, collegamenti "
        "al runner esistente e guardrail sui nuovi E2E; non esegue tutti i test e "
        "non certifica servizi reali."
    ),
}
