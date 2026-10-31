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

**Possibili miglioramenti autonomi futuri**
- vista temporale più leggibile per run;
- aggregazione dei tempi per fase/componente;
- evidenziazione automatica dei colli di bottiglia.

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

La Larva-system appartiene al Gruppo B. Una prima versione può essere
deterministica e basata su health/eventi/soglie, senza rete neurale.

Non è ancora implementata come componente autonomo perché prima vanno decisi:
- segnali osservati;
- frequenza;
- soglie;
- azioni consentite;
- escalation;
- comportamento quando la diagnostica stessa è degradata.

## Principio di costruzione

Il Gruppo B deve restare prevalentemente deterministico. I modelli possono
osservare, classificare o suggerire; non devono diventare fonti autorevoli di
stato, permessi o risultati di effetti esterni.
