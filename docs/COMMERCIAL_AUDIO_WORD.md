# Agente Commerciale Word — contratto di implementazione

## Regole confermate

- File Word di proprietà dell'utente, con più clienti nello stesso documento.
- L'utente può modificare, rinominare e spostare i file senza usare Cora.
- Trascrizione Whisper **su comando**, invariata.
- Analisi commerciale **su comando**, distinta dalla trascrizione.
- Scrittura dell'agente: **esclusivamente aggiunta** di una nuova voce di conversazione nel blocco cliente individuato. Sono vietate cancellazioni, sostituzioni, riordini e correzioni del contenuto esistente.
- Ogni proposta di scrittura richiede conferma esplicita ed **è valida al massimo 24 ore**.
- Il Calendario Cora non è la cronologia commerciale Word: la creazione di eventi è una funzionalità separata che richiede approvazione.

## Fase 1 implementata in questa PR

`core/commercial_word.py` legge un DOCX in memoria, segmenta blocchi delimitati da separatori e ricerca intestazioni/interlocutori. `propose_append` crea **solo un candidato in memoria** collocando data e annotazione immediatamente prima del separatore seguente. Verifica gli hash del documento e confronta l'XML canonico di ogni paragrafo preesistente prima e dopo l'inserimento e dopo la serializzazione. Non salva file sul disco e non abilita alcuna capacità di scrittura per l'agente.

I casi non riconoscibili non devono essere indovinati. Le regole di segmentazione basate su trattini sono un primo approccio conservativo, da migliorare con casi rappresentativi prima dell'attivazione sul NAS.

## Fasi da completare PRIMA dell'uso sul NAS

1. **Sorgenti:** configurare un root esplicito delle cartelle commerciali; scanner ricorsivo solo lettura, indicizzazione incrementale e ricostruzione dopo spostamenti/rinominazioni, senza dipendere da percorsi salvati. Mai introdurre una ricerca indiscriminata nell'intero filesystem.
2. **Ricerca:** risoluzione del cliente fra molti file e regioni, risultati multipli in caso di ambiguità, selezione umana se il match non è univoco.
3. **Analisi:** pulsante manuale sulle trascrizioni, estrazione con modello locale di conversazione/data/cliente/accordi, mantenendo il riferimento alla registrazione originale. Non scrivere durante l'analisi.
4. **Proposte:** storage PostgreSQL persistente con `expires_at = created_at + interval '24 hours'`, approva/rifiuta, storico, ID registrazione/cliente/versione e testo esatto da aggiungere. Revisione esplicita di un'anteprima aggiornata se il file cambia durante l'attesa.
5. **Pubblicazione:** solo dopo approvazione, ritrovare il blocco nel file attuale; eseguire backup persistente, validare il candidato append-only, scrivere con sostituzione atomica senza perdere modifiche concorrenti. Se file spostato o cambiato, ricalcolare e richiedere **nuova approvazione**, non applicare la proposta vecchia.
6. **Collaudi:** test sui Word rappresentativi in copie isolate; nessun file cliente originale deve essere archiviato in GitHub.

## Limiti dichiarati

Il modulo implementato non è ancora un Agente Commerciale operativo e **non è collegato alle API Audio**. Un DOCX può contenere elementi non rappresentati da semplici paragrafi (tabelle, forme, revisioni Word); richiedere un controllo documentale completo prima di pubblicare automaticamente anche modifiche solo additive.
