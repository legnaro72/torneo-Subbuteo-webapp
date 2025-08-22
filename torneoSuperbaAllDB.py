import streamlit as st
import pandas as pd
from pymongo import MongoClient
from pymongo.server_api import ServerApi

st.write("Chiavi disponibili nei secrets:", list(st.secrets.keys()))

# -------------------------
# Connessione a MongoDB Atlas
# -------------------------

# Variabili globali per i DB
players_client=None
tournaments_client=None
players_collection=None
tournaments_collection=None
players_db=None
tournaments_db=None

st.info("Tentativo di connessione ai database...")

try:
    # Connessione al database dei giocatori
    MONGO_URI=st.secrets["MONGO_URI"]
    players_client=MongoClient(MONGO_URI, server_api=ServerApi("1"))
    players_client.admin.command("ping")  # test ping
    players_db=players_client.get_database("giocatori_subbuteo")
    players_collection=players_db.get_collection("superba_players")
    st.success("✅ Connessione al database giocatori riuscita!")

    # Connessione al database dei tornei
    MONGO_URI_TOURNAMENTS=st.secrets["MONGO_URI_TOURNAMENTS"]
    tournaments_client=MongoClient(MONGO_URI_TOURNAMENTS, server_api=ServerApi("1"))
    tournaments_client.admin.command("ping")  # test ping
    tournaments_db=tournaments_client.get_database("subbuteo_tournaments")
    tournaments_collection=tournaments_db.get_collection("tournaments")
    st.success("✅ Connessione al database tornei riuscita!")

except KeyError as e:
    st.error(f"❌ Errore: manca la chiave '{e}'. Aggiungi MONGO_URI e MONGO_URI_TOURNAMENTS in st.secrets.")
    players_collection=None
    tournaments_collection=None
except Exception as e:
    st.error(f"❌ Errore di connessione a MongoDB: {e}")
    players_collection=None
    tournaments_collection=None
