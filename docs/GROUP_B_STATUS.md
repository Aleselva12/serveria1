# Gruppo B — Orchestrazione interna del sistema

Stato verificato sul codice corrente. Questo documento separa ciò che è già
implementato da ciò che è parziale o richiede una decisione architetturale.

## B1 — Stato e comunicazione interna

**Implementato**
- lifecycle persistente di root/child run in PostgreSQL;
- state machine esplicita in `core.run_states`;
- `TaskEnvelope`, `ComponentResult`, `ComponentEvent`;
- Component Bus tipizzato in-process;
- Event Bus live con replay limitato;
- domain events transazionali;
- cancellazione cooperativa.

**Consolidato ora**
- manifest unico di ownership in `core.system_coordinator`;
- endpoint read-only `GET /api/v1/runtime/coordinator`;
- vista sintetica in Attività.

**Da decidere**
- rapporto definitivo fra `waiting_approval` del protocollo e
  `awaiting_approval` del lifecycle;
- eventuale trasporto distribuito futuro del Component Bus/Event Bus.

## B2 — Contesto e memoria operativa

**Implementato**
- context pages deterministiche;
- context budget e compattazione;
- preload task-scoped;
- memoria persistente, episodica e working memory;
- owner/system context;
- embedding/background processing.

**Parziale**
- il Context Manager globale non esiste ancora come contratto unico;
- il Context Manager del Programmatore è sperimentale e opt-in.

**Da decidere**
- registro letterale vs registro rielaborato;
- contratto input/output del Context Manager;
- politica di espansione progressiva e limiti;
- quale componente può richiedere altro contesto.

## B3 — Controllo e sicurezza

**Implementato**
- permission engine deterministico;
- AUTO / CONFIRM / BLOCKED;
- capability contracts;
- generic approvals persistenti;
- operation journal;
- protezione dagli effetti incerti.

**Da decidere**
- politica completa dei permessi;
- regole per nodi/worker;
- quali azioni possono diventare automatiche;
- relazione tra approval, task sospeso e successiva ripresa.

## B4 — Risorse e scheduling

**Implementato**
- coda runtime limitata;
- un singolo slot di esecuzione modello locale;
- inventario macchine;
- worker remoti;
- ON/OFF manuale;
- selezione manuale modello;
- binding agente → macchina/modello.

**Mancante intenzionalmente**
- scheduler automatico multi-worker;
- allocazione automatica GPU/RAM;
- migrazione automatica dei task tra nodi;
- wake/sleep automatico delle macchine.

**Decisione corrente**
La scelta manuale resta autorevole finché non viene progettata la policy risorse.

## B5 — Osservabilità e diagnostica

**Implementato**
- trace modello/tool/nodi;
- timing e first token;
- eventi critici persistenti;
- diagnostic archive best-effort PostgreSQL;
- parent/child run;
- operation journal;
- pagina Attività;
- health/stato componenti.

**Consolidato ora**
- Attività mostra lo stato sintetico del System Coordinator e la validità
  dell'ownership.

**Consolidato ora**
- Attività mostra anche i tempi principali del run selezionato, ordinati per durata, per individuare più rapidamente i colli di bottiglia.

**Possibili miglioramenti autonomi futuri**
- vista temporale completa per run;
- aggregazione storica dei tempi per componente;
- evidenziazione automatica dei colli di bottiglia ricorrenti.

## B6 — Affidabilità e recovery

**Implementato**
- timeout;
- cancellazione;
- process interruption recovery;
- `DurabilityLost`;
- `EffectUncertain`;
- operazioni write/delegate interrotte marcate uncertain;
- revisione manuale degli effetti incerti;
- retry metadata nei capability contracts.

**Parziale**
- recovery identifica il problema ma non riprende automaticamente il piano;
- non esiste ancora una policy globale di retry/replan;
- non esiste una coda persistente general-purpose per task lunghi riprendibili.

**Da decidere**
- matrice idempotenza/retry;
- criteri di ripresa dopo restart;
- task background e coda persistente;
- quando fallire, attendere, ritentare o chiedere intervento utente.

## Larva-system

La Larva-system appartiene al Gruppo B.

**Implementato ora — v0 observer-only**
- componente deterministico `core.system_larva`;
- legge esclusivamente lo snapshot del Coordinator;
- segnala ownership/permessi invalidi, runtime chiuso e problemi oggettivi della diagnostica;
- stato nominal / warning / critical;
- nessuna azione, retry, modifica permessi o scheduling.

**Da decidere prima di renderla attiva**
- frequenza autonoma;
- soglie non binarie;
- escalation;
- azioni consentite;
- comportamento quando la diagnostica stessa è degradata;
- eventuale rete neurale successiva.

## Principio di costruzione

Il Gruppo B deve restare prevalentemente deterministico. I modelli possono
osservare, classificare o suggerire; non devono diventare fonti autorevoli di
stato, permessi o risultati di effetti esterni.


## Collegamenti operativi completati

### Capability Registry operativo
È disponibile `GET /api/v1/runtime/capabilities`. La vista deriva dai contratti
eseguibili reali e riporta componente, input richiesti, effect/retry, permessi,
stato runtime, modello/macchina e disponibilità corrente. Non è una seconda
fonte di verità.

### Runtime / Component Bus
Le capability invocate tramite gli adapter agentici passano ora dal
`ComponentBus` usando `TaskEnvelope` e producono `ComponentResult`.
Il confine reale di esecuzione resta `execute_capability()`, che mantiene
validazione, permessi, approval e operation journal.

### Decisioni standard
Gli esiti tecnici vengono ridotti al vocabolario:
- complete
- retry_safe
- needs_replan
- needs_approval
- resource_unavailable
- effect_uncertain
- cancelled
- fatal

`effect_uncertain` ha precedenza su un eventuale esito nominale del tool.

### Attività
La pagina Attività mostra:
- Capability Registry operativo;
- stato live del Component Bus;
- ultima decisione per componente;
- decisioni orchestrative osservate nel run;
- eventi tecnici e operation journal già esistenti.
