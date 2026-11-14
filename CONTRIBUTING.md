# Contribuire a Cora Lab

Grazie per l'interesse! Cora è un progetto open source self-hosted e
private-first in sviluppo attivo. Contributi, segnalazioni e revisioni sono
benvenuti, ma non è garantita l'accettazione di ogni modifica.

## Prima di iniziare

- Leggi il [README](README.md) e la [licenza MIT](LICENSE).
- Per orientarti nell'architettura, parti da
  [docs/AGENT_CONTEXT.md](docs/AGENT_CONTEXT.md) e dalla documentazione
  specialistica linkata nel README.
- Controlla gli issue e le pull request già aperti per evitare duplicati.
- Per modifiche architetturali o interventi estesi, apri prima un issue che
  descriva il problema, i vincoli e la soluzione proposta.

## Tipi di contributo

- Bug riproducibili, con passaggi, comportamento atteso e osservato.
- Test automatici e miglioramenti alla robustezza dei componenti.
- Documentazione, guide di avvio e correzioni di ambiguità.
- Migliorie circoscritte a interfaccia, accessibilità e usabilità.
- Ottimizzazioni misurate per esecuzione e modelli locali.

## Sviluppo e verifica

La procedura locale documentata è nel [README](README.md):
configura un ambiente di sviluppo separato dal server di produzione usando
`.env.example` (senza pubblicare la tua configurazione locale).

Backend:

```sh
python -m pip install -r requirements-core.txt
python -m unittest discover -s tests -v
```

Frontend:

```sh
cd frontend
npm ci
npm test
npm run build
```

Non eseguire test di database su dati di produzione. Alcune verifiche
richiedono servizi esterni e non sono necessariamente riproducibili in locale.
Un test CI riuscito non dimostra che un server specifico funzioni correttamente.

## Pull request

1. Crea un branch dal `main` aggiornato.
2. Mantieni le modifiche piccole e focalizzate; evita refactor non correlati.
3. Aggiungi o aggiorna i test quando modifichi un comportamento.
4. Spiega motivazione, file interessati, verifiche eseguite e limiti rimasti.
5. Evita modifiche distruttive a database, configurazione di produzione,
   updater e procedure di deploy senza analisi di compatibilità e rollback.
6. Attendi la revisione del maintainer prima del merge.

## Sicurezza e privacy

**Non allegare mai** token OAuth, password, chiavi API, file `deploy.env`,
`.env` reali, chiavi private, backup, log con credenziali, dati di clienti,
file personali o dettagli di infrastruttura privata.

Per una potenziale vulnerabilità, **non aprire un issue pubblico contenente
istruzioni di sfruttamento o segreti**. Contatta il maintainer tramite i
canali riservati disponibili sul suo profilo GitHub o la funzione privata
di segnalazione vulnerabilità di GitHub, se abilitata. Non pubblicare
credenziali nemmeno come prova del problema.

## Licenza dei contributi

Contribuendo, accetti che il tuo contributo sia distribuito nell'ambito
della [licenza MIT](LICENSE) del progetto e dichiari di avere il diritto
di fornirlo. Non includere codice o asset di terzi senza una licenza
compatibile e le attribuzioni necessarie.
