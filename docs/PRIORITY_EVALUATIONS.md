# Priorita: modello e lista condivisa

La valutazione usa un modello Ollama dedicato, configurato da
`CORA_ROADMAP_CLASSIFIER_MODEL` (default `qwen3:1.7b`). Non eredita il modello
assegnato al Supervisor. Aprire Architettura per vedere modello configurato,
origine della configurazione, disponibilita e modello effettivamente dichiarato
nell'ultima valutazione salvata. Sono mostrati anche data, numero massimo di
obiettivi e pesi del punteggio.

Il modello propone sei valori da 0 a 5. Il server ricalcola il punteggio 0-100 e
ordina per punteggio decrescente, poi ID a parita. La formula non e cambiata:
importanza e urgenza +4, dipendenze e impatto +3, sforzo -2, rischio -1, con
normalizzazione dell'intervallo possibile. Punteggi e confidenza sono indicativi.

La selezione resta limitata a 8 obiettivi per ogni richiesta; non si presenta
questo confronto come una valutazione automatica di tutte le 45 stelle.
L'inferenza parte soltanto da Valuta priorita nella mappa. Aprire Home o
Architettura legge lo storico o il catalogo, senza avviare inferenze.

Le valutazioni valide sono salvate nel database dalla migrazione 0010. La Home,
sia desktop sia mobile, mostra i primi 5 punti dell'ultimo risultato salvato; gli
altri compaiono in un elenco espandibile chiuso per impostazione predefinita.
La mappa recupera lo stesso risultato al ricaricamento. La Home mostra la data,
il modello richiesto e quello riportato da Ollama, oltre alla confidenza.

Una risposta da un modello diverso o una risposta incompleta viene rifiutata.
Se il provider omette il modello effettivo, il risultato e dichiarato non
confermato: il nome richiesto non viene spacciato per prova del modello usato.
Un errore di valutazione non sostituisce l'ultima lista valida. Se il database non
puo salvare, il risultato corrente rimane visibile con avviso e la Home mantiene
l'ultima valutazione disponibile. Nessun testo completo dei criteri aggiuntivi e
salvato separatamente; vengono salvati titoli, punteggi, spiegazioni e metadati.

Le vecchie valutazioni che vivevano soltanto nello stato del browser non sono
recuperabili: dopo il primo rilascio occorre una nuova valutazione per popolare
la Home. I risultati non modificano i nodi della mappa, i colori dei collaudi o
le priorita deliberate dal proprietario.

API: GET /api/v1/roadmap/classifier/status per configurazione e ultima prova del
modello; GET /api/v1/roadmap/classifier/latest per l'ultima lista; POST sul
percorso esistente /api/v1/roadmap/classifier/preview per valutare e salvare.
Il normale aggiornamento applica la migrazione; nessuna copia manuale di file.
