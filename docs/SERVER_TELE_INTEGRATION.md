# Magazzino Tele — servizio indipendente da Cora

Stato: progetto di installazione; nessun deploy sul server Debian.

## Requisiti operativi confermati

- Utente: una sola persona, la zia del proprietario, dal suo computer già connesso a Tailscale.
- Obiettivo: gestione quotidiana del magazzino sempre disponibile, anche quando il PC del proprietario è spento.
- Nessun collegamento a Cora: nessun tool, agente, accesso al database, endpoint o controllo IA.
- Interfaccia separata dalla web UI Serveria. **Opzione iniziale preferita:** riutilizzare Tkinter sul PC della zia, con MySQL che resta acceso sul Debian. Non serve riscrivere oggi l'interfaccia web.
- Codice Magazzino Tele in una cartella autonoma e database indipendente da Cora. Non usare `/state` di Cora e non mescolare dump/volumi dei due programmi.

## Disposizione raccomandata sul Debian

```text
/srv/apps/
  cora/                     # progetto Serveria; PostgreSQL e state Cora
  magazzino-tele/
    app/                    # checkout o copia revisionata del programma Tele
    compose.yml             # stack MySQL e futuri componenti Tele
    config/                 # file privati di configurazione, permessi stretti
    backups/                # backup MySQL Tele dedicati
```

Il percorso è una proposta, non è stato creato sul Debian. Nel repository `serveria1` la configurazione Tele rimane in `deploy/integrations/`; se si sceglie un unico repository per entrambi i sorgenti, includere il codice Tele in una directory `apps/magazzino-tele/`, con versionamento e build separati e un processo esplicito di sincronizzazione dalla repository originaria. Non importare automaticamente database, dump, credenziali o file locali nel Git pubblico.

## Collegamento del PC della zia

1. Installare l'applicazione Tkinter sul suo PC, non eseguire la GUI sul server headless.
2. Spostare la configurazione MySQL in un file locale non committato, con host = IP Tailscale stabile o nome MagicDNS del Debian e una porta dedicata.
3. Eseguire MySQL in Docker separato con `restart: unless-stopped`, volume persistente e healthcheck.
4. Per accesso diretto MySQL, pubblicare **solo** sull'indirizzo Tailscale del Debian usando l'override `server-tele.tailscale.yml`; non esporre `0.0.0.0` o il router. Limitare inoltre in Tailscale ACL/grants la porta esclusivamente al dispositivo autorizzato della zia e ai dispositivi amministrativi strettamente necessari. Verificare le regole effettive: Docker può interagire con le regole del firewall host.
5. Credenze MySQL personali dell'app, a privilegi minimi; non usare root. Sul PC conservare le credenziali in configurazione protetta, evitando log e stampe debug.
6. Impostare servizio Docker e Tailscale per il riavvio automatico; verificare connessione dopo reboot, guasto rete, PC spento e riconnessione.
7. Evitare di inserire il servizio in `compose.yml` Cora, nel Component Registry o nel tool catalog. Il solo isolamento di Docker non costituisce controllo di accesso.
8. Per modificare l'app in futuro, lavorare su branch e rilasci separati; Cora non acquisisce alcuna autorizzazione implicita solo perché condivide l'hardware.

**Nota di sicurezza:** il client desktop parlerà a un servizio DB remoto. È una soluzione semplice su rete privata ma meno isolata di una futura API autenticata. Verificare configurazione TLS del DB/connessione e Tailscale, restrizioni MySQL, permessi e regole ACL prima dell'uso regolare.

## Rischi attuali da risolvere prima della messa online

- La repository pubblica `Aleselva12/magazzino-tele` include riferimenti a credenziali MySQL in script diagnostici/test. Ruotare le credenziali e spostarle fuori dal codice. Una cancellazione dal file più recente non rimuove una credenziale già divulgata dalla cronologia Git.
- Il progetto attuale usa Tkinter e MySQL: nessuna GUI web è stata costruita o promessa per questa fase.
- Il backup privato Cora **non copre** il database Tele. Realizzare dump periodici MySQL consistenti, conservazione separata, copia fuori dal medesimo disco quando possibile e prova di ripristino su volume vuoto.
- Prima di importare il database della zia: conservare un dump originale, verificare schema/charset, integrità e conteggi e testare import su database vuoto.
- I dati possono essere meno critici per l'azienda, ma una perdita impedirebbe il lavoro quotidiano. Non sostituire il gestionale attivo finché connessione e restore non funzionano.

## Sequenza di rilascio

1. Isolare i sorgenti Magazzino Tele dal progetto Cora; rimuovere password dal codice e preparare configurazione client.
2. Validare configurazione MySQL separata e client su un ambiente di prova, senza importare dati reali.
3. Installare sul Debian, con bind Tailscale e ACL, e importare solo dopo il backup della sorgente.
4. Aggiornare il client sul PC della zia; testare visualizzazione, inserimento, modifica, eliminazione e ricerche con dati di prova.
5. Verificare persistenza, riavvio automatico, backup e restore prima dell'utilizzo definitivo.

## Stato checkpoint

- Fast-path Supervisor e rimozione prompt obsoleto: modifiche proposte nella stessa PR, in attesa dei controlli.
- Backup Cora: infrastruttura già presente ma attivazione host non attestata.
- Collaudo complessivo Serveria: rinviato al checkpoint finale di stasera; installazione Magazzino Tele è attività separata.
