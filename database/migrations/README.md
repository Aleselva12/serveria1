# Migrazioni

`database/schema.sql` è il baseline `0001_baseline`. Dall'introduzione del
registro `cora_schema_migrations` il baseline e le migrazioni applicate sono
immutabili: per cambiare schema aggiungere `0002_nome.sql`, poi `0003_nome.sql`.
I file sono ordinati e applicati con checksum SHA-256 in un'unica transazione
protetta da advisory lock PostgreSQL. Un file modificato o una versione presente
nel DB ma assente nel codice interrompe l'avvio.

Sul database esistente la prima installazione riesegue il baseline idempotente
e lo registra. Non ricostruisce eventi storici né ripete azioni applicative.
Successivamente lo schema già applicato viene saltato.

Una migrazione deve contenere soltanto SQL transazionale; non usare `COMMIT`,
`VACUUM` o `CREATE INDEX CONCURRENTLY`. Le modifiche dei dati devono essere
esplicite e revisionabili. Prima di aggiornare creare e verificare un backup.
Un downgrade del codice non è un downgrade del DB: ripristinare il backup su
un target vuoto con la versione corrispondente.
