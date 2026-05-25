import os
from datetime import datetime

import certifi
import streamlit as st
from pymongo import MongoClient
from pymongo.server_api import ServerApi

from .security import hash_password, password_needs_upgrade, verify_password


DEFAULT_MONGO_URI = "mongodb+srv://massimilianoferrando:Legnaro21!$@cluster0.t3750lc.mongodb.net/?retryWrites=true&w=majority"
DB_PWD = "Password"
AUTH_COLLECTION = "auth_password"
DB_NAME_PLAYERS = "giocatori_subbuteo"
PLAYERS_COLLECTIONS = {
    "Superba": "superba_players",
}
DB_LOGIN = "Log"
LOG_COLLECTION = "Login"


@st.cache_resource
def get_mongo_client():
    mongo_uri = os.getenv("MONGO_URI_AUTH")
    if not mongo_uri:
        try:
            mongo_uri = st.secrets.get("MONGO_URI_AUTH") or st.secrets.get("MONGO_URI")
        except Exception:
            mongo_uri = None
    mongo_uri = mongo_uri or DEFAULT_MONGO_URI
    return MongoClient(
        mongo_uri,
        server_api=ServerApi("1"),
        connectTimeoutMS=5000,
        serverSelectionTimeoutMS=5000,
        socketTimeoutMS=5000,
        tlsCAFile=certifi.where(),
    )


def log_event(username: str, esito: str, dettagli: dict | None = None):
    try:
        get_mongo_client()[DB_LOGIN][LOG_COLLECTION].insert_one(
            {
                "timestamp": datetime.utcnow(),
                "username": username,
                "esito": esito,
                "dettagli": dettagli or {},
            }
        )
    except Exception as exc:
        print(f"Errore durante il logging: {exc}")


def find_user(username: str, club: str = "Superba"):
    client = get_mongo_client()
    db_players = client[DB_NAME_PLAYERS]
    collection_name = PLAYERS_COLLECTIONS.get(club)
    if not collection_name:
        return None
    try:
        player = db_players[collection_name].find_one(
            {"Giocatore": {"$regex": f"^{username}$", "$options": "i"}}
        )
        if player:
            player["_collection"] = collection_name
        return player
    except Exception as exc:
        print(f"Errore durante la ricerca nella collection {collection_name}: {exc}")
        return None


def find_user_by_id(user_id: str, collection_name: str = "superba_players"):
    from bson import ObjectId

    try:
        player = get_mongo_client()[DB_NAME_PLAYERS][collection_name].find_one({"_id": ObjectId(user_id)})
        if player:
            player["_collection"] = collection_name
        return player
    except Exception:
        return None


def validate_system_password(pwd: str) -> bool:
    try:
        return get_mongo_client()[DB_PWD][AUTH_COLLECTION].find_one({"Password": pwd}) is not None
    except Exception:
        return False


def update_user_password(player, new_pwd: str):
    hashed = hash_password(new_pwd)
    get_mongo_client()[DB_NAME_PLAYERS][player["_collection"]].update_one(
        {"_id": player["_id"]},
        {"$set": {"Password": hashed, "SetPwd": 1}},
    )
    log_event(
        player.get("Giocatore", "Sconosciuto"),
        "Impostazione nuova password",
        {"azione": "Cambio password", "club": player.get("_collection")},
    )
    return hashed


def validate_user_password(player, password: str) -> bool:
    stored = str(player.get("Password", "") if player else "")
    ok = verify_password(password, stored)
    if ok and password_needs_upgrade(stored):
        player["Password"] = update_user_password(player, password)
    return ok


def user_payload(player, role: str | None = None):
    return {
        "username": player.get("Giocatore"),
        "role": role or player.get("Ruolo", "W"),
        "collection": player["_collection"],
        "id": str(player["_id"]),
    }
