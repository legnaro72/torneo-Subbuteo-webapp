import streamlit as st
import pandas as pd
from pymongo import MongoClient
from pymongo.server_api import ServerApi
import requests
from io import StringIO
import random
from fpdf import FPDF
from datetime import datetime
import json
import time


st.write("Chiavi disponibili nei secrets:", list(st.secrets.keys()))

# Variabili globali per i DB
players_client=None
tournaments_client=None
players_collection=None
tournaments_collection=None
players_db=None
tournaments_db=None

# -------------------------
# Connessione a MongoDB Atlas
# -------------------------

players_collection = None
st.info("Tentativo di connessione a MongoDB...")
try:
    MONGO_URI = st.secrets["MONGO_URI"]
    server_api = ServerApi('1')
    client = MongoClient(MONGO_URI, server_api=server_api)
    
    # Ho corretto il nome del database e della collection
    db = client.get_database("giocatori_subbuteo")
    players_collection = db.get_collection("superba_players") 

    _ = players_collection.find_one()
    st.success("✅ Connessione a MongoDB Atlas riuscita per la lettura dei giocatori.")
except Exception as e:
    st.error(f"❌ Errore di connessione a MongoDB: {e}. Non sarà possibile caricare i giocatori dal database.")# -------------------------
