# Portali web dei club

Il portale Superba è isolato in `superba_web/`. I cloni generati da `ClonaMigrazione.py` sono in `piercrew_web/` e `tigullio_web/`. Ogni cartella contiene frontend React, API FastAPI, logo, tema, configurazione Vercel e istruzioni. Lo script non si collega a MongoDB e non pubblica automaticamente.

Deploy attuali: Superba `https://superbaweb.vercel.app/`, PierCrew `https://piercrewweb.vercel.app/`, Tigullio `https://tigullioweb.vercel.app/`. I tre progetti Vercel hanno root separate. PierCrew e Tigullio usano credenziali MongoDB condivise con Superba per i cluster, ma collezioni distinte definite in ciascun `backend/store.py`. Le rispettive variabili `<CLUB>_WRITE_ENABLED=true` autorizzano salvataggi solo attraverso i controlli di ruolo dell'app. I quattro link `LEGACY_*_URL` per clone puntano agli URL verificati del rispettivo vecchio hub Streamlit.

Superba è la sorgente di sviluppo. Dopo aver verificato un miglioramento in Superba, per portarlo ai cloni senza ricrearli eseguire:

```powershell
superba_web\.venv\Scripts\python.exe ClonaMigrazione.py sync piercrew
superba_web\.venv\Scripts\python.exe ClonaMigrazione.py sync tigullio
# oppure entrambi
superba_web\.venv\Scripts\python.exe ClonaMigrazione.py sync all
```

`sync` aggiorna e aggiunge i file comuni, senza eliminare file nei cloni. Conserva `backend/store.py`, `src/theme.css`, logo, `.env.example`, README, dati di deploy locali e dipendenze. La clonazione iniziale (`ClonaMigrazione.py piercrew`, `tigullio` oppure `all`) continua a fermarsi se la destinazione esiste. La fonte dei nomi delle collezioni è coerente con il vecchio `clona_club.py`: `piercrew_players`/`PierCrew`/`PierCrewSvizzero` e `tigullio_players`/`Tigullio`/`TigullioSvizzero`.

Per ogni nuovo progetto Vercel impostare come root la propria cartella e configurare `MONGO_URI`, `MONGO_URI_AUTH`, `MONGO_URI_TOURNEMENTS`, `<CLUB>_APP_ORIGIN` e `<CLUB>_WRITE_ENABLED` come indicato nel suo `.env.example`. Attivare le scritture solo dopo aver verificato connessione, ruoli e collezioni corrette. I link alle vecchie app sono variabili `LEGACY_*_URL` opzionali: i cloni non ereditano gli URL Superba. Ogni portale richiede un progetto Vercel e un dominio distinti.

I file legacy `.streamlit/secrets.toml` e `pathWebApp e secure .txt` non devono essere pubblicati. Sono stati rimossi dall'indice Git corrente, ma possono restare nella cronologia dei commit precedenti: gli URI eventualmente presenti in quella cronologia vanno sostituiti nei servizi interessati.
