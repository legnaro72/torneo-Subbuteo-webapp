import streamlit as st
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
import os
from datetime import datetime
import certifi

# Configurazione connessione MongoDB
MONGO_URI = os.getenv("MONGO_URI_AUTH", "mongodb+srv://massimilianoferrando:Legnaro21!$@cluster0.t3750lc.mongodb.net/")
DB_PWD = "Password"
AUTH_COLLECTION = "auth_password"
DB_NAME_PLAYERS = "giocatori_subbuteo"
PLAYERS_COLLECTION1 = "superba_players"
PLAYERS_COLLECTION2 = "piercrew_players"
PLAYERS_COLLECTION3 = "tigullio_players"

# Database e collezione Login
DB_Login = "Log"
LOG_COLLECTION = "Login"

def get_mongo_client():
    return MongoClient(MONGO_URI,
                     server_api=ServerApi('1'),
                     connectTimeoutMS=5000,
                     serverSelectionTimeoutMS=5000,
                     tlsCAFile=certifi.where())

def log_event(username: str, esito: str, dettagli: dict = None):
    """
    Salva un log nella collezione 'Login' del DB 'Log'.
    """
    try:
        client = get_mongo_client()
        db_Login = client[DB_Login]
        Login_coll = db_Login[LOG_COLLECTION]
        log_entry = {
            "timestamp": datetime.utcnow(),
            "username": username,
            "esito": esito,
            "dettagli": dettagli or {}
        }
        Login_coll.insert_one(log_entry)
    except Exception as e:
        print(f"Errore durante il logging: {e}")

def find_user(username: str, club: str = None):
    """
    Cerca un utente nel database.
    """
    client = get_mongo_client()
    db_players = client[DB_NAME_PLAYERS]

    collections = []
    if club == 'Superba':
        collections = [PLAYERS_COLLECTION1]
    elif club == 'PierCrew':
        collections = [PLAYERS_COLLECTION2]
    elif club == 'Tigullio':
        collections = [PLAYERS_COLLECTION3]
    else:
        collections = [PLAYERS_COLLECTION1, PLAYERS_COLLECTION2, PLAYERS_COLLECTION3]

    for coll in collections:
        try:
            player = db_players[coll].find_one({"Giocatore": {'$regex': f'^{username}$', '$options': 'i'}})
            if player:
                player["_collection"] = coll
                return player
        except Exception as e:
            print(f"Errore durante la ricerca nella collection {coll}: {e}")

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
    # Log impostazione nuova password
    log_event(player.get("Giocatore", "Sconosciuto"), "Impostazione nuova password", {
        "azione": "Cambio password",
        "club": player.get("_collection")
    })

def show_auth_screen(club: str = "Superba"):
    """
    Mostra la schermata di autenticazione.
    """
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "read_only" not in st.session_state:
        st.session_state.read_only = False
    if "auth_phase" not in st.session_state:
        st.session_state.auth_phase = "username"
    if "player" not in st.session_state:
        st.session_state.player = None
    if "club" not in st.session_state:
        st.session_state.club = club

    if st.session_state.authenticated:
        return True

    st.title("🔐 Accesso al Torneo Subbuteo")

    # FASE 1: username
    if st.session_state.auth_phase == "username":
        with st.form(key="auth_form_username"):
            username = st.text_input("Username", key="auth_username")
            col1, col2 = st.columns([1, 2])
            with col1:
                submitted = st.form_submit_button("Accedi")
            with col2:
                guest_submitted = st.form_submit_button("Accedi come ospite")

            if guest_submitted:
                st.session_state.authenticated = True
                st.session_state.read_only = True
                st.session_state.user = {
                    "username": "Ospite",
                    "role": "G",
                    "collection": "guests",
                    "id": None
                }
                log_event("Ospite", "Accesso riuscito", {"ruolo": "Guest"})
                st.rerun()

        if submitted:
            if not username:
                st.error("Inserisci lo username")
                return False

            log_event(username, "Inserimento username", {"azione": "Tentativo Log", "club": st.session_state.club})

            player = find_user(username, st.session_state.club)
            if not player:
                st.error(f"Utente non trovato nel club {st.session_state.club}")
                log_event(username, "Utente non trovato", {"motivo": "Username inesistente", "club": st.session_state.club})
                return False

            st.session_state.player = player
            ruolo = player.get("Ruolo", "R")

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
                log_event(player.get("Giocatore"), "Accesso riuscito", {"club": player["_collection"], "ruolo": ruolo})
                st.rerun()
            else:
                if int(player.get("SetPwd", 0)) == 1:
                    st.session_state.auth_phase = "password"
                else:
                    st.session_state.auth_phase = "set_password"
                st.rerun()

    # FASE 2: password
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
                log_event(player.get("Giocatore"), "Accesso riuscito", {"club": player["_collection"], "ruolo": player.get("Ruolo", "W")})
                st.rerun()
            else:
                st.error("Password errata")
                log_event(player.get("Giocatore", "Sconosciuto"), "Password errata", {"motivo": "Password non corrispondente"})

    # FASE 3: impostazione nuova password
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
                log_event(st.session_state.player.get("Giocatore", "Sconosciuto"), "Password non impostata", {"motivo": "System password errata"})
                return False
            if not new_pwd or not confirm_pwd:
                st.error("Inserisci entrambe le password")
                return False
            if new_pwd != confirm_pwd:
                st.error("Le password non coincidono")
                return False

            player = st.session_state.player
            if player is None:
                st.error("Errore: utente non presente nella sessione")
                return False

            update_user_password(player, new_pwd)
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
            log_event(player.get("Giocatore"), "Impostazione nuova password", {"club": player["_collection"], "ruolo": player.get("Ruolo", "W")})
            st.rerun()

    return st.session_state.authenticated

def verify_write_access():
    return st.session_state.get("authenticated", False) and not st.session_state.get("read_only", False)

def get_current_user():
    return st.session_state.get("user")
