import streamlit as st
import pandas as pd
from datetime import datetime
import random
import time
from fpdf import FPDF
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson import ObjectId

# =============================
# Connessione a MongoDB
# =============================
@st.cache_resource
def init_connection():
    try:
        # 🔍 Debug: stampo le chiavi dei secrets disponibili
        st.write("🔑 Secrets disponibili:", list(st.secrets.keys()))
        
        mongo_uri=st.secrets["MONGO_URI"]
        st.write("✅ Uso MONGO_URI da secrets.toml")
    except KeyError:
        # Fallback: se non trova MONGO_URI nei secrets
        st.warning("⚠️ MONGO_URI non trovato nei secrets. Uso URI di fallback hardcoded.")
        mongo_uri = "mongodb+srv://utente:password@cluster.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
    
    return MongoClient(mongo_uri, server_api=ServerApi("1"))
# Collezioni
players_collection = client["giocatori_subbuteo"]["superba_players"]
tournaments_collection = db["tournaments"]
matches_collection = db["matches"]
standings_collection = db["standings"]

# =============================
# Funzioni utilità DB
# =============================
def get_players():
    players = list(players_collection.find({}, {"_id": 0}))
    return pd.DataFrame(players)

def create_tournament(name, players):
    tournament = {"name": name, "created_at": datetime.now()}
    tournament_id = tournaments_collection.insert_one(tournament).inserted_id

    # genera calendario base (round robin semplice)
    matches = []
    players_list = players["Giocatore"].tolist()
    random.shuffle(players_list)

    for i in range(len(players_list)):
        for j in range(i+1, len(players_list)):
            matches.append({
                "tournament_id": tournament_id,
                "player1": players_list[i],
                "player2": players_list[j],
                "score1": None,
                "score2": None,
                "validated": False
            })

    matches_collection.insert_many(matches)
    return tournament_id

def get_matches(tournament_id):
    return list(matches_collection.find({"tournament_id": ObjectId(tournament_id)}))

def update_match(match_id, score1, score2, validated):
    matches_collection.update_one(
        {"_id": ObjectId(match_id)},
        {"$set": {
            "score1": score1,
            "score2": score2,
            "validated": validated
        }}
    )

def calculate_standings(tournament_id):
    matches = matches_collection.find({
        "tournament_id": ObjectId(tournament_id),
        "validated": True
    })

    stats = {}
    for m in matches:
        p1, p2 = m["player1"], m["player2"]
        s1, s2 = m["score1"], m["score2"]

        for p in [p1, p2]:
            if p not in stats:
                stats[p] = {"Punti": 0, "Giocate": 0, "Vinte": 0, "Pareggi": 0, "Perse": 0, "GF": 0, "GS": 0}

        stats[p1]["Giocate"] += 1
        stats[p2]["Giocate"] += 1
        stats[p1]["GF"] += s1
        stats[p1]["GS"] += s2
        stats[p2]["GF"] += s2
        stats[p2]["GS"] += s1

        if s1 > s2:
            stats[p1]["Punti"] += 3
            stats[p1]["Vinte"] += 1
            stats[p2]["Perse"] += 1
        elif s1 < s2:
            stats[p2]["Punti"] += 3
            stats[p2]["Vinte"] += 1
            stats[p1]["Perse"] += 1
        else:
            stats[p1]["Punti"] += 1
            stats[p2]["Punti"] += 1
            stats[p1]["Pareggi"] += 1
            stats[p2]["Pareggi"] += 1

    standings_df = pd.DataFrame([
        {"Giocatore": p, **v} for p, v in stats.items()
    ])
    standings_df.sort_values(by=["Punti", "GF"], ascending=False, inplace=True)

    standings_collection.update_one(
        {"tournament_id": ObjectId(tournament_id)},
        {"$set": {"standings": standings_df.to_dict(orient="records")}},
        upsert=True
    )

    return standings_df

# =============================
# Streamlit UI
# =============================
st.set_page_config(page_title="⚽ Torneo Subbuteo - MongoDB", layout="wide")

st.title("⚽ Torneo Subbuteo - Gestione completa su MongoDB")

# Selezione torneo
tournaments = list(tournaments_collection.find())
tournament_names = {str(t["_id"]): t["name"] for t in tournaments}

tournament_id = st.selectbox("Seleziona torneo", [""] + list(tournament_names.keys()), format_func=lambda x: tournament_names.get(x, ""))

if not tournament_id:
    st.subheader("Crea nuovo torneo")
    nome = st.text_input("Nome torneo")
    if st.button("Crea"):
        players_df = get_players()
        if players_df.empty:
            st.error("Nessun giocatore trovato in DB!")
        else:
            new_id = create_tournament(nome, players_df)
            st.success(f"Torneo '{nome}' creato!")
            st.experimental_rerun()
else:
    st.subheader(f"Torneo: {tournament_names[tournament_id]}")

    tab1, tab2, tab3 = st.tabs(["📋 Partite", "🏆 Classifica", "📄 Export"])

    with tab1:
        matches = get_matches(tournament_id)
        for m in matches:
            col1, col2, col3, col4, col5 = st.columns([2,1,1,1,1])
            with col1:
                st.write(f"{m['player1']} - {m['player2']}")
            with col2:
                s1 = st.number_input("G1", value=m["score1"] if m["score1"] is not None else 0, key=f"s1_{m['_id']}")
            with col3:
                s2 = st.number_input("G2", value=m["score2"] if m["score2"] is not None else 0, key=f"s2_{m['_id']}")
            with col4:
                val = st.checkbox("Validata", value=m["validated"], key=f"val_{m['_id']}")
            with col5:
                if st.button("Salva", key=f"save_{m['_id']}"):
                    update_match(m["_id"], s1, s2, val)
                    st.success("Aggiornato!")
                    st.experimental_rerun()

    with tab2:
        standings = calculate_standings(tournament_id)
        st.dataframe(standings)

    with tab3:
        if st.button("Esporta PDF Classifica"):
            standings = calculate_standings(tournament_id)

            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", "B", 16)
            pdf.cell(200, 10, txt="Classifica Torneo Subbuteo", ln=True, align="C")

            pdf.set_font("Arial", size=12)
            for idx, row in standings.iterrows():
                line = f"{row['Giocatore']} - {row['Punti']} pts"
                pdf.cell(200, 10, txt=line, ln=True)

            pdf.output("classifica.pdf")
            with open("classifica.pdf", "rb") as f:
                st.download_button("Scarica PDF", f, file_name="classifica.pdf")