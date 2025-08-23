import streamlit as st
from pymongo import MongoClient
from pymongo.server_api import ServerApi

st.title("Test connessione MongoDB")

# Debug: mostra chiavi disponibili nei secrets
st.write("Chiavi disponibili nei secrets:", list(st.secrets.keys()))

# -------------------------
# Connessione a MongoDB Atlas - Giocatori
# -------------------------

players_collection = None
tournaments_collection = None
server_api = ServerApi('1')  # riusabile per entrambi

try:
    # Connessione Giocatori
    MONGO_URI = st.secrets["MONGO_URI"]
    client_players = MongoClient(MONGO_URI, server_api=server_api)

    db_players = client_players.get_database("giocatori_subbuteo")
    players_collection = db_players.get_collection("superba_players")

    _ = players_collection.find_one()
    st.success("✅ Connessione a MongoDB Atlas (giocatori) riuscita.")

except Exception as e:
    st.error(f"❌ Errore di connessione a MongoDB (giocatori): {e}")


# -------------------------
# Connessione a MongoDB Atlas - Tournaments
# -------------------------

try:
    # Connessione Tournaments
    MONGO_URI_TOURNAMENTS = st.secrets["MONGO_URI_TOURNAMENTS"]
    client_tournaments = MongoClient(MONGO_URI_TOURNAMENTS, server_api=server_api)

    db_tournaments = client_tournaments.get_database("subbuteo_tournament")
    tournaments_collection = db_tournaments.get_collection("tournament")

    _ = tournaments_collection.find_one()
    st.success("✅ Connessione a MongoDB Atlas (tournaments) riuscita.")

except Exception as e:
    st.error(f"❌ Errore di connessione a MongoDB (tournaments): {e}")
