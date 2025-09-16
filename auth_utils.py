import streamlit as st
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
import os
from datetime import datetime

# Configurazione connessione MongoDB
MONGO_URI = os.getenv("MONGO_URI_AUTH", "mongodb+srv://massimilianoferrando:Legnaro21!$@cluster0.t3750lc.mongodb.net/")
DB_PWD = "Password"
AUTH_COLLECTION = "auth_password"
DB_NAME_PLAYERS = "giocatori_subbuteo"
PLAYERS_COLLECTION1 = "superba_players"
PLAYERS_COLLECTION2 = "piercrew_players"

def get_mongo_client():
    return MongoClient(MONGO_URI, server_api=ServerApi('1'), connectTimeoutMS=5000, serverSelectionTimeoutMS=5000)

def find_user(username: str):
    client = get_mongo_client()
    db_players = client[DB_NAME_PLAYERS]
    for coll in [PLAYERS_COLLECTION1, PLAYERS_COLLECTION2]:
        try:
            player = db_players[coll].find_one({"Giocatore": {'$regex': f'^{username}$', '$options': 'i'}})
        except Exception:
            player = None
        if player:
            player["_collection"] = coll
            return player
    return None

def validate_system_password(pwd: str) -> bool:
    client = get_mongo_client()
    try:
        db_pwd = client[DB_PWD]
        return db_pwd[AUTH_COLLECTION].find_one({"Password": pwd}) is not None
    except Exception:
        return False

def update_user_password(player, new_pwd: str):
    client = get_mongo_client()
    db_players = client[DB_NAME_PLAYERS]
    coll = db_players[player["_collection"]]
    coll.update_one(
        {"_id": player["_id"]},
        {"$set": {"Password": new_pwd, "SetPwd": 1}}
    )

def show_auth_screen():
    # Inizializza stato
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "read_only" not in st.session_state:
        st.session_state.read_only = False
    if "auth_phase" not in st.session_state:
        st.session_state.auth_phase = "username"  # username / password / set_password
    if "player" not in st.session_state:
        st.session_state.player = None

    # Se già autenticato, esci
    if st.session_state.authenticated:
        return True

    st.title("🔐 Accesso al Torneo Subbuteo")

    # FASE 1: username
    if st.session_state.auth_phase == "username":
        with st.form(key="auth_form_username"):
            username = st.text_input("Username", key="auth_username")
            col1, col2 = st.columns([1, 2])
            with col1:
                submitted = st.form_submit_button("Accedi", help="Verifica esistenza username")
            with col2:
                guest_submitted = st.form_submit_button("Accedi come ospite", help="Accedi in modalità sola lettura")
                
            if guest_submitted:
                st.session_state.authenticated = True
                st.session_state.read_only = True
                st.session_state.user = {
                    "username": "Ospite",
                    "role": "G",  # G per Guest
                    "collection": "guests",
                    "id": None
                }
                st.rerun()
        if submitted:
            if not username:
                st.error("Inserisci lo username")
                return False
            player = find_user(username)
            if not player:
                st.error("Utente non trovato")
                return False
            st.session_state.player = player
            ruolo = player.get("Ruolo", "R")
            # ruolo R => sola lettura
            if ruolo == "R":
                st.session_state.authenticated = True
                st.session_state.read_only = True
                st.session_state.user = {
                    "username": player.get("Giocatore"),
                    "role": ruolo,
                    "collection": player["_collection"],
                    "id": str(player["_id"])
                }
                st.success("✅ Accesso in sola lettura")
                st.rerun()
            else:
                # Se ha già password impostata
                if int(player.get("SetPwd", 0)) == 1:
                    st.session_state.auth_phase = "password"
                else:
                    st.session_state.auth_phase = "set_password"
                st.rerun()

    # FASE 2: password esistente
    elif st.session_state.auth_phase == "password":
        st.markdown("### Inserisci la tua password")
        with st.form(key="auth_form_password"):
            pwd = st.text_input("Password", type="password", key="auth_pwd_input")
            submit_pwd = st.form_submit_button("Invia Password")
        if submit_pwd:
            player = st.session_state.player
            stored = str(player.get("Password", "") if player else "")
            if pwd == stored and pwd != "":
                st.session_state.authenticated = True
                st.session_state.read_only = False
                st.session_state.user = {
                    "username": player.get("Giocatore"),
                    "role": player.get("Ruolo", "W"),
                    "collection": player["_collection"],
                    "id": str(player["_id"])
                }
                st.success("✅ Accesso con diritti di scrittura")
                st.rerun()
            else:
                st.error("Password errata")

    # FASE 3: impostazione nuova password (richiede System Password)
    elif st.session_state.auth_phase == "set_password":
        st.markdown("### Imposta la tua password (richiede System Password)")
        with st.form(key="auth_form_setpwd"):
            sys_pwd = st.text_input("System Password", type="password", key="auth_sys_pwd")
            new_pwd = st.text_input("New Password", type="password", key="auth_new_pwd")
            confirm_pwd = st.text_input("Confermare New Password", type="password", key="auth_confirm_pwd")
            submit_set = st.form_submit_button("Imposta Password")
        if submit_set:
            if not validate_system_password(sys_pwd):
                st.error("System Password non valida")
                return False
            if not new_pwd or not confirm_pwd:
                st.error("Inserisci entrambe le password")
                return False
            if new_pwd != confirm_pwd:
                st.error("Le password non coincidono")
                return False
            # Aggiorna password sul record utente
            player = st.session_state.player
            if player is None:
                st.error("Errore: utente non presente nella sessione")
                return False
            update_user_password(player, new_pwd)
            # Aggiorna il player in sessione con SetPwd=1 e Password aggiornata
            player["Password"] = new_pwd
            player["SetPwd"] = 1
            st.session_state.player = player
            st.session_state.authenticated = True
            st.session_state.read_only = False
            st.session_state.user = {
                "username": player.get("Giocatore"),
                "role": player.get("Ruolo", "W"),
                "collection": player["_collection"],
                "id": str(player["_id"])
            }
            st.success("✅ Password impostata e accesso con scrittura")
            st.rerun()

    return st.session_state.authenticated

def verify_write_access():
    return st.session_state.get("authenticated", False) and not st.session_state.get("read_only", False)

def get_current_user():
    return st.session_state.get("user")
