# Migrazioni

`database/schema.sql` Ã¨ il baseline `0001_baseline`. Dall'introduzione del
registro `cora_schema_migrations` il baseline e le migrazioni applicate sono
immutabili: per cambiare schema aggiungere `0002_nome.sql`, poi `0003_nome.sql`.
I file sono ordinati e applicati con checksum SHA-256 in un'unica transazione
protetta da advisory lock PostgreSQL. Un file modificato o una versione presente
nel DB ma assente nel codice interrompe l'avvio.

Sul database esistente la prima installazione riesegue il baseline idempotente
e lo registra. Non ricostruisce eventi storici nÃ© ripete azioni applicative.
Successivamente lo schema giÃ  applicato viene saltato.

Una migrazione deve contenere soltanto SQL transazionale; non usare `COMMIT`,
`VACUUM` o `CREATE INDEX CONCURRENTLY`. Le modifiche dei dati devono essere
esplicite e revisionabili. Prima di aggiornare creare e verificare un backup.
Un downgrade del codice non Ã¨ un downgrade del DB: ripristinare il backup su
un target vuoto con la versione corrispondente.

## Inventario alla base dell’audit

| Versione | Contenuto |
| --- | --- |
| 0001 | Baseline in `../schema.sql` |
| 0002 | Metadati allegati chat, registrazioni audio e condivisioni file |
| 0003 | Storico consultazioni |
| 0004 | Sottoscrizioni notifiche push |
| 0005 | Progetti delle conversazioni |
| 0006 | Proposte di note commerciali Word |

L’esecutore è `core/database.py` dalla radice del repository. Normalizza CRLF in LF prima del checksum; rifiuta versioni duplicate, inserimenti precedenti all’ultima applicata, checksum cambiati e schema più nuovo del codice. Si attiva alla prima connessione che richiede lo schema, non è un comando di deploy separato.

Il test di contratto è `tests/test_database_migration_contract.py`; i test PostgreSQL e il trial updater richiedono istanze sacrificabili. Nessuna migrazione sul Debian reale eseguita nell’[audit del 25 ottobre](../../docs/README_AUDIT_20261025.md).
