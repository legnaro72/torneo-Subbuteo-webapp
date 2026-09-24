# Portale Superba

Portale React/Vite con API FastAPI per il **torneo all’italiana**, le **fasi finali**, lo **svizzero** e la **gestione club**. Usa gli utenti e i documenti MongoDB del mondo Superba. Le app classiche rimangono disponibili tramite token `auth_handoff` monouso, già supportato da `shared/auth/session_manager.py`.

## Cosa è disponibile

- Login degli utenti esistenti, attivazione iniziale con password di sistema, ospite in sola lettura. Sessione server in MongoDB e cookie `HttpOnly`.
- Hub e archivio; creazione con giocatori registrati e ospiti, modifica di squadra e potenziale, gironi automatici o manuali (fino a 8), andata o andata e ritorno e anteprima del calendario.
- Calendario con tre formati dei nomi e tre viste degli incontri (compact, premium, standard); navigazione per giornata; filtri richiudibili per stato, andata/ritorno, giocatore e girone; modifica dei risultati anche dalle partite filtrate, classifica e ritiro multiplo.
- Viste degli incontri ottimizzate per smartphone e selezione delle giornate con transizioni leggere. Con un solo girone la UI e il PDF mostrano direttamente giornata e classifica, senza «Girone 1». I tornei hanno link diretti `/torneo/italiana/Nome`, `/torneo/finali/Nome` e `/torneo/svizzero/Nome`; è accettata anche la forma `/?tipo=...&torneo=...`. Il link richiede l’accesso al portale.
- Fasi finali da preliminari completati: classifica complessiva, qualificati, tabellone a eliminazione diretta o gironi, assegnazione manuale o automatica, andata/ritorno, risultati, avanzamento, palmarès e PDF Gazzettino. Il preliminare rimane conservato.
- Svizzero: giocatori registrati e ospiti, squadre e potenziali, turni fissi o fino a esaurimento incroci, riposi, abbinamenti senza rivincite, risultati, classifica con scontri diretti, conclusione, palmarès e PDF.
- Musica di sottofondo attivabile, celebrazione dei vincitori, passaggio alle fasi finali, PDF in stile Gazzettino con logo, classifiche e calendario, CSV, rinomina, conclusione e palmarès. Bozze locali, esportazione delle bozze e controllo dei salvataggi concorrenti.
- Gestione club integrata: anagrafica, aggiunta e modifica giocatori, modifica rapida della tabella, ruoli, reset password, palmarès, archivi italiano e svizzero, eliminazione selettiva o globale dei tornei, CSV e Gazzetta PDF. Musica originale del club attivabile. L’app classica rimane raggiungibile dagli amministratori.
- Passaggio con accesso automatico alle app Streamlit classiche, disponibile come percorso alternativo.

Il logout del portale revoca **la sessione del portale**. Le vecchie app hanno cookie e sessioni propri: il loro logout globale richiede una fase successiva. L’ospite apre le altre app dalla loro pagina di login. Nel nuovo pannello club `A` può gestire tutto, `W` può aggiungere e modificare i dati ordinari dei giocatori, `R` e ospiti consultano. Solo `A` può cambiare ruoli, resettare password ed eliminare giocatori o tornei. Le eliminazioni globali escludono i Campionati; queste e le eliminazioni selettive dei Campionati richiedono la password corrente dell’amministratore.

Come nella versione classica, i tornei il cui nome contiene `Campionato` sono modificabili solo dagli amministratori. Gli ospiti inseriti durante la creazione appartengono esclusivamente al torneo: la loro presenza non cambia l’anagrafica MongoDB.

## Avvio locale senza MongoDB

Da `superba_web/`, in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
npm install
$env:SUPERBA_DEMO='true'
$env:SUPERBA_APP_ORIGIN='http://127.0.0.1:5173'
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In un secondo terminale, nella stessa cartella:

```powershell
npm run dev
```

Aprire `http://127.0.0.1:5173`. Credenziali **solo demo**: `Andrea` / `superba-demo`. La demo è interamente in memoria e non usa l’URI MongoDB. Al riavvio dell’API i dati demo ripartono dall’inizio.

## Configurazione reale

Usare variabili d’ambiente della piattaforma, **mai un file con segreti in Git**. Vedere `.env.example` per i nomi:

| Variabile | Uso |
|---|---|
| `MONGO_URI` | Cluster dei giocatori (`giocatori_subbuteo.superba_players`) |
| `MONGO_URI_AUTH` | Cluster di utenti, password di sistema e sessioni. Se assente, usa `MONGO_URI` |
| `MONGO_URI_TOURNEMENTS` | Cluster `TorneiSubbuteo.Superba` e `TorneiSubbuteo.SuperbaSvizzero`. Se assente, usa `MONGO_URI` |
| `SUPERBA_APP_ORIGIN` | Origine esatta del frontend, ad es. `https://nome.vercel.app` |
| `SUPERBA_WRITE_ENABLED` | `true` in produzione per consentire salvataggi avviati da utenti autenticati con ruolo `A` o `W`; per impostazione predefinita i comandi sui tornei sono bloccati |
| `SUPERBA_DEMO` | `true` solo per la demo locale; su Vercel viene rifiutato |
| `SPORTMONKS_TOKEN` | Facoltativo: aggiunge alla ricerca stemmi le squadre comprese nel proprio piano Sportmonks |
| `FOOTBALL_DATA_TOKEN` | Facoltativo: aggiunge alla ricerca stemmi le squadre accessibili tramite football-data.org |

La ricerca Premium unisce i risultati di Wikidata/Wikimedia Commons e dell'archivio pubblico football-logos senza token. Se presenti, aggiunge anche Sportmonks e football-data.org; un guasto di una fonte non blocca le altre. I token restano soltanto sul server. Le immagini dei club possono essere soggette a diritti di marchio distinti dalla licenza del repository o dell'API: verificarli prima di riutilizzarle altrove.

Per la pulizia automatica delle sessioni e dei tentativi scaduti sono consigliati indici TTL su `auth_subbuteo.portal_sessions.expires_at` e `auth_subbuteo.portal_login_attempts.expires_at`, entrambi con `expireAfterSeconds: 0`. Non sono stati creati durante questa migrazione: le query verificano comunque la scadenza. L’agente non ha eseguito scritture sul database reale; sessioni e modifiche saranno generate soltanto dalle azioni degli utenti nell’app.

Il portale è pubblicato su [superbaweb.vercel.app](https://superbaweb.vercel.app) nel progetto Vercel `superba_web`. Gli URI MongoDB sono variabili segrete Vercel; `SUPERBA_APP_ORIGIN` punta a quell’indirizzo e `SUPERBA_WRITE_ENABLED=true` è impostato solo in produzione. La route `GET /api/health` ha verificato dal server Vercel entrambe le connessioni MongoDB tramite sole letture, senza esporre documenti. La preview senza scritture resta separata. Non sono stati inseriti giocatori o tornei di prova nel database reale.

## Verifiche

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
npm run build
```

I test confrontano i calcoli estratti con le funzioni Streamlit originali e usano MongoDB simulato per login, permessi, salvataggi, conflitti, ritiri, conclusione, finali, svizzero, gestione club e passaggio alle vecchie app. Non sostituiscono prove con MongoDB reale né una verifica completa del browser in produzione.

## Ambito della migrazione

Il progetto non impone alcuna migrazione dello schema MongoDB. La gestione club può eliminare tornei dalle collezioni italiana e svizzera solo quando un amministratore ne conferma esplicitamente la cancellazione. Le app classiche restano disponibili dalle pagine delle competizioni.
