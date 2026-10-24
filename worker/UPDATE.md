# Aggiornare il bridge desktop per le conversazioni degli agenti

Il test «Prova inferenza» in Macchine usa /generate. Può riuscire anche con
un vecchio worker privo di /chat. La chat agenti richiede entrambi gli endpoint.

1. Sul desktop Windows, individua la cartella worker usata per avviare il
   container cora-desktop-worker. Conserva il file privato .env con il token
   esistente; non generare un nuovo token. Se hai personalizzato compose.yml,
   conserva una copia e applica le stesse personalizzazioni al file aggiornato.
2. Estrai questo ZIP e copia worker.py, Dockerfile e compose.yml nella cartella
   worker esistente, sostituendo i sorgenti. Lo ZIP non contiene né modifica .env.
3. Apri PowerShell in quella cartella ed esegui:

   ```powershell
   docker compose up -d --build --force-recreate worker
   curl.exe http://127.0.0.1:8765/health
   ```

   Nella risposta health deve comparire la capacità "agent-chat". Docker deve
   poter scaricare l'immagine base se non è già disponibile. Mantieni Ollama
   Windows e Tailscale Serve configurati come prima.
4. In Cora, Architettura → Cora centrale: seleziona il desktop e il modello
   scelto in Macchine, poi Salva assegnazione. Se già salvata, premi Ricarica
   modelli: non serve salvare nuovamente. Premi Verifica modello con una chiamata.
5. Solo dopo l'esito positivo invia una nuova domanda in chat. Il nome riportato
   dal provider è verificabile nella scheda e in Attività. Cambiare uno specialista
   non cambia il modello di Cora centrale.

Il pacchetto proviene dalla versione Cora che lo serve; non include credenziali,
configurazioni private né modelli. La ricostruzione aggiorna solo il bridge,
non scarica nuovi pesi Ollama e non cambia il modello selezionato dal proprietario.
