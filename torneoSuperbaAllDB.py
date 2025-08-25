import streamlit as st
import pandas as pd
import random
from fpdf import FPDF
from datetime import datetime
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId

# -------------------------------------------------
# CONFIG PAGINA
# -------------------------------------------------

st.set_page_config(page_title="⚽Campionato/Torneo Subbuteo", layout="wide")

# -------------------------
# STATO
# -------------------------

if 'df_torneo' not in st.session_state:
    st.session_state['df_torneo'] = pd.DataFrame()

DEFAULT_STATE = {
    'calendario_generato': False,
    'mostra_form_creazione': False,
    'girone_sel': "Girone 1",
    'giornata_sel': 1,
    'mostra_assegnazione_squadre': False,
    'mostra_gironi': False,
    'gironi_manuali_completi': False,
    'giocatori_selezionati_definitivi': [],
    'gioc_info': {},
    'navigazione_modalita': "Tendina",   # "Tendina" o "Bottoni"
    'filtro_attivo': 'Nessuno',
    'tournament_id': None,
    'nome_torneo': None
}
for k, v in DEFAULT_STATE.items():
    if k not in st.session_state:
        st.session_state[k] = v

# -------------------------------------------------
# FUNZIONI UTILI
# -------------------------------------------------

def calcola_classifica(df, girone):
    """Calcola classifica di un girone (solo partite validate)."""
    df_g = df[(df["Girone"] == girone) & (df["Validata"] == True)]
    squadre = list(set(df_g["SquadraCasa"]).union(set(df_g["SquadraTrasferta"])))
    classifica = {s: {"Punti": 0, "GF": 0, "GS": 0, "DR": 0} for s in squadre}
    for _, row in df_g.iterrows():
        sc, st = row["SquadraCasa"], row["SquadraTrasferta"]
        gc, gt = row["GolCasa"], row["GolTrasferta"]
        if pd.isna(gc) or pd.isna(gt):
            continue
        classifica[sc]["GF"] += gc
        classifica[sc]["GS"] += gt
        classifica[st]["GF"] += gt
        classifica[st]["GS"] += gc
        if gc > gt:
            classifica[sc]["Punti"] += 3
        elif gt > gc:
            classifica[st]["Punti"] += 3
        else:
            classifica[sc]["Punti"] += 1
            classifica[st]["Punti"] += 1
    for s in classifica:
        classifica[s]["DR"] = classifica[s]["GF"] - classifica[s]["GS"]
    df_class = pd.DataFrame([
        {"Squadra": s, **val} for s, val in classifica.items()
    ])
    df_class = df_class.sort_values(
        by=["Punti", "DR", "GF"], ascending=[False, False, False]
    ).reset_index(drop=True)
    return df_class

def tutte_partite_validate(df):
    """Verifica se tutte le partite sono validate."""
    return not df.empty and df["Validata"].all()

def aggiorna_nome_torneo_db(new_name):
    """Aggiorna nome torneo su DB Mongo (se collegato)."""
    if st.session_state.get("tournament_id"):
        client = MongoClient("mongodb://localhost:27017", server_api=ServerApi("1"))
        db = client["tornei_subbuteo"]
        tournaments_collection = db["tornei"]
        tournaments_collection.update_one(
            {"_id": ObjectId(st.session_state["tournament_id"])},
            {"$set": {"nome": new_name}}
        )
        st.session_state["nome_torneo"] = new_name

def mostra_banner_vincitori(df):
    """Mostra banner con vincitori di ogni girone."""
    gironi = df["Girone"].unique()
    for g in gironi:
        classifica = calcola_classifica(df, g)
        if not classifica.empty:
            vincitore = classifica.iloc[0]["Squadra"]
            st.success(f"🏆 Vincitore {g}: **{vincitore}**")

# -------------------------------------------------
# SIDEBAR
# -------------------------------------------------

st.sidebar.title("⚙️ Opzioni")

# Navigazione giornate
st.sidebar.subheader("Navigazione giornate")
st.session_state["navigazione_modalita"] = st.sidebar.radio(
    "Seleziona modalità", ["Tendina", "Bottoni"], index=0
)

if st.session_state["navigazione_modalita"] == "Tendina":
    st.session_state["giornata_sel"] = st.sidebar.selectbox(
        "Scegli giornata",
        sorted(st.session_state["df_torneo"]["Giornata"].unique()) if not st.session_state["df_torneo"].empty else [1],
        index=0
    )
else:
    giornate = sorted(st.session_state["df_torneo"]["Giornata"].unique()) if not st.session_state["df_torneo"].empty else [1]
    idx = giornate.index(st.session_state["giornata_sel"]) if st.session_state["giornata_sel"] in giornate else 0
    col1, col2, col3 = st.sidebar.columns([1,2,1])
    with col1:
        if st.button("⬅️") and idx > 0:
            st.session_state["giornata_sel"] = giornate[idx-1]
    with col2:
        st.write(f"**Giornata {st.session_state['giornata_sel']}**")
    with col3:
        if st.button("➡️") and idx < len(giornate)-1:
            st.session_state["giornata_sel"] = giornate[idx+1]

# Mostra classifica
if st.sidebar.button("Mostra classifica"):
    gironi = sorted(st.session_state["df_torneo"]["Girone"].unique()) if not st.session_state["df_torneo"].empty else []
    if gironi:
        gir_sel = st.sidebar.selectbox("Seleziona girone", gironi)
        if gir_sel:
            df_class = calcola_classifica(st.session_state["df_torneo"], gir_sel)
            st.sidebar.dataframe(df_class, use_container_width=True)

# -------------------------------------------------
# MAIN
# -------------------------------------------------

st.title("⚽ Campionato / Torneo Subbuteo")

if not st.session_state["df_torneo"].empty:
    giornata = st.session_state["giornata_sel"]
    df_giornata = st.session_state["df_torneo"][st.session_state["df_torneo"]["Giornata"] == giornata]

    st.subheader(f"Giornata {giornata}")
    st.dataframe(df_giornata, use_container_width=True)

    # Se tutte validate → aggiorna DB + banner
    if tutte_partite_validate(st.session_state["df_torneo"]):
        if st.session_state["nome_torneo"] and not st.session_state["nome_torneo"].startswith("completato_"):
            nuovo_nome = f"completato_{st.session_state['nome_torneo']}"
            aggiorna_nome_torneo_db(nuovo_nome)
        mostra_banner_vincitori(st.session_state["df_torneo"])
else:
    st.info("⚠️ Nessun torneo caricato o generato.")
