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


# Final T11 refinement: prove that health evidence keeps its release identity and
# cannot turn stale/synthetic/interrupted observations into a live green state.
# All checks below already existed; this only wires selected deterministic tests
# into the canonical one-shot runner.
SUITES["evidence_provenance_regression"] = {
    "title": "T11: provenienza rilascio, persistenza e affidabilità evidenze",
    "component": "cora",
    "tests": (
        "tests.test_archive_release_identity.ArchiveRevisionTests.test_valid_archive_is_used_when_build_marker_is_empty",
        "tests.test_archive_release_identity.ArchiveRevisionTests.test_checkout_placeholder_cannot_certify_a_version",
        "tests.test_archive_release_identity.ArchiveRevisionTests.test_build_marker_remains_authoritative",
        "tests.test_verification_usage.UsageEvidenceTests.test_catalog_checks_have_runners_and_explicit_scope",
        "tests.test_verification_usage.UsageEvidenceTests.test_synthetic_runs_cannot_publish_live_evidence_or_read_google",
        "tests.test_verification_usage.UsageEvidenceTests.test_runtime_evidence_survives_missing_fixture_without_forging_freshness",
        "tests.test_node_verification_api.NodeVerificationAPITests.test_reload_recovers_progress_without_starting_another_suite",
        "tests.test_node_verification_api.NodeVerificationAPITests.test_results_and_progress_are_recorded_after_every_check",
    ),
    "nodes": [
        "T11.p3", "T11.p3.m1", "T11.p3.m2",
        "T11.p4",
    ],
    "scope": (
        "Test già presenti e isolati: identità del commit installato, separazione "
        "tra evidenza sintetica e uso reale, persistenza del progresso e recupero "
        "dopo interruzione. Non esegue deploy, servizi esterni o nuovi E2E reali."
    ),
}


# Repository tests already passing in the API image, grouped by area so the
# one-shot runner reports them on the tree. Modules that skip without
# PostgreSQL/host (e.g. test_updater, test_runtime_postgres) stay repository-only;
# classes/methods that skip in the image are left out so a suite never reports "skipped".
SUITES['release_update_regression'] = {
    "title": 'Aggiornamenti: updater, rilascio e bridge',
    "component": 'cora',
    "tests": ('tests.test_update_once', 'tests.test_updater_self_update.DatabaseProbeTests', 'tests.test_updater_self_update.HelperShapeTests', 'tests.test_updater_self_update.StatusEndpointTests', 'tests.test_deployment', 'tests.test_home_updater_bridge', 'tests.test_terminal_updater', 'tests.test_worker_updater_env', 'tests.test_calendar_service_account_updater', 'tests.test_desktop_auth_update', 'tests.test_project_files', 'tests.test_requirement_locks',),
    "nodes": ['R5.2.p1', 'R5.2.p2'],
    "scope": 'Updater, rilascio, bridge e lock delle dipendenze su fixture; installazione reale sul Debian esclusa.',
}
SUITES['host_ops_regression'] = {
    "title": 'Host Debian: diagnostica e manutenzione',
    "component": 'cora',
    "tests": ('tests.test_host_diagnostics', 'tests.test_host_maintenance.BootstrapTests', 'tests.test_host_maintenance.LifecycleTests', 'tests.test_host_maintenance.PrerequisiteTests',),
    "nodes": ['R4.1.p1', 'R4.1.p2', 'R4.1.p3'],
    "scope": 'Diagnostica host e manutenzione updater simulate; host reale coperto da debian_host_e2e.',
}
SUITES['backend_lifecycle_regression'] = {
    "title": 'Backend: avvio, arresto ordinato ed errori DB',
    "component": 'cora',
    "tests": ('tests.test_shutdown_drain.ShutdownDrainTests.test_shutdown_waits_for_running_and_cancels_queued_work', 'tests.test_shutdown_drain.ShutdownDrainTests.test_terminal_worker_is_retained_and_awaited_during_final_database_write', 'tests.test_shutdown_drain.ShutdownDrainTests.test_lifespan_drains_late_and_queued_postprocessing_before_pool_close', 'tests.test_shutdown_drain.ShutdownDrainTests.test_cancellation_finalization_waits_for_stop_transition', 'tests.test_shutdown_drain.ShutdownDrainTests.test_postprocessing_can_restart_and_drains_after_a_failed_job', 'tests.test_audit_easy_fixes', 'tests.test_public_database_errors',),
    "nodes": ['R4.2.p2'],
    "scope": "Ciclo di vita dell'API, drenaggio dei lavori ed errori database non esposti; container reali esclusi.",
}
SUITES['backup_regression'] = {
    "title": 'Backup privati: creazione e cifratura',
    "component": 'cora',
    "tests": ('tests.test_private_backups.BackupTests.test_changed_mounts_fail_before_stopping_any_service', 'tests.test_private_backups.BackupTests.test_retention_does_not_count_or_remove_incomplete_corrupt_or_unrelated', 'tests.test_private_backups.BackupTests.test_dump_failure_restarts_pinned_images_and_never_prunes', 'tests.test_private_backups.BackupTests.test_private_root_rejects_backup_inside_git_checkout', 'tests.test_private_backups.BackupTests.test_failed_restart_keeps_recovery_marker_and_boot_recovers_exact_images', 'tests.test_private_backups.BackupTests.test_unapproved_or_wrong_state_mount_audit_is_rejected', 'tests.test_private_backups.BackupTests.test_restore_checks_archive_traversal_before_stopping_services',),
    "nodes": ['R5.1.p1'],
    "scope": 'Backup su cartelle temporanee; ripristino reale coperto da backup_restore.',
}
SUITES['managed_apps_regression'] = {
    "title": 'App esterne: allowlist, Nextcloud e collegamenti',
    "component": 'cora',
    "tests": ('tests.test_managed_apps', 'tests.test_nextcloud_aio', 'tests.test_monitoring',),
    "nodes": ['R5.2.p3', 'nextcloud.p4'],
    "scope": 'Allowlist e installazione simulate; servizi esterni reali esclusi.',
}
SUITES['chat_tools_regression'] = {
    "title": 'Chat: strumenti, allegati e grafo',
    "component": 'cora',
    "tests": ('tests.test_chat_tools', 'tests.test_chat_attachments', 'tests.test_graph_fastpath', 'tests.test_tool_definitions',),
    "nodes": ['A1.p2', 'T2.p3'],
    "scope": 'Strumenti e grafo con agente simulato; modello reale escluso.',
}
SUITES['chat_context_regression'] = {
    "title": 'Chat: contesto pagine e politica di generazione',
    "component": 'cora',
    "tests": ('tests.test_context_pages', 'tests.test_owner_context_pages', 'tests.test_generation_policy',),
    "nodes": ['A1.p1', 'T6.p1'],
    "scope": 'Selezione del contesto e budget di generazione su messaggi campione; qualità IA reale esclusa.',
}
SUITES['conversation_history_regression'] = {
    "title": 'Conversazioni: cronologia e organizzazione',
    "component": 'cora',
    "tests": ('tests.test_consultations.ConsultationTests', 'tests.test_workspace_organization',),
    "nodes": ['A2.p1', 'A2.p2'],
    "scope": 'Storico e rinomina/archiviazione su fixture; PostgreSQL produttivo escluso.',
}
SUITES['library_files_regression'] = {
    "title": 'Libreria e file server: accesso, ricerca e percorsi',
    "component": 'files',
    "tests": ('tests.test_library_preflight', 'tests.test_library_routing', 'tests.test_library_workspace', 'tests.test_server_files', 'tests.test_api_source_permissions',),
    "nodes": ['B2.p1', 'B2.p2', 'B1.p1', 'B1.p2'],
    "scope": 'Directory temporanee e permessi; mount e dischi reali esclusi.',
}
SUITES['documents_regression'] = {
    "title": 'Documenti: Word e note commerciali',
    "component": 'files',
    "tests": ('tests.test_word_files', 'tests.test_commercial_notes', 'tests.test_commercial_word',),
    "nodes": ['B3.p1', 'C2.p4'],
    "scope": 'DOCX generati su fixture; account e documenti reali esclusi.',
}
SUITES['calendar_auth_regression'] = {
    "title": 'Calendario: autorizzazioni Google',
    "component": 'calendar',
    "tests": ('tests.test_calendar.CalendarValidationTests', 'tests.test_google_calendar_service_account', 'tests.test_google_calendar_web_auth',),
    "nodes": ['C1b', 'C1.p6'],
    "scope": 'OAuth e service account simulati; calendario reale coperto da calendar_e2e.',
}
SUITES['audio_ui_regression'] = {
    "title": 'Audio: interfaccia di acquisizione',
    "component": 'audio',
    "tests": ('tests.test_audio_ui',),
    "nodes": ['C3.p1'],
    "scope": "Contratti dell'interfaccia audio; microfono e trascrizione reali esclusi.",
}
SUITES['models_config_regression'] = {
    "title": 'Modelli: configurazione, profili e prestazioni',
    "component": 'worker',
    "tests": ('tests.test_default_models', 'tests.test_model_configuration', 'tests.test_model_thinking', 'tests.test_ollama_tool_arguments', 'tests.test_performance_profile', 'tests.test_usability_latency',),
    "nodes": ['R3.1.p1', 'R3.2.p1', 'T8.p3'],
    "scope": 'Configurazione e risposte modello simulate; inferenza reale esclusa.',
}
SUITES['worker_chat_regression'] = {
    "title": 'Worker: chat remota',
    "component": 'worker',
    "tests": ('tests.test_worker_chat',),
    "nodes": ['assegnare'],
    "scope": 'Trasporto worker simulato; worker reale coperto da worker_e2e.',
}
SUITES['programmer_agent_regression'] = {
    "title": 'Programmatore: ciclo, router e recupero risposte',
    "component": 'cora',
    "tests": ('tests.test_programmer_loop_context', 'tests.test_programmer_response_recovery', 'tests.test_programmer_router',),
    "nodes": ['G1.p2'],
    "scope": 'Repository e modello simulati; modifiche reali escluse.',
}
SUITES['architecture_regression'] = {
    "title": 'Architettura: panoramica, runtime e confini',
    "component": 'cora',
    "tests": ('tests.test_architecture_overview', 'tests.test_architecture_runtime', 'tests.test_component_boundaries', 'tests.test_operational_capabilities',),
    "nodes": ['T12.p2', 'T10.p1'],
    "scope": 'Grafo compilato e confini dei componenti su fixture; servizi reali esclusi.',
}
SUITES['security_audit_regression'] = {
    "title": 'Sicurezza: proxy, login e accessi',
    "component": 'cora',
    "tests": ('tests.test_audit_closure',),
    "nodes": ['R6.1.p2', 'R6.2.p2'],
    "scope": 'Identità proxy, limiti login e trasporti simulati; rete reale esclusa.',
}
SUITES['roadmap_priority_regression'] = {
    "title": 'Roadmap: priorità e classificatore',
    "component": 'cora',
    "tests": ('tests.test_priority_checks', 'tests.test_priority_evaluations', 'tests.test_roadmap_classifier',),
    "nodes": ['T12.p1'],
    "scope": 'Valutazioni con provider simulato; modello locale reale escluso.',
}
SUITES['verification_runner_regression'] = {
    "title": "Collaudi: runner e suite dell'albero",
    "component": 'cora',
    "tests": ('tests.test_node_verification', 'tests.test_tree_verification_suites',),
    "nodes": ['T11.p2', 'T11.p4'],
    "scope": 'Runner dei collaudi e coerenza suite/nodi su fixture; esiti reali esclusi.',
}
