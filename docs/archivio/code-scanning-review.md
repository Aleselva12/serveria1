# Revisione degli avvisi CodeQL allegati

Baseline esaminata: `65916a7ba47cc33925d0b6ef5e20799455c34925` (main dopo PR #24).
Le righe della tabella sono quelle delle liste ricevute, non quelle dopo la patch.
73 avvisi: 70 `Uncontrolled data used in path expression`, 3 `Information exposure through an exception`.
Gli allegati contengono titolo e posizione, non le tracce complete source-to-sink di CodeQL. La tabella traccia ogni avviso; non equivale a una conferma di chiusura da parte di GitHub.

## Risultati e correzioni

- I percorsi pubblici avevano già un filtro su `..`, percorsi assoluti e link: non si assume che ogni avviso fosse un exploit distinto. Il nuovo confinamento normalizza, controlla il confine con separatore (anche cartelle sorelle con prefisso uguale), rifiuta link e restituisce il percorso effettivamente verificato.
- Ogni ingresso mantiene i propri controlli: query per download/preview/search, body per cartelle e trasferimenti, form e filename per upload, righe DB per condivisioni, metadati del cestino per restore, metadati su disco per upload riprendibili. Sorgente e destinazione sono validate separatamente.
- Gli ID delle sessioni e del cestino accettano esattamente 32 cifre esadecimali; gli slot sono confinati alla propria area interna. La pulizia delle sessioni non legge metadati attraverso link simbolici. Schema e nomi salvati vengono validati di nuovo prima del riutilizzo. Le sessioni completate non ricevono altri blocchi.
- Le copie IA continuano a conservare un originale distinto, senza hard link all'originale; anche il percorso dell'originale restituito dall'upload viene risolto prima della copia.
- La stringa dell'eccezione DB raggiungeva salute, memoria e stato componenti. Ora l'origine restituisce un messaggio costante, senza password, host, SQL o percorsi. Le tre propagazioni sono coperte dalla stessa prova di regressione.

Non sono state disattivate regole, aggiunte soppressioni o archiviate segnalazioni. Serve una nuova analisi CodeQL per confermare la chiusura degli avvisi. Questi controlli non sono un isolamento da un processo esterno che modifichi contemporaneamente il NAS: il lock applicativo non controlla altri writer e non elimina tutte le race filesystem.

## Verifica deployment separata

Il fixture File Server usava la cartella predefinita degli originali dentro il sorgente: nel candidato Docker read-only non può crearla. Ora usa una cartella temporanea esplicita. Il fixture CI dell’updater stampa il log privato di build/test solo in caso di preparazione fallita, così ulteriori cause diventano diagnosticabili; il servizio di produzione non espone quel log. L’esito Docker resta da confermare in CI.

## Corrispondenza puntuale

| ID | Titolo | File e riga segnalata | Funzione o flusso esaminato | Correzione pertinente |
|---|---|---|---|---|
| #1 | Uncontrolled data used in path expression | `core/ia_library.py:38` | `copy_document` | sorgente risolta, destinazione e staging confinati; copia indipendente |
| #2 | Uncontrolled data used in path expression | `core/ia_library.py:40` | `copy_document` | sorgente risolta, destinazione e staging confinati; copia indipendente |
| #3 | Uncontrolled data used in path expression | `core/ia_library.py:51` | `copy_document` | sorgente risolta, destinazione e staging confinati; copia indipendente |
| #4 | Uncontrolled data used in path expression | `core/ia_library.py:54` | `copy_document` | sorgente risolta, destinazione e staging confinati; copia indipendente |
| #5 | Uncontrolled data used in path expression | `core/server_files.py:88` | `resolve` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #6 | Uncontrolled data used in path expression | `core/server_files.py:90` | `resolve` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #7 | Uncontrolled data used in path expression | `core/server_files.py:96` | `exists` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #8 | Uncontrolled data used in path expression | `core/server_files.py:101` | `vacant` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #9 | Uncontrolled data used in path expression | `core/server_files.py:101` | `vacant` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #10 | Uncontrolled data used in path expression | `core/server_files.py:103` | `vacant` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #11 | Uncontrolled data used in path expression | `core/server_files.py:136` | `node` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #12 | Uncontrolled data used in path expression | `core/server_files.py:138` | `node` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #13 | Uncontrolled data used in path expression | `core/server_files.py:138` | `node` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #14 | Uncontrolled data used in path expression | `core/server_files.py:138` | `node` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #17 | Uncontrolled data used in path expression | `core/server_files.py:249` | `children` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #18 | Uncontrolled data used in path expression | `core/server_files.py:270` | `download` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #19 | Uncontrolled data used in path expression | `core/server_files.py:272` | `download` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #20 | Uncontrolled data used in path expression | `core/server_files.py:281` | `mkdir` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #24 | Uncontrolled data used in path expression | `core/server_files.py:306` | `transfer` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #28 | Uncontrolled data used in path expression | `core/server_files.py:312` | `transfer` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #29 | Uncontrolled data used in path expression | `core/server_files.py:312` | `transfer` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #30 | Uncontrolled data used in path expression | `core/server_files.py:313` | `transfer` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #31 | Uncontrolled data used in path expression | `core/server_files.py:315` | `transfer` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #32 | Uncontrolled data used in path expression | `core/server_files.py:319` | `transfer` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #33 | Uncontrolled data used in path expression | `core/server_files.py:319` | `transfer` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #34 | Uncontrolled data used in path expression | `core/server_files.py:321` | `transfer` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #35 | Uncontrolled data used in path expression | `core/server_files.py:322` | `transfer` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #36 | Uncontrolled data used in path expression | `core/server_files.py:326` | `transfer` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #37 | Uncontrolled data used in path expression | `core/server_files.py:326` | `transfer` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #38 | Uncontrolled data used in path expression | `core/server_files.py:331` | `transfer` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #39 | Uncontrolled data used in path expression | `core/server_files.py:348` | `trash` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #40 | Uncontrolled data used in path expression | `core/server_files.py:388` | `restore` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #41 | Uncontrolled data used in path expression | `core/server_files.py:388` | `restore` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #42 | Uncontrolled data used in path expression | `core/server_files.py:388` | `restore` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #47 | Information exposure through an exception | `api.py:146` | `health → database_status` | messaggio pubblico costante in database_status, verificato in tutti i consumatori |
| #49 | Uncontrolled data used in path expression | `core/server_files.py:305` | `transfer` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #50 | Uncontrolled data used in path expression | `core/server_files.py:184` | `upload_to` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #51 | Uncontrolled data used in path expression | `core/server_files.py:188` | `upload_to` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #52 | Uncontrolled data used in path expression | `core/server_files.py:309` | `transfer` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #53 | Uncontrolled data used in path expression | `core/server_files.py:309` | `transfer` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #54 | Uncontrolled data used in path expression | `core/server_files.py:309` | `transfer` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #55 | Uncontrolled data used in path expression | `core/server_files.py:400` | `restore` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #56 | Uncontrolled data used in path expression | `core/server_files.py:162` | `upload_to` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #57 | Uncontrolled data used in path expression | `core/server_files.py:303` | `transfer` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #58 | Uncontrolled data used in path expression | `core/server_files.py:303` | `transfer` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #59 | Uncontrolled data used in path expression | `core/server_files.py:392` | `restore` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #60 | Uncontrolled data used in path expression | `core/server_files.py:399` | `restore` | resolve/confined_path; contenimento distinto di sorgente, destinazione e cestino |
| #64 | Information exposure through an exception | `core/runtime_api.py:174` | `component_states → component_runtime_status → database_status` | messaggio pubblico costante in database_status, verificato in tutti i consumatori |
| #65 | Information exposure through an exception | `api.py:235` | `memory_status → memory_stats → database_status` | messaggio pubblico costante in database_status, verificato in tutti i consumatori |
| #66 | Uncontrolled data used in path expression | `core/file_extras.py:33` | `fingerprint` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #67 | Uncontrolled data used in path expression | `core/file_extras.py:48` | `preview` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #68 | Uncontrolled data used in path expression | `core/file_extras.py:54` | `preview` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #69 | Uncontrolled data used in path expression | `core/file_extras.py:67` | `preview` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #70 | Uncontrolled data used in path expression | `core/file_extras.py:71` | `preview` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #71 | Uncontrolled data used in path expression | `core/file_extras.py:74` | `preview` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #72 | Uncontrolled data used in path expression | `core/file_extras.py:82` | `search` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #73 | Uncontrolled data used in path expression | `core/file_extras.py:112` | `create_share` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #74 | Uncontrolled data used in path expression | `core/file_extras.py:161` | `session` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #75 | Uncontrolled data used in path expression | `core/file_extras.py:161` | `session` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #76 | Uncontrolled data used in path expression | `core/file_extras.py:161` | `session` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #77 | Uncontrolled data used in path expression | `core/file_extras.py:163` | `session` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #78 | Uncontrolled data used in path expression | `core/file_extras.py:167` | `session` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #79 | Uncontrolled data used in path expression | `core/file_extras.py:179` | `start_upload` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #80 | Uncontrolled data used in path expression | `core/file_extras.py:207` | `upload_status` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #81 | Uncontrolled data used in path expression | `core/file_extras.py:216` | `upload_chunk` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #82 | Uncontrolled data used in path expression | `core/file_extras.py:219` | `upload_chunk` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #83 | Uncontrolled data used in path expression | `core/file_extras.py:233` | `complete_upload` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #84 | Uncontrolled data used in path expression | `core/file_extras.py:234` | `complete_upload` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #85 | Uncontrolled data used in path expression | `core/file_extras.py:238` | `complete_upload` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #86 | Uncontrolled data used in path expression | `core/file_extras.py:239` | `complete_upload` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #87 | Uncontrolled data used in path expression | `core/file_extras.py:247` | `complete_upload` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #88 | Uncontrolled data used in path expression | `core/file_extras.py:248` | `complete_upload` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
| #89 | Uncontrolled data used in path expression | `core/file_extras.py:255` | `abandon_upload` | resolve/confined_path per contenuti; slot confinato e UploadMetadata per sessioni |
