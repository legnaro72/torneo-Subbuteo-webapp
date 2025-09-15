import streamlit as st
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
import os
from datetime import datetime
import logging
from typing import Optional, Dict, Any

# Lista globale per i messaggi di debug
debug_messages = []

def add_debug_message(message: str, level: str = "info") -> None:
    """Aggiunge un messaggio di debug alla lista dei messaggi"""
    if 'debug_messages' not in st.session_state:
        st.session_state.debug_messages = []
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    debug_message = f"[{timestamp}] [{level.upper()}] {message}"
    st.session_state.debug_messages.append(debug_message)
    
    # Limita la lista a 100 messaggi
    if len(st.session_state.debug_messages) > 100:
        st.session_state.debug_messages = st.session_state.debug_messages[-100:]
    
    # Stampa sulla console e scrive su file
    print(debug_message)
    
    # Assicurati che la directory dei log esista
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Scrivi il log su file
    log_file = os.path.join(log_dir, 'login.log')
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(debug_message + '\n')
    except Exception as e:
        print(f"Errore nella scrittura del log: {str(e)}")

# Configurazione connessione MongoDB
MONGO_URI = os.getenv("MONGO_URI_AUTH", "mongodb+srv://massimilianoferrando:Legnaro21!$@cluster0.t3750lc.mongodb.net/")
DB_NAME = "Password"
AUTH_COLLECTION = "auth_password"
DB_NAME_PLAYERS = "giocatori_subbuteo"
PLAYERS_COLLECTION1 = "superba_players"
PLAYERS_COLLECTION2 = "piercrew_players"
DB_LOGIN_LOGS = "Login"
LOGIN_LOGS_COLLECTION = "Logs"

def get_mongo_collection(collection_name: str):
    """Restituisce una collezione MongoDB specifica"""
    try:
        client = MongoClient(MONGO_URI, server_api=ServerApi('1'), connectTimeoutMS=5000, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')  # Verifica la connessione
        db = client[DB_NAME]
        
        # Crea la collezione se non esiste
        if collection_name not in db.list_collection_names():
            db.create_collection(collection_name)
            
        return db[collection_name]
    except Exception as e:
        add_debug_message(f"Errore durante il recupero della collezione {collection_name}: {str(e)}", "error")
        return None

def check_credentials(username: str, password: str) -> Dict[str, Any]:
    """Verifica le credenziali dell'utente e restituisce un dizionario con il risultato"""
    result = {
        'success': False,
        'message': '',
        'user': None
    }
    
    if not username or not password:
        result['message'] = "Username e password sono obbligatori"
        return result
    
    try:
        # 1. Verifica che l'utente esista in una delle due collezioni di giocatori
        client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
        db_players = client[DB_NAME_PLAYERS]
        
        # Debug: verifica le collezioni disponibili
        collections = db_players.list_collection_names()
        add_debug_message(f"Collezioni trovate: {collections}", "debug")
        
        # Debug: mostra tutte le voci nelle collezioni rilevanti
        debug_collections = [PLAYERS_COLLECTION1, PLAYERS_COLLECTION2]
        for coll_name in debug_collections:
            if coll_name in collections:
                try:
                    all_entries = list(db_players[coll_name].find({}, {"Giocatore": 1, "_id": 0}).limit(50))  # Limite a 50 voci per non sovraccaricare
                    nomi = [entry.get('Giocatore', 'N/D') for entry in all_entries]
                    add_debug_message(f"Giocatori in {coll_name} ({len(nomi)}): {nomi}", "debug")
                    
                    # Confronto case-insensitive
                    matches = [name for name in nomi if isinstance(name, str) and username.lower() == name.lower()]
                    if matches:
                        add_debug_message(f"Trovata corrispondenza esatta (case-insensitive) in {coll_name}: {matches}", "debug")
                    else:
                        # Cerca corrispondenze parziali per debug
                        partial_matches = [name for name in nomi if isinstance(name, str) and username.lower() in name.lower()]
                        if partial_matches:
                            add_debug_message(f"Possibili corrispondenze parziali in {coll_name}: {partial_matches}", "debug")
                except Exception as e:
                    add_debug_message(f"Errore durante l'analisi di {coll_name}: {str(e)}", "error")
        
        # Cerca il giocatore nella prima collezione (superba_players)
        player = None
        collection_used = None
        
        if PLAYERS_COLLECTION1 in collections:
            player = db_players[PLAYERS_COLLECTION1].find_one(
                {"Giocatore": {'$regex': f'^{username}$', '$options': 'i'}}
            )
            if player:
                collection_used = PLAYERS_COLLECTION1
                player['_collection'] = collection_used
        
        # Se non trovato, cerca nella seconda collezione (piercrew_players)
        if not player and PLAYERS_COLLECTION2 in collections:
            player = db_players[PLAYERS_COLLECTION2].find_one(
                {"Giocatore": {'$regex': f'^{username}$', '$options': 'i'}}
            )
            if player:
                collection_used = PLAYERS_COLLECTION2
                player['_collection'] = collection_used
        
        if not player:
            error_msg = f"Username '{username}' non trovato in nessuna collezione. Collezioni disponibili: {collections}"
            add_debug_message(error_msg, "warning")
            result['message'] = "Nome utente non valido"
            log_login_attempt(username, False, error_msg)
            return result
            
        # 2. Verifica la password
        try:
            db_auth = client[DB_NAME]
            # Verifica se la collezione esiste
            if AUTH_COLLECTION not in db_auth.list_collection_names():
                result['message'] = "Errore: collezione di autenticazione non trovata"
                log_login_attempt(username, False, "Collezione di autenticazione non trovata")
                return result
                
            auth_collection = db_auth[AUTH_COLLECTION]
            
            # Cerca la password (case sensitive)
            password = str(password).strip()
            add_debug_message(f"Verifica password per utente: {username}", "debug")
            add_debug_message(f"Password fornita: {password}", "debug")
            
            # Debug: mostra tutti i documenti nella collezione auth
            try:
                all_auths = list(auth_collection.find({}, {"Password": 1, "_id": 0}))
                add_debug_message(f"Documenti nella collezione {AUTH_COLLECTION}: {all_auths}", "debug")
            except Exception as e:
                add_debug_message(f"Errore nel recupero dei documenti di autenticazione: {str(e)}", "error")
            
            auth_doc = auth_collection.find_one({"Password": password})  # Nota: Password con P maiuscola
            
            if not auth_doc:
                result['message'] = "Password non valida"
                log_login_attempt(username, False, "Password non valida")
                return result
        except Exception as e:
            error_msg = f"Errore durante la verifica della password: {str(e)}"
            add_debug_message(error_msg, "error")
            result['message'] = "Errore durante l'autenticazione"
            log_login_attempt(username, False, error_msg)
            return result
            
        # 3. Log del tentativo di accesso riuscito
        log_login_attempt(username, True, f"Accesso riuscito per l'utente {username}")
        
        # Determina il ruolo in base alla collezione di provenienza
        player_role = 'user'
        if player.get('_collection') == PLAYERS_COLLECTION1:
            player_role = 'superba_user'
        elif player.get('_collection') == PLAYERS_COLLECTION2:
            player_role = 'piercrew_user'
        
        result['success'] = True
        result['message'] = "Accesso riuscito"
        result['user'] = {
            'username': player.get('Nome'),
            'id': str(player.get('_id')),
            'role': auth_doc.get('role', player_role),
            'original_collection': player.get('_collection', PLAYERS_COLLECTION1)
        }
        
        return result
        
    except Exception as e:
        error_msg = f"Errore durante l'autenticazione: {str(e)}"
        add_debug_message(error_msg, "error")
        log_login_attempt(username, False, error_msg)
        result['message'] = "Si è verificato un errore durante l'autenticazione"
        return result

def log_login_attempt(username: str, success: bool, message: str = "") -> None:
    """Registra un tentativo di accesso nel database MongoDB"""
    try:
        add_debug_message(f"Tentativo di connessione a MongoDB con URI: {MONGO_URI}", "debug")
        
        # Connessione al database
        client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
        
        # Verifica la connessione
        try:
            client.admin.command('ping')
            add_debug_message("Connessione a MongoDB stabilita con successo", "debug")
        except Exception as e:
            add_debug_message(f"Errore nella connessione a MongoDB: {str(e)}", "error")
            return
            
        db = client[DB_LOGIN_LOGS]
        add_debug_message(f"Database selezionato: {DB_LOGIN_LOGS}", "debug")
        
        # Verifica se la collezione esiste, altrimenti la crea
        collection_names = db.list_collection_names()
        add_debug_message(f"Collezioni disponibili: {collection_names}", "debug")
        
        if LOGIN_LOGS_COLLECTION not in collection_names:
            add_debug_message(f"Collezione {LOGIN_LOGS_COLLECTION} non trovata, creazione in corso...", "debug")
            try:
                db.create_collection(LOGIN_LOGS_COLLECTION)
                add_debug_message(f"Creata nuova collezione: {LOGIN_LOGS_COLLECTION}", "info")
            except Exception as e:
                add_debug_message(f"Errore nella creazione della collezione: {str(e)}", "error")
        
        logs_collection = db[LOGIN_LOGS_COLLECTION]
        
        # Inizializza i valori di default
        ip_address = 'unknown'
        user_agent = 'unknown'
        
        # Prova a ottenere le informazioni della richiesta HTTP in modo sicuro
        try:
            ctx = st.runtime.scriptrunner.get_script_run_ctx()
            if hasattr(ctx, 'request') and hasattr(ctx.request, 'headers'):
                headers = ctx.request.headers
                ip_address = headers.get('X-Forwarded-For', 'unknown')
                user_agent = headers.get('User-Agent', 'unknown')
        except Exception as header_error:
            add_debug_message(f"Errore nel recupero degli header: {str(header_error)}", "warning")
        
        log_entry = {
            'username': username,
            'timestamp': datetime.utcnow(),
            'success': success,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'message': message
        }
        
        # Inserisci il log nel database
        try:
            add_debug_message(f"Tentativo di inserimento del log: {log_entry}", "debug")
            result = logs_collection.insert_one(log_entry)
            add_debug_message(f"Log accesso registrato con ID: {result.inserted_id}", "debug")
            
            # Verifica che il documento sia stato effettivamente inserito
            if result.inserted_id:
                doc = logs_collection.find_one({"_id": result.inserted_id})
                if doc:
                    add_debug_message(f"Documento verificato nel database: {doc}", "debug")
                else:
                    add_debug_message("Attenzione: il documento non è stato trovato dopo l'inserimento", "error")
            else:
                add_debug_message("Nessun ID restituito dall'inserimento", "error")
                
        except Exception as e:
            add_debug_message(f"Errore durante l'inserimento del log: {str(e)}", "error")
        
    except Exception as e:
        add_debug_message(f"Errore durante il log dell'accesso nel database: {str(e)}", "error")

def verify_write_access():
    """Verifica se l'utente ha i permessi di scrittura"""
    if 'read_only' not in st.session_state:
        return False
    return st.session_state.authenticated and not st.session_state.read_only

def get_current_user() -> Optional[Dict[str, Any]]:
    """Restituisce le informazioni dell'utente attualmente autenticato"""
    return st.session_state.get("user")

def show_auth_screen():
    """Mostra la schermata di autenticazione con opzione di sola lettura"""
    st.title("🔐 Accesso")
    
    # Inizializza lo stato
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.read_only = True
    
    # Se già autenticato, esci
    if st.session_state.authenticated:
        return True
        
    # Se in modalità sola lettura, mostra solo il pulsante di accesso
    if st.session_state.get("read_only"):
        if st.button("🔓 Accedi per modificare"):
            st.session_state["read_only"] = False
            st.rerun()
        return False
    
    # Form di login
    with st.form("auth_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Accedi")
        
        if submitted:
            if not username:
                st.error("Inserisci il tuo username")
                return False
                
            auth_result = check_credentials(username, password)
            if auth_result['success']:
                st.session_state["authenticated"] = True
                st.session_state["read_only"] = False
                st.session_state["user"] = auth_result['user']
                st.success(f"Accesso riuscito come {auth_result['user']['username']}!")
                st.rerun()
            else:
                st.error(auth_result['message'] or "Autenticazione fallita")
    
    # Se non autenticato, mostra il pulsante per la modalità sola lettura
    if not st.session_state.get("authenticated"):
        if st.button("👁️ Accedi in modalità sola lettura"):
            st.session_state["read_only"] = True
            st.session_state["authenticated"] = False
            st.rerun()
    
    return st.session_state.get("authenticated", False)

def verify_write_access():
    """Verifica se l'utente ha i permessi di scrittura"""
    if 'read_only' not in st.session_state:
        return False
    return st.session_state.authenticated and not st.session_state.read_only

def add_password(password: str, username: str = "admin", role: str = "admin"):
    """Aggiunge una nuova password al database"""
    try:
        auth_collection = get_mongo_collection(AUTH_COLLECTION)
        if not auth_collection:
            return False, "Errore di connessione al database"
            
        # Verifica se la password esiste già
        existing = auth_collection.find_one({"password": password})
        if existing:
            return False, "Questa password esiste già"
            
        # Aggiungi la nuova password
        auth_collection.insert_one({
            "username": username,
            "password": password,
            "role": role,
            "created_at": datetime.utcnow(),
            "created_by": st.session_state.get("user", {}).get("username", "system")
        })
        
        # Log dell'azione
        log_login_attempt(
            username=st.session_state.get("user", {}).get("username", "system"),
            success=True,
            message=f"Aggiunta nuova password per l'utente {username} con ruolo {role}"
        )
        
        return True, "Password aggiunta con successo"
    except Exception as e:
        error_msg = f"Errore durante l'aggiunta della password: {str(e)}"
        log_login_attempt(
            username=st.session_state.get("user", {}).get("username", "system"),
            success=False,
            message=error_msg
        )
        return False, error_msg

def list_passwords():
    """Restituisce l'elenco di tutte le password (solo per amministrazione)"""
    try:
        auth_collection = get_mongo_collection(AUTH_COLLECTION)
        if not auth_collection:
            return []
        return list(auth_collection.find({}, {"password": 1, "username": 1, "role": 1, "_id": 0
        }))
    except Exception as e:
        add_debug_message(f"Errore durante il recupero delle password: {str(e)}", "error")
        return []

def remove_password(password: str) -> bool:
    """Rimuove una password dal database"""
    try:
        auth_collection = get_mongo_collection(AUTH_COLLECTION)
        if not auth_collection:
            return False
            
        result = auth_collection.delete_one({"password": password})
        
        # Log dell'azione
        log_login_attempt(
            username=st.session_state.get("user", {}).get("username", "system"),
            success=result.deleted_count > 0,
            message=f"Rimozione password: {password}"
        )
        
        return result.deleted_count > 0
    except Exception as e:
        error_msg = f"Errore durante la rimozione della password: {str(e)}"
        add_debug_message(error_msg, "error")
        log_login_attempt(
            username=st.session_state.get("user", {}).get("username", "system"),
            success=False,
            message=error_msg
        )
        return False

def show_debug_messages():
    """Mostra i messaggi di debug nell'interfaccia"""
    if not debug_messages:
        st.write("Nessun messaggio di debug disponibile")
        return
    
    st.subheader("🔍 Log di Debug")
    
    # Filtra i messaggi per livello
    level_filter = st.selectbox(
        "Filtra per livello",
        ["Tutti"] + sorted(set(msg['level'] for msg in debug_messages)),
        index=0
    )
    
    # Mostra i messaggi in ordine cronologico inverso (i più recenti prima)
    filtered_messages = [
        msg for msg in debug_messages
        if level_filter == "Tutti" or msg['level'] == level_filter
    ]
    
    # Stile per i messaggi
    style = """
    <style>
        .debug-box {
            border-left: 5px solid #4CAF50;
            padding: 10px;
            margin: 5px 0;
            background-color: #f8f9fa;
            border-radius: 0 5px 5px 0;
        }
        .debug-box.warning {
            border-left-color: #ff9800;
            background-color: #fff3e0;
        }
        .debug-box.error {
            border-left-color: #f44336;
            background-color: #ffebee;
        }
        .debug-box.debug {
            border-left-color: #2196F3;
            background-color: #e3f2fd;
        }
        .debug-time {
            font-size: 0.8em;
            color: #666;
            margin-right: 10px;
        }
        .debug-level {
            font-weight: bold;
            margin-right: 10px;
        }
        .debug-message {
            word-wrap: break-word;
        }
    </style>
    """
    st.markdown(style, unsafe_allow_html=True)
    
    # Mostra i messaggi
    for msg in reversed(filtered_messages):
        level_class = msg['level'].lower()
        if level_class not in ['info', 'warning', 'error', 'debug']:
            level_class = 'info'
            
        st.markdown(
            f"""
            <div class="debug-box {level_class}">
                <div>
                    <span class="debug-time">{msg['time']}</span>
                    <span class="debug-level">{msg['level'].upper()}</span>
                </div>
                <div class="debug-message">{msg['message']}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # Pulsante per pulire i log
    if st.button("🔄 Aggiorna log"):
        st.rerun()
        
    if st.button("🗑️ Pulisci log"):
        debug_messages.clear()
        st.rerun()
