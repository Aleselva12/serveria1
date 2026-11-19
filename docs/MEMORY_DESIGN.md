# Memoria Cora — decisioni del 19 novembre 2026

Stato: progetto concordato, **non ancora implementato**. Questa tranche modifica
collaudi e roadmap, non il comportamento della memoria. Fonte delle decisioni:
conversazione con il proprietario del 19/11/2026.

## Biblioteca e rappresentazioni

Il registro letterale conserva evidenze originali: messaggi, richieste, risultati,
errori e conferme osservate. Una richiesta di azione non prova l'esito. Correzioni
e verifiche sono annotazioni successive. Chat, operation journal e domain events
esistono già, ma non costituiscono una biblioteca letterale unificata completa.
Contenuti sensibili, retention e confini di raccolta devono essere definiti prima
di estendere la registrazione; non è previsto copiare indiscriminatamente tutti
i dati del server.

Il registro rielaborato contiene resoconti leggibili, derivati e rigenerabili,
con riferimenti agli originali. Arriva dopo la base letterale. Gli episodi e le
sintesi chat attuali sono basi riutilizzabili, non il sistema completo deciso qui.

La memoria simbolica rappresenta entità, fatti, decisioni e relazioni tipizzate.
Ogni affermazione distingue dichiarazione, osservazione e deduzione; conserva
fonte, versione, ambito e validità temporale. Un documento e un grafo sono due
viste complementari, non fonti concorrenti.

La biblioteca presenta schede con titolo, descrizione breve, contenuto, fonti,
versioni e collegamenti. L'indice gerarchico dà un ingresso e le relazioni
consentono percorsi trasversali senza duplicare persone o progetti. PostgreSQL
resta autorevole; Markdown è vista/esportazione, non una seconda copia modificabile
indipendentemente. Ambiti: globale, azienda, progetto e attività.

## Navigazione e memorie brevi

Il Context Manager T6 dovrà permettere indice, ricerca, apertura scheda,
attraversamento dei collegamenti e lettura della fonte originale, con budget,
permessi, provenienza e informazioni mancanti espliciti. Le attuali context
pages, la selezione lessicale e il budget non realizzano già questo percorso.

Un piccolo nucleo di memorie brevi curate orienta le attività. Candidati iniziali
da inserire nella successiva implementazione, non caricati da questa modifica:

- uso prevalentemente remoto tramite Tailscale;
- obiettivi concreti, verificabili e utili al lavoro quotidiano;
- fatti verificati distinti da ipotesi e incertezze;
- implementazione separata dal collaudo finale;
- elaborazione riepiloghi Mail nella finestra 03:00–04:00 Europe/Rome.

Solo poche indicazioni universali restano sempre disponibili; le altre vengono
recuperate per ambito. Una memoria recuperata non concede permessi e il testo di
un documento non diventa automaticamente un'istruzione autorevole.

La "forza gravitazionale" è una sperimentazione successiva: pertinenza,
importanza e collegamenti possono influenzare l'ordinamento, mai dimostrare verità
o prevalere su una correzione esplicita. Formula, decadimento e criteri non sono
ancora approvati come comportamento operativo.

## Roadmap e criteri di chiusura

T7.p1–p4 descrivono i quattro archivi esistenti; T7.p5 resta Custode futuro.
T7.p6–p10 descrivono registro letterale, rielaborato, simbolico, biblioteca e
memorie brevi. T6 governa il recupero, senza duplicare questi archivi.

La prima implementazione dovrà dimostrare, su dati sintetici, il ciclo
salva → nuova conversazione/processo → ritrova → correggi → rileggi; isolamento
degli ambiti; navigazione fino alla fonte; gestione di conflitti e budget.
Un test dei contratti non certifica pertinenza semantica o inferenza reale.
