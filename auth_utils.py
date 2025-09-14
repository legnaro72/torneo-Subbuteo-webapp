import streamlit as st
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
import os
from datetime import datetime

# Lista globale per i messaggi di debug
debug_messages = []

def add_debug_message(message: str, level: str = "info"):
    """Aggiunge un messaggio di debug alla lista"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    debug_messages.append({
        'time': timestamp,
        'message': message,
        'level': level
    })
    # Stampa anche su console
    print(f"[{timestamp}] [{level.upper()}] {message}")

# Configurazione connessione MongoDB
MONGO_URI = os.getenv("MONGO_URI_AUTH", "mongodb+srv://massimilianoferrando:Legnaro21!$@cluster0.t3750lc.mongodb.net/")
DB_NAME = "Password"
COLLECTION_NAME = "auth_password"

def get_auth_collection():
    """Restituisce la collezione di autenticazione"""
    try:
        client = MongoClient(MONGO_URI, server_api=ServerApi('1'), connectTimeoutMS=5000, serverSelectionTimeoutMS=5000)
        
        # Verifica la connessione
        client.admin.command('ping')
        
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        
        # Verifica che la collezione esista
        if COLLECTION_NAME not in db.list_collection_names():
            return None
            
        return collection
        
    except Exception:
        return None

def check_password(password: str) -> bool:
    """Verifica se la password è corretta nel database"""
    if not password:
        return False
    
    try:
        # 1. Connessione al database
        auth_collection = get_auth_collection()
        if auth_collection is None:
            return False
        
        # 2. Recupera TUTTI i documenti
        all_docs = list(auth_collection.find({}))
        if not all_docs:
            return False
        
        # 3. Cerca la password
        for doc in all_docs:
            # Verifica se esiste il campo password (case sensitive prima)
            password_key = 'password' if 'password' in doc else None
            
            # Se non trovato, cerca case insensitive
            if not password_key:
                for key in doc.keys():
                    if key.lower() == 'password':
                        password_key = key
                        break
            
            if password_key:
                stored_pwd = doc[password_key]
                
                # Verifica il tipo del valore della password
                if not isinstance(stored_pwd, str):
                    stored_pwd = str(stored_pwd)
                
                # Normalizza entrambe le stringhe per il confronto
                password_norm = str(password).strip()
                stored_pwd_norm = str(stored_pwd).strip()
                
                # Confronto esatto
                if stored_pwd_norm == password_norm:
                    return True
        
        # Se non trovata, proviamo con una ricerca case-insensitive
        for doc in all_docs:
            if 'password' in doc and str(doc['password']).lower() == str(password).lower():
                return True
        
        return False
            
    except Exception:
        return False

def show_auth_screen():
    """Mostra la schermata di autenticazione con opzione di sola lettura"""
    # Inizializza lo stato
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.read_only = True
    
    # Se già autenticato, esci
    if st.session_state.authenticated:
        return True
        
    # Schermata di benvenuto
    st.title("🔐 Accesso Torneo Subbuteo")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔓 Accesso in sola lettura", use_container_width=True, type="primary"):
            st.session_state.authenticated = True
            st.session_state.read_only = True
            st.rerun()
            
    with col2:
        if st.button("✏️ Accesso in scrittura", use_container_width=True, type="secondary"):
            st.session_state.show_password_field = True
            
        if st.session_state.get('show_password_field', False):
            with st.form("login_form"):
                password = st.text_input("Inserisci la password", type="password")
                if st.form_submit_button("Accedi"):
                    if check_password(password):
                        st.session_state.authenticated = True
                        st.session_state.read_only = False
                        st.session_state.show_password_field = False
                        st.rerun()
                    else:
                        st.error("Password non valida. Riprova o accedi in sola lettura.")
    
    st.markdown("---")
    st.info("💡 Seleziona 'Accesso in sola lettura' per visualizzare i tornei o 'Accesso in scrittura' per effettuare modifiche.")
    
    return st.session_state.authenticated

def verify_write_access():
    """Verifica se l'utente ha i permessi di scrittura"""
    if 'read_only' not in st.session_state:
        return False
    return st.session_state.authenticated and not st.session_state.read_only

def add_password(password: str, username: str = "admin", role: str = "admin") -> bool:
    """Aggiunge una nuova password al database"""
    try:
        auth_collection = get_auth_collection()
        if not auth_collection:
            return False
            
        # Crea il documento da inserire
        doc = {
            "username": username,
            "password": password,
            "role": role,
            "created_at": datetime.utcnow()
        }
        
        # Inserisci il documento
        result = auth_collection.insert_one(doc)
        return result.inserted_id is not None
        
    except Exception as e:
        add_debug_message(f"Errore durante l'aggiunta della password: {str(e)}", "error")
        return False

def list_passwords():
    """Restituisce l'elenco di tutte le password (solo per amministrazione)"""
    try:
        auth_collection = get_auth_collection()
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
        auth_collection = get_auth_collection()
        if not auth_collection:
            return False
            
        result = auth_collection.delete_one({"password": password})
        return result.deleted_count > 0
        
    except Exception as e:
        add_debug_message(f"Errore durante la rimozione della password: {str(e)}", "error")
        return False
