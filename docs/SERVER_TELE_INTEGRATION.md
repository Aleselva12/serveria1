# Magazzino Tele — gestionale web autonomo

Stato: primo prototipo integrato nella PR; nessun deploy sul Debian, nessuna migrazione di dati certificata.

## Requisiti definitivi

- L'utente principale è la zia del proprietario, da PC remoto membro della tailnet.
- Aprirà un'interfaccia **web** separata: `http://<indirizzo-tailscale-server>:8082`.
- Non si usa Tkinter sul client. Non si integra con frontend, API, PostgreSQL, tool, agenti, permission engine o IA di Cora.
- Nessuna schermata di login applicativo richiesta. L'assenza di login rende l'accesso alla porta web possibile a **qualsiasi dispositivo effettivamente autorizzato dalle policy Tailscale**, non automaticamente soltanto alla zia. Restrizioni ACL/grants e assenza di port forwarding sono indispensabili.
- Il database MySQL richiede comunque credenziali **tecniche interne**; non sono chieste alla zia e non vanno eliminate.
- Codice in `apps/magazzino-tele/web/`, stack in `deploy/integrations/server-tele.mysql.yml`, database in volume Docker `server_tele_mysql` separato. Nel server finale suggerita cartella autonoma `/srv/apps/magazzino-tele/`.

## Ricostruzione dalla repository storica

Fonte: `Aleselva12/magazzino-tele` su `master`, `backend/crud.py`, `backend/inventario_crud.py`, `interfaccia/pages/ordini.py` e `backup/2025-08-17_18-16-33/backup_info.txt`.

| Tabelle storiche | Utilizzo osservato |
|---|---|
| `customers` | Anagrafica clienti/fornitori; ricerca per codice e descrizione; ordine collegato al cliente |
| `schema colori semplice` | Elenco di nomi colori |
| `prodotti_completi` | Catalogo combinazioni modello-colore; contiene codici/nome modello e codici/nome colore; codice prodotto da combinazione |
| `modelli` | Catalogo modelli, ricerca per codice e nome |
| `magazzino` | Giacenze aggregate per `codiceprodotto` |
| `ordini` | Testata ordine, codice cliente, data, evasione |
| `ordiniprodotti` | Prodotti e quantità appartenenti all'ordine |

Colori: l'elenco filtrabile usa principalmente `prodotti_completi` e talvolta `schema colori semplice`; **non** creare colori dimostrativi come dati reali. Il programma storico contiene una lista demo quando manca il database: non va usata nella migrazione.

Clienti: `customers` è la fonte per ricerca/autocomplete; il codice mostra sia riferimenti a `codice`, sia `ï»¿codiceunivoco`, sia `codice_cliente`, `ragione_sociale` e `CoF` (C/F: cliente/fornitore). Il nome effettivo delle colonne va confermato con `SHOW COLUMNS` sul dump in uso, senza alterarlo per ipotesi.

Il backup storico del 17/08/2025 elenca tutte e sette le tabelle. **La sola lista prova l'esistenza delle tabelle in quel momento, non la disponibilità attuale dei record.** La lettura del file SQL associato attraverso il connettore non ha restituito contenuti: non possiamo affermare che l'anagrafica clienti, colori, prodotti e ordini sia stata effettivamente copiata. Occorre il dump MySQL effettivo o gli Excel originali (se presenti e coerenti).

## Prototipo interfaccia

Il nuovo frontend Flask offre sette schede: Clienti, Colori, Prodotti, Modelli, Ordini, Righe ordine, Magazzino. Elenca fino a 50 righe per pagina, ricerca nelle colonne, creazione e modifica generica, eliminazione con conferma, con colonne lette da `information_schema`. Non modifica né crea automaticamente le tabelle; richiede un database già importato e una chiave primaria per modifica/cancellazione. Le relazioni tra entità non sono ancora accompagnate da flussi assistiti: **questa non è ancora la sostituzione completa dell'esperienza ordini Tkinter**.

Nota: senza login e con CRUD generico, ogni utente autorizzato sulla porta può modificare i dati. Limitare la porta Tailscale con ACL e controlli sulla rete; non pubblicarla nel router, nel reverse proxy pubblico né su `0.0.0.0`.

## Installazione prevista (non eseguita)

1. Ruotare e togliere dal codice le credenziali MySQL storiche che compaiono nella repository pubblica. La cronologia Git rimane un possibile vettore di divulgazione.
2. Creare un `.env` privato sul server con `SERVER_TELE_DB_PASSWORD`, `SERVER_TELE_ROOT_PASSWORD`, `SERVER_TELE_TAILSCALE_IP` reale; permessi stretti. Non mettere `.env` su GitHub.
3. Con il repo disponibile sul server: `docker compose -f deploy/integrations/server-tele.mysql.yml config` (verificare porte e volumi). Quindi, dopo controllo, `docker compose -f deploy/integrations/server-tele.mysql.yml up -d --build`. La porta web HTTP 8082 sarà associata al solo IP Tailscale del server. Non esiste alcuna porta MySQL esposta sul sistema host.
4. Prima di migrare, fare dump del MySQL originario e verificare numero di righe, charset, valori, PK/FK, indice, tabelle, clienti e colori. Importare su database isolato e confrontare esattamente gli elementi del catalogo. Nessun seed fittizio.
5. Verificare con la zia il percorso completo creazione ordine → scelta cliente → scelta modello e colore → quantità → salvataggio → ricerca → modifica → evasione. Aggiungere form guidati se richiesti per eguagliare il comportamento storico.
6. Separare backup MySQL, retention e restore dal sistema di backup Cora. Testare un restore isolato prima di trasferire l'uso quotidiano.
7. Testare funzionamento da PC della zia e riconnessione/reboot del server. Non considerare completata la messa in produzione prima di queste verifiche.

## Isolamento

Cora non monta i dati o il volume Tele, non dispone di credenziali Tele, non espone capability per la sua gestione e non lo controlla. Un eventuale futuro accesso tramite Programmatore richiederà una decisione esplicita distinta.

## Checkpoint

Il collaudo di Serveria/Cora è rinviato a stasera come concordato. Il collaudo operativo di Magazzino Tele avverrà separatamente, con lo schema e i dati effettivi.
