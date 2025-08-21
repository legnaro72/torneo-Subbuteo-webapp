import streamlit as st
import pandas as pd
import requests
from io import StringIO
import random
from fpdf import FPDF
from datetime import datetime
import json
import time
from pymongo import MongoClient
from pymongo.server_api import ServerApi

# --- Funzione di stile per None/nan invisibili e colorazione righe ---
def combined_style(df):
    is_dark=st.get_option("theme.base")=="dark"
    def apply_row_style(row):
        base = [''] * len(row)
        if row.name == 0:
            base = ['background-color: #d4edda; color: black'] * len(row)
        elif row.name <= 2:
            base = ['background-color: #fff3cd; color: black'] * len(row)
        return base

    def hide_none(val):
        sval = str(val).strip().lower()
        if sval in ["none", "nan", ""]:
            return 'color: transparent; text-shadow: none;'
        return ''

    styled_df = df.style.apply(apply_row_style, axis=1)
    styled_df = styled_df.map(hide_none)
    
    return styled_df
# ---------------------------------------------------------------------

st.set_page_config(page_title="⚽ Torneo Subbuteo - Sistema Svizzero", layout="wide")

# -------------------------
# Connessione a MongoDB Atlas
# -------------------------

players_collection = None
st.info("Tentativo di connessione a MongoDB...")
try:
    MONGO_URI = st.secrets["MONGO_URI"]
    server_api = ServerApi('1')
    client = MongoClient(MONGO_URI, server_api=server_api)
    
    db = client.get_database("giocatori_subbuteo")
    players_collection = db.get_collection("superba_players")  # CORRETTO qui

    _ = players_collection.find_one()
    st.success("✅ Connessione a MongoDB Atlas riuscita per la lettura dei giocatori.")
except Exception as e:
    st.error(f"❌ Errore di connessione a MongoDB: {e}. Non sarà possibile caricare i giocatori dal database.")

st.markdown("""
    <style>
    ul, li { list-style-type: none !important; padding-left: 0 !important; margin-left: 0 !important; }
    .big-title { text-align: center; font-size: clamp(16px, 4vw, 36px); font-weight: bold; margin-top: 10px; margin-bottom: 20px; color: red; word-wrap: break-word; white-space: normal; }
    div[data-testid="stNumberInput"] label::before { content: none; }
    </style>
""", unsafe_allow_html=True)


def carica_giocatori_da_db():
    if 'players_collection' in globals() and players_collection is not None:
        try:
            count = players_collection.count_documents({})
            if count == 0:
                st.warning("⚠️ La collection 'superba_players' è vuota o non esiste. Non è stato caricato alcun giocatore.")
                return pd.DataFrame()
            else:
                st.info(f"✅ Trovati {count} giocatori nel database. Caricamento in corso...")
            
            df = pd.DataFrame(list(players_collection.find()))
            
            if '_id' in df.columns:
                df = df.drop(columns=['_id'])
            
            if 'Giocatore' not in df.columns:
                st.error("❌ Errore: la colonna 'Giocatore' non è presente nel database dei giocatori.")
                return pd.DataFrame()
                
            return df
        except Exception as e:
            st.error(f"❌ Errore durante la lettura dalla collection dei giocatori: {e}")
            return pd.DataFrame()
    else:
        st.warning("⚠️ La connessione a MongoDB non è attiva.")
        return pd.DataFrame()

# --- NAVIGAZIONE COMPATTA ---
def navigation_controls(label, value, min_val, max_val, key_prefix=""):
    col1, col2, col3 = st.columns([1, 3, 1])  # pulsante - testo - pulsante

    with col1:
        if st.button("◀️", key=f"{key_prefix}_prev", use_container_width=True):
            st.session_state[value] = max(min_val, st.session_state[value] - 1)

    with col2:
        st.markdown(
            f"<div style='text-align:center; font-weight:bold;'>{label} {st.session_state[value]}</div>",
            unsafe_allow_html=True
        )

    with col3:
        if st.button("▶️", key=f"{key_prefix}_next", use_container_width=True):
            st.session_state[value] = min(max_val, st.session_state[value] + 1)

if "girone" not in st.session_state:
    st.session_state.girone = 1    # valore iniziale
if "giornata" not in st.session_state:
    st.session_state.giornata = 1 # valore iniziale
    
# RIMOZIONE DELLA FUNZIONE OBSOLETA
# def carica_giocatori_master(url=URL_GIOCATORI):
# ...


def genera_calendario_auto(giocatori, num_gironi, tipo="Solo andata"):
    random.shuffle(giocatori)
    gironi = [[] for _ in range(num_gironi)]
    for i, nome in enumerate(giocatori):
        gironi[i % num_gironi].append(nome)
    
    return genera_calendario_from_list(gironi, tipo)

def genera_calendario_from_list(gironi_popolati, tipo="Solo andata"):
    partite = []
    for idx, girone in enumerate(gironi_popolati, 1):
        g = f"Girone {idx}"
        gr = girone[:]
        if len(gr) % 2 == 1:
            gr.append("Riposo")
        n = len(gr)
        half = n // 2

        teams = gr[:]
        for giornata in range(n - 1):
            for i in range(half):
                casa, ospite = teams[i], teams[-(i+1)]
                if casa != "Riposo" and ospite != "Riposo":
                    partite.append({"Girone": g, "Giornata": giornata+1,
                                     "Casa": casa, "Ospite": ospite, "GolCasa": None, "GolOspite": None, "Valida": False})
                    if tipo == "Andata e ritorno":
                        partite.append({"Girone": g, "Giornata": giornata+1 + (n - 1),
                                         "Casa": ospite, "Ospite": casa, "GolCasa": None, "GolOspite": None, "Valida": False})
            teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    return pd.DataFrame(partite)

def aggiorna_classifica(df):
    if 'Girone' not in df.columns:
        return pd.DataFrame()

    gironi = df['Girone'].dropna().unique()
    classifiche = []

    for girone in gironi:
        partite = df[(df['Girone'] == girone) & (df['Valida'] == True)]
        if partite.empty:
            continue
        squadre = pd.unique(partite[['Casa','Ospite']].values.ravel())
        stats = {s: {'Punti':0,'V':0,'P':0,'S':0,'GF':0,'GS':0,'DR':0} for s in squadre}

        for _, r in partite.iterrows():
            try:
                gc, go = int(r['GolCasa']), int(r['GolOspite'])
            except:
                gc, go = 0, 0
            casa, ospite = r['Casa'], r['Ospite']
            stats[casa]['GF'] += gc
            stats[casa]['GS'] += go
            stats[ospite]['GF'] += go
            stats[ospite]['GS'] += gc

            if gc > go:
                stats[casa]['Punti'] += 2
                stats[casa]['V'] += 1
                stats[ospite]['S'] += 1
            elif gc < go:
                stats[ospite]['Punti'] += 2
                stats[ospite]['V'] += 1
                stats[casa]['S'] += 1
            else:
                stats[casa]['Punti'] += 1
                stats[ospite]['Punti'] += 1
                stats[casa]['P'] += 1
                stats[ospite]['P'] += 1

        for s in squadre:
            stats[s]['DR'] = stats[s]['GF'] - stats[s]['GS']

        df_stat = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index':'Squadra'})
        df_stat['Girone'] = girone
        classifiche.append(df_stat)

    if len(classifiche) == 0:
        return None

    df_classifica = pd.concat(classifiche, ignore_index=True)
    df_classifica = df_classifica.sort_values(by=['Girone','Punti','DR'], ascending=[True,False,False])
    return df_classifica

def esporta_pdf(df_torneo, df_classifica):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Calendario e Classifiche Torneo", ln=True, align='C')

    line_height = 6
    margin_bottom = 15
    page_height = 297

    gironi = df_torneo['Girone'].dropna().unique()

    for girone in gironi:
        pdf.set_font("Arial", 'B', 14)
        if pdf.get_y() + 8 + margin_bottom > page_height:
            pdf.add_page()
        pdf.cell(0, 8, f"{girone}", ln=True)

        giornate = sorted(df_torneo[df_torneo['Girone'] == girone]['Giornata'].dropna().unique())

        for g in giornate:
            needed_space = 7 + line_height + line_height + margin_bottom
            if pdf.get_y() + needed_space > page_height:
                pdf.add_page()

            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 7, f"Giornata {g}", ln=True)
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(60, 6, "Casa", border=1)
            pdf.cell(20, 6, "Gol", border=1, align='C')
            pdf.cell(20, 6, "Gol", border=1, align='C')
            pdf.cell(60, 6, "Ospite", border=1)
            pdf.ln()

            pdf.set_font("Arial", '', 11)
            # CORREZIONE: Ho sostituito 'df' con 'df_torneo'
            partite = df_torneo[(df_torneo['Girone'] == girone) & (df_torneo['Giornata'] == g)]

            for _, row in partite.iterrows():
                if pdf.get_y() + line_height + margin_bottom > page_height:
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 7, f"Giornata {g} (continua)", ln=True)
                    pdf.set_font("Arial", 'B', 11)
                    pdf.cell(60, 6, "Casa", border=1)
                    pdf.cell(20, 6, "Gol", border=1, align='C')
                    pdf.cell(20, 6, "Gol", border=1, align='C')
                    pdf.cell(60, 6, "Ospite", border=1)
                    pdf.ln()
                    pdf.set_font("Arial", '', 11)

                pdf.set_text_color(255, 0, 0) if not row['Valida'] else pdf.set_text_color(0, 0, 0)

                pdf.cell(60, 6, str(row['Casa']), border=1)
                pdf.cell(20, 6, str(row['GolCasa']) if pd.notna(row['GolCasa']) else "-", border=1, align='C')
                pdf.cell(20, 6, str(row['GolOspite']) if pd.notna(row['GolOspite']) else "-", border=1, align='C')
                pdf.cell(60, 6, str(row['Ospite']), border=1)
                pdf.ln()
            pdf.ln(3)

        if pdf.get_y() + 40 + margin_bottom > page_height:
            pdf.add_page()

        pdf.set_font("Arial", 'B', 13)
        pdf.cell(0, 8, f"Classifica {girone}", ln=True)

        df_c = df_classifica[df_classifica['Girone'] == girone]

        pdf.set_font("Arial", 'B', 11)
        headers = ["Squadra", "Punti", "V", "P", "S", "GF", "GS", "DR"]
        col_widths = [60, 15, 15, 15, 15, 15, 15, 15]
        for i, h in enumerate(headers):
            pdf.cell(col_widths[i], 6, h, border=1, align='C')
        pdf.ln()
        pdf.set_font("Arial", '', 11)
        for _, r in df_c.iterrows():
            if pdf.get_y() + line_height + margin_bottom > page_height:
                pdf.add_page()
                pdf.set_font("Arial", 'B', 11)
                for i, h in enumerate(headers):
                    pdf.cell(col_widths[i], 6, h, border=1, align='C')
                pdf.ln()
                pdf.set_font("Arial", '', 11)

            pdf.cell(col_widths[0], 6, str(r['Squadra']), border=1)
            pdf.cell(col_widths[1], 6, str(r['Punti']), border=1, align='C')
            pdf.cell(col_widths[2], 6, str(r['V']), border=1, align='C')
            pdf.cell(col_widths[3], 6, str(r['P']), border=1, align='C')
            pdf.cell(col_widths[4], 6, str(r['S']), border=1, align='C')
            pdf.cell(col_widths[5], 6, str(r['GF']), border=1, align='C')
            pdf.cell(col_widths[6], 6, str(r['GS']), border=1, align='C')
            pdf.cell(col_widths[7], 6, str(r['DR']), border=1, align='C')
            pdf.ln()
        pdf.ln(10)

    pdf_bytes = pdf.output(dest='S').encode('latin1')
    return pdf_bytes

def mostra_calendario_giornata(df, girone_sel, giornata_sel):
    df_giornata = df[(df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel)].copy()
    if 'Valida' not in df_giornata.columns:
        df_giornata['Valida'] = False

    def safe_int(val):
        try:
            sval = str(val).strip().lower()
            if sval in ["none", "nan", ""] or not sval.isdigit():
                return 0
            return int(float(val))
        except (ValueError, TypeError):
            return 0

    for idx, row in df_giornata.iterrows():
        casa = row['Casa']
        ospite = row['Ospite']
        val = row['Valida']

        col1, col2, col3, col4, col5 = st.columns([5, 1.5, 1, 1.5, 1])

        with col1:
            st.markdown(f"**{casa}** vs **{ospite}**")

        with col2:
            st.number_input(
                "", min_value=0, max_value=20,
                key=f"golcasa_{idx}",
                value=safe_int(row['GolCasa']),
                label_visibility="hidden"
            )

        with col3:
            st.markdown("-")

        with col4:
            st.number_input(
                "", min_value=0, max_value=20,
                key=f"golospite_{idx}",
                value=safe_int(row['GolOspite']),
                label_visibility="hidden"
            )

        with col5:
            st.checkbox(
                "Valida",
                key=f"valida_{idx}",
                value=val
            )
        
        if st.session_state.get(f"valida_{idx}", False):
            st.markdown("<hr>", unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:red; margin-bottom: 15px;">Partita non ancora validata ❌</div>', unsafe_allow_html=True)

    def salva_risultati_giornata():
        df = st.session_state['df_torneo']
        df_giornata_copia = df[(df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel)].copy()
        for idx, _ in df_giornata_copia.iterrows():
            df.at[idx, 'GolCasa'] = st.session_state[f"golcasa_{idx}"]
            df.at[idx, 'GolOspite'] = st.session_state[f"golospite_{idx}"]
            df.at[idx, 'Valida'] = st.session_state[f"valida_{idx}"]
