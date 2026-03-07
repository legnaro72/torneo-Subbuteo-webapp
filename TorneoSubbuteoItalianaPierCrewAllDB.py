import streamlit as st

# Configurazione pagina (DEVE essere il primo comando Streamlit)
st.set_page_config(
    page_title="Torneo Subbuteo",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

import pandas as pd
import numpy as np
import json
import os
import time
import datetime
import pytz
from datetime import datetime, timedelta
import pymongo
from pymongo import MongoClient
import certifi
import random
import string
import hashlib
import hmac
import base64
import urllib.parse
import urllib3
import requests
import io
from PIL import Image
import base64
from io import BytesIO
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import matplotlib.patches as patches
from matplotlib.colors import LinearSegmentedColormap
import matplotlib as mpl
import seaborn as sns
from bson import ObjectId
from streamlit_modal import Modal
import streamlit.components.v1 as components
import plotly.express as px
import plotly.graph_objects as go
from streamlit_extras.switch_page_button import switch_page
import pytz
from streamlit_modal import Modal
import seaborn as sns

# Importa il modulo di autenticazione centralizzato
import auth_utils as auth
from auth_utils import verify_write_access

# Importa moduli comuni per stili, audio e componenti UI
from common.styles import inject_all_styles
from common.audio import (
    autoplay_background_audio, autoplay_audio, 
    toggle_audio_callback, start_background_audio, setup_audio_sidebar
)
from common.ui_components import (
    render_tournament_header, setup_common_sidebar, 
    setup_player_selection_mode, navigation_buttons,
    enable_session_keepalive
)

# Configurazione della pagina
# Configurazione pagina spostata all'inizio

# ==============================================================================
# ISTRUZIONE DEFINITIVA: AVVIO AUDIO DI SOTTOFONDO PERSISTENTE
# ==============================================================================
# Definisci la tua URL raw per l'audio di sfondo
BACKGROUND_AUDIO_URL = "https://raw.githubusercontent.com/legnaro72/torneo-Subbuteo-webapp/main/Gianna%20Nannini%20%26%20Edoardo%20Bennato%20-%20UNESTATE%20ITALIANA%20(Videoclip%20Italia%2090).mp3"
HUB_URL = "https://farm-tornei-subbuteo-piercrew-all-db.streamlit.app/"

# -------------------------
# GESTIONE DELLO STATO E FUNZIONI INIZIALI
# -------------------------
if 'df_torneo' not in st.session_state:
    st.session_state['df_torneo'] = pd.DataFrame()

from logging_utils import log_action

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
    'usa_bottoni': False,
    'filtro_attivo': 'Nessuno',  # stato per i filtri
    'azione_scelta': None,   # <-- aggiunta
    'giocatori_ritirati': [],
    'usa_multiselect_giocatori': False,  # REQUISITO 1: Default False = Checkbox Individuali
    'usa_nomi_come_squadre': False,     # REQUISITO 4
    'bg_audio_disabled': False
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value

def reset_app_state():
    for key in list(st.session_state.keys()):
        if key not in ['df_torneo', 'sidebar_state_reset']:
            st.session_state.pop(key)
    st.session_state.update(DEFAULT_STATE)
    st.session_state['df_torneo'] = pd.DataFrame()

# -------------------------
# FUNZIONI CONNESSIONE MONGO (SENZA SUCCESS VERDI)
# -------------------------
@st.cache_resource
def _get_italiana_client(uri):
    """Crea e cache il client MongoDB per evitare riconnessioni ad ogni rerun."""
    return MongoClient(uri, server_api=ServerApi('1'))

def init_mongo_connection(uri, db_name, collection_name, show_ok: bool = False):
    """
    Se show_ok=True mostra un messaggio di ok.
    Di default è False per evitare i badge verdi.
    Usa un client cached per massima fluidità.
    """
    try:
        client = _get_italiana_client(uri)
        db = client.get_database(db_name)
        col = db.get_collection(collection_name)
        _ = col.find_one({})
        if show_ok:
            st.info(f"Connessione a {db_name}.{collection_name} ok.")
        return col
    except Exception as e:
        st.error(f"❌ Errore di connessione a {db_name}.{collection_name}: {e}")
        return None

# -------------------------
# UTILITY — le funzioni audio, toggle e navigation_buttons sono ora importate da common/
# -------------------------

# -------------------------
# FUNZIONI DI GESTIONE DATI SU MONGO
# -------------------------
@st.cache_data(ttl=60)
def carica_giocatori_da_db(_players_collection):
    """Carica giocatori dal DB (cached per 60 secondi per fluidità)."""
    if _players_collection is None:
        return pd.DataFrame()
    try:
        df = pd.DataFrame(list(_players_collection.find({}, {"_id": 0})))
        return df if not df.empty else pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Errore durante la lettura dei giocatori: {e}")
        return pd.DataFrame()

def carica_tornei_da_db(tournaments_collection):
    if tournaments_collection is None:
        return []
    try:
        return list(tournaments_collection.find({}, {"nome_torneo": 1}))
    except Exception as e:
        st.error(f"❌ Errore caricamento tornei: {e}")
        return []

def carica_torneo_da_db(tournaments_collection, tournament_id):
    if tournaments_collection is None:
        return None
    try:
        torneo_data = tournaments_collection.find_one({"_id": ObjectId(tournament_id)})
        if torneo_data and 'calendario' in torneo_data:
            df_torneo = pd.DataFrame(torneo_data['calendario'])
            df_torneo['Valida'] = df_torneo['Valida'].astype(bool)
            # Pulisci e converti esplicitamente
            df_torneo['GolCasa'] = pd.to_numeric(df_torneo['GolCasa'], errors='coerce')
            df_torneo['GolOspite'] = pd.to_numeric(df_torneo['GolOspite'], errors='coerce')
            df_torneo = df_torneo.fillna(0)
            df_torneo['GolCasa'] = df_torneo['GolCasa'].astype('Int64')
            df_torneo['GolOspite'] = df_torneo['GolOspite'].astype('Int64')
            st.session_state['df_torneo'] = df_torneo
            # Salva l'ID del torneo nella sessione
            st.session_state['tournament_id'] = str(torneo_data['_id'])
            st.session_state['nome_torneo'] = torneo_data.get('nome_torneo', 'Torneo senza nome')
        return torneo_data
    except Exception as e:
        st.error(f"❌ Errore caricamento torneo: {e}")
        return None

def salva_torneo_su_db(tournaments_collection, df_torneo, nome_torneo, tournament_id=None):
    if tournaments_collection is None:
        return None
    try:
        df_torneo_pulito = df_torneo.where(pd.notna(df_torneo), None)
        data = {"nome_torneo": nome_torneo, "calendario": df_torneo_pulito.to_dict('records')}
        
        # Se abbiamo un ID torneo, aggiorniamo il torneo esistente
        if tournament_id:
            tournaments_collection.update_one(
                {"_id": ObjectId(tournament_id)},
                {"$set": data}
            )
            # logging: aggiornamento torneo
            try:
                user = st.session_state.get('user', 'unknown') if 'st' in globals() else 'system'
                log_action(
                    username=user,
                    action='creatorneo',
                    torneo=nome_torneo,
                    details={'torneo_id': str(result.inserted_id)}
                )
            except Exception as e:
                print(f"[LOGGING] errore in salva_torneo_su_db (update): {e}")
            return tournament_id
        else:
            # Altrimenti creiamo un nuovo torneo
            result = tournaments_collection.insert_one(data)
            # logging: creazione torneo
            try:
                user = st.session_state.get('user', 'unknown') if 'st' in globals() else 'system'
                log_action(
                    username=user,
                    action='creatorneo',
                    torneo=nome_torneo,
                    details={'torneo_id': str(result.inserted_id)}
                )
            except Exception as e:
                print(f"[LOGGING] errore in salva_torneo_su_db (insert): {e}")
            return result.inserted_id
    except Exception as e:
        st.error(f"❌ Errore salvataggio torneo: {e}")
        return None

def aggiorna_torneo_su_db(tournaments_collection, tournament_id, df_torneo):
    if tournaments_collection is None:
        return False
    try:
        df_torneo_pulito = df_torneo.where(pd.notna(df_torneo), None)
        tournaments_collection.update_one(
            {"_id": ObjectId(tournament_id)},
            {"$set": {"calendario": df_torneo_pulito.to_dict('records')}}
        )
        # logging: aggiornamento torneo
        try:
            user = st.session_state.get('user', 'unknown') if 'st' in globals() else 'system'
            log_action(
                username=user,
                action='aggiorna_torneo',
                torneo=st.session_state.get('nome_torneo'),
                details={'torneo_id': str(tournament_id), 'num_match': ...}
            )
        except Exception as e:
            print(f"[LOGGING] errore in aggiorna_torneo_su_db: {e}")
        return True
    except Exception as e:
        st.error(f"❌ Errore aggiornamento torneo: {e}")
        return False
        
def redirect_to_final_phase(torneo_nome):
    """Reindirizza l'utente allo script delle fasi finali."""
    redirect_url = f"https://torneo-subbuteo-ff-piercrew-ita-all-db.streamlit.app/?torneo={urllib.parse.quote(torneo_nome)}"
    st.markdown(
        f"""
        <script>
            window.location.href = "{redirect_url}";
        </script>
        <p style="text-align:center; font-size:1.2rem;">
            ⏳ Reindirizzamento in corso...<br>
            Se non parte entro pochi secondi <a href="{redirect_url}" style="font-size:1.5em; font-weight:bold;">clicca qui 👈</a>
        </p>
        """,
        unsafe_allow_html=True
    )
    # Per fermare l'esecuzione dello script attuale dopo il reindirizzamento
    st.stop()
# -------------------------
# CALENDARIO & CLASSIFICA LOGIC
# -------------------------
def genera_calendario_from_list(gironi, tipo="Solo andata"):
    partite = []
    for idx, girone in enumerate(gironi, 1):
        gname = f"Girone {idx}"
        gr = girone[:]
        if len(gr) % 2 == 1:
            gr.append("Riposo")
        n = len(gr)
        half = n // 2
        teams = gr[:]

        for giornata in range(n - 1):
            for i in range(half):
                casa, ospite = teams[i], teams[-(i + 1)]
                if casa != "Riposo" and ospite != "Riposo":
                    partite.append({
                        "Girone": gname, "Giornata": giornata + 1,
                        "Casa": casa, "Ospite": ospite, "GolCasa": 0, "GolOspite": 0, "Valida": False
                    })
                    if tipo == "Andata e ritorno":
                        partite.append({
                            "Girone": gname, "Giornata": giornata + 1 + n - 1,
                            "Casa": ospite, "Ospite": casa, "GolCasa": 0, "GolOspite": 0, "Valida": False
                        })
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
        squadre = pd.unique(partite[['Casa', 'Ospite']].values.ravel())
        stats = {s: {'Punti': 0, 'G': 0, 'V': 0, 'P': 0, 'S': 0, 'GF': 0, 'GS': 0, 'DR': 0} for s in squadre}
        for _, r in partite.iterrows():
            gc, go = int(r['GolCasa'] or 0), int(r['GolOspite'] or 0)
            casa, ospite = r['Casa'], r['Ospite']
            stats[casa]['G'] += 1
            stats[ospite]['G'] += 1
            stats[casa]['GF'] += gc; stats[casa]['GS'] += go
            stats[ospite]['GF'] += go; stats[ospite]['GS'] += gc
            if gc > go:
                stats[casa]['Punti'] += 2; stats[casa]['V'] += 1; stats[ospite]['S'] += 1
            elif gc < go:
                stats[ospite]['Punti'] += 2; stats[ospite]['V'] += 1; stats[casa]['S'] += 1
            else:
                stats[casa]['Punti'] += 1; stats[ospite]['Punti'] += 1; stats[casa]['P'] += 1; stats[ospite]['P'] += 1
        for s in squadre:
            stats[s]['DR'] = stats[s]['GF'] - stats[s]['GS']
        df_stat = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index': 'Squadra'})
        df_stat['Girone'] = girone
        classifiche.append(df_stat)
    if not classifiche:
        return pd.DataFrame()
    df_classifica = pd.concat(classifiche, ignore_index=True)
    
    # Aggiungi una colonna 'Ritirato'
    giocatori_ritirati = st.session_state.get('giocatori_ritirati', [])
    df_classifica['Ritirato'] = df_classifica['Squadra'].apply(lambda x: x in giocatori_ritirati)
    
    df_classifica = df_classifica.sort_values(by=['Girone', 'Punti', 'DR'], ascending=[True, False, False])
    return df_classifica

# -------------------------
# FUNZIONI DI VISUALIZZAZIONE & EVENTI
# -------------------------
import streamlit as st
import pandas as pd
import random
from fpdf import FPDF
from datetime import datetime
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
import json
import urllib.parse
import requests
import base64
import time
import re # Aggiungi la libreria 're' per le espressioni regolari


def parse_team_player(val):
    if isinstance(val, str) and "-" in val:
        squadra, giocatore = val.split("-", 1)
        return squadra.strip(), giocatore.strip()
    return val, ""

def mostra_calendario_giornata(df, girone_sel, giornata_sel, modalita_visualizzazione):
    df_giornata = df[(df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel)].copy()
    if df_giornata.empty:
        st.info("📅 Nessuna partita per questa giornata.")
        return

    giocatore_map = {}
    if 'df_squadre' in st.session_state and not st.session_state.df_squadre.empty:
        giocatore_map = dict(zip(st.session_state.df_squadre['Squadra'], st.session_state.df_squadre['Giocatore']))

    if not giocatore_map:
        st.warning("⚠️ Dati delle squadre non trovati. Assicurati che il torneo sia stato inizializzato correttamente.")
    
    for idx, row in df_giornata.iterrows():
        squadra_casa, giocatore_casa = parse_team_player(row['Casa'])
        squadra_ospite, giocatore_ospite = parse_team_player(row['Ospite'])
        
        with st.container(border=True):
            stringa_partita = ""
            if modalita_visualizzazione == 'completa':
                stringa_partita = f"🏠{squadra_casa} ({giocatore_casa}) 🆚 {squadra_ospite} ({giocatore_ospite})🛫"
            elif modalita_visualizzazione == 'squadre':
                stringa_partita = f"🏠{squadra_casa} 🆚 {squadra_ospite}🛫"
            elif modalita_visualizzazione == 'giocatori':
                stringa_partita = f"🏠{giocatore_casa} 🆚 {giocatore_ospite}🛫"
            
            st.markdown(f"<p style='text-align:center; font-weight:bold;'>⚽ Partita</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align:center; font-weight:bold;'>{stringa_partita}</p>", unsafe_allow_html=True)
            
            c_score1, c_score2 = st.columns(2)
            with c_score1:
                # Chiave unica che usa i valori originali del DataFrame, garantendo la coerenza
                key_golcasa = f"golcasa_{girone_sel}_{giornata_sel}_{row['Casa']}_{row['Ospite']}"
                st.number_input(
                    "Gol Casa",
                    min_value=0, max_value=20,
                    key=key_golcasa,
                    value=int(row['GolCasa']) if pd.notna(row['GolCasa']) else 0,
                    disabled=row['Valida'],
                    #label_visibility="hidden"
                )
          
            with c_score2:
                # Chiave unica che usa i valori originali del DataFrame, garantendo la coerenza
                key_golospite = f"golospite_{girone_sel}_{giornata_sel}_{row['Casa']}_{row['Ospite']}"
                st.number_input(
                    "Gol Ospite",
                    min_value=0, max_value=20,
                    key=key_golospite,
                    value=int(row['GolOspite']) if pd.notna(row['GolOspite']) else 0,
                    disabled=row['Valida'],
                    #label_visibility="hidden"
                )
            
            st.divider()
            # Chiave unica che usa i valori originali del DataFrame, garantendo la coerenza
            key_valida = f"valida_{girone_sel}_{giornata_sel}_{row['Casa']}_{row['Ospite']}"
            st.checkbox(
                "✅ Valida",
                key=key_valida,
                value=bool(row['Valida']) if pd.notna(row['Valida']) else False,
                disabled=st.session_state.get('read_only', False)
            )
            
            is_valid = st.session_state.get(key_valida, False)
            if is_valid:
                st.success("✅ Partita validata!")
            else:
                st.warning("⚠️ Partita non ancora validata.")

def mostra_calendario_premium(df, girone_sel, giornata_sel, modalita_visualizzazione):
    """Visualizzazione ultra-moderna (stile bracket card) per inserimento risultati."""
    df_giornata = df[(df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel)].copy()
    if df_giornata.empty:
        return

    st.markdown(f"### 🏆 {girone_sel} - Giornata {giornata_sel} (Vista Premium)")
    
    # CSS locale per la vista premium
    st.markdown("""
    <style>
    .match-header-premium {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        color: white;
        text-align: center;
        padding: 4px;
        font-size: 0.75rem;
        font-weight: 800;
        border-radius: 8px 8px 0 0;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-top: -16px;
        margin-left: -16px;
        margin-right: -16px;
        margin-bottom: 15px;
    }
    .team-name-premium {
        font-weight: 700;
        font-size: 1.1rem;
        padding-top: 5px;
    }

    /* ===== AVVISO PORTRAIT — visibile solo su telefoni in verticale ===== */
    .portrait-warning {
        display: none;
        background: linear-gradient(135deg, #ff6b35, #f7931e);
        color: white;
        text-align: center;
        padding: 12px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 0.9rem;
        margin-bottom: 10px;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
    @media screen and (max-width: 640px) and (orientation: portrait) {
        .portrait-warning {
            display: block !important;
        }
    }
    </style>
    
    <div class="portrait-warning">
        📱🔄 Ruota il telefono in <b>ORIZZONTALE</b> per la vista premium!
    </div>
    
    <script>
    // Tenta di bloccare l'orientamento in landscape (funziona solo se in fullscreen/PWA)
    try {
        if (screen.orientation && screen.orientation.lock) {
            screen.orientation.lock('landscape').catch(function(e) {
                console.log('Landscape lock non disponibile:', e.message);
            });
        }
    } catch(e) {
        console.log('Screen Orientation API non supportata');
    }
    </script>
    """, unsafe_allow_html=True)

    for idx, row in df_giornata.iterrows():
        # Parsing dei nomi
        casa, gio_c = parse_team_player(row['Casa'])
        osp, gio_o = parse_team_player(row['Ospite'])
        
        # Etichette in base alla modalità
        if modalita_visualizzazione == 'giocatori':
            label_c, label_o = gio_c, gio_o
        elif modalita_visualizzazione == 'squadre':
            label_c, label_o = casa, osp
        else:
            label_c, label_o = f"{casa} ({gio_c})", f"{osp} ({gio_o})"

        # Card Premium con Streamlit
        with st.container(border=True):
            # Header della card
            st.markdown(f"<div class='match-header-premium'>GIRONE {girone_sel} • MATCH {idx+1}</div>", unsafe_allow_html=True)
            
            # Prepariamo le chiavi (SINCRONIZZATE con la vista standard)
            key_golcasa = f"golcasa_{girone_sel}_{giornata_sel}_{row['Casa']}_{row['Ospite']}"
            key_golospite = f"golospite_{girone_sel}_{giornata_sel}_{row['Casa']}_{row['Ospite']}"
            key_valida = f"valida_{girone_sel}_{giornata_sel}_{row['Casa']}_{row['Ospite']}"
            
            # Layout su 4 colonne: Casa | Score1 | Score2 | Ospite
            c1, c2, c3, c4 = st.columns([3, 1, 1, 3])
            
            with c1:
                st.markdown(f"<div style='text-align:right;' class='team-name-premium'>🏠 {label_c}</div>", unsafe_allow_html=True)
            
            with c2:
                # Usiamo le stesse chiavi per sincronizzare istantaneamente le due viste
                st.number_input("GC", 0, 20, key=f"prem_{key_golcasa}", value=int(row['GolCasa']) if pd.notna(row['GolCasa']) else 0, label_visibility="collapsed", disabled=row['Valida'])
                st.session_state[key_golcasa] = st.session_state[f"prem_{key_golcasa}"]
            
            with c3:
                st.number_input("GO", 0, 20, key=f"prem_{key_golospite}", value=int(row['GolOspite']) if pd.notna(row['GolOspite']) else 0, label_visibility="collapsed", disabled=row['Valida'])
                st.session_state[key_golospite] = st.session_state[f"prem_{key_golospite}"]

            with c4:
                st.markdown(f"<div style='text-align:left;' class='team-name-premium'>{label_o} 🛫</div>", unsafe_allow_html=True)
            
            # Riga Validazione
            v1, v2 = st.columns([6, 1.5])
            with v2:
                st.checkbox("Valida Risultato ✅", key=f"prem_{key_valida}", value=bool(row['Valida']), disabled=st.session_state.get('read_only', False))
                st.session_state[key_valida] = st.session_state[f"prem_{key_valida}"]
            
            if st.session_state.get(key_valida):
                st.success(f"✅ Risultato confermato: {st.session_state[key_golcasa]} - {st.session_state[key_golospite]}")

def mostra_calendario_compact(df, girone_sel, giornata_sel, modalita_visualizzazione):
    """Visualizzazione ultra-compatta — SquadraA [0] - [0] SquadraB [✓] con landscape forzato su mobile."""
    df_giornata = df[(df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel)].copy()
    if df_giornata.empty:
        return

    st.markdown(f"### ⚡ {girone_sel} - Giornata {giornata_sel} (Compatta)")
    
    # ═══ JAVASCRIPT: forza orientamento landscape su mobile ═══
    # ═══ CSS: nasconde +/- e compatta gli input ═══
    # ═══ CSS: mostra avviso se il telefono è in portrait ═══
    st.markdown("""
        <style>
        /* ===== NASCONDI STEPPER +/- ===== */
        div[data-testid="stNumberInput"] button {
            display: none !important;
        }
        div[data-testid="stNumberInput"] input::-webkit-outer-spin-button,
        div[data-testid="stNumberInput"] input::-webkit-inner-spin-button {
            -webkit-appearance: none !important;
            margin: 0 !important;
        }
        div[data-testid="stNumberInput"] input[type="number"] {
            -moz-appearance: textfield !important;
        }

        /* ===== INPUT NUMERICI MICRO ===== */
        div[data-testid="stNumberInput"] {
            max-width: 48px !important;
        }
        div[data-testid="stNumberInput"] div[data-baseweb="input"] {
            padding: 0 !important;
        }
        div[data-testid="stNumberInput"] input {
            padding: 3px 1px !important;
            text-align: center !important;
            font-weight: bold !important;
            font-size: 0.95rem !important;
        }

        /* ===== CHECKBOX COMPATTA ===== */
        div[data-testid="stCheckbox"] {
            margin-top: 0 !important;
        }

        /* ===== AVVISO PORTRAIT — visibile solo su telefoni in verticale ===== */
        .portrait-warning {
            display: none;
            background: linear-gradient(135deg, #ff6b35, #f7931e);
            color: white;
            text-align: center;
            padding: 12px;
            border-radius: 8px;
            font-weight: 700;
            font-size: 0.9rem;
            margin-bottom: 10px;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        @media screen and (max-width: 640px) and (orientation: portrait) {
            .portrait-warning {
                display: block !important;
            }
        }
        </style>
        
        <div class="portrait-warning">
            📱🔄 Ruota il telefono in <b>ORIZZONTALE</b> per la vista compatta!
        </div>
        
        <script>
        // Tenta di bloccare l'orientamento in landscape (funziona solo se in fullscreen/PWA)
        try {
            if (screen.orientation && screen.orientation.lock) {
                screen.orientation.lock('landscape').catch(function(e) {
                    // Silenzioso: su browser normali non è supportato senza fullscreen
                    console.log('Landscape lock non disponibile:', e.message);
                });
            }
        } catch(e) {
            console.log('Screen Orientation API non supportata');
        }
        </script>
    """, unsafe_allow_html=True)

    for idx, row in df_giornata.iterrows():
        casa, gio_c = parse_team_player(row['Casa'])
        osp, gio_o = parse_team_player(row['Ospite'])
        
        if modalita_visualizzazione == 'giocatori':
            label_c, label_o = gio_c, gio_o
        elif modalita_visualizzazione == 'squadre':
            label_c, label_o = casa, osp
        else:
            label_c, label_o = f"{casa} ({gio_c})", f"{osp} ({gio_o})"

        # Chiavi sincronizzate con la vista standard/premium
        key_golcasa = f"golcasa_{girone_sel}_{giornata_sel}_{row['Casa']}_{row['Ospite']}"
        key_golospite = f"golospite_{girone_sel}_{giornata_sel}_{row['Casa']}_{row['Ospite']}"
        key_valida = f"valida_{girone_sel}_{giornata_sel}_{row['Casa']}_{row['Ospite']}"

        # ═══ TUTTO SU UNA RIGA: SquadraA [0] - [0] SquadraB [✓] ═══
        c1, c2, c3, c4, c5, c6 = st.columns([3, 0.8, 0.3, 0.8, 3, 0.7])
        
        with c1:
            st.markdown(f"<div style='text-align:right; font-weight:700; font-size:0.78rem; padding-top:6px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{label_c}</div>", unsafe_allow_html=True)
        
        with c2:
            st.number_input("GC", 0, 20, key=f"comp_{key_golcasa}",
                            value=int(row['GolCasa']) if pd.notna(row['GolCasa']) else 0,
                            label_visibility="collapsed", disabled=row['Valida'])
            st.session_state[key_golcasa] = st.session_state[f"comp_{key_golcasa}"]
        
        with c3:
            st.markdown("<div style='text-align:center; font-weight:bold; font-size:0.8rem; padding-top:6px;'>-</div>", unsafe_allow_html=True)
            
        with c4:
            st.number_input("GO", 0, 20, key=f"comp_{key_golospite}",
                            value=int(row['GolOspite']) if pd.notna(row['GolOspite']) else 0,
                            label_visibility="collapsed", disabled=row['Valida'])
            st.session_state[key_golospite] = st.session_state[f"comp_{key_golospite}"]

        with c5:
            st.markdown(f"<div style='text-align:left; font-weight:700; font-size:0.78rem; padding-top:6px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{label_o}</div>", unsafe_allow_html=True)

        with c6:
            st.checkbox("✓", key=f"comp_{key_valida}", value=bool(row['Valida']),
                        label_visibility="collapsed",
                        disabled=st.session_state.get('read_only', False))
            st.session_state[key_valida] = st.session_state[f"comp_{key_valida}"]

                
def salva_risultati_giornata(tournaments_collection, girone_sel, giornata_sel):
    try:
        print(f"[DEBUG] Inizio salvataggio risultati per girone: {girone_sel}, giornata: {giornata_sel}")
        df = st.session_state['df_torneo'].copy()
        
        # Filtra le partite della giornata corrente
        mask = (df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel)
        df_giornata = df[mask].copy()
        print(f"[DEBUG] Trovate {len(df_giornata)} partite per questa giornata")

        # Aggiorna i risultati
        for idx, row in df_giornata.iterrows():
            key_golcasa = f"golcasa_{girone_sel}_{giornata_sel}_{row['Casa']}_{row['Ospite']}"
            key_golospite = f"golospite_{girone_sel}_{giornata_sel}_{row['Casa']}_{row['Ospite']}"
            key_valida = f"valida_{girone_sel}_{giornata_sel}_{row['Casa']}_{row['Ospite']}"
            
            # Converti esplicitamente i valori in tipi nativi di Python
            gol_casa = int(st.session_state.get(key_golcasa, 0) or 0)
            gol_ospite = int(st.session_state.get(key_golospite, 0) or 0)
            valida = bool(st.session_state.get(key_valida, False))

            # Aggiorna il DataFrame
            df.loc[idx, 'GolCasa'] = gol_casa
            df.loc[idx, 'GolOspite'] = gol_ospite
            df.loc[idx, 'Valida'] = valida

        # Conversione esplicita dei tipi
        df['GolCasa'] = pd.to_numeric(df['GolCasa'], errors='coerce').fillna(0).astype(int)
        df['GolOspite'] = pd.to_numeric(df['GolOspite'], errors='coerce').fillna(0).astype(int)
        df['Valida'] = df['Valida'].astype(bool)

        # Aggiorna il session state
        st.session_state['df_torneo'] = df

        # Verifica l'ID del torneo
        if 'tournament_id' not in st.session_state:
            print("[ERROR] Nessun tournament_id in sessione")
            st.error("❌ Errore: ID del torneo non trovato. Impossibile salvare.")
            return False

        

        # Salva su MongoDB
        ok = aggiorna_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], df)
        if not ok:
            print("[ERROR] Errore durante l'aggiornamento del torneo su MongoDB")
            st.error("❌ Errore durante il salvataggio su MongoDB.")
            return False
            
        # ------------------------------------------------------------------
        # CORREZIONE DEL LOGGING: Usiamo il DataFrame AGGIORNATO (df) filtrato
        # ------------------------------------------------------------------
        df_giornata_aggiornata = df[mask] # 👈 Usa df [mask] che contiene i risultati corretti!
            
        # Prepara i dati per il logging
        partite_modificate = []
        for _, row in df_giornata_aggiornata.iterrows(): # 👈 CICLA sui dati corretti
            partita = {
                'partita': f"{row['Casa']} vs {row['Ospite']}",
                'risultato': f"{int(row['GolCasa'])}-{int(row['GolOspite'])}",
                'valida': bool(row['Valida'])
            }
            partite_modificate.append(partita)

        # Logging
        try:
            user = st.session_state.get('user', 'unknown') if 'st' in globals() else 'system'
            nome_torneo = st.session_state.get('nome_torneo', 'Torneo sconosciuto')
            
            log_action(
                username=user,
                action='salvarisultati',
                torneo=nome_torneo,
                details={
                    'torneo_id': str(st.session_state.get('tournament_id')),
                    'giornata': int(giornata_sel),
                    'partite_modificate': partite_modificate
                }
            )
            print(f"[DEBUG] Log inviato per {len(partite_modificate)} partite modificate")
            st.toast("💾 Risultati salvati con successo!")
            
        except Exception as e:
            print(f"[ERROR] Errore durante il logging: {str(e)}")
            import traceback
            traceback.print_exc()
            st.toast("💾 Risultati salvati, ma si è verificato un errore nel logging")

        # Verifica se tutte le partite sono state validate
        if df['Valida'].all():
            nome_completato = f"completato_{st.session_state['nome_torneo']}"
            classifica_finale = aggiorna_classifica(df)
            salva_torneo_su_db(tournaments_collection, df, nome_completato)
            st.session_state['torneo_completato'] = True
            st.session_state['classifica_finale'] = classifica_finale
            st.session_state['show_redirect_button'] = True 
            st.toast(f"🏁 Torneo completato e salvato come {nome_completato} ✅")

        return True
        
    except Exception as e:
        print(f"[CRITICAL] Errore critico in salva_risultati_giornata: {str(e)}")
        import traceback
        traceback.print_exc()
        st.error("❌ Si è verificato un errore durante il salvataggio dei risultati.")
        return False
        
def gestisci_abbandoni(df_torneo, giocatori_da_ritirare, tournaments_collection):
    df = df_torneo.copy()
    
    # Aggiungi a session state la lista dei giocatori che hanno abbandonato
    if 'giocatori_ritirati' not in st.session_state:
        st.session_state['giocatori_ritirati'] = []
    
    for giocatore in giocatori_da_ritirare:
        squadra_ritirata = ""
        # Cerca la squadra del giocatore nel df_squadre
        if 'df_squadre' in st.session_state:
            squadra_info = st.session_state['df_squadre'][st.session_state['df_squadre']['Giocatore'] == giocatore]
            if not squadra_info.empty:
                squadra_ritirata = squadra_info.iloc[0]['Squadra']
        
        # Aggiungi la squadra e/o il giocatore alla lista dei ritirati
        if squadra_ritirata:
            st.session_state['giocatori_ritirati'].append(f"{squadra_ritirata}-{giocatore}")
        st.session_state['giocatori_ritirati'].append(giocatore)
    
    st.session_state['giocatori_ritirati'] = list(set(st.session_state['giocatori_ritirati'])) # Rimuove duplicati
    
    # Estrai le squadre corrispondenti ai giocatori che si ritirano
    squadre_da_ritirare = st.session_state['giocatori_ritirati']
    
    if not squadre_da_ritirare:
        st.warning("⚠️ Nessun giocatore selezionato per l'abbandono.")
        return df_torneo

    st.info(f"🔄 Gestione abbandono per i seguenti giocatori: {', '.join(giocatori_da_ritirare)}")
    
    matches_to_update = 0
    # Aggiorna il DataFrame
    for idx, row in df.iterrows():
        casa_ritirato = any(ritirato in row['Casa'] for ritirato in squadre_da_ritirare)
        ospite_ritirato = any(ritirato in row['Ospite'] for ritirato in squadre_da_ritirare)

        # Caso: giocatore ritirato contro giocatore attivo
        if casa_ritirato and not ospite_ritirato:
            df.loc[idx, 'GolCasa'] = 0
            df.loc[idx, 'GolOspite'] = 3
            df.loc[idx, 'Valida'] = True
            matches_to_update += 1
        elif ospite_ritirato and not casa_ritirato:
            df.loc[idx, 'GolCasa'] = 3
            df.loc[idx, 'GolOspite'] = 0
            df.loc[idx, 'Valida'] = True
            matches_to_update += 1
        # Caso: due giocatori ritirati (risultato 0-0)
        elif casa_ritirato and ospite_ritirato:
            df.loc[idx, 'GolCasa'] = 0
            df.loc[idx, 'GolOspite'] = 0
            df.loc[idx, 'Valida'] = True
            matches_to_update += 1

    st.session_state['df_torneo'] = df
    
    # Salva su DB
    if 'tournament_id' in st.session_state:
        try:
            ok = aggiorna_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], df)
            if ok:
                try:
                    user = st.session_state.get('user', 'unknown') if 'st' in globals() else 'system'
                    log_action(
                        username=user,
                        action='abbandono_player',
                        torneo=st.session_state.get('nome_torneo'),
                        details={'torneo_id': st.session_state.get('tournament_id'), 'players': giocatori_da_ritirare, 'matches_updated': matches_to_update}
                    )

                except Exception as e:
                    print(f"[LOGGING] errore in gestisci_abbandoni: {e}")
                st.toast(f"✅ Aggiornati {matches_to_update} incontri. Modifiche salvate su MongoDB!")
            else:
                st.error("❌ Errore durante il salvataggio su MongoDB.")
        except Exception as e:
            st.error(f"❌ Errore durante il salvataggio su MongoDB: {e}")
    else:
        st.error("❌ ID del torneo non trovato. Impossibile salvare.")
    return df

# --- CLASSIFICA ---
@st.fragment
def mostra_classifica_stilizzata(df_classifica, girone_sel):
    """Mostra la classifica stilizzata (aggiornabile indipendentemente grazie a @st.fragment)."""
    if df_classifica is None or df_classifica.empty:
        st.info("⚽ Nessuna partita validata")
        return
    df_girone = df_classifica[df_classifica['Girone'] == girone_sel].copy()

    # Rimuovi la colonna 'Ritirato' per la visualizzazione, ma usala per lo stile
    df_to_show = df_girone.drop(columns=['Ritirato'])

    # Stile delle righe in base alla colonna 'Ritirato'
    def highlight_withdrawn(s):
        is_withdrawn = s['Ritirato']
        return ['background-color: lightgray'] * len(s) if is_withdrawn else [''] * len(s)

    # Usa la colonna 'Squadra' per applicare lo stile
    styled_df = df_girone.style.apply(highlight_withdrawn, axis=1)

    st.dataframe(styled_df, width="stretch", hide_index=True)

# -------------------------
#  export PDF (NON MODIFICARE)
from datetime import datetime
import os

class GazzettaPDF(FPDF):
    def __init__(self, nome_torneo, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.nome_torneo = nome_torneo

    def header(self):
        # 🟦 Sfondo Header super istituzionale (Blu Navy vibrante)
        self.set_fill_color(26, 54, 93)  
        self.rect(0, 0, 210, 32, 'F')
        
        # 🟡 Linea dorata di accento sotto l'header
        self.set_fill_color(212, 175, 55) 
        self.rect(0, 32, 210, 1.5, 'F')
        
        # 🛡️ Logo "PierCrew" a sinistra (se disponibile)
        logo_path = "logo_piercrew.jpg"
        start_x = 10
        if os.path.exists(logo_path):
            self.image(logo_path, 12, 5, 22)
            start_x = 40
            
        # 📰 Titolo "Gazzettino" Ufficiale
        self.set_xy(start_x, 8)
        self.set_font("Arial", 'B', 24)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, "IL GAZZETTINO DEL PIER CREW", border=0, ln=1, align='L')
        
        # 🏆 Sottotitolo (Nome del torneo e data aggiornamento)
        self.set_x(start_x)
        self.set_font("Arial", 'I', 11)
        self.set_text_color(220, 225, 235)
        data_stampa = datetime.now().strftime("%d/%m/%Y alle %H:%M")
        self.cell(0, 6, f"Referto Ufficiale: {self.nome_torneo} | Aggiornato il {data_stampa}", border=0, ln=1, align='L')
        
        self.ln(12)

    def footer(self):
        # Posizione a 1.5 cm dal fondo
        self.set_y(-15)
        
        # 🟦 Bordo inferiore istituzionale (Blu Navy)
        self.set_fill_color(26, 54, 93)  
        self.rect(0, 287, 210, 10, 'F')
        
        self.set_font('Arial', 'B', 8)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, f'Pagina {self.page_no()} - Generato automaticamente dal Gestionale Tornei Subbuteo', 0, 0, 'C')

def esporta_pdf(df_torneo, df_classifica, nome_torneo):
    pdf = GazzettaPDF(nome_torneo, orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    
    gironi = df_torneo['Girone'].dropna().unique()
    
    for girone in gironi:
        # ======= 📊 SEZIONE CLASSIFICA (Messa in alto per ovvia importanza) =======
        pdf.set_font("Arial", 'B', 16)
        pdf.set_fill_color(230, 235, 245) # Azzurrino per il titolo sezione
        pdf.set_text_color(26, 54, 93)
        pdf.cell(0, 10, f" CLASSIFICA: {str(girone).upper()} ", border=1, ln=True, fill=True, align='C')
        pdf.ln(3)

        df_c = df_classifica[df_classifica['Girone'] == girone]
        
        # Table Header Classifica
        pdf.set_font("Arial", 'B', 11)
        pdf.set_fill_color(26, 54, 93) # Sfondo scuro per header tabella
        pdf.set_text_color(255, 255, 255) # Testo bianco
        
        headers_classifica = ["Pos", "Squadra", "PTI", "G", "V", "P", "S", "GF", "GS", "DR"]
        widths_class = [10, 56, 12, 10, 10, 10, 10, 12, 12, 16]
        
        for i, h in enumerate(headers_classifica):
            pdf.cell(widths_class[i], 8, h, border=1, align='C', fill=True)
        pdf.ln()

        # Table Body Classifica (con Zebra-striping)
        pdf.set_font("Arial", '', 11)
        pdf.set_text_color(0, 0, 0)
        
        for idx, (_, r) in enumerate(df_c.iterrows()):
            fill = (idx % 2 == 0) # Righe alternate
            pdf.set_fill_color(245, 248, 250) if fill else pdf.set_fill_color(255, 255, 255)
            
            squadra = r['Squadra'] if pd.notna(r['Squadra']) else "-"
            # Taglia i nomi troppo lunghi
            if len(str(squadra)) > 30:
                 squadra = str(squadra)[:27] + "..."
                 
            pdf.cell(widths_class[0], 7, str(idx+1), border='LR', align='C', fill=fill)
            # Make team text slightly bold
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(widths_class[1], 7, " " + str(squadra), border='LR', align='L', fill=fill)
            pdf.set_font("Arial", '', 11)
            pdf.cell(widths_class[2], 7, str(r['Punti']), border='LR', align='C', fill=fill)
            pdf.cell(widths_class[3], 7, str(r.get('G', 0)), border='LR', align='C', fill=fill)
            pdf.cell(widths_class[4], 7, str(r['V']), border='LR', align='C', fill=fill)
            pdf.cell(widths_class[5], 7, str(r['P']), border='LR', align='C', fill=fill)
            pdf.cell(widths_class[6], 7, str(r['S']), border='LR', align='C', fill=fill)
            pdf.cell(widths_class[7], 7, str(r['GF']), border='LR', align='C', fill=fill)
            pdf.cell(widths_class[8], 7, str(r['GS']), border='LR', align='C', fill=fill)
            pdf.cell(widths_class[9], 7, str(r['DR']), border='LR', align='C', fill=fill)
            pdf.ln()
            
        # Draw bottom border of the table
        pdf.cell(sum(widths_class), 0, '', border='T', ln=True)
        pdf.ln(10)

        # ======= 🗓️ SEZIONE CALENDARIO E RISULTATI =======
        giornate = sorted(df_torneo[df_torneo['Girone'] == girone]['Giornata'].dropna().unique())
        for g in giornate:
            # Controllo spazio residuo (se troppo stretto creiamo nuova pagina)
            if pdf.get_y() > 250:
                 pdf.add_page()
                 
            pdf.set_font("Arial", 'B', 12)
            pdf.set_fill_color(230, 235, 245)
            pdf.set_text_color(26, 54, 93)
            # Intestazione Giornata esteticamente piacevole
            pdf.cell(0, 8, f" Giornata {g} - {str(girone)} ", ln=True, fill=True)
            
            pdf.set_font("Arial", '', 10)
            headers_calc = ["Casa", "Risultato", "Ospite", "Status"]
            widths_calc = [60, 30, 60, 40]
            
            # Header tabellina Risultati
            pdf.set_fill_color(240, 240, 240)
            pdf.set_text_color(100, 100, 100)
            for i, h in enumerate(headers_calc):
                pdf.cell(widths_calc[i], 6, h, border=1, align='C', fill=True)
            pdf.ln()
            
            pdf.set_text_color(0, 0, 0)
            partite = df_torneo[(df_torneo['Girone'] == girone) & (df_torneo['Giornata'] == g)]
            for idx_p, row in partite.iterrows():
                fill = (idx_p % 2 == 0)
                pdf.set_fill_color(248, 249, 250) if fill else pdf.set_fill_color(255, 255, 255)
            
                def safe_val(v, default="-"):
                    if isinstance(v, pd.Series): v = v.iloc[0] if not v.empty else default
                    if isinstance(v, (list, tuple)): v = v[0] if len(v) > 0 else default
                    try:
                        if pd.isna(v): return default
                    except: pass
                    s_v = str(v).strip()
                    if s_v.lower() in ["none", "nan", "<na>", ""]: return default
                    return s_v

                casa   = safe_val(row.get('Casa'), "-")
                ospite = safe_val(row.get('Ospite'), "-")
                golc   = safe_val(row.get('GolCasa'), " ")
                golo   = safe_val(row.get('GolOspite'), " ")
                
                if len(casa) > 28: casa = casa[:25]+"..."
                if len(ospite) > 28: ospite = ospite[:25]+"..."

                valida = row.get('Valida', False)
                status_Testo = " UFFICIALE " if valida else " DA GIOCARE "
                res = f"{golc} - {golo}" if valida else " - "
                
                # Stampa Casa
                if valida: pdf.set_font("Arial", '', 10) 
                else: pdf.set_font("Arial", 'I', 10)
                pdf.cell(widths_calc[0], 7, "  " + casa, border='LR', fill=fill)
                
                # Stampa Risultato
                pdf.set_font("Arial", 'B', 11)
                pdf.cell(widths_calc[1], 7, res, border='L', align='C', fill=fill)
                
                # Stampa Ospite
                if valida: pdf.set_font("Arial", '', 10) 
                else: pdf.set_font("Arial", 'I', 10)
                pdf.cell(widths_calc[2], 7, "  " + ospite, border='LR', align='L', fill=fill)
                
                # Stampa Status (Verde se Ufficiale, Grigio se Da Giocare)
                pdf.set_font("Arial", 'B', 8)
                if valida:
                    pdf.set_text_color(42, 157, 143) # Verde Scuro
                else:
                    pdf.set_text_color(180, 180, 180) # Grigio
                    
                pdf.cell(widths_calc[3], 7, status_Testo, border='R', align='C', fill=fill)
                pdf.set_text_color(0, 0, 0) # reset
                pdf.ln()
                
            pdf.cell(sum(widths_calc), 0, '', border='T', ln=True) # bottom line
            pdf.ln(4)
        pdf.add_page() # Forza una nuova pagina pulita per il prossimo girone (se ce n'è uno)

    pdf_bytes = bytes(pdf.output())
    return pdf_bytes

# -------------------------
# APP UI: stile e layout — CSS centralizzato in common/styles.py
# -------------------------
def inject_css():
    inject_all_styles()  # Delega al modulo condiviso
    # Override locale ultra-aggressivo per rimuovere lo spazio vuoto in alto (solo PierCrew)
    st.html("""
        <style>
        .stAppViewBlockContainer {
            padding-top: 1rem !important;
        }
        .stMainBlockContainer {
            padding-top: 1rem !important;
        }
        </style>
    """)
    return



# -------------------------
# APP
# -------------------------
def main():
    # Iniezione immediata del CSS per evitare il gap in alto
    inject_css()

    # Mostra la schermata di autenticazione
    #authenticated = auth.show_auth_screen()
    #if not authenticated:
    #    st.stop()   # blocca tutto finché non sei loggato
    
    # Mostra la schermata di autenticazione se non si è già autenticati
    if not st.session_state.get('authenticated', False):
        auth.show_auth_screen(club="PierCrew")
        st.stop()   # blocca tutto finché non sei loggato

    # Attiva il sistema di keep-alive per mantenere la sessione durante le partite
    enable_session_keepalive()

    # Debug: mostra utente autenticato e ruolo
    if st.session_state.get("authenticated"):
        user = st.session_state.get("user", {})
        st.sidebar.markdown(f"**👤 Utente:** {user.get('username', '??')}")
        st.sidebar.markdown(f"**🔑 Ruolo:** {user.get('role', '??')}")
  
    # Downgrade automatico per Campionati
    if st.session_state.get("authenticated"):
        # Verifica che la chiave 'nome_torneo' esista nello stato della sessione
        nome_torneo = st.session_state.get("nome_torneo")
        
        # Se il nome del torneo è presente e contiene il tag "Campionato"
        if nome_torneo and "Campionato" in nome_torneo:
            user = st.session_state.get("user", {})
            
            # Se l'utente non è un amministratore, imposta la modalità di sola lettura
            if user.get("role") != "A":
                st.session_state.read_only = True
                st.sidebar.warning("⛔ Accesso in sola lettura: solo un amministratore può modificare i Campionati.")
            
    if st.session_state.get('sidebar_state_reset', False):
        reset_app_state()
        st.session_state['sidebar_state_reset'] = False
        st.rerun()

    # Avvio audio ad ogni rerun. La logica JS all'interno di questa funzione
    # assicura che l'elemento audio nel browser venga creato una sola volta
    # e mantenuto attivo.
    # Inizializza lo stato dell'audio se non esiste
    if "bg_audio_disabled" not in st.session_state:
        st.session_state.bg_audio_disabled = False
    
    # L'avvio dell'audio è stato spostato dopo il titolo per evitare gap in alto
    


    # Connessioni (senza messaggi verdi)
    players_collection = init_mongo_connection(st.secrets["MONGO_URI"], "giocatori_subbuteo", "piercrew_players", show_ok=False)
    tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], "TorneiSubbuteo", "PierCrew", show_ok=False)
    

    # Carica i dati dei giocatori e delle squadre da MongoDB
    # Questo viene fatto all'avvio per assicurare che i dati siano sempre disponibili
    df_squadre_db = carica_giocatori_da_db(players_collection)
    if not df_squadre_db.empty:
        st.session_state['df_squadre'] = df_squadre_db
    else:
        st.session_state['df_squadre'] = pd.DataFrame(columns=['Giocatore', 'Squadra', 'Potenziale'])
    # --- Auto-load from URL param (es. ?torneo=nome_torneo) ---
    # usa experimental_get_query_params per compatibilità
    # usa st.query_params (nuova API stabile)
    q = st.query_params
    if 'torneo' in q and q['torneo']:
        # con la nuova API è già una stringa, non più una lista
        raw_param = q['torneo']
        try:
            torneo_param = urllib.parse.unquote_plus(raw_param)
        except Exception:
            torneo_param = raw_param

        # evita ripetuti tentativi se il torneo è già in session_state
        already_loaded = (
            st.session_state.get('calendario_generato', False)
            and st.session_state.get('nome_torneo') == torneo_param
        )

        if not already_loaded:
            if tournaments_collection is not None:
                torneo_doc = tournaments_collection.find_one({"nome_torneo": torneo_param})
                if not torneo_doc:
                    try:
                        torneo_doc = tournaments_collection.find_one({"_id": ObjectId(torneo_param)})
                    except Exception:
                        torneo_doc = None

                if torneo_doc:
                    st.session_state['tournament_id'] = str(torneo_doc['_id'])
                    st.session_state['nome_torneo'] = torneo_doc.get('nome_torneo', torneo_param)
                    torneo_data = carica_torneo_da_db(
                        tournaments_collection, st.session_state['tournament_id']
                    )
                    if torneo_data and 'calendario' in torneo_data:
                        st.session_state['calendario_generato'] = True
                        st.toast(f"✅ Torneo '{st.session_state['nome_torneo']}' caricato automaticamente")
                        # pulisci i query params per evitare loop di reload
                        st.query_params.clear()
                        st.rerun()

                    else:
                        st.warning(f"⚠️ Trovato documento torneo ma non è presente il calendario o si è verificato un errore.")
                else:
                    st.warning(f"⚠️ Torneo '{torneo_param}' non trovato nel DB.")


    # Titolo con stile personalizzato
    if st.session_state.get('calendario_generato', False) and 'nome_torneo' in st.session_state:
        st.markdown(f"""
        <div style='text-align:center; padding:20px; border-radius:10px; background: linear-gradient(90deg, #457b9d, #1d3557); box-shadow: 0 4px 14px #00000022;'>
            <h1 style='color:white; margin:0; font-weight:700;'>🇮🇹⚽ {st.session_state['nome_torneo']} 🏆🇮🇹</h1>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style='text-align:center; padding:20px; border-radius:10px; background: linear-gradient(90deg, #457b9d, #1d3557); box-shadow: 0 4px 14px #00000022;'>
            <h1 style='color:white; margin:0; font-weight:700;'>🇮🇹⚽ Torneo PierCrew – Gestione Gironi 🏆🇮🇹</h1>
        </div>
        """, unsafe_allow_html=True)

    # Avvio audio di sottofondo 
    if not st.session_state.bg_audio_disabled:
        autoplay_background_audio(BACKGROUND_AUDIO_URL)

   
    df_master = carica_giocatori_da_db(players_collection)

    if players_collection is None and tournaments_collection is None:
        st.error("❌ Impossibile avviare l'applicazione. La connessione a MongoDB non è disponibile.")
        return

    # ✅ 1. 🕹 Gestione Rapida + 👤 Mod Selezione Partecipanti
    setup_common_sidebar(show_user_info=False, hub_url=HUB_URL)  # user info già mostrata sopra
    setup_audio_sidebar()
    setup_player_selection_mode()
    
    if st.session_state.get('calendario_generato', False):
        df = st.session_state['df_torneo']
        classifica = aggiorna_classifica(df)
        
        # --- FUNZIONI DI SINCRONIZZAZIONE ---
        def sync_tipo_vista(source_key):
            val = st.session_state[source_key].lower()
            st.session_state['tipo_vista_selezionata'] = val
            # Forza l'altro widget a riflettere il valore resettandone la chiave se necessario
            # (In realtà basta aggiornare la variabile di stato usata nell'index)

        def sync_usa_bottoni(source_key):
            val = st.session_state[source_key]
            st.session_state['usa_bottoni_sidebar'] = val
        
        st.sidebar.markdown("---")
        
        # ✅ 3. 🔧 Utility (sezione principale con sottosezioni)
        st.sidebar.subheader("🔧 Utility")
        
        # 🔎 Visualizzazione incontri
        with st.sidebar.expander("🔎 Visualizzazione incontri", expanded=False):
            # Radio button per formato incontri
            modalita_visualizzazione_sidebar = st.radio(
                "Formato nomi:",
                ("Completa", "Solo squadre", "Solo giocatori"),
                index=1,
                key="modalita_visualizzazione_sidebar",
                horizontal=False
            )
            # Mappa il valore del radio button
            mappa_modalita = {
                "Completa": "completa",
                "Solo squadre": "squadre",
                "Solo giocatori": "giocatori"
            }
            st.session_state['modalita_scelta_sidebar'] = mappa_modalita[modalita_visualizzazione_sidebar]
            
            st.markdown("---")
            
            # Radio button per tipo di vista (Sincronizzato con la pagina principale)
            current_view = st.session_state.get('tipo_vista_selezionata', 'compact').capitalize()
            st.radio(
                "Tipo di vista:",
                ("Compact", "Premium", "Standard"),
                index=("Compact", "Premium", "Standard").index(current_view),
                key="tipo_vista_sidebar_widget",
                on_change=sync_tipo_vista,
                args=("tipo_vista_sidebar_widget",)
            )
            
            st.markdown("---")
            
            # Checkbox "Navigazione giornate con bottoni"
            # Sincronizzato con la pagina principale
            current_nav = st.session_state.get('usa_bottoni_sidebar', False)
            st.checkbox(
                "🎛️ Navigazione giornate con bottoni", 
                value=current_nav,
                key="modalita_navigazione_sidebar",
                on_change=sync_usa_bottoni,
                args=("modalita_navigazione_sidebar",)
            )
        
        # 🏃‍♂ Gestione abbandoni
        with st.sidebar.expander("🏃‍♂️ Gestione abbandoni", expanded=False):
            # Estrai la lista di tutti i giocatori presenti nel torneo
            giocatori_attivi = sorted(list(set(df['Casa'].unique().tolist() + df['Ospite'].unique().tolist())))
            
            # Multiselect per giocatori che si ritirano
            giocatori_selezionati = st.multiselect(
                "Seleziona i giocatori che si ritirano",
                options=giocatori_attivi,
                key='ritiro_giocatori_multiselect'
            )

            # Bottone conferma abbandono
            if st.button("⚠️ Confermami l'abbandono!", key="btn_abbandono", width="stretch"):
                if giocatori_selezionati:
                    gestisci_abbandoni(st.session_state['df_torneo'], giocatori_selezionati, tournaments_collection)
                    st.rerun()
                else:
                    st.warning("❌ Seleziona almeno un giocatore per gestire l'abbandono.")
        
        
        # 💬 Visualizzazione Classifica per girone
        with st.sidebar.expander("💬 Visualizzazione Classifica", expanded=False):
            gironi_attivi = sorted(st.session_state['df_torneo']['Girone'].dropna().unique().tolist())
            if len(gironi_attivi) == 1:
                girone_unico = gironi_attivi[0]
                if st.button(f"📊 Apri Classifica ({girone_unico})", key="btn_classifica_sidebar_uni", width="stretch"):
                    st.session_state['mostra_classifica_girone'] = girone_unico
                    st.rerun()
            elif len(gironi_attivi) > 1:
                gironi_sidebar = gironi_attivi.copy()
                gironi_sidebar.insert(0, 'Nessuno')
                girone_class_sel = st.selectbox("Seleziona Girone", gironi_sidebar, key="sidebar_classifica_girone")
                if st.button("📱 Apri Classifica", key="btn_classifica_sidebar_multi", width="stretch"):
                    if girone_class_sel != 'Nessuno':
                        st.session_state['mostra_classifica_girone'] = girone_class_sel
                        st.rerun()
                    else:
                        st.info("Seleziona un girone.")
            else:
                st.info("Nessun girone attivo.")
        


        st.markdown("---")
        st.markdown("### 🔍 Ricerca e Filtri (Calendario Multi-Girone)")
        
        # ✅ SELETTORE VISTA + NAVIGAZIONE BOTTONI
        col_v1, col_v2, col_v3 = st.columns([0.15, 0.45, 0.4], vertical_alignment="center")
        with col_v1:
            st.markdown("**Stile Vista:**")
        with col_v2:
            current_view_main = st.session_state.get('tipo_vista_selezionata', 'compact').capitalize()
            st.radio(
                "Stile Vista:",
                ("Compact", "Premium", "Standard"),
                index=("Compact", "Premium", "Standard").index(current_view_main),
                horizontal=True,
                label_visibility="collapsed",
                key="tipo_vista_main_widget",
                on_change=sync_tipo_vista,
                args=("tipo_vista_main_widget",)
            )
        
        with col_v3:
            current_nav_main = st.session_state.get('usa_bottoni_sidebar', False)
            st.checkbox(
                "🎛️ Naviga a bottoni", 
                value=current_nav_main,
                key="modalita_navigazione_main_widget",
                on_change=sync_usa_bottoni,
                args=("modalita_navigazione_main_widget",)
            )

        df = st.session_state['df_torneo'].copy()
        df_filtrato = pd.DataFrame()

        # Usa pulsanti orizzontali in cima per il menu principale dei filtri
        col_filt1, col_filt2 = st.columns([0.15, 0.85], vertical_alignment="center")
        with col_filt1:
            st.markdown("**Visualizza:**")
        with col_filt2:
            filtro_principale = st.radio(
                "Visualizza:",
                ('Nessuno', 'Stato partite', 'Giocatore', 'Girone'),
                horizontal=True,
                label_visibility="collapsed",
                key='filtro_principale_selettore_main'
            )

        if filtro_principale == 'Nessuno':
            # Non mostrare nessun dataframe qui, la navigazione del calendario si occuperà di questo
            pass

        elif filtro_principale == 'Stato partite':
            stato = st.radio(
                "Scegli lo stato:",
                ('Giocate', 'Da Giocare'),
                horizontal=True,
                key='stato_selettore_main'
            )
            st.subheader(f"🗓️ Partite {stato.lower()}")
            
            if stato == 'Giocate':
                df_filtrato = df[df['Valida'] == True]
            else: # 'Da Giocare'
                df_filtrato = df[df['Valida'] == False]
            
            #if not df_filtrato.empty:
            # --- visuale tabella per "Stato partite" ---
            if not df_filtrato.empty:
                col1, col2, col3 = st.columns([1, 6, 1])
                with col2:
                    st.image("mobile.png")

                # copia con indice originale, poi useremo idx_map per aggiornare il df principale
                df_show = df_filtrato.reset_index().copy()
                idx_map = df_show['index'].tolist()    # mappa indici originali

                # prima colonna checkbox (vuota come intestazione)
                df_show.insert(0, 'Sel', False)

                # pulizie richieste
                df_show['Girone'] = df_show['Girone'].astype(str).str.replace("Girone ", "", regex=False)
                
                # Gestione visualizzazione nomi in base alla selezione dell'utente
                modalita_visualizzazione = st.session_state.get('modalita_visualizzazione_sidebar', 'Solo squadre')
                
                if modalita_visualizzazione == 'Solo squadre':
                    # Prende la parte prima del trattino
                    df_show['Casa'] = df_show['Casa'].apply(lambda x: str(x).split("-")[0].strip() if pd.notna(x) and "-" in str(x) else x)
                    df_show['Ospite'] = df_show['Ospite'].apply(lambda x: str(x).split("-")[0].strip() if pd.notna(x) and "-" in str(x) else x)
                elif modalita_visualizzazione == 'Solo giocatori':
                    # Prende la parte dopo il trattino, se esiste
                    df_show['Casa'] = df_show['Casa'].apply(
                        lambda x: str(x).split("-")[1].strip() if pd.notna(x) and "-" in str(x) and len(str(x).split("-")) > 1 else x
                    )
                    df_show['Ospite'] = df_show['Ospite'].apply(
                        lambda x: str(x).split("-")[1].strip() if pd.notna(x) and "-" in str(x) and len(str(x).split("-")) > 1 else x
                    )
                # Se è 'Completa' non facciamo nulla, manteniamo il testo così com'è

                # numero di gironi totali (usiamo il df principale)
                num_gironi = df['Girone'].nunique() if 'Girone' in df.columns else 1

                # colonne che vogliamo aggiornare poi
                editable_cols = ['GolCasa', 'GolOspite', 'Valida']

                # scegli quali colonne mostrare (se num_gironi==1 omettiamo 'Girone')
                display_cols = ['Sel']
                if num_gironi > 1:
                    display_cols.append('Girone')
                display_cols += ['Giornata','Casa','Ospite','GolCasa','GolOspite','Valida']

                # column_config (senza usare hidden)
                column_config = {
                    "Sel": st.column_config.CheckboxColumn("", width=15),
                    "index": st.column_config.Column("ID", width=15),  # non mostrata, usiamo idx_map
                    "Giornata": st.column_config.NumberColumn("🗓️", min_value=0, step=1, width=15),
                    "Casa": st.column_config.TextColumn("🏠", width=50),
                    "Ospite": st.column_config.TextColumn("🛫", width=50),
                    "GolCasa": st.column_config.NumberColumn("⚽️", min_value=0, max_value=20, width=15),
                    "GolOspite": st.column_config.NumberColumn("⚽️", min_value=0, max_value=20, width=15),
                    "Valida": st.column_config.CheckboxColumn("✅", width=15),
                }
                if num_gironi > 1:
                    column_config["Girone"] = st.column_config.TextColumn("🏟️", width=15)

                df_edit = st.data_editor(
                    df_show[display_cols],
                    width="stretch",
                    num_rows="dynamic",
                    column_config=column_config
                )

                if st.button("💾 Salva modifiche tabella"):
                    # aggiorna df_torneo usando idx_map (posizione -> indice originale)
                    for i in range(len(df_edit)):
                        row = df_edit.iloc[i]
                        orig_idx = idx_map[i]
                        for col in editable_cols:
                            st.session_state['df_torneo'].at[orig_idx, col] = row[col]
                    if st.session_state.get('tournament_id'):
                        aggiorna_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], st.session_state['df_torneo'])
                    st.success("Modifiche salvate!")
            else:
                st.info(f"🎉 Nessuna partita {stato.lower()} trovata.")

                
        elif filtro_principale == 'Giocatore':
            col_f1, col_f2, col_f3 = st.columns([1, 1, 1], vertical_alignment="bottom")
            giocatori = sorted(list(set(df['Casa'].unique().tolist() + df['Ospite'].unique().tolist())))
            with col_f1:
                giocatore_scelto = st.selectbox("🧑‍💼 Filtra per giocatore:", [''] + giocatori, key='filtro_giocatore_sel_main')
            if giocatore_scelto:
                with col_f2:
                    stato_gioc = st.radio(
                        "Stato partita:",
                        ('Tutte', 'Giocate', 'Da Giocare'),
                        horizontal=True,
                        key='stato_giocatore_radio_main'
                    )
                with col_f3:
                    # Filtro andata/ritorno
                    tipo_gioc = st.radio(
                        "Tipo:",
                        ('Entrambe', 'Andata', 'Ritorno'),
                        horizontal=True,
                        key='tipo_giocatore_radio_main'
                    )
                st.subheader(f"🗓️ Partite per {giocatore_scelto}")

                df_filtrato = df[(df['Casa'] == giocatore_scelto) | (df['Ospite'] == giocatore_scelto)]

                # Applica filtro stato
                if stato_gioc == 'Giocate':
                    df_filtrato = df_filtrato[df_filtrato['Valida'] == True]
                elif stato_gioc == 'Da Giocare':
                    df_filtrato = df_filtrato[df_filtrato['Valida'] == False]

                # Applica filtro andata/ritorno
                if tipo_gioc != 'Entrambe':
                    max_giornata = df_filtrato['Giornata'].max() if not df_filtrato.empty else 0
                    if max_giornata > 0:
                        n_giornate = max_giornata // 2 if tipo_gioc == 'Andata' else max_giornata - (max_giornata // 2)
                        if tipo_gioc == 'Andata':
                            df_filtrato = df_filtrato[df_filtrato['Giornata'] <= n_giornate]
                        else:  # 'Ritorno'
                            df_filtrato = df_filtrato[df_filtrato['Giornata'] > max_giornata // 2]

                #if not df_filtrato.empty:
                # --- visuale tabella per "Giocatore" ---
                if not df_filtrato.empty:
                    col1, col2, col3 = st.columns([1, 6, 1])
                    with col2:
                        st.image("mobile.png")

                    df_show = df_filtrato.reset_index().copy()
                    idx_map = df_show['index'].tolist()
                    df_show.insert(0, 'Sel', False)

                    df_show['Girone'] = df_show['Girone'].astype(str).str.replace("Girone ", "", regex=False)
                    
                    # Gestione visualizzazione nomi in base alla selezione dell'utente
                    modalita_visualizzazione = st.session_state.get('modalita_visualizzazione_sidebar', 'Solo squadre')
                    
                    if modalita_visualizzazione == 'Solo squadre':
                        df_show['Casa'] = df_show['Casa'].apply(lambda x: str(x).split("-")[0].strip() if pd.notna(x) and "-" in str(x) else x)
                        df_show['Ospite'] = df_show['Ospite'].apply(lambda x: str(x).split("-")[0].strip() if pd.notna(x) and "-" in str(x) else x)
                    elif modalita_visualizzazione == 'Solo giocatori':
                        df_show['Casa'] = df_show['Casa'].apply(
                            lambda x: str(x).split("-")[1].strip() if pd.notna(x) and "-" in str(x) and len(str(x).split("-")) > 1 else x
                        )
                        df_show['Ospite'] = df_show['Ospite'].apply(
                            lambda x: str(x).split("-")[1].strip() if pd.notna(x) and "-" in str(x) and len(str(x).split("-")) > 1 else x
                        )

                    num_gironi = df['Girone'].nunique() if 'Girone' in df.columns else 1

                    editable_cols = ['GolCasa', 'GolOspite', 'Valida']

                    display_cols = ['Sel']
                    if num_gironi > 1:
                        display_cols.append('Girone')
                    display_cols += ['Giornata','Casa','Ospite','GolCasa','GolOspite','Valida']

                    column_config = {
                        "Sel": st.column_config.CheckboxColumn("", width=15),
                        "index": st.column_config.Column("ID", width=15),  # non mostrata, usiamo idx_map
                        "Giornata": st.column_config.NumberColumn("🗓️", min_value=0, step=1, width=15),
                        "Casa": st.column_config.TextColumn("🏠", width=50),
                        "Ospite": st.column_config.TextColumn("🛫", width=50),
                        "GolCasa": st.column_config.NumberColumn("⚽️", min_value=0, max_value=20, width=15),
                        "GolOspite": st.column_config.NumberColumn("⚽️", min_value=0, max_value=20, width=15),
                        "Valida": st.column_config.CheckboxColumn("✅", width=15),
                    }
                    if num_gironi > 1:
                        column_config["Girone"] = st.column_config.TextColumn("🏟️", width=15)

                    df_edit = st.data_editor(
                        df_show[display_cols],
                        width="stretch",
                        num_rows="dynamic",
                        column_config=column_config
                    )

                    if st.button("💾 Salva modifiche tabella (Giocatore)"):
                        for i in range(len(df_edit)):
                            row = df_edit.iloc[i]
                            orig_idx = idx_map[i]
                            for col in editable_cols:
                                st.session_state['df_torneo'].at[orig_idx, col] = row[col]
                        if st.session_state.get('tournament_id'):
                            aggiorna_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], st.session_state['df_torneo'])
                        st.success("Modifiche salvate!")
                else:
                    st.info("🎉 Nessuna partita trovata per questo giocatore.")

                
        elif filtro_principale == 'Girone':
            col_g1, col_g2, col_g3 = st.columns([1, 1, 1], vertical_alignment="bottom")
            gironi_disponibili = sorted(df['Girone'].unique().tolist())
            with col_g1:
                girone_scelto = st.selectbox("🧩 Filtra per Girone:", gironi_disponibili, key='filtro_girone_sel_main')
            if girone_scelto:
                with col_g2:
                    stato_gir = st.radio(
                        "Stato partita:",
                        ('Tutte', 'Giocate', 'Da Giocare'),
                        horizontal=True,
                        key='stato_girone_radio_main'
                    )
                with col_g3:
                    tipo_gir = st.radio(
                        "Tipo:",
                        ('Entrambe', 'Andata', 'Ritorno'),
                        horizontal=True,
                        key='tipo_girone_radio_main'
                    )
                st.subheader(f"🗓️ Partite {girone_scelto}")

                df_filtrato = df[df['Girone'] == girone_scelto]

                # Applica filtro stato
                if stato_gir == 'Giocate':
                    df_filtrato = df_filtrato[df_filtrato['Valida'] == True]
                elif stato_gir == 'Da Giocare':
                    df_filtrato = df_filtrato[df_filtrato['Valida'] == False]

                # Applica filtro andata/ritorno
                if tipo_gir != 'Entrambe':
                    max_giornata = df_filtrato['Giornata'].max() if not df_filtrato.empty else 0
                    if max_giornata > 0:
                        n_giornate = max_giornata // 2 if tipo_gir == 'Andata' else max_giornata - (max_giornata // 2)
                        if tipo_gir == 'Andata':
                            df_filtrato = df_filtrato[df_filtrato['Giornata'] <= n_giornate]
                        else:  # 'Ritorno'
                            df_filtrato = df_filtrato[df_filtrato['Giornata'] > max_giornata // 2]

                #if not df_filtrato.empty:
                # --- visuale tabella per "Girone" ---
                if not df_filtrato.empty:
                    col1, col2, col3 = st.columns([1, 6, 1])
                    with col2:
                        st.image("mobile.png")

                    df_show = df_filtrato.reset_index().copy()
                    idx_map = df_show['index'].tolist()
                    df_show.insert(0, 'Sel', False)

                    df_show['Girone'] = df_show['Girone'].astype(str).str.replace("Girone ", "", regex=False)
                    
                    # Gestione visualizzazione nomi in base alla selezione dell'utente
                    modalita_visualizzazione = st.session_state.get('modalita_visualizzazione_sidebar', 'Solo squadre')
                    
                    if modalita_visualizzazione == 'Solo squadre':
                        df_show['Casa'] = df_show['Casa'].apply(lambda x: str(x).split("-")[0].strip() if pd.notna(x) and "-" in str(x) else x)
                        df_show['Ospite'] = df_show['Ospite'].apply(lambda x: str(x).split("-")[0].strip() if pd.notna(x) and "-" in str(x) else x)
                    elif modalita_visualizzazione == 'Solo giocatori':
                        df_show['Casa'] = df_show['Casa'].apply(
                            lambda x: str(x).split("-")[1].strip() if pd.notna(x) and "-" in str(x) and len(str(x).split("-")) > 1 else x
                        )
                        df_show['Ospite'] = df_show['Ospite'].apply(
                            lambda x: str(x).split("-")[1].strip() if pd.notna(x) and "-" in str(x) and len(str(x).split("-")) > 1 else x
                        )

                    num_gironi = df['Girone'].nunique() if 'Girone' in df.columns else 1

                    editable_cols = ['GolCasa', 'GolOspite', 'Valida']

                    display_cols = ['Sel']
                    if num_gironi > 1:
                        display_cols.append('Girone')
                    display_cols += ['Giornata','Casa','Ospite','GolCasa','GolOspite','Valida']

                    column_config = {
                        "Sel": st.column_config.CheckboxColumn("", width=15),
                        "index": st.column_config.Column("ID", width=15),  # non mostrata, usiamo idx_map
                        "Giornata": st.column_config.NumberColumn("🗓️", min_value=0, step=1, width=15),
                        "Casa": st.column_config.TextColumn("🏠", width=50),
                        "Ospite": st.column_config.TextColumn("🛫", width=50),
                        "GolCasa": st.column_config.NumberColumn("⚽️", min_value=0, max_value=20, width=15),
                        "GolOspite": st.column_config.NumberColumn("⚽️", min_value=0, max_value=20, width=15),
                        "Valida": st.column_config.CheckboxColumn("✅", width=15),
                    }
                    if num_gironi > 1:
                        column_config["Girone"] = st.column_config.TextColumn("🏟️", width=15)

                    df_edit = st.data_editor(
                        df_show[display_cols],
                        width="stretch",
                        num_rows="dynamic",
                        column_config=column_config
                    )

                    if st.button("💾 Salva modifiche tabella (Girone)"):
                        for i in range(len(df_edit)):
                            row = df_edit.iloc[i]
                            orig_idx = idx_map[i]
                            for col in editable_cols:
                                st.session_state['df_torneo'].at[orig_idx, col] = row[col]
                        if st.session_state.get('tournament_id'):
                            aggiorna_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], st.session_state['df_torneo'])
                        st.success("Modifiche salvate!")
                else:
                    st.info("🎉 Nessuna partita trovata per questo girone.")

                
        st.sidebar.markdown("---")
        
        # ✅ 5. 📤 Esportazione (in fondo)
        st.sidebar.subheader("📤 Esportazione")
        if classifica is not None and not classifica.empty:
            if st.sidebar.button("📄 Prepara PDF", width="stretch"):
                pdf_bytes = esporta_pdf(df, classifica, st.session_state['nome_torneo'])
                st.session_state['pdf_pronto'] = pdf_bytes
            if st.session_state.get('pdf_pronto'):
                st.sidebar.download_button(
                    label="📥 Scarica PDF torneo",
                    data=st.session_state['pdf_pronto'],
                    file_name=f"torneo_{st.session_state['nome_torneo']}.pdf",
                    mime="application/pdf",
                    width="stretch"
                )
        else:
            st.sidebar.info("ℹ️ Nessuna partita valida. Compila e valida i risultati per generare la classifica.")

        # Calendario (nessun filtro)
        st.markdown("---")
        if filtro_principale == 'Nessuno':
            col_head1, col_head2 = st.columns([3, 1], vertical_alignment="bottom")
            with col_head1:
                st.subheader("🗺️ Navigazione Calendario")
            with col_head2:
                # UX SUITE: Pulsante Classifica rapido nella pagina principale
                if st.button("📊 Vedi Classifica", key="btn_classifica_main_quick", type="primary", width="stretch"):
                    gironi_attivi = sorted(st.session_state['df_torneo']['Girone'].dropna().unique().tolist())
                    if gironi_attivi:
                        st.session_state['mostra_classifica_girone'] = st.session_state.get('girone_sel', gironi_attivi[0])
                        st.rerun()
            df = st.session_state['df_torneo']

            gironi = sorted(df['Girone'].dropna().unique().tolist())
            
            # Controlla se il girone selezionato esiste, altrimenti imposta il primo
            if st.session_state.get('girone_sel') not in gironi:
                st.session_state['girone_sel'] = gironi[0] if gironi else None

            # Definisci le giornate correnti per il girone selezionato
            if st.session_state['girone_sel']:
                giornate_correnti = sorted(
                    df[df['Girone'] == st.session_state['girone_sel']]['Giornata'].dropna().unique().tolist()
                )
            else:
                giornate_correnti = []

            # Imposta la giornata di default alla prima utile o alla prima disponibile
            if 'giornata_sel_initialized' not in st.session_state or st.session_state.get('nuovo_girone_selezionato', False):
                if giornate_correnti:
                    df_da_validare = df[(df['Valida'] == False) & (df['Girone'] == st.session_state['girone_sel'])]
                    if not df_da_validare.empty:
                        prima_giornata_utile = df_da_validare['Giornata'].min()
                        st.session_state['giornata_sel'] = prima_giornata_utile
                    else:
                        st.session_state['giornata_sel'] = giornate_correnti[0]
                else:
                    st.session_state['giornata_sel'] = 1
                st.session_state['giornata_sel_initialized'] = True
                st.session_state['nuovo_girone_selezionato'] = False

            # Selettore del Girone
            nuovo_girone = st.selectbox("📁 Seleziona Girone", gironi, index=gironi.index(st.session_state['girone_sel']))
            if nuovo_girone != st.session_state['girone_sel']:
                st.session_state['girone_sel'] = nuovo_girone
                st.session_state['nuovo_girone_selezionato'] = True
                st.rerun()

            # Utilizza le impostazioni dalla sidebar
            modalita_scelta = st.session_state.get('modalita_scelta_sidebar', 'squadre')
            modalita_bottoni = st.session_state.get('usa_bottoni_sidebar', False)

            # Logica di visualizzazione basata sulla checkbox
            if modalita_bottoni:
                if giornate_correnti:
                    navigation_buttons("Giornata", 'giornata_sel', giornate_correnti[0], giornate_correnti[-1])
                else:
                    st.info("Nessuna giornata disponibile per la navigazione.")
            else:
                if giornate_correnti:
                    try:
                        current_index = giornate_correnti.index(st.session_state['giornata_sel'])
                    except ValueError:
                        current_index = 0
                        st.session_state['giornata_sel'] = giornate_correnti[0]
                    nuova_giornata = st.selectbox("📅 Seleziona Giornata", giornate_correnti, index=current_index)
                    if nuova_giornata != st.session_state['giornata_sel']:
                        st.session_state['giornata_sel'] = nuova_giornata
                        st.rerun()
                else:
                    st.info("Nessuna giornata disponibile.")

            # Se stiamo mostrando la classifica
            if st.session_state.get('mostra_classifica_girone'):
                girone = st.session_state['mostra_classifica_girone']
                
                # Mostra la classifica
                st.markdown(f"# 📊 Classifica {girone}")
                classifica = aggiorna_classifica(df)
                if classifica is not None and not classifica.empty:
                    mostra_classifica_stilizzata(classifica, girone)
                else:
                    st.info("⚽ Nessuna partita validata per questo girone.")
                
                # Bottone per tornare indietro
                if st.button("🔙 Torna al calendario"):
                    st.session_state['mostra_classifica_girone'] = None
                    st.rerun()
                
                # Non mostrare il resto
                st.stop()
            
            # Richiama la funzione con il parametro di visualizzazione corretto
            if giornate_correnti:
                vista_scelta = st.session_state.get('tipo_vista_selezionata', 'compact')
                
                if vista_scelta == 'compact':
                    mostra_calendario_compact(df, st.session_state['girone_sel'], st.session_state['giornata_sel'], modalita_scelta)
                elif vista_scelta == 'premium':
                    mostra_calendario_premium(df, st.session_state['girone_sel'], st.session_state['giornata_sel'], modalita_scelta)
                else: # standard
                    mostra_calendario_giornata(df, st.session_state['girone_sel'], st.session_state['giornata_sel'], modalita_scelta)
            else:
                st.info("Seleziona un girone per visualizzare il calendario.")

            if st.button(
                "💾 Salva Risultati Giornata",
                disabled=st.session_state.get('read_only', True),
                help="Accesso in scrittura richiesto" if st.session_state.get('read_only', True) else "Salva i risultati della giornata"
            ):
                if verify_write_access():
                    salva_risultati_giornata(tournaments_collection, st.session_state['girone_sel'], st.session_state['giornata_sel'])
        # Fine Calendario 

    else:
        if st.session_state.get('azione_scelta') is None:
            st.markdown("### Scegli azione 📝")
            c1, c2 = st.columns([1,1])
            
            with c1:
                # mostra la colonna "Carica torneo" solo se l'utente non ha ancora scelto o ha scelto 'carica'
                if st.session_state.get('azione_scelta') in (None, 'carica'):           
                    with st.container(border=True):
                        st.markdown(
                            """<div style='text-align:center'>
                            <h2>📂 Carica torneo esistente</h2>
                            <p style='margin:0.2rem 0 1rem 0'>Riprendi un torneo salvato (MongoDB)</p>
                            </div>""",
                            unsafe_allow_html=True,
                        )
                        tornei_disponibili = carica_tornei_da_db(tournaments_collection)
                        if tornei_disponibili:
                            tornei_map = {t['nome_torneo']: str(t['_id']) for t in tornei_disponibili}
                            nome_sel = st.selectbox("📦 Seleziona torneo esistente", list(tornei_map.keys()))
                            if st.button("Carica torneo (MongoDB) 📂", key="btn_carica", width="stretch"):
                                st.session_state['tournament_id'] = tornei_map[nome_sel]
                                st.session_state['nome_torneo'] = nome_sel
                                torneo_data = carica_torneo_da_db(tournaments_collection, st.session_state['tournament_id'])
                                if torneo_data and 'calendario' in torneo_data:
                                    st.session_state['calendario_generato'] = True
                                    st.toast("✅ Torneo caricato con successo")
                                    st.rerun()
                                else:
                                    st.error("❌ Errore durante il caricamento del torneo. Riprova.")
                        else:
                            st.info("ℹ️ Nessun torneo salvato trovato su MongoDB.")

            with c2:
                # mostra la colonna "Nuovo torneo" solo se l'utente non ha ancora scelto o ha scelto 'crea'
                if st.session_state.get('azione_scelta') in (None, 'crea'):
                    with st.container(border=True):
                        st.markdown(
                            """<div style='text-align:center'>
                            <h2>✨ Crea nuovo torneo</h2>
                            <p style='margin:0.2rem 0 1rem 0'>Genera primo turno scegliendo giocatori del Club PierCrew</p>
                            </div>""",
                            unsafe_allow_html=True,
                        )
                        
                        if st.button("Nuovo torneo ✨", key="btn_nuovo", width="stretch"):
                            st.session_state['mostra_form_creazione'] = True
                            st.session_state['azione_scelta'] = 'crea'
                            st.rerun()
            
            st.markdown("---")

        if st.session_state.get('mostra_form_creazione', False):
            # bottone Indietro: torna alla scelta iniziale
            #1if st.session_state.get('azione_scelta') == 'crea':
                #1if st.button("🔙 Indietro", key="indietro_crea"):
                    #1st.session_state['mostra_form_creazione'] = False
                    #1st.session_state['azione_scelta'] = None
                    #1st.rerun()
            # ── STEP 1: Dettagli Nuovo Torneo + Selezione Giocatori ──
            # Nasconde questa sezione dopo la conferma dei giocatori
            if not st.session_state.get('giocatori_confermati', False):
                st.markdown("---")
                st.header("🆕 Dettagli Nuovo Torneo")
                nome_default = f"TorneoSubbuteo_{datetime.now().strftime('%d%m%Y')}"
                nome_torneo = st.text_input("📝 Nome del torneo", value=st.session_state.get("nome_torneo", nome_default), key="nome_torneo_input")
                st.session_state["nome_torneo"] = nome_torneo
                num_gironi = st.number_input("🔢 Numero di gironi", 1, 8, value=st.session_state.get("num_gironi", 1), key="num_gironi_input")
                st.session_state["num_gironi"] = num_gironi
                tipo_calendario = st.selectbox("📅 Tipo calendario", ["Solo andata", "Andata e ritorno"], key="tipo_calendario_input")
                st.session_state["tipo_calendario"] = tipo_calendario
                n_giocatori = st.number_input("👥 Numero giocatori", 3, 64, value=st.session_state.get("n_giocatori", 3), key="n_giocatori_input")
                st.session_state["n_giocatori"] = n_giocatori

                st.markdown("### 👥 Seleziona Giocatori")
                amici = df_master['Giocatore'].tolist() if not df_master.empty else []
                
                # Aggiungi checkbox per importare tutti i giocatori
                importa_tutti = st.checkbox("Importa tutti i giocatori del Club", key="importa_tutti_giocatori")
                
                # Se il checkbox è selezionato, seleziona automaticamente tutti i giocatori
                if importa_tutti:
                    amici_selezionati = amici
                    st.session_state["n_giocatori"] = len(amici)  # Aggiorna automaticamente il numero di partecipanti
                    st.session_state["amici_selezionati"] = amici  # Salva la selezione
                else:
                    # Usa il valore corretto per il controllo della modalità
                    usa_multiselect = st.session_state.get('usa_multiselect_giocatori', False)
                    
                    if usa_multiselect:
                        # Modalità MULTISELECT
                        amici_selezionati = st.multiselect(
                            "Seleziona giocatori dal database", 
                            sorted(amici),   # già ordinati alfabeticamente
                            default=st.session_state.get("amici_selezionati", []), 
                            key="amici_multiselect"
                        )
                    else:
                        # Modalità CHECKBOX INDIVIDUALI
                        st.markdown("### Seleziona i giocatori")
                        amici_selezionati = st.session_state.get("amici_selezionati", []).copy()
                        
                        # Crea una griglia di checkbox (3 colonne)
                        cols = st.columns(3)
                        for i, giocatore in enumerate(sorted(amici)):
                            with cols[i % 3]:
                                # Usa il valore corrente dalla lista dei selezionati come default
                                is_checked = giocatore in amici_selezionati
                                if st.checkbox(giocatore, value=is_checked, key=f"chk_{giocatore}"):
                                    if giocatore not in amici_selezionati:
                                        amici_selezionati.append(giocatore)
                                else:
                                    if giocatore in amici_selezionati:
                                        amici_selezionati.remove(giocatore)
                        
                        # Aggiorna la lista dei giocatori selezionati nella sessione
                        st.session_state["amici_selezionati"] = amici_selezionati


                num_supplementari = st.session_state["n_giocatori"] - len(amici_selezionati)
                if num_supplementari < 0:
                    st.warning(f"⚠️ Hai selezionato più giocatori ({len(amici_selezionati)}) del numero partecipanti ({st.session_state['n_giocatori']}). Riduci la selezione.")
                    return

                st.markdown(f"🙋‍♂️ Giocatori ospiti da aggiungere: **{max(0, num_supplementari)}**")
                giocatori_supplementari = []
                if 'giocatori_supplementari_list' not in st.session_state:
                    st.session_state['giocatori_supplementari_list'] = [''] * max(0, num_supplementari)

                for i in range(max(0, num_supplementari)):
                    nome_ospite = st.text_input(f"Nome ospite {i+1}", value=st.session_state['giocatori_supplementari_list'][i], key=f"ospite_{i}")
                    st.session_state['giocatori_supplementari_list'][i] = nome_ospite
                    if nome_ospite:
                        giocatori_supplementari.append(nome_ospite.strip())
                        
                # Opzione post-selezione: popolare il campo "Nome squadra" con il nome del giocatore
                usa_nomi_giocatori = st.checkbox(
                    "Usa i nomi dei giocatori come nomi delle squadre",
                    key="usa_nomi_giocatori",
                    value=False
                )
                #inizio
                if st.button("✅ Conferma Giocatori", width="stretch", disabled=st.session_state.get('read_only', True)):
                    if not verify_write_access():
                        return

                    # unisci selezione DB + giocatori ospiti
                    giocatori_scelti = amici_selezionati + [g for g in giocatori_supplementari if g]
                    # controllo minimo 3 giocatori
                    if len(set(giocatori_scelti)) < 3:
                        st.warning("⚠️ Inserisci almeno 3 giocatori diversi.")
                        return

                    # salva la lista definitiva (rimuove duplicati preservando l'ordine)
                    # dict.fromkeys mantiene l'ordine in Python >= 3.7
                    st.session_state['giocatori_selezionati_definitivi'] = list(dict.fromkeys(giocatori_scelti))

                    st.session_state['mostra_assegnazione_squadre'] = True
                    st.session_state['mostra_gironi'] = False
                    st.session_state['gironi_manuali_completi'] = False
                    st.session_state['giocatori_confermati'] = True

                    # Ricostruisce gioc_info preservando potenziale e altri attributi dal DB,
                    # ma — se l'opzione è attiva — imposta Squadra = nome del giocatore
                    st.session_state['gioc_info'] = {}
                    usa_nomi = st.session_state.get('usa_nomi_giocatori', False)

                    for gioc in st.session_state['giocatori_selezionati_definitivi']:
                        if not df_master.empty and 'Giocatore' in df_master.columns and gioc in df_master['Giocatore'].values:
                            row = df_master[df_master['Giocatore'] == gioc].iloc[0]
                            squadra_default = row.get('Squadra', "")
                            # compatibilità col nome colonna Potenziale (es. 'Potenziale')
                            try:
                                potenziale_default = int(row.get('Potenziale', row.get('potenziale', 4)))
                            except Exception:
                                potenziale_default = 4
                        else:
                            squadra_default = ""
                            potenziale_default = 4

                        # se l'opzione è attiva, sovrascrivo SOLO il nome della squadra con il nome del giocatore
                        if usa_nomi:
                            squadra_default = gioc

                        st.session_state['gioc_info'][gioc] = {"Squadra": squadra_default, "Potenziale": potenziale_default}

                    st.toast("✅ Giocatori confermati")
                    st.rerun()
            # ── FINE STEP 1 ──

            # ── STEP 2: Modifica Squadra e Potenziale ──
            if st.session_state.get('mostra_assegnazione_squadre', False) and not st.session_state.get('mostra_gironi', False):
                # Bottone Indietro per tornare alla selezione giocatori
                if st.button("⬅️ Torna alla selezione giocatori", key="back_to_players"):
                    st.session_state['giocatori_confermati'] = False
                    st.session_state['mostra_assegnazione_squadre'] = False
                    st.rerun()
                st.markdown("---")
                st.markdown("### ⚽ Modifica Squadra e Potenziale")
                st.markdown("Assegna una squadra e un valore di potenziale a ciascun giocatore.")
                
                # Inizializza gioc_info se non esiste
                if 'gioc_info' not in st.session_state:
                    st.session_state['gioc_info'] = {}
                
                # Mostra i controlli per ogni giocatore
                for gioc in st.session_state['giocatori_selezionati_definitivi']:
                    if gioc not in st.session_state['gioc_info']:
                        if not df_master.empty and gioc in df_master['Giocatore'].values:
                            row = df_master[df_master['Giocatore'] == gioc].iloc[0]
                            squadra_default = row['Squadra']
                            potenziale_default = int(row['Potenziale'])
                        else:
                            squadra_default = ""
                            potenziale_default = 4
                        st.session_state['gioc_info'][gioc] = {"Squadra": squadra_default, "Potenziale": potenziale_default}

                    c1, c2 = st.columns([2, 1])
                    with c1:
                        squadra_nuova = st.text_input(f"🏳️‍⚧️ Squadra per {gioc}", value=st.session_state['gioc_info'][gioc]["Squadra"], key=f"squadra_{gioc}")
                    with c2:
                        potenziale_nuovo = st.slider(f"⭐ Potenziale per {gioc}", 1, 10, int(st.session_state['gioc_info'][gioc]["Potenziale"]), key=f"potenziale_{gioc}")
                    st.session_state['gioc_info'][gioc]["Squadra"] = squadra_nuova
                    st.session_state['gioc_info'][gioc]["Potenziale"] = potenziale_nuovo

                if st.button("✅ Conferma Squadre e Potenziali", width="stretch", disabled=st.session_state.get('read_only', True)):
                    if not verify_write_access():
                        return
                    # Salva i dati delle squadre
                    squadre_dati = [
                        {"Giocatore": giocatore, "Squadra": info["Squadra"], "Potenziale": info["Potenziale"]}
                        for giocatore, info in st.session_state['gioc_info'].items()
                    ]
                    st.session_state['df_squadre'] = pd.DataFrame(squadre_dati)
                    
                    # Nascondi il form corrente e mostra il successivo
                    st.session_state['mostra_assegnazione_squadre'] = False
                    st.session_state['mostra_gironi'] = True
                    st.session_state['gironi_manuali_completi'] = False
                    
                    # Prepara i dati dei giocatori con squadra e potenziale
                    giocatori_con_dati = []
                    for giocatore, info in st.session_state['gioc_info'].items():
                        giocatori_con_dati.append({
                            'nome': giocatore,
                            'squadra': info['Squadra'],
                            'potenziale': info['Potenziale'],
                            'coppia': f"{info['Squadra']} - {giocatore}"
                        })
                    
                    # Ordina per potenziale (dal più alto al più basso)
                    giocatori_ordinati = sorted(
                        giocatori_con_dati,
                        key=lambda x: x['potenziale'],
                        reverse=True
                    )
                    
                    num_gironi = st.session_state.get('num_gironi', 1)
                    gironi = {f'Girone {i+1}': [] for i in range(num_gironi)}
                    
                    # Distribuisci le coppie squadra-giocatore nei gironi in modo bilanciato
                    for i, giocatore in enumerate(giocatori_ordinati):
                        girone_idx = i % num_gironi
                        girone_nome = f'Girone {girone_idx + 1}'
                        gironi[girone_nome].append(giocatore['coppia'])
                    
                    # Salva sia le coppie che i dati completi per riferimento
                    st.session_state['gironi_auto_generati'] = gironi
                    st.session_state['dettagli_giocatori'] = {g['coppia']: g for g in giocatori_con_dati}
                    
                    # Inizializza i gironi manuali con la proposta automatica
                    for i, (girone, giocatori) in enumerate(gironi.items(), 1):
                        st.session_state[f'manual_girone_{i}'] = giocatori
                    
                    st.toast("✅ Squadre e potenziali confermati")
                    st.rerun()

            # ── STEP 3: Gironi e Generazione Calendario ──
            if st.session_state.get('mostra_gironi', False):
                # Bottone Indietro per tornare alla modifica squadre/potenziali
                if st.button("⬅️ Torna a Squadre e Potenziali", key="back_to_squads"):
                    st.session_state['mostra_gironi'] = False
                    st.session_state['mostra_assegnazione_squadre'] = True
                    st.session_state['gironi_manuali_completi'] = False
                    st.rerun()
                st.markdown("---")
                st.markdown("### 🧩 Modalità di creazione dei gironi")
                
                # Genera automaticamente i gironi bilanciati per potenziale
                if 'gironi_auto_generati' not in st.session_state:
                    # Prepara i dati dei giocatori con squadra e potenziale
                    giocatori_con_dati = []
                    for giocatore, info in st.session_state['gioc_info'].items():
                        giocatori_con_dati.append({
                            'nome': giocatore,
                            'squadra': info['Squadra'],
                            'potenziale': info['Potenziale'],
                            'coppia': f"{info['Squadra']} - {giocatore}"
                        })
                    
                    # Ordina per potenziale (dal più alto al più basso)
                    giocatori_ordinati = sorted(
                        giocatori_con_dati,
                        key=lambda x: x['potenziale'],
                        reverse=True
                    )
                    
                    # Crea i gironi bilanciati
                    num_gironi = st.session_state.get('num_gironi', 1)
                    gironi = {f'Girone {i+1}': [] for i in range(num_gironi)}
                    
                    # Distribuisci le coppie squadra-giocatore nei gironi in modo bilanciato
                    for i, giocatore in enumerate(giocatori_ordinati):
                        girone_idx = i % num_gironi
                        girone_nome = f'Girone {girone_idx + 1}'
                        gironi[girone_nome].append(giocatore['coppia'])
                    
                    # Salva sia le coppie che i dati completi per riferimento
                    st.session_state['gironi_auto_generati'] = gironi
                    st.session_state['dettagli_giocatori'] = {g['coppia']: g for g in giocatori_con_dati}
                
                # Mostra anteprima gironi automatici
                st.markdown("### 📊 Anteprima Gironi Automatici")
                st.markdown("Ecco come verrebbero suddivisi i giocatori nei gironi con la modalità automatica:")
                
                # Crea una tabella HTML per visualizzare i gironi in modo ordinato
                num_colonne = min(3, st.session_state.get('num_gironi', 1))
                colonne = st.columns(num_colonne)
                
                for idx, (girone, coppie) in enumerate(st.session_state['gironi_auto_generati'].items()):
                    with colonne[idx % num_colonne]:
                        # Calcola il potenziale medio del girone
                        potenziali = [st.session_state['dettagli_giocatori'][coppia]['potenziale'] for coppia in coppie]
                        pot_medio = sum(potenziali) / len(potenziali) if potenziali else 0
                        
                        with st.expander(f"{girone} (Pot. medio: {pot_medio:.1f}⭐)", expanded=True):
                            for coppia in coppie:
                                dettagli = st.session_state['dettagli_giocatori'][coppia]
                                st.markdown(f"- {coppia} - {dettagli['potenziale']}⭐")
                
                st.markdown("---")
                modalita_gironi = st.radio(
                    "Scegli come popolare i gironi", 
                    ["Popola Gironi Automaticamente", "Popola Gironi Manualmente"], 
                    key="modo_gironi_radio"
                )

                if modalita_gironi == "Popola Gironi Manualmente":
                    st.warning("⚠️ Se hai modificato il numero di giocatori, assicurati che i gironi manuali siano coerenti prima di generare il calendario.")
                    gironi_manuali = {}
                    
                    # Prepara l'elenco delle coppie squadra-giocatore disponibili
                    giocatori_con_dati = []
                    for giocatore, info in st.session_state['gioc_info'].items():
                        coppia = f"{info['Squadra']} - {giocatore}"
                        giocatori_con_dati.append(coppia)
                    
                    # Inizializza i gironi manuali se non esistono
                    for i in range(st.session_state['num_gironi']):
                        girone_key = f'Girone {i+1}'
                        st.markdown(f"**📦 {girone_key}**")
                        
                        # Recupera i giocatori già assegnati a questo girone
                        giocatori_assegnati = st.session_state.get(f"manual_girone_{i+1}", [])
                        
                        # Filtra i giocatori già assegnati ad altri gironi
                        giocatori_disponibili = [g for g in giocatori_con_dati 
                                              if g not in sum(gironi_manuali.values(), []) 
                                              or g in giocatori_assegnati]
                        
                        # Seleziona i giocatori per questo girone
                        giocatori_selezionati = st.multiselect(
                            f"Seleziona i giocatori per {girone_key}",
                            options=giocatori_disponibili,
                            default=giocatori_assegnati,
                            key=f"manual_girone_select_{i}",
                            format_func=lambda x: x
                        )
                        
                        # Aggiorna lo stato con i giocatori selezionati
                        st.session_state[f'manual_girone_{i+1}'] = giocatori_selezionati
                        gironi_manuali[girone_key] = giocatori_selezionati

                    if st.button("✅ Conferma Gironi Manuali", width="stretch", disabled=st.session_state.get('read_only', True)):
                        if not verify_write_access():
                            return
                        # Verifica che tutti i giocatori siano stati assegnati
                        giocatori_assegnati = [g for girone in gironi_manuali.values() for g in girone]
                        
                        # Verifica duplicati
                        if len(giocatori_assegnati) != len(set(giocatori_assegnati)):
                            st.error("⚠️ Alcuni giocatori sono stati assegnati più volte!")
                        # Verifica che il numero di giocatori corrisponda
                        elif len(giocatori_assegnati) != len(st.session_state['giocatori_selezionati_definitivi']):
                            st.error(f"⚠️ Devi assegnare tutti i {len(st.session_state['giocatori_selezionati_definitivi'])} giocatori!")
                        # Verifica che i gironi non siano vuoti
                        elif any(len(girone) == 0 for girone in gironi_manuali.values()):
                            st.error("⚠️ Tutti i gironi devono contenere almeno un giocatore!")
                        else:
                            # Salva i gironi manuali
                            st.session_state['gironi_manuali'] = gironi_manuali
                            st.session_state['gironi_manuali_completi'] = True
                            
                            # Prepara i dettagli per la visualizzazione
                            dettagli_giocatori = {}
                            for giocatore, info in st.session_state['gioc_info'].items():
                                coppia = f"{info['Squadra']} - {giocatore}"
                                dettagli_giocatori[coppia] = {
                                    'nome': giocatore,
                                    'squadra': info['Squadra'],
                                    'potenziale': info['Potenziale'],
                                    'coppia': coppia
                                }
                            st.session_state['dettagli_giocatori'] = dettagli_giocatori
                            
                            st.toast("✅ Gironi manuali confermati")
                            st.rerun()

                if st.button("🏁 Genera Calendario", width="stretch", disabled=st.session_state.get('read_only', True)):
                    if not verify_write_access():
                        return
                    if modalita_gironi == "Popola Gironi Manualmente" and not st.session_state.get('gironi_manuali_completi', False):
                        st.error("❌ Per generare il calendario manualmente, clicca prima su 'Conferma Gironi Manuali'.")
                        return

                    # Prepara i gironi finali in base alla modalità selezionata
                    if modalita_gironi == "Popola Gironi Automaticamente":
                        gironi_finali = [list(girone) for girone in st.session_state['gironi_auto_generati'].values()]
                        giocatori_formattati = [gioc for girone in gironi_finali for gioc in girone]
                    else:
                        gironi_finali = [list(girone) for girone in st.session_state['gironi_manuali'].values()]
                        giocatori_formattati = [gioc for girone in gironi_finali for gioc in girone]
                        
                        # Verifica che tutte le coppie abbiano il formato corretto
                        for coppia in giocatori_formattati:
                            if ' - ' not in coppia:
                                st.error(f"⚠️ Formato non valido per la coppia: {coppia}")
                                return

                    #st.write(":blue[Segnale 2: Gironi finali creati, sto per generare il calendario]")

                    for girone in gironi_finali:
                        if len(girone) < 2:
                            st.error("❌ Errore: Un girone contiene meno di due giocatori. Aggiungi altri giocatori o modifica i gironi.")
                            return

                    try:
                        tid = None
                        df_torneo = genera_calendario_from_list(gironi_finali, st.session_state['tipo_calendario'])

                        df_torneo['Girone'] = df_torneo['Girone'].astype('string')
                        df_torneo['Casa'] = df_torneo['Casa'].astype('string')
                        df_torneo['Ospite'] = df_torneo['Ospite'].astype('string')

                        #st.write(":blue[Segnale 3: Calendario generato, sto per salvare su MongoDB]")

                        st.session_state['debug_message'] = {
                            'tid_valore': "Non ancora salvato.",
                            'df_colonne': list(df_torneo.columns),
                            'df_dtypes': df_torneo.dtypes.to_dict(),
                            'messaggio': "Debug salvato correttamente."
                        }

                        # Salva il torneo su MongoDB
                        tid = salva_torneo_su_db(
                            tournaments_collection, 
                            df_torneo, 
                            st.session_state['nome_torneo'],
                            tournament_id=st.session_state.get('tournament_id')
                        )

                        if tid:
                            st.session_state['df_torneo'] = df_torneo
                            st.session_state['tournament_id'] = str(tid)
                            st.session_state['calendario_generato'] = True
                            st.session_state['debug_message'] = {
                                'tid_valore': str(tid),
                                'df_colonne': list(df_torneo.columns),
                                'df_dtypes': df_torneo.dtypes.to_dict(),
                                'messaggio': "Torneo salvato correttamente."
                            }
                            st.toast("✅ Calendario generato e salvato su MongoDB")
                            st.rerun()
                        else:
                            st.error("❌ Errore durante il salvataggio del torneo. Controlla la connessione al database.")
                    except Exception as e:
                        st.error(f"❌ Errore critico durante il salvataggio: {e}")
                        st.rerun()
                    
    # Banner vincitori
    if st.session_state.get('torneo_completato', False) and st.session_state.get('classifica_finale') is not None:
        vincitori = []
        df_classifica = st.session_state['classifica_finale']
        for girone in df_classifica['Girone'].unique():
            primo = df_classifica[df_classifica['Girone'] == girone].iloc[0]['Squadra']
            vincitori.append(f"🏅 {girone}: {primo}")
            
        vincitori_stringa = ", ".join(vincitori)

        # Visualizza il banner personalizzato con i vincitori
        st.markdown(
            f"""
            <div style='background:linear-gradient(90deg, gold, orange);
                        padding:20px;
                        border-radius:12px;
                        text-align:center;
                        color:black;
                        font-size:28px;
                        font-weight:bold;
                        margin-top:20px;'>
                🎉 Torneo Completato! Vincitori → {vincitori_stringa}
            </div>
            """, unsafe_allow_html=True)
        
        # Calcola il numero di gironi in base alla classifica finale
        num_gironi = len(df_classifica['Girone'].unique()) if 'Girone' in df_classifica.columns else 0
        st.write("Numero di gironi rilevati:", num_gironi)
        
        # Esegui l'animazione e la musica solo se c'è almeno un girone
        if num_gironi > 0:
            try:
                # Riproduci l'audio della vittoria
                try:
                    audio_url = "https://raw.githubusercontent.com/legnaro72/torneo-Subbuteo-webapp/main/docs/wearethechamp.mp3"
                    response = requests.get(audio_url, timeout=10)
                    response.raise_for_status()
                    autoplay_audio(response.content)
                except Exception as e:
                    st.warning(f"Impossibile caricare l'audio: {str(e)}")
                    st.warning("La riproduzione dell'audio non è disponibile")
                
                # Crea un contenitore vuoto per i messaggi
                placeholder = st.empty()
                
                # Lancia i palloncini in un ciclo per 3 secondi
                with placeholder.container():
                    st.balloons()
                    time.sleep(1)
                
                with placeholder.container():
                    st.balloons()
                    time.sleep(1)
                
                with placeholder.container():
                    st.balloons()
                    time.sleep(1)
                    
            except requests.exceptions.RequestException as e:
                st.error(f"Errore durante il caricamento dell'audio: {e}")

        
        # Nuovo blocco di codice per il reindirizzamento
        if st.session_state.get('show_redirect_button', False):
            st.markdown("---")
            st.subheader("🚀 Prosegui alle fasi finali?")
            st.info("Il torneo è completo e salvato. Vuoi passare all'applicazione per le fasi finali?")
            
            # Questo bottone chiamerà la funzione di reindirizzamento
            if st.button("👉 Vai alle Fasi Finali", use_container_width=True):
                redirect_to_final_phase(f"completato_{st.session_state['nome_torneo']}")
    # Footer leggero
    st.markdown("---")
    st.caption("⚽ Subbuteo Tournament Manager •  Made by Legnaro72")

if __name__ == "__main__":
    main()
