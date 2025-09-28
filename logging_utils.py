from pymongo import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime
import certifi
import os

# Configurazione connessione MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://massimilianoferrando:Legnaro21!$@cluster0.t3750lc.mongodb.net/")
DB_LOGS = "Log"
ACTIONS_COLLECTION = "Actions"

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
    """
    print(f"[DEBUG] Tentativo di log - Utente: {username}, Azione: {action}, Torneo: {torneo}")
    
    try:
        print("[DEBUG] Creazione client MongoDB...")
        client = get_mongo_client()
        print(f"[DEBUG] Client MongoDB creato: {client is not None}")
        
        print(f"[DEBUG] Connessione al database: {DB_LOGS}")
        db = client[DB_LOGS]
        print(f"[DEBUG] Connessione alla collezione: {ACTIONS_COLLECTION}")
        collection = db[ACTIONS_COLLECTION]
        
        log_entry = {
            "timestamp": datetime.utcnow(),
            "username": username,
            "action": action,
            "torneo": torneo,
            "details": details or {}
        }
        
        print(f"[DEBUG] Inserimento log: {log_entry}")
        result = collection.insert_one(log_entry)
        print(f"[DEBUG] Log inserito con ID: {result.inserted_id}")
        
        return True
    except Exception as e:
        import traceback
        error_msg = f"Errore durante il logging dell'azione: {e}\n{traceback.format_exc()}"
        print(f"[ERROR] {error_msg}")
        return False
