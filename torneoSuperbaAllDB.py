import streamlit as st
from pymongo import MongoClient
from pymongo.server_api import ServerApi

st.title("Test connessione MongoDB")

# Debug: mostra chiavi disponibili nei secrets
st.write("Chiavi disponibili nei secrets:", list(st.secrets.keys()))

players_collection = None

try:
    # Recupero la stringa di connessione dal secrets.toml
    MONGO_URI = st.secrets["MONGO_URI"]

    # Creo client Mongo
    client = MongoClient(MONGO_URI, server_api=ServerApi("1"))

    # Connetto al database e alla collection
    db = client.get_database("giocatori_subbuteo")
    players_collection = db.get_collection("superba_players")

    # Test query
    uno = players_collection.find_one()
    st.success("✅ Connessione a MongoDB Atlas riuscita!")
    st.json(uno)

except Exception as e:
    st.error(f"❌ Errore di connessione a MongoDB: {e}")
