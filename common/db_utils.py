"""
db_utils.py — Utility di connessione e gestione MongoDB per Subbuteo.

Centralizza:
  - Connessione MongoDB (init_mongo_connection)
  - Check connessione internet
  - Caricamento giocatori da DB
  - Caricamento/salvataggio/aggiornamento tornei
"""
import streamlit as st
import pandas as pd
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
import certifi
import socket


def check_internet_connection() -> bool:
    """Verifica la connessione internet tentando un DNS lookup."""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        return True
    except OSError:
        return False


def init_mongo_connection(uri: str, db_name: str, collection_name: str, show_ok: bool = False):
    """
    Inizializza la connessione a MongoDB e ritorna la collection.
    
    Args:
        uri: Stringa di connessione MongoDB.
        db_name: Nome del database.
        collection_name: Nome della collection.
        show_ok: Se True, mostra un messaggio di successo nella sidebar.
    
    Returns:
        La collection MongoDB, oppure None se la connessione fallisce.
    """
    try:
        client = MongoClient(
            uri,
            server_api=ServerApi('1'),
            connectTimeoutMS=5000,
            socketTimeoutMS=5000,
            serverSelectionTimeoutMS=5000,
            tlsCAFile=certifi.where()
        )
        client.admin.command('ping')
        db = client[db_name]
        collection = db[collection_name]
        _ = collection.find_one()  # Verifica accesso
        if show_ok:
            st.sidebar.success(f"✅ Connesso a {db_name}.{collection_name}")
        return collection
    except Exception as e:
        st.sidebar.error(f"❌ Errore connessione a {db_name}.{collection_name}: {e}")
        return None


def init_mongo_direct(uri: str, db_name: str, collection_name: str):
    """
    Connessione diretta per il Torneo Svizzero (senza certifi path esplicito).
    Ritorna (players_collection, tournaments_collection) per il flusso specifico.
    
    Args:
        uri: Stringa di connessione MongoDB.
        db_name: Nome del database.
        collection_name: Nome della collection.
    
    Returns:
        La collection MongoDB, oppure None se la connessione fallisce.
    """
    try:
        client = MongoClient(
            uri,
            server_api=ServerApi('1'),
            connectTimeoutMS=5000,
            socketTimeoutMS=5000,
            serverSelectionTimeoutMS=5000
        )
        client.admin.command('ping')
        db = client.get_database(db_name)
        collection = db.get_collection(collection_name)
        _ = collection.find_one()
        return collection
    except Exception as e:
        st.sidebar.error(f"❌ Errore connessione a {db_name}.{collection_name}: {e}")
        return None


def carica_giocatori_da_db(players_collection) -> pd.DataFrame:
    """
    Carica i giocatori dal database e li ritorna come DataFrame.
    
    Args:
        players_collection: Collection MongoDB dei giocatori.
    
    Returns:
        DataFrame con colonne [Giocatore, Squadra, Potenziale, ...].
    """
    if players_collection is None:
        return pd.DataFrame()
    try:
        df = pd.DataFrame(list(players_collection.find()))
        if '_id' in df.columns:
            df = df.drop(columns=['_id'])
        if 'Giocatore' not in df.columns:
            st.error("❌ Colonna 'Giocatore' non trovata nel DB giocatori.")
            return pd.DataFrame()
        return df
    except Exception as e:
        st.error(f"❌ Errore lettura giocatori: {e}")
        return pd.DataFrame()


def carica_tornei_da_db(tournaments_collection, prefix: list = None) -> list:
    """
    Carica l'elenco dei tornei dal DB, eventualmente filtrando per prefisso.
    
    Args:
        tournaments_collection: Collection MongoDB dei tornei.
        prefix: Lista di prefissi per filtrare i nomi (opzionale).
    
    Returns:
        Lista di dizionari con _id e nome_torneo.
    """
    if tournaments_collection is None:
        return []
    try:
        if prefix:
            import re
            patterns = [re.compile(f"^{p}", re.IGNORECASE) for p in prefix]
            query = {"$or": [{"nome_torneo": {"$regex": p}} for p in patterns]}
            tornei = list(tournaments_collection.find(query, {"nome_torneo": 1}))
        else:
            tornei = list(tournaments_collection.find({}, {"nome_torneo": 1}))
        return tornei
    except Exception as e:
        st.error(f"❌ Errore caricamento elenco tornei: {e}")
        return []


def carica_torneo_da_db(tournaments_collection, tournament_id: str) -> dict:
    """
    Carica un singolo torneo dal DB e lo ritorna come dizionario.
    
    Args:
        tournaments_collection: Collection MongoDB dei tornei.
        tournament_id: ID del torneo (stringa ObjectId).
    
    Returns:
        Dizionario con i dati del torneo, oppure None.
    """
    if tournaments_collection is None:
        return None
    try:
        doc = tournaments_collection.find_one({"_id": ObjectId(tournament_id)})
        if not doc:
            return None

        # Converti il calendario in DataFrame
        calendario_raw = doc.get("calendario", doc.get("df_torneo"))
        if calendario_raw:
            df = pd.DataFrame(calendario_raw)
            st.session_state['df_torneo'] = df

            # Converti tipi
            for col in ['GolCasa', 'GolOspite']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

            bool_col = 'Valida' if 'Valida' in df.columns else 'Validata'
            if bool_col in df.columns:
                df[bool_col] = df[bool_col].apply(lambda x: bool(x) if x is not None else False)

            st.session_state['df_torneo'] = df
            doc['calendario'] = df

        return doc
    except Exception as e:
        st.error(f"❌ Errore caricamento torneo: {e}")
        return None


def aggiorna_torneo_su_db(tournaments_collection, tournament_id: str, df_torneo: pd.DataFrame) -> bool:
    """
    Aggiorna il calendario di un torneo esistente su MongoDB.
    
    Args:
        tournaments_collection: Collection MongoDB dei tornei.
        tournament_id: ID del torneo (stringa ObjectId).
        df_torneo: DataFrame aggiornato del torneo.
    
    Returns:
        True se aggiornato con successo, False altrimenti.
    """
    if tournaments_collection is None:
        st.error("❌ Connessione MongoDB non disponibile.")
        return False
    try:
        # Prepara i records per MongoDB
        records = df_torneo.copy()
        for col in records.columns:
            if records[col].dtype == 'bool':
                records[col] = records[col].astype(bool)
        
        result = tournaments_collection.update_one(
            {"_id": ObjectId(tournament_id)},
            {"$set": {"calendario": records.to_dict('records')}}
        )
        return result.modified_count > 0 or result.matched_count > 0
    except Exception as e:
        st.error(f"❌ Errore aggiornamento torneo: {e}")
        return False


def salva_torneo_su_db(tournaments_collection, df_torneo: pd.DataFrame, nome_torneo: str, tournament_id: str = None) -> str:
    """
    Salva un nuovo torneo o aggiorna uno esistente su MongoDB.
    
    Args:
        tournaments_collection: Collection MongoDB dei tornei.
        df_torneo: DataFrame del torneo.
        nome_torneo: Nome del torneo.
        tournament_id: ID del torneo da aggiornare (opzionale).
    
    Returns:
        ID del torneo salvato (stringa), oppure None.
    """
    if tournaments_collection is None:
        st.error("❌ Connessione MongoDB non disponibile.")
        return None
    try:
        from datetime import datetime
        records = df_torneo.to_dict('records')
        
        torneo_data = {
            "nome_torneo": nome_torneo,
            "calendario": records,
            "data_salvataggio": datetime.utcnow(),
        }

        if tournament_id:
            tournaments_collection.update_one(
                {"_id": ObjectId(tournament_id)},
                {"$set": torneo_data}
            )
            return tournament_id
        else:
            result = tournaments_collection.insert_one(torneo_data)
            return str(result.inserted_id)
    except Exception as e:
        st.error(f"❌ Errore salvataggio torneo: {e}")
        return None
