from pymongo import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime
import certifi
import os

# Configurazione connessione MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://massimilianoferrando:Legnaro21!$@cluster0.t3750lc.mongodb.net/")
DB_LOGS = "Log"
ACTIONS_COLLECTION = "Actions"

# Abilita il debug
DEBUG = True

def get_mongo_client():
    return MongoClient(MONGO_URI,
                     server_api=ServerApi('1'),
                     connectTimeoutMS=5000,
                     serverSelectionTimeoutMS=5000,
                     tlsCAFile=certifi.where())

def log_action(username: str, action: str, torneo: str, details: dict = None):
    """
    Registra un'azione nel database di logging.
    
    Args:
        username: Nome dell'utente che ha eseguito l'azione
        action: Tipo di azione (es. 'salvataggio', 'modifica', 'validazione')
        torneo: Nome del torneo su cui è stata eseguita l'azione
        details: Dettagli aggiuntivi dell'azione (opzionale)
    
    Returns:
        bool: True se il log è stato registrato con successo, False altrimenti
    """
    if DEBUG:
        print(f"[LOG_ACTION] Inizio log - Utente: {username}, Azione: {action}, Torneo: {torneo}")
        if details:
            print(f"[LOG_ACTION] Dettagli: {details}")
    
    client = None
    try:
        if DEBUG:
            print("[LOG_ACTION] Creazione client MongoDB...")
        
        client = get_mongo_client()
        
        if DEBUG:
            print(f"[LOG_ACTION] Client MongoDB creato: {client is not None}")
            
        # Verifica la connessione al server
        if client:
            client.admin.command('ping')
            if DEBUG:
                print("[LOG_ACTION] Connessione al server MongoDB verificata")
        
        if DEBUG:
            print(f"[LOG_ACTION] Connessione al database: {DB_LOGS}")
        
        db = client[DB_LOGS]
        
        if DEBUG:
            print(f"[LOG_ACTION] Connessione alla collezione: {ACTIONS_COLLECTION}")
        
        collection = db[ACTIONS_COLLECTION]
        
        # Crea il documento di log con tutti i dettagli
        log_entry = {
            "timestamp": datetime.utcnow(),
            "username": username,
            "action": action,
            "torneo": torneo,
            "ip_address": os.environ.get("REMOTE_ADDR", "unknown"),
            "user_agent": os.environ.get("HTTP_USER_AGENT", "unknown"),
            "details": details or {}
        }
        
        if DEBUG:
            print(f"[LOG_ACTION] Inserimento log: {log_entry}")
        
        # Inserisci il log nel database
        result = collection.insert_one(log_entry)
        
        if DEBUG:
            print(f"[LOG_ACTION] Log inserito con ID: {result.inserted_id}")
        
        return True
        
    except Exception as e:
        import traceback
        error_msg = f"[LOG_ACTION_ERROR] Errore durante il logging: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        
        # Prova a registrare l'errore in un file di log locale
        try:
            with open('error_log.txt', 'a', encoding='utf-8') as f:
                f.write(f"{datetime.now().isoformat()} - {error_msg}\n")
        except Exception as file_err:
            print(f"[LOG_ACTION_ERROR] Impossibile scrivere su file di log: {file_err}")
        
        return False
        
    finally:
        # Chiudi la connessione in ogni caso
        if client:
            try:
                client.close()
                if DEBUG:
                    print("[LOG_ACTION] Connessione al database chiusa")
            except Exception as close_err:
                print(f"[LOG_ACTION_ERROR] Errore nella chiusura della connessione: {close_err}")
