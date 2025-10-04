import streamlit as st
import base64
import datetime
import io
import json
import os
import re
import time
import uuid
from datetime import datetime as dt, timedelta
from io import BytesIO
import logging_utils as log

import numpy as np
import pandas as pd
import pymongo
import pytz
import requests
from bson import ObjectId
from bson.json_util import dumps, loads
from pymongo import MongoClient, server_api
import urllib.parse
from fpdf import FPDF
import warnings
import certifi
import math

# Import auth utilities
import auth_utils as auth

# Silenzia solo il warning di deprecazione relativo a st.experimental_get_query_params
warnings.filterwarnings(
    "ignore",
    message=".*st.experimental_get_query_params.*",
    category=DeprecationWarning
)

# ==============================================================================
# ✨ Configurazione e stile di pagina (con nuove emoji e colori)
# ==============================================================================
st.set_page_config(
    page_title="⚽ Fase Finale Torneo Subbuteo",
    layout="wide",
    page_icon="🏆",
    initial_sidebar_state="expanded"
)

def reset_app_state():
    """Resetta lo stato dell'applicazione"""
    keys_to_reset = [
        "df_torneo", "df_squadre", "turno_attivo", "risultati_temp",
        "nuovo_torneo_step", "club_scelto", "giocatori_selezionati_db",
        "giocatori_ospiti", "giocatori_totali", "torneo_iniziato",
        "setup_mode", "torneo_finito", "edited_df_squadre",
        "gioc_info", "modalita_visualizzazione","bg_audio_disabled"
    ]
    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key]
            
# ==============================================================================
# ISTRUZIONE DEFINITIVA: AVVIO AUDIO DI SOTTOFONDO PERSISTENTE
# ==============================================================================
# Definisci la tua URL raw per l'audio di sfondo
BACKGROUND_AUDIO_URL = "https://raw.githubusercontent.com/legnaro72/torneo-Subbuteo-webapp/main/⚽️%20UEFA%20Champions%20League%20🏆%20[TESTO%20originale%20+%20traduzione%20HQ]%20-%20NEW%20VERSION.mp3"

# ==============================================================================

#ul, li { list-style-type: none !important; padding-left: 0 !important; margin-left: 0 !important; }
# -------------------------
# CSS personalizzato
# -------------------------
st.markdown("""
<style>
    .stLinkButton {
        width: 100% !important;
        margin: 10px 0;
    }
    .stLinkButton a {
        width: 100%;
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%) !important;
        color: white !important;
        padding: 10px 20px !important;
        border: none !important;
        border-radius: 8px !important;
        text-align: center !important;
        text-decoration: none !important;
        display: inline-block !important;
        font-size: 16px !important;
        margin: 4px 2px !important;
        cursor: pointer !important;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
    }
    .stLinkButton a:hover {
        background: linear-gradient(135deg, #2a5298 0%, #1e3c72 100%) !important;
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
    }
</style>
""", unsafe_allow_html=True)
st.markdown("""
<style>

ul, li { list-style-type: none !important; padding-left: 0 !important; margin-left: 0 !important; margin: 0 !important; padding: 0 !important; }
.big-title { 
    text-align: center; 
    font-size: clamp(22px, 4vw, 42px); 
    font-weight: 700; 
    margin: 15px 0 10px; 
    color: white; 
    background: linear-gradient(90deg, #457b9d, #1d3557);
    border-radius: 10px;
    box-shadow: 0 4px 14px #00000022;
    padding: 15px;
    text-shadow: 0 1px 2px #0002; 
}
.sub-title { 
    font-size: 20px; 
    font-weight: 700; 
    margin-top: 10px; 
    color: white;
    background: linear-gradient(90deg, #457b9d, #1d3557);
    border-radius: 10px;
    box-shadow: 0 4px 14px #00000022;
    padding: 10px;
    text-align: center;
}
.stButton>button { 
    background: linear-gradient(90deg, #457b9d, #1d3557); 
    color: white; 
    border-radius: 10px; 
    padding: 0.55em 1.0em; 
    font-weight: 700; 
    border: 0; 
    box-shadow: 0 4px 14px #00000022;
}
.stButton>button:hover { 
    transform: translateY(-1px); 
    box-shadow: 0 6px 18px #00000033; 
}
.stDownloadButton>button { 
    background: linear-gradient(90deg, #457b9d, #1d3557); 
    color: white; 
    border-radius: 10px; 
    font-weight: 700; 
    border: 0; 
    box-shadow: 0 4px 14px #00000022;
}
.stDownloadButton>button:hover { 
    transform: translateY(-1px); 
    box-shadow: 0 6px 18px #00000033; 
}
.stDataFrame { border: 2px solid #f4a261; border-radius: 10px; }
.pill { display:inline-block; padding: 4px 10px; border-radius: 999px; background:#f1faee; color:#1d3557; font-weight:700; border:1px solid #a8dadc; }
.small-muted { font-size: 0.9rem; opacity: 0.8; }
hr { margin: 0.6rem 0 1rem 0; }
.main-title {
    font-size: 2.5rem; 
    font-weight: 700; 
    text-align: center; 
    margin-bottom: 2rem;
    color: white;
    background: linear-gradient(90deg, #457b9d, #1d3557);
    border-radius: 10px;
    box-shadow: 0 4px 14px #00000022;
    padding: 20px;
    animation: bounce 1s ease-in-out infinite alternate;
}
@keyframes bounce {
  from { transform: translateY(0px); }
  to { transform: translateY(-5px); }
}
/* Main content h3 styling */
.main .block-container h3 { 
    color: white; 
    font-weight: 700;
    background: linear-gradient(90deg, #457b9d, #1d3557);
    border-radius: 10px;
    box-shadow: 0 4px 14px #00000022;
    padding: 10px;
    text-align: center;
}
/* Sidebar h3 styling - keep default */
.css-1d391kg h3, [data-testid="stSidebar"] h3 {
    color: #1d3557;
    font-weight: 700;
    background: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    padding: 0 !important;
    text-align: left !important;
}
.match-card {
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 15px;
    margin-bottom: 10px;
    background-color: #f9f9f9;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
.validation-status-ok { color: green; font-weight: bold; }
.validation-status-nok { color: red; font-weight: bold; }

/* Sidebar h3 styling - mantiene stile normale */
.css-1d391kg h3, [data-testid="stSidebar"] h3 {
    color: #1d3557;
    font-weight: 700;
    background: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    padding: 0 !important;
    text-align: left !important;
}

/* Tema scuro - sidebar subheaders bianchi con selettori più specifici */
@media (prefers-color-scheme: dark) {
    [data-testid="stSidebar"] h3,
    .css-1d391kg h3,
    [data-testid="stSidebar"] .element-container h3,
    .css-1d391kg .element-container h3 {
        color: #ffffff !important;
        background: none !important;
    }
}

/* Streamlit dark theme - sidebar subheaders bianchi con priorità massima */
.stApp[data-theme="dark"] [data-testid="stSidebar"] h3,
.stApp[data-theme="dark"] .css-1d391kg h3,
.stApp[data-theme="dark"] [data-testid="stSidebar"] .element-container h3,
.stApp[data-theme="dark"] .css-1d391kg .element-container h3,
.stApp[data-theme="dark"] [data-testid="stSidebar"] div h3,
.stApp[data-theme="dark"] .css-1d391kg div h3 {
    color: #ffffff !important;
    background: none !important;
}

/* Selettori ancora più specifici per forzare il bianco sui subheader */
html[data-theme="dark"] [data-testid="stSidebar"] h3,
html[data-theme="dark"] .css-1d391kg h3,
body[data-theme="dark"] [data-testid="stSidebar"] h3,
body[data-theme="dark"] .css-1d391kg h3 {
    color: #ffffff !important;
}

/* Override per tutti i possibili selettori di subheader nella sidebar */
[data-testid="stSidebar"] h3[class*="css"],
.css-1d391kg h3[class*="css"] {
    color: #ffffff !important;
}

/* CSS con massima specificità per tema scuro */
.stApp[data-theme="dark"] [data-testid="stSidebar"] * h3,
.stApp[data-theme="dark"] .css-1d391kg * h3 {
    color: #ffffff !important;
}

/* Approccio universale - forza bianco su TUTTI gli h3 della sidebar nel tema scuro */
@media (prefers-color-scheme: dark) {
    [data-testid="stSidebar"] h3 {
        color: white !important;
    }
}

.stApp[data-theme="dark"] [data-testid="stSidebar"] h3 {
    color: white !important;
}

/* Selettore CSS universale per tutti gli elementi h3 nella sidebar */
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] .stMarkdown h3,
[data-testid="stSidebar"] div h3 {
    color: white !important;
}

/* Forza il colore blu per i subheader della sidebar in entrambi i temi */
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] h3[class*="st-emotion-cache"],
[data-testid="stSidebar"] h3[class*="css"],
[data-testid="stSidebar"] h3[class*="element-container"],
[data-testid="stSidebar"] h3[class*="stMarkdown"],
[data-testid="stSidebar"] h3[class*="stSubheader"],
[data-testid="stSidebar"] h3[class*="stHeadingContainer"],
[data-testid="stSidebar"] h3[class*="stTitle"],
[data-testid="stSidebar"] .stMarkdown h3,
[data-testid="stSidebar"] .element-container h3,
[data-testid="stSidebar"] .stSubheader h3,
[data-testid="stSidebar"] .stHeadingContainer h3,
[data-testid="stSidebar"] .stTitle h3,
.stApp[data-theme="light"] [data-testid="stSidebar"] h3,
.stApp[data-theme="dark"] [data-testid="stSidebar"] h3,
html[data-theme="light"] [data-testid="stSidebar"] h3,
html[data-theme="dark"] [data-testid="stSidebar"] h3,
body[data-theme="light"] [data-testid="stSidebar"] h3,
body[data-theme="dark"] [data-testid="stSidebar"] h3 {
    color: #0078D4 !important;
    font-weight: 700;
    background: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    padding: 0 !important;
    text-align: left !important;
}

/* Rimuovi eventuali stili di hover o focus che potrebbero sovrascrivere */
[data-testid="stSidebar"] h3:hover,
[data-testid="stSidebar"] h3:focus,
[data-testid="stSidebar"] h3:active {
    color: #0078D4 !important;
}

/* Forza il colore anche per i temi personalizzati */
[data-testid="stSidebar"] h3[style*="color"],
[data-testid="stSidebar"] h3[style*="color"]:hover,
[data-testid="stSidebar"] h3[style*="color"]:focus {
    color: #0078D4 !important;
}

/* Stile per i pulsanti di collegamento nella sidebar */
[data-testid="stSidebar"] .stLinkButton,
[data-testid="stSidebar"] .stLinkButton a,
[data-testid="stSidebar"] .stLinkButton a:visited,
[data-testid="stSidebar"] .stLinkButton a:hover,
[data-testid="stSidebar"] .stLinkButton a:active {
    background: linear-gradient(90deg, #457b9d, #1d3557) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.5rem 1rem !important;
    font-weight: 700 !important;
    text-align: center !important;
    text-decoration: none !important;
    display: inline-block !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1) !important;
}

/* Stile al passaggio del mouse */
[data-testid="stSidebar"] .stLinkButton:hover,
[data-testid="stSidebar"] .stLinkButton a:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15) !important;
}

/* Stile al click */
[data-testid="stSidebar"] .stLinkButton:active,
[data-testid="stSidebar"] .stLinkButton a:active {
    transform: translateY(0) !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1) !important;
}

/* Stile per il tema scuro */
[data-testid="stSidebar"][data-baseweb="dark"] .stLinkButton,
[data-testid="stSidebar"][data-baseweb="dark"] .stLinkButton a,
.stApp[data-theme="dark"] [data-testid="stSidebar"] .stLinkButton,
.stApp[data-theme="dark"] [data-testid="stSidebar"] .stLinkButton a {
    background: linear-gradient(90deg, #1d3557, #457b9d) !important;
    color: white !important;
}

/* Stile per il tema scuro al passaggio del mouse */
[data-testid="stSidebar"][data-baseweb="dark"] .stLinkButton:hover,
[data-testid="stSidebar"][data-baseweb="dark"] .stLinkButton a:hover,
.stApp[data-theme="dark"] [data-testid="stSidebar"] .stLinkButton:hover,
.stApp[data-theme="dark"] [data-testid="stSidebar"] .stLinkButton a:hover {
    background: linear-gradient(90deg, #1d3557, #3a6ea5) !important;
}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 🛠️ UTILITY FUNZIONI
# ==============================================================================
REQUIRED_COLS = ['Girone', 'Giornata', 'Casa', 'Ospite', 'GolCasa', 'GolOspite', 'Valida', 'GiocatoreCasa', 'GiocatoreOspite']
db_name = "TorneiSubbuteo"
col_name = "PierCrew"

def autoplay_audio(audio_data: bytes):
    try:
        # Salva l'audio in un file temporaneo
        with open("temp_audio.mp3", "wb") as f:
            f.write(audio_data)
        
        # Usa il componente audio di Streamlit con autoplay
        audio_file = open("temp_audio.mp3", 'rb')
        audio_bytes = audio_file.read()
        st.audio(audio_bytes, format='audio/mp3', start_time=0, autoplay=True)
        
        # Pulisci il file temporaneo
        try:
            os.remove("temp_audio.mp3")
        except:
            pass
            
    except Exception as e:
        st.error(f"Errore nella riproduzione dell'audio: {e}")
        # Fallback al metodo precedente
        try:
            b64 = base64.b64encode(audio_data).decode("utf-8")
            md = f"""
            <audio autoplay controls style="display:none">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
            """
            st.markdown(md, unsafe_allow_html=True)
        except:
            st.warning("Impossibile riprodurre l'audio")
            
def toggle_audio_callback():
    """Funzione di callback per la checkbox dell'audio."""
    # Questa funzione viene chiamata quando la checkbox cambia.
    # Non ha bisogno di fare nulla, ma l'atto di chiamarla
    # garantisce che st.session_state.bg_audio_disabled sia aggiornato
    # prima del rerun.
    pass
            
def autoplay_background_audio(audio_url: str):
    import requests, base64

    if "background_audio_data" not in st.session_state:
        try:
            response = requests.get(audio_url, timeout=10)
            response.raise_for_status()
            audio_data = response.content
            st.session_state.background_audio_data = base64.b64encode(audio_data).decode("utf-8")
        except Exception as e:
            st.warning(f"Errore caricamento audio: {e}")
            return False

    b64 = st.session_state.background_audio_data

    html_code = f"""
    <script>
    const audio_id = "subbuteo_background_audio";
    let audio_element = document.getElementById(audio_id);

    if (!audio_element) {{
        // Crea una sola volta
        audio_element = document.createElement("audio");
        audio_element.id = audio_id;
        audio_element.src = "data:audio/mp3;base64,{b64}";
        audio_element.loop = true;
        audio_element.autoplay = true;
        audio_element.volume = 0.5;
        document.body.appendChild(audio_element);
        console.log("🎵 Audio creato");
    }} else {{
        console.log("🎵 Audio già presente, non ricreato");
    }}

    // Se è in pausa, prova a farlo ripartire
    if (audio_element.paused) {{
        audio_element.play().catch(e => {{
            console.log("⚠️ Autoplay bloccato, ripartirà al primo click.");
        }});
    }}
    </script>
    """
    st.components.v1.html(html_code, height=0, width=0, scrolling=False)
    return True

    """
    Inietta un elemento <audio> persistente nel DOM con autoplay e loop.
    Funziona anche dopo i rerun di Streamlit.
    """
    import requests, base64

    # Scarica l'mp3 una sola volta in base64
    if "background_audio_data" not in st.session_state:
        try:
            response = requests.get(audio_url, timeout=10)
            response.raise_for_status()
            audio_data = response.content
            st.session_state.background_audio_data = base64.b64encode(audio_data).decode("utf-8")
        except Exception as e:
            st.warning(f"Errore caricamento audio: {e}")
            return False

    b64 = st.session_state.background_audio_data

    js_code = f"""
    <script>
    const audio_id = "subbuteo_background_audio";
    let audio_element = document.getElementById(audio_id);

    // Se non esiste, crealo
    if (!audio_element) {{
        audio_element = new Audio("data:audio/mp3;base64,{b64}");
        audio_element.id = audio_id;
        audio_element.loop = true;
        audio_element.volume = 0.5;
        document.body.appendChild(audio_element);
        console.log("🎵 Audio creato");
    }}

    // Se è in pausa, prova a ripartire
    if (audio_element.paused) {{
        audio_element.play().catch(e => {{
            console.log("⚠️ Autoplay bloccato, ripartirà al primo click.");
        }});
    }}
    </script>
    """
    st.components.v1.html(js_code, height=0, width=0, scrolling=False)
    return True

# Avvio audio (solo al primo run)
#if "background_audio_started" not in st.session_state:
#    autoplay_background_audio(BACKGROUND_AUDIO_URL)
#    st.session_state.background_audio_started = True

# Avvio audio ad ogni rerun. La logica JS all'interno di questa funzione
# assicura che l'elemento audio nel browser venga creato una sola volta
# e mantenuto attivo.
# Inizializza lo stato dell'audio se non esiste
if "bg_audio_disabled" not in st.session_state:
    st.session_state.bg_audio_disabled = False
if not st.session_state.bg_audio_disabled:
    autoplay_background_audio(BACKGROUND_AUDIO_URL)  

def check_csv_structure(df: pd.DataFrame) -> tuple[bool, str]:
    """Controlla che le colonne necessarie siano presenti nel DataFrame."""
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        return False, f"Colonne mancanti nel CSV: {missing}"
    return True, ""

def to_bool_series(s):
    """Converte una serie in booleana in modo robusto."""
    if s.dtype == bool:
        return s
    return s.astype(str).str.strip().str.lower().isin(["true", "1", "s", "si", "sì", "y", "yes"])

def tournament_is_complete(df: pd.DataFrame) -> tuple[bool, str]:
    """Verifica se tutte le partite sono validate e i gol sono numerici."""
    v = to_bool_series(df['Valida'])
    if not v.all():
        problematic_rows = df[~v].index.tolist()
        return False, f"Sono presenti partite non validate. Righe problematiche: {problematic_rows}"
    try:
        gc_ok = pd.to_numeric(df['GolCasa'], errors='coerce').notna().all()
        go_ok = pd.to_numeric(df['GolOspite'], errors='coerce').notna().all()
        if not (gc_ok and go_ok):
            return False, "Sono presenti gol non numerici o mancanti."
    except Exception:
        return False, "Errore nel parsing dei gol."
    return True, ""

def classifica_complessiva(df: pd.DataFrame) -> pd.DataFrame:
    """Calcola la classifica complessiva (tutte le partite validate), 2 punti vittoria / 1 pareggio."""
    partite = df[to_bool_series(df['Valida'])].copy()
    partite['GolCasa'] = pd.to_numeric(partite['GolCasa'], errors='coerce').fillna(0).astype(int)
    partite['GolOspite'] = pd.to_numeric(partite['GolOspite'], errors='coerce').fillna(0).astype(int)
    
    partite['Casa'] = partite['Casa'].astype(str).fillna('')
    partite['Ospite'] = partite['Ospite'].astype(str).fillna('')
    
    squadre = pd.unique(partite[['Casa', 'Ospite']].values.ravel())
    stats = {s: {'Punti':0,'V':0,'P':0,'S':0,'GF':0,'GS':0,'DR':0} for s in squadre}
    
    squadre_casa = set(partite['Casa'].unique())
    squadre_ospite = set(partite['Ospite'].unique())
    all_squadre = list(squadre_casa.union(squadre_ospite))
    
    stats = {s: {'Punti':0,'V':0,'P':0,'S':0,'GF':0,'GS':0,'DR':0} for s in all_squadre}

    for _, r in partite.iterrows():
        casa, osp = r['Casa'], r['Ospite']
        gc, go = int(r['GolCasa']), int(r['GolOspite'])
        
        # Gestisce i casi in cui una squadra potrebbe non aver giocato partite
        if casa in stats:
            stats[casa]['GF'] += gc; stats[casa]['GS'] += go
        if osp in stats:
            stats[osp]['GF'] += go; stats[osp]['GS'] += gc
        
        if gc > go:
            if casa in stats:
                stats[casa]['Punti'] += 2; stats[casa]['V'] += 1
            if osp in stats:
                stats[osp]['S'] += 1
        elif gc < go:
            if osp in stats:
                stats[osp]['Punti'] += 2; stats[osp]['V'] += 1
            if casa in stats:
                stats[casa]['S'] += 1
        else:
            if casa in stats:
                stats[casa]['Punti'] += 1
            if osp in stats:
                stats[osp]['Punti'] += 1

        if casa in stats: stats[casa]['P'] += 1
        if osp in stats: stats[osp]['P'] += 1

    rows = []
    for s, d in stats.items():
        d['DR'] = d['GF'] - d['GS']
        rows.append({'Squadra': s, **d})
    dfc = pd.DataFrame(rows)
    if dfc.empty:
        return dfc
    dfc = dfc.sort_values(by=['Punti','DR','GF','V','Squadra'], ascending=[False, False, False, False, True]).reset_index(drop=True)
    dfc.index = dfc.index + 1
    dfc.insert(0, 'Pos', dfc.index)
    return dfc.reset_index(drop=True)

def serpentino_seed(squadre_ordinate: list[str], num_gironi: int) -> list[list[str]]:
    """Distribuzione 1..N a serpentina: G1,G2,...,Gk, poi Gk,...,G1, ecc."""
    gironi = [[] for _ in range(num_gironi)]
    direction = 1
    g = 0
    for s in squadre_ordinate:
        gironi[g].append(s)
        if direction == 1 and g == num_gironi - 1:
            direction = -1
        elif direction == -1 and g == 0:
            direction = 1
        else:
            g += direction
    return gironi

def bilanciato_ko_seed(df_classifica: pd.DataFrame, n_squadre: int) -> list[dict]:
    """Genera accoppiamenti bilanciati per KO con i nomi dei giocatori."""
    squadre_qualificate = df_classifica.head(n_squadre).copy()
    squadre_qualificate = squadre_qualificate[['Squadra', 'Giocatore']].to_dict('records')
    
    matches = []
    n = len(squadre_qualificate)
    for i in range(n // 2):
        squadra_a_info = squadre_qualificate[i]
        squadra_b_info = squadre_qualificate[n - 1 - i]
        
        matches.append({
            'SquadraA': squadra_a_info['Squadra'],
            'GiocatoreA': squadra_a_info['Giocatore'],
            'SquadraB': squadra_b_info['Squadra'],
            'GiocatoreB': squadra_b_info['Giocatore']
        })
    return matches

def round_robin(teams: list[str], andata_ritorno: bool=False) -> pd.DataFrame:
    """Genera calendario round-robin (metodo circle). Ritorna DF con Giornata/Casa/Ospite."""
    teams = teams[:]
    if len(teams) < 2:
        return pd.DataFrame(columns=['Giornata','Casa','Ospite'])
    bye = None
    if len(teams) % 2 == 1:
        bye = "Riposo"
        teams.append(bye)
    n = len(teams)
    giornate = n - 1
    metà = n // 2
    curr = teams[:]
    rows = []
    for g in range(1, giornate+1):
        for i in range(metà):
            a = curr[i]; b = curr[-(i+1)]
            if a != bye and b != bye:
                rows.append({'Giornata': g, 'Casa': a, 'Ospite': b})
        curr = [curr[0]] + [curr[-1]] + curr[1:-1]
    df = pd.DataFrame(rows)
    if andata_ritorno:
        inv = df.copy()
        inv['Giornata'] = inv['Giornata'] + giornate
        inv = inv.rename(columns={'Casa':'Ospite','Ospite':'Casa'})
        df = pd.concat([df, inv], ignore_index=True)
    return df

def standings_from_matches(df: pd.DataFrame, key_group: str) -> pd.DataFrame:
    """Classifica per gruppi su DataFrame con colonne: key_group, Casa, Ospite, GolCasa, GolOspite, Valida"""
    if df.empty:
        return pd.DataFrame()
    partite = df[to_bool_series(df['Valida'])].copy()
    if partite.empty:
        return pd.DataFrame()
    partite['GolCasa'] = pd.to_numeric(partite['GolCasa'], errors='coerce').fillna(0).astype(int)
    partite['GolOspite'] = pd.to_numeric(partite['GolOspite'], errors='coerce').fillna(0).astype(int)
    
    partite['Casa'] = partite['Casa'].astype(str).fillna('')
    partite['Ospite'] = partite['Ospite'].astype(str).fillna('')
    
    out = []
    for gruppo, blocco in partite.groupby(key_group):
        blocco['Casa'] = blocco['Casa'].astype(str).fillna('')
        blocco['Ospite'] = blocco['Ospite'].astype(str).fillna('')
        
        squadre = pd.unique(blocco[['Casa','Ospite']].values.ravel())
        stats = {s: {'Punti':0,'V':0,'P':0,'S':0,'GF':0,'GS':0,'DR':0} for s in squadre}
        for _, r in blocco.iterrows():
            c, o = r['Casa'], r['Ospite']
            gc, go = int(r['GolCasa']), int(r['GolOspite'])
            stats[c]['GF'] += gc; stats[c]['GS'] += go
            stats[o]['GF'] += go; stats[o]['GS'] += gc
            if gc > go:
                stats[c]['Punti'] += 2; stats[c]['V'] += 1; stats[o]['S'] += 1
            elif gc < go:
                stats[o]['Punti'] += 2; stats[o]['V'] += 1; stats[c]['S'] += 1
            else:
                stats[c]['Punti'] += 1; stats[o]['Punti'] += 1
            stats[c]['P'] += 1; stats[o]['P'] += 1
        for s, d in stats.items():
            d['DR'] = d['GF'] - d['GS']
            out.append({'Gruppo': gruppo, 'Squadra': s, **d})
    dfc = pd.DataFrame(out)
    if dfc.empty:
        return dfc
    dfc = dfc.sort_values(by=['Gruppo','Punti','DR','GF','V','Squadra'], ascending=[True,False,False,False,False,True])
    return dfc.reset_index(drop=True)

# ==============================================================================
# 📄 FUNZIONI PER EXPORT PDF
# ==============================================================================
def generate_pdf_gironi(df_finale_gironi: pd.DataFrame) -> bytes:
    """Genera un PDF con calendario e classifica dei gironi."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Calendario e Classifiche Gironi", 0, 1, 'C')
    pdf.set_font("Helvetica", "", 12)

    gironi = sorted(df_finale_gironi['Girone'].unique())

    for girone in gironi:
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(255, 0, 0)
        
        girone_blocco = df_finale_gironi[df_finale_gironi['Girone'] == girone]
        is_complete = all(girone_blocco['Valida'])
        
        pdf.cell(0, 10, f"Girone {girone}", 0, 1, 'L')
        pdf.set_text_color(0, 0, 0)

        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "Classifica:", 0, 1, 'L')
        pdf.set_font("Helvetica", "", 10)
        
        classifica = standings_from_matches(girone_blocco, key_group='Girone')
        
        if not classifica.empty:
            classifica = classifica.sort_values(by=['Punti', 'DR', 'GF', 'V', 'Squadra'], ascending=[False, False, False, False, True]).reset_index(drop=True)
            classifica.index = classifica.index + 1
            classifica.insert(0, 'Pos', classifica.index)

            col_widths = [10, 40, 15, 15, 15, 15, 15, 15, 15]
            headers = ["Pos", "Squadra", "Punti", "V", "P", "S", "GF", "GS", "DR"]
            for i, h in enumerate(headers):
                pdf.cell(col_widths[i], 7, h, 1, 0, 'C')
            pdf.ln()
            for _, r in classifica.iterrows():
                for i, c in enumerate(headers):
                    val = r.get(c, "N/A")
                    if c == 'Pos':
                        val = int(val)
                    pdf.cell(col_widths[i], 7, str(val), 1, 0, 'C')
                pdf.ln()
        else:
            pdf.cell(0, 7, "Nessuna partita validata in questo girone.", 0, 1)

        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "Calendario partite:", 0, 1, 'L')
        pdf.set_font("Helvetica", "", 10)

        partite_girone = girone_blocco.sort_values(by='Giornata').reset_index(drop=True)
        for idx, partita in partite_girone.iterrows():
            if not is_complete and not partita['Valida']:
                pdf.set_text_color(255, 0, 0)
            else:
                pdf.set_text_color(0, 0, 0)
            
            res = f"{int(partita['GolCasa'])} - {int(partita['GolOspite'])}" if partita['Valida'] and pd.notna(partita['GolCasa']) and pd.notna(partita['GolOspite']) else " - "
            pdf.cell(0, 7, f"Giornata {int(partita['Giornata'])}: {partita['Casa']} vs {partita['Ospite']} ({res})", 0, 1)
        
        pdf.set_text_color(0, 0, 0)
        pdf.ln(5)

    #return bytes(pdf.output(dest='S'))
    return pdf.output(dest='S').encode('latin-1')

def generate_pdf_ko(rounds_ko: list[pd.DataFrame]) -> bytes:
    """Genera un PDF con il tabellone a eliminazione diretta."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    
    pdf.cell(0, 10, "Tabellone Eliminazione Diretta", 0, 1, 'C')
    
    for df_round in rounds_ko:
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, df_round['Round'].iloc[0], 0, 1, 'L')
        
        pdf.set_font("Helvetica", "", 12)
        for _, match in df_round.iterrows():
            if not match['Valida']:
                pdf.set_text_color(255, 0, 0)
            else:
                pdf.set_text_color(0, 0, 0)
                
            res = f"{int(match['GolA'])} - {int(match['GolB'])}" if match['Valida'] and pd.notna(match['GolA']) and pd.notna(match['GolB']) else " - "
            pdf.cell(0, 7, f"Partita {int(match['Match'])}: {match['SquadraA']} vs {match['SquadraB']} ({res})", 0, 1)

    pdf.set_text_color(0, 0, 0)
    #return pdf.output(dest='S').encode('latin1')
    #return bytes(pdf.output(dest='S'))
    return pdf.output(dest='S').encode('latin-1')

def render_round(df_round, round_idx, modalita_visualizzazione="squadre"):
    # Check if user has write access
    has_write_access = st.session_state.get("user", {}).get("role") not in ["ospite", "lettura"]
    
    st.markdown(f"### {df_round['Round'].iloc[0]}")
    st.markdown("---")
    
    # Show read-only warning if in read-only mode
    if not has_write_access:
        st.warning("🔒 Modalità di sola lettura. Non è possibile modificare i risultati.")
    
    df_temp = df_round.copy()

    def parse_team_player(val):
        # Divide "Squadra-Giocatore" in due parti
        if isinstance(val, str) and "-" in val:
            squadra, giocatore = val.split("-", 1)
            return squadra.strip(), giocatore.strip()
        return val, ""

    for idx, match in df_temp.iterrows():
        with st.container(border=True):
            key_gol_a = f"ko_gola_{round_idx}_{idx}"
            key_gol_b = f"ko_golb_{round_idx}_{idx}"
            key_valida = f"ko_valida_{round_idx}_{idx}"

            if key_gol_a not in st.session_state:
                st.session_state[key_gol_a] = int(match['GolA']) if pd.notna(match['GolA']) else 0
            if key_gol_b not in st.session_state:
                st.session_state[key_gol_b] = int(match['GolB']) if pd.notna(match['GolB']) else 0
            if key_valida not in st.session_state:
                st.session_state[key_valida] = bool(match['Valida']) if pd.notna(match['Valida']) else False

            # --- Parsing locale ---
            squadra_a, giocatore_a = parse_team_player(match['SquadraA'])
            squadra_b, giocatore_b = parse_team_player(match['SquadraB'])

            # --- Visualizzazione dinamica ---
            if modalita_visualizzazione == "completa":
                stringa_incontro = f"🏠{squadra_a} ({giocatore_a}) 🆚 {squadra_b} ({giocatore_b})🛫"
            elif modalita_visualizzazione == "giocatori":
                stringa_incontro = f"🏠{giocatore_a} 🆚 {giocatore_b}🛫"
            else:  # "squadre" o default
                stringa_incontro = f"🏠{squadra_a} 🆚 {squadra_b}🛫"

            st.markdown(f"<h3 style='text-align:center;'>⚽ Partita</h3>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align:center; font-weight:bold;'>{stringa_incontro}</p>", unsafe_allow_html=True)

            c_score1, c_score2 = st.columns(2)
            with c_score1:
                st.number_input(
                    "Gol Casa",
                    min_value=0, max_value=20,
                    key=key_gol_a,
                    disabled=st.session_state[key_valida] or not has_write_access,  # Disable if validated or read-only
                    label_visibility="hidden"
                )
            with c_score2:
                st.number_input(
                    "Gol Ospite",
                    min_value=0, max_value=20,
                    key=key_gol_b,
                    disabled=st.session_state[key_valida] or not has_write_access,  # Disable if validated or read-only
                    label_visibility="hidden"
                )

            st.markdown("---")
            
            # Show validation checkbox only if user has write access
            if has_write_access:
                st.checkbox(
                    "✅ Valida Risultato",
                    key=key_valida,
                    disabled=not has_write_access
                )
            else:
                # Show a message if the match is validated in read-only mode
                if st.session_state.get(key_valida, False):
                    st.success("✅ Partita validata")
                else:
                    st.info("⏳ Partita in corso...")

            # Update the round data with current state
            df_round.loc[idx, 'GolA'] = st.session_state[key_gol_a]
            df_round.loc[idx, 'GolB'] = st.session_state[key_gol_b]
            df_round.loc[idx, 'Valida'] = st.session_state.get(key_valida, False)

            # Show validation status
            if st.session_state.get(key_valida, False):
                st.success("✅ Partita validata!")
            else:
                st.warning("⚠️ Partita non ancora validata.")

    # Only update the round data if user has write access
    if has_write_access:
        st.session_state['rounds_ko'][round_idx] = df_round.copy()
# ==============================================================================
# 🧠 FUNZIONI DI GESTIONE STATO E INTERAZIONE CON DB
# ==============================================================================
def reset_fase_finale():
    """Reset dello stato della sessione per la fase finale."""
    keys = [
        'fase_scelta','gironi_num','gironi_ar','gironi_seed',
        'df_finale_gironi','girone_sel','giornata_sel',
        'round_corrente','rounds_ko','seeds_ko','n_inizio_ko',
        'giornate_mode', 'tournament_name_raw', 'filter_player', 'filter_girone',
        'df_torneo_preliminare'
    ]
    for k in keys:
        if k in st.session_state:
            del st.session_state[k]

def reset_to_setup():
    """Reset completo per tornare alla schermata iniziale."""
    reset_fase_finale()
    st.session_state['ui_show_pre'] = True
    st.session_state['fase_modalita'] = None
    st.session_state['df_torneo_preliminare'] = None
    st.session_state['tournament_id'] = None
    st.session_state['tournament_name'] = None
    if 'player_map' in st.session_state:
        del st.session_state['player_map']
    if 'ko_setup_complete' in st.session_state:
        del st.session_state['ko_setup_complete']

def get_base_name(name):
    """Rimuove i prefissi noti dal nome del torneo per avere un nome base pulito."""
    prefixes = ['completato_', 'fasefinaleAGironi_', 'fasefinaleEliminazionediretta_', 'finito_', 'fasefinale', 'Eliminazionediretta_']
    pattern = r'^(?:' + '|'.join(re.escape(p) for p in prefixes) + r')+'
    cleaned_name = re.sub(pattern, '', name)
    return cleaned_name.strip('_')

@st.cache_resource
def init_mongo_connection(uri, db_name, collection_name, show_ok: bool = False):
    """Inizializza la connessione a MongoDB."""
    try:
        client = MongoClient(uri, server_api=server_api.ServerApi('1'))
        db = client.get_database(db_name)
        col = db.get_collection(collection_name)
        _ = col.find_one({})
        if show_ok:
            st.toast(f"Connessione a {db_name}.{col_name} ok.")
        return col
    except Exception as e:
        st.error(f"❌ Errore di connessione a {db_name}.{col_name}: {e}")
        return None


# ------------------------------------------------------------------------------
# 🛰️ Gestione automatica del parametro `?torneo=` in query string (con debug)
# ------------------------------------------------------------------------------
def handle_query_param_load():
    """
    Carica automaticamente un torneo se presente nella query string (?torneo=...).
    Usa esattamente lo stesso flusso del caricamento manuale, senza ricostruire colonne a mano.
    """
    try:
        # Prioritizza il nuovo API st.query_params
        if hasattr(st, "query_params"):
            q = dict(st.query_params)
        else:
            # Fallback per le vecchie versioni di Streamlit
            q = st.experimental_get_query_params() or {}
    except Exception:
        q = {}
    # niente parametro "torneo"? esci subito
    if not q or "torneo" not in q or not q["torneo"]:
        return

    raw = q["torneo"]
    if isinstance(raw, list) and raw:
        raw = raw[0]

    try:
        torneo_param = urllib.parse.unquote_plus(raw)
    except Exception:
        torneo_param = raw

    # evita loop multipli
    if st.session_state.get("query_loaded_torneo") == torneo_param:
        return

    # connessione al DB
    try:
        tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], db_name, col_name)
    except Exception:
        tournaments_collection = None

    if tournaments_collection is None:
        return

    # cerca il torneo nel DB
    torneo_doc = tournaments_collection.find_one({"nome_torneo": torneo_param})
    if not torneo_doc:
        try:
            torneo_doc = tournaments_collection.find_one({"_id": ObjectId(torneo_param)})
        except Exception:
            torneo_doc = None

    if not torneo_doc:
        st.warning(f"⚠️ Torneo '{torneo_param}' non trovato nel DB.")
        try:
            if hasattr(st, "experimental_set_query_params"):
                st.experimental_set_query_params()
            else:
                st.query_params.clear()
        except Exception:
            pass
        return

    torneo_id = str(torneo_doc["_id"])
    st.session_state["tournament_id"] = torneo_id
    st.session_state["tournament_name"] = torneo_doc.get("nome_torneo", torneo_param)

    # usa la stessa funzione di caricamento manuale
    torneo_data = carica_torneo_da_db(tournaments_collection, torneo_id)

    if torneo_data and "calendario" in torneo_data:
        df_torneo = pd.DataFrame(torneo_data['calendario'])
        
        # --- 🐛 INIZIO CORREZIONE DEL BUG 🐛 ---
        st.session_state['df_torneo_preliminare'] = df_torneo
        
        is_complete, msg = tournament_is_complete(df_torneo)
        if not is_complete:
            st.error(f"❌ Il torneo preliminare selezionato non è completo: {msg}")
            # Non procedere se il torneo non è completo
            return

        # Genera player map e classifica qui, come fatto nella parte manuale
        if 'GiocatoreCasa' not in df_torneo.columns:
            df_torneo['GiocatoreCasa'] = ""
        if 'GiocatoreOspite' not in df_torneo.columns:
            df_torneo['GiocatoreOspite'] = ""
        
        player_map = pd.concat([df_torneo[['Casa', 'GiocatoreCasa']].rename(columns={'Casa':'Squadra', 'GiocatoreCasa':'Giocatore'}),
                                df_torneo[['Ospite', 'GiocatoreOspite']].rename(columns={'Ospite':'Squadra', 'GiocatoreOspite':'Giocatore'})])
        player_map = player_map.drop_duplicates().set_index('Squadra')['Giocatore'].to_dict()
        st.session_state['player_map'] = player_map
        
        df_classifica = classifica_complessiva(df_torneo)
        df_classifica['Giocatore'] = df_classifica['Squadra'].map(player_map)
        st.session_state['df_classifica_preliminare'] = df_classifica
        
        st.session_state['ui_show_pre'] = False
        st.session_state["query_loaded_torneo"] = torneo_param
        # --- 🐛 FINE CORREZIONE DEL BUG 🐛 ---
        
        st.toast(f"✅ Torneo '{st.session_state['tournament_name']}' caricato automaticamente")

        # pulisci query params
        try:
            if hasattr(st, "experimental_set_query_params"):
                st.experimental_set_query_params()
            else:
                st.query_params.clear()
        except Exception:
            pass

        # rerun per applicare stato
        try:
            if hasattr(st, "experimental_rerun"):
                st.rerun()
            else:
                st.rerun()
        except Exception:
            pass
    else:
        st.warning(f"⚠️ Trovato documento torneo ma non è presente il calendario o si è verificato un errore.")
# ------------------------------------------------------------------------------
# Fine gestione query param
# ------------------------------------------------------------------------------

def carica_tornei_da_db(tournaments_collection, prefix: list[str]):
    """Carica l'elenco dei tornei dal DB filtrando per prefisso."""
    if tournaments_collection is None:
        return []
    try:
        regex_prefix = '|'.join(re.escape(p) for p in prefix)
        tornei = tournaments_collection.find({"nome_torneo": {"$regex": f"^{regex_prefix}"}}, {"nome_torneo": 1})
        return list(tornei)
    except Exception as e:
        st.error(f"❌ Errore caricamento tornei: {e}")
        return []

def carica_torneo_da_db(tournaments_collection, tournament_id):
    """Carica un singolo torneo dal DB e lo converte in DataFrame."""
    if tournaments_collection is None:
        return None
    try:
        torneo_data = tournaments_collection.find_one({"_id": ObjectId(tournament_id)})
        if torneo_data and 'calendario' in torneo_data:
            # Assicurati che l'ID del torneo sia incluso nei dati restituiti
            torneo_data['_id'] = str(torneo_data['_id'])  # Converti ObjectId in stringa
            df_torneo = pd.DataFrame(torneo_data['calendario'])
            df_torneo['Valida'] = to_bool_series(df_torneo['Valida'])
            df_torneo['GolCasa'] = pd.to_numeric(df_torneo['GolCasa'], errors='coerce').astype('Int64')
            df_torneo['GolOspite'] = pd.to_numeric(df_torneo['GolOspite'], errors='coerce').astype('Int64')
            return torneo_data
    except Exception as e:
        st.error(f"❌ Errore caricamento torneo: {e}")
        return None
    return None

def aggiorna_torneo_su_db(tournaments_collection, tournament_id, df_torneo):
    """Aggiorna il calendario di un torneo esistente su MongoDB."""
    if tournaments_collection is None:
        return False
    try:
        df_torneo_pulito = df_torneo.where(pd.notna(df_torneo), None)
        tournaments_collection.update_one(
            {"_id": ObjectId(tournament_id)},
            {"$set": {"calendario": df_torneo_pulito.to_dict('records')}}
        )
        return True
    except Exception as e:
        st.error(f"❌ Errore aggiornamento torneo: {e}")
        return False

def clona_torneo_su_db(tournaments_collection, source_id, new_name):
    """Clona un torneo esistente su MongoDB, gli assegna un nuovo nome e ne ripulisce il calendario."""
    if tournaments_collection is None:
        return None, None
    try:
        source_data = tournaments_collection.find_one({"_id": ObjectId(source_id)})
        if not source_data:
            st.error(f"❌ Torneo sorgente con ID {source_id} non trovato.")
            return None, None
        
        old_name = source_data.get('nome_torneo', 'sconosciuto')
        source_data.pop('_id')
        source_data['nome_torneo'] = new_name
        source_data['calendario'] = []
        result = tournaments_collection.insert_one(source_data)
        
        # Log dell'operazione
        username = st.session_state.get('user', {}).get('username', 'sconosciuto')
        log.log_action(
            username=username,
            action="clonazione_torneo",
            torneo=new_name,
            details={
                "tipo_operazione": "clonazione",
                "torneo_originale": old_name,
                "torneo_originale_id": source_id,
                "nuovo_torneo_id": str(result.inserted_id)
            }
        )
        
        st.toast(f"✅ Torneo clonato con successo! Nuovo nome: **{new_name}**")
        return result.inserted_id, new_name
        
    except Exception as e:
        st.error(f"❌ Errore nella clonazione del torneo: {e}")
        return None, None

def rinomina_torneo_su_db(tournaments_collection, tournament_id, new_name):
    """Rinomina un torneo esistente su MongoDB."""
    if tournaments_collection is None:
        return False
    try:
        # Ottieni il vecchio nome per il log
        torneo = tournaments_collection.find_one({"_id": ObjectId(tournament_id)})
        if not torneo:
            st.error("❌ Torneo non trovato")
            return False
            
        old_name = torneo.get('nome_torneo', 'sconosciuto')
        
        tournaments_collection.update_one(
            {"_id": ObjectId(tournament_id)},
            {"$set": {"nome_torneo": new_name}}
        )
        
        # Log dell'operazione
        username = st.session_state.get('user', {}).get('username', 'sconosciuto')
        log.log_action(
            username=username,
            action="rinomina_torneo",
            torneo=tournament_id,
            details={
                "tipo_operazione": "rinomina",
                "vecchio_nome": old_name,
                "nuovo_nome": new_name
            }
        )
        
        return True
    except Exception as e:
        st.error(f"❌ Errore nella ridenominazione del torneo: {e}")
        return False

def salva_risultati_ko():
    """Aggiorna il DataFrame e lo stato della sessione con i risultati del round corrente KO."""
    tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], db_name, col_name)
    if tournaments_collection is None:
        st.error("❌ Errore di connessione al DB.")
        return
    
    current_round_df = st.session_state['rounds_ko'][-1].copy()
    current_round_idx = len(st.session_state['rounds_ko']) - 1
    winners = []
    all_valid = True
    
    for idx, row in current_round_df.iterrows():
        gol_a_key = f"ko_gola_{current_round_idx}_{idx}"
        gol_b_key = f"ko_golb_{current_round_idx}_{idx}"
        valida_key = f"ko_valida_{current_round_idx}_{idx}"
        
        is_validated = st.session_state.get(valida_key, False)
        
        if is_validated:
            gol_a = st.session_state.get(gol_a_key, 0)
            gol_b = st.session_state.get(gol_b_key, 0)
            
            if int(gol_a) == int(gol_b):
                st.warning("❌ I pareggi non sono consentiti in un tabellone a eliminazione diretta!")
                return 
    
            current_round_df.at[idx, 'GolA'] = int(gol_a)
            current_round_df.at[idx, 'GolB'] = int(gol_b)
            current_round_df.at[idx, 'Valida'] = True
            
            if int(gol_a) > int(gol_b):
                current_round_df.at[idx, 'Vincitore'] = row['SquadraA']
                winners.append(row['SquadraA'])
            elif int(gol_b) > int(gol_a):
                current_round_df.at[idx, 'Vincitore'] = row['SquadraB']
                winners.append(row['SquadraB'])
        else:
            all_valid = False
    
    if not all_valid:
        st.error("❌ Per generare il prossimo round, tutte le partite devono essere validate.")
        return
    
    st.session_state['rounds_ko'][-1] = current_round_df.copy()

    df_ko_da_salvare = current_round_df.copy()
    df_ko_da_salvare.rename(columns={'SquadraA': 'Casa', 'SquadraB': 'Ospite', 'GolA': 'GolCasa', 'GolB': 'GolOspite', 'GiocatoreA': 'GiocatoreCasa', 'GiocatoreB': 'GiocatoreOspite'}, inplace=True)
    df_ko_da_salvare['Girone'] = 'Eliminazione Diretta'
    df_ko_da_salvare['Giornata'] = len(st.session_state['rounds_ko'])

    df_final_torneo = st.session_state.get('df_torneo_preliminare', pd.DataFrame()).copy()

    # Aggiorna solo le righe KO già presenti (Girone, Giornata, Casa, Ospite)
    for idx, row in df_ko_da_salvare.iterrows():
        mask = (
            (df_final_torneo['Girone'] == row['Girone']) &
            (df_final_torneo['Giornata'] == row['Giornata']) &
            (df_final_torneo['Casa'] == row['Casa']) &
            (df_final_torneo['Ospite'] == row['Ospite'])
        )
        if mask.any():
            # Aggiorna la riga esistente
            for col in ['GolCasa', 'GolOspite', 'Valida', 'GiocatoreCasa', 'GiocatoreOspite', 'Vincitore']:
                df_final_torneo.loc[mask, col] = row[col]
        else:
            # Se non esiste, aggiungi la riga (caso raro)
            df_final_torneo = pd.concat([df_final_torneo, pd.DataFrame([row])], ignore_index=True)
    
    if aggiorna_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], df_final_torneo):
        username = st.session_state.get('user', {}).get('username', 'sconosciuto')
        round_name = st.session_state.get('round_corrente', 'Round sconosciuto')
        
        # Prepara i dettagli delle partite per il log
        partite_dettaglio = []
        for _, partita in current_round_df.iterrows():
            partite_dettaglio.append({
                'squadra_casa': partita['SquadraA'],
                'squadra_ospite': partita['SquadraB'],
                'gol_casa': partita['GolA'],
                'gol_ospite': partita['GolB'],
                'vincitore': partita['Vincitore']
            })
            
        # Log del salvataggio dei risultati con dettagli partite
        log.log_action(
            username=username,
            action="salva_risultati_ko",
            torneo=st.session_state.get('tournament_id', 'sconosciuto'),
            details={
                "tipo_operazione": "salva_risultati",
                "round": round_name,
                "partite_salvate": len(current_round_df),
                "partite": partite_dettaglio
            }
        )
        
        st.toast("✅ Risultati salvati su DB!")
        st.session_state['df_torneo_preliminare'] = df_final_torneo
    else:
        st.error("❌ Errore nel salvataggio su DB.")
    
    if len(winners) > 1:
        next_round_name = ""
        if len(winners) == 8:
            next_round_name = "Quarti di finale"
        elif len(winners) == 4:
            next_round_name = "Semifinali"
        elif len(winners) == 2:
            next_round_name = "Finale"
    
        next_matches = []
        
        # Uso la player map salvata in session_state per i prossimi round
        player_map = st.session_state.get('player_map', {})

        for i in range(0, len(winners), 2):
            winner_a = winners[i]
            winner_b = winners[i+1]
            next_matches.append({
                'Round': next_round_name,
                'Match': (i // 2) + 1,
                'SquadraA': winner_a,
                'GiocatoreA': player_map.get(winner_a, ''),
                'SquadraB': winner_b,
                'GiocatoreB': player_map.get(winner_b, ''),
                'GolA': None, 'GolB': None, 'Valida': False, 'Vincitore': None
            })
        st.session_state['rounds_ko'].append(pd.DataFrame(next_matches))
        st.session_state['round_corrente'] = next_round_name
        
        # Log della generazione del nuovo round
        username = st.session_state.get('user', {}).get('username', 'sconosciuto')
        log.log_action(
            username=username,
            action="genera_round_ko",
            torneo=st.session_state.get('tournament_id', 'sconosciuto'),
            details={
                "tipo_operazione": "genera_round",
                "round_precedente": st.session_state.get('round_corrente', 'Round sconosciuto'),
                "nuovo_round": next_round_name,
                "squadre_qualificate": winners
            }
        )
        
        st.success(f"Prossimo turno: {next_round_name} generato!")
    
    elif len(winners) == 1:
        st.balloons()
        #st.success(f"🏆 Il torneo è finito! Il vincitore è: {winners[0]}")
        # Salva il vincitore nella session_state
        st.session_state['vincitore_torneo'] = winners[0]
        
        # we are the champions
        # Codice corretto per scaricare l'audio dall'URL
        audio_url = "https://raw.githubusercontent.com/legnaro72/torneo-Subbuteo-webapp/main/docs/wearethechamp.mp3"
        #audio_url = "./wearethechamp.mp3"
        try:
            response = requests.get(audio_url, timeout=10) # Imposta un timeout
            response.raise_for_status() # Lancia un'eccezione per risposte HTTP errate
            autoplay_audio(response.content)
        except requests.exceptions.RequestException as e:
            st.error(f"Errore durante lo scaricamento dell'audio: {e}")

        # Crea un contenitore vuoto per i messaggi
        placeholder = st.empty()

        # Lancia i palloncini in un ciclo per 3 secondi
        with placeholder.container():
            st.balloons()
            time.sleep(1) # Aspetta 1 secondo
        
        with placeholder.container():
            st.balloons()
            time.sleep(1) # Aspetta 1 secondo
        
        with placeholder.container():
            st.balloons()
            time.sleep(1) # Aspetta 1 secondo
        
        
        if not st.session_state['tournament_name'].startswith('finito_'):
            nuovo_nome = f"finito_{st.session_state['tournament_name']}"
            rinomina_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], nuovo_nome)
            st.session_state['tournament_name'] = nuovo_nome
            
    time.sleep(1)
    #st.rerun()

# ==============================================================================
# 🚀 LOGICA APPLICAZIONE PRINCIPALE
# ==============================================================================
def main():
    # Forza l'aggiornamento dello stato di autenticazione
    if 'user' not in st.session_state:
        st.session_state['user'] = {}
    
    # Gestione del ruolo utente
    user_role = st.session_state['user'].get('role')
    if user_role == 'G':
        st.session_state['user']['role'] = 'ospite'  # Converti 'G' in 'ospite'
    elif user_role == 'R':
        st.session_state['user']['role'] = 'lettura'  # Converti 'R' in 'lettura'
    elif not user_role:
        st.session_state['user']['role'] = 'ospite'  # Default a ospite se manca il ruolo
        
    if not st.session_state.get('authenticated', False):
        auth.show_auth_screen(club="PierCrew")
        return
        
    if st.session_state.get('sidebar_state_reset', False):
        reset_app_state()
        st.session_state['sidebar_state_reset'] = False
        st.rerun()

    # Inizializzazione stato
    # chiamata per gestire ?torneo=... in query string
    handle_query_param_load()
    if 'ui_show_pre' not in st.session_state: st.session_state['ui_show_pre'] = True
    if 'fase_modalita' not in st.session_state: st.session_state['fase_modalita'] = None
    if 'filter_player' not in st.session_state: st.session_state['filter_player'] = None
    if 'filter_girone' not in st.session_state: st.session_state['filter_girone'] = None
    if 'df_torneo_preliminare' not in st.session_state: st.session_state['df_torneo_preliminare'] = None
    if 'tournament_id' not in st.session_state: st.session_state['tournament_id'] = None
    if 'tournament_name' not in st.session_state: st.session_state['tournament_name'] = None
    if 'giornate_mode' not in st.session_state: st.session_state['giornate_mode'] = None
    if 'giornata_nav_mode' not in st.session_state: st.session_state['giornata_nav_mode'] = 'Menu a tendina'
    if 'player_map' not in st.session_state: st.session_state['player_map'] = {}
    if 'ko_setup_complete' not in st.session_state: st.session_state['ko_setup_complete'] = False
    
    if 'show_all_ko_matches' not in st.session_state:
        st.session_state['show_all_ko_matches'] = False
    
    # Header dinamico
    tournament_name = st.session_state.get("tournament_name")
    
    if tournament_name and not st.session_state['ui_show_pre']:
        cleaned_name = re.sub(r'\(.*\)', '', tournament_name).strip()
        st.markdown(f"""
        <div style='text-align:center; padding:20px; border-radius:10px; background: linear-gradient(90deg, #457b9d, #1d3557); box-shadow: 0 4px 14px #00000022;'>
            <h1 style='color:white; font-weight:700;'>🇮🇹⚽ {cleaned_name} 🏆🇮🇹</h1>
        </div>
        """, unsafe_allow_html=True)
    elif tournament_name and st.session_state['ui_show_pre']:
        st.markdown(f"""
        <div style='text-align:center; padding:20px; border-radius:10px; background: linear-gradient(90deg, #457b9d, #1d3557); box-shadow: 0 4px 14px #00000022;'>
            <h1 style='color:white; font-weight:700;'>🇮🇹⚽ {tournament_name} 🏆🇮🇹</h1>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Questo blocco viene eseguito all'avvio o quando il nome non è impostato
        st.markdown(f"""
        <div style='text-align:center; padding:20px; border-radius:10px; background: linear-gradient(90deg, #457b9d, #1d3557); box-shadow: 0 4px 14px #00000022;'>
            <h1 style='color:white; font-weight:700;'>🇮🇹⚽ Fase Finale Torneo Subbuteo 🏆🇮🇹</h1>
        </div>
        """, unsafe_allow_html=True)
    # Sidebar (tutti i pulsanti qui)
    # Debug: mostra utente autenticato e ruolo
    if st.session_state.get("authenticated"):
        user = st.session_state.get("user", {})
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**👤 Utente:** {user.get('username', '??')}")
        st.sidebar.markdown(f"**🔑 Ruolo:** {user.get('role', '??')}")
        st.sidebar.markdown("---")
    # ✅ 0. 🎵️ Gestione Audio Sottofondo 
    st.sidebar.subheader("🎵️ Gestione Audio Sottofondo")
    st.sidebar.checkbox(
        "Disabilita audio di sottofondo🔊",
        key="bg_audio_disabled",
        on_change=toggle_audio_callback
    )

    
    # ✅ 1. 🕹️ Gestione Rapida (sempre in cima)
    st.sidebar.markdown("---")
    st.sidebar.subheader("🕹️ Gestione Rapida")
    st.sidebar.link_button("➡️ Vai a Hub Tornei", "https://farm-tornei-subbuteo-piercrew-all-db.streamlit.app/", use_container_width=True)
    st.sidebar.markdown("---")
    
    if not st.session_state['ui_show_pre']:
        
        # ✅ 2. ⚙️ Opzioni Torneo
        st.sidebar.subheader("⚙️ Opzioni Torneo")
        
        # Check if user has write access
        has_write_access = st.session_state.get("user", {}).get("role") not in ["ospite", "lettura"]
        
        # Save Tournament button - disabled in read-only mode
        if st.sidebar.button(
            "💾 Salva Torneo", 
            key="save_tournament_ko", 
            use_container_width=True,
            disabled=not has_write_access,
            help="Salva i risultati del torneo" + ("" if has_write_access else " (accesso in sola lettura)")
        ):
            if has_write_access:
                salva_risultati_ko()
            else:
                st.error("⛔ Accesso in sola lettura. Non è possibile salvare le modifiche.")
        
        # Terminate Tournament button - disabled in read-only mode
        if st.sidebar.button(
            "🏁 Termina Torneo", 
            key="terminate_tournament_ko", 
            use_container_width=True,
            disabled=not has_write_access,
            help="Termina il torneo corrente" + ("" if has_write_access else " (accesso in sola lettura)")
        ):
            if has_write_access:
                # Log dell'azione di terminazione torneo
                username = st.session_state.get('user', {}).get('username', 'sconosciuto')
                tournament_id = st.session_state.get('tournament_id', 'sconosciuto')
                
                # Prepara i dettagli del torneo per il log
                torneo_details = {
                    "tipo_operazione": "terminazione_torneo",
                    "stato": "torneo_terminato",
                    "vincitore": st.session_state.get('vincitore_torneo', 'Nessun vincitore definito'),
                    "data_terminazione": datetime.datetime.now().isoformat(),
                    "round_corrente": st.session_state.get('round_corrente', 'Nessun round attivo')
                }
                
                # Log dell'azione
                log.log_action(
                    username=username,
                    action="termina_torneo",
                    torneo=tournament_id,
                    details=torneo_details
                )
                
                st.session_state.update({"vincitore_torneo": "Torneo terminato manualmente"})
                st.toast("✅ Torneo terminato con successo!")
            else:
                st.error("⛔ Accesso in sola lettura. Non è possibile terminare il torneo.")
        
        # Back to setup button - always enabled
        if st.sidebar.button("⬅️ Torna a classifica e scelta fase finale", key="back_to_setup", use_container_width=True):
            reset_to_setup()
            st.rerun()
        
        st.sidebar.markdown("---")
        
        # ✅ 3. 🔧 Utility (sezione principale con sottosezioni)
        st.sidebar.subheader("🔧 Utility")
        
        # 🔎 Visualizzazione incontri
        with st.sidebar.expander("🔎 Visualizzazione incontri", expanded=False):
            modalita_visualizzazione = st.radio(
                "Formato incontri tabellone:",
                options=["squadre", "completa", "giocatori"],
                index=0,
                format_func=lambda x: {
                    "squadre": "Solo squadre",
                    "completa": "Squadra + Giocatore",
                    "giocatori": "Solo giocatori"
                }[x],
                key="modalita_visualizzazione_ko"
            )
        
        # 📅 Visualizzazione incontri giocati
        with st.sidebar.expander("📅 Visualizzazione incontri giocati", expanded=False):
            if st.button("📋 Mostra tutti gli incontri disputati", key="show_all_matches", use_container_width=True):
                st.session_state['show_all_ko_matches'] = True
                st.rerun()
        
        st.sidebar.markdown("---")
        
        # ✅ 4. 📤 Esportazione (in fondo)
        st.sidebar.subheader("📤 Esportazione")           
        if st.session_state.get('giornate_mode') == "ko" and 'rounds_ko' in st.session_state:
            if st.sidebar.button("📄 Prepara PDF", key="prepare_pdf", use_container_width=True):
                pdf_bytes = generate_pdf_ko(st.session_state['rounds_ko'])
                st.sidebar.download_button(
                    label="📥 Scarica PDF Torneo",
                    data=pdf_bytes,
                    file_name="fase_finale_tabellone_ko.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
        else:
            st.sidebar.info("ℹ️ Nessun torneo KO attivo. Completa le partite per generare il PDF.")

    if st.session_state['ui_show_pre']:
        # Inizializza la connessione al database
        uri = os.environ.get("MONGO_URI_TOURNEMENTS")
        if not uri:
            uri = st.secrets["MONGO_URI_TOURNEMENTS"]
        tournaments_collection = init_mongo_connection(uri, db_name, col_name, show_ok=False)
        
        # Se non c'è una connessione al database, mostra un messaggio di errore
        if tournaments_collection is None:
            st.error("❌ Impossibile connettersi al database. Verifica la connessione e riprova.")
            st.markdown("---")
            if st.button("🔄 Ricarica la pagina", key="reload_page"):
                st.rerun()
            return
            
        # Seleziona l'opzione corrente o imposta quella predefinita
        if 'opzione_selezione' not in st.session_state:
            st.session_state['opzione_selezione'] = None
        
        # Se non è stata ancora fatta una selezione, mostra le due opzioni
        if st.session_state['opzione_selezione'] is None:
            st.markdown("### Scegli azione 📝")
            c1, c2 = st.columns([1,1])
            
            with c1:
                with st.container(border=True):
                    st.markdown(
                        """<div style='text-align:center'>
                        <h2>📂 Carica fase finale esistente</h2>
                        <p style='margin:0.2rem 0 1rem 0'>Riprendi una fase finale salvata (MongoDB)</p>
                        </div>""",
                        unsafe_allow_html=True,
                    )
                    if st.button("Carica fase finale esistente 📂", key="btn_carica_fase", use_container_width=True):
                        st.session_state['opzione_selezione'] = "Continuare una fase finale esistente"
                        st.rerun()

            with c2:
                with st.container(border=True):
                    st.markdown(
                        """<div style='text-align:center'>
                        <h2>✨ Crea nuova fase finale</h2>
                        <p style='margin:0.2rem 0 1rem 0'>Genera fase finale da torneo preliminare completato</p>
                        </div>""",
                        unsafe_allow_html=True,
                    )
                    # Check if user has write access for creating new phase
                    has_write_access = st.session_state.get("user", {}).get("role") not in ["ospite", "lettura"]
                    
                    if st.button(
                        "Crea nuova fase finale ✨", 
                        key="btn_nuova_fase", 
                        use_container_width=True,
                        disabled=not has_write_access,
                        help="Non disponibile in modalità ospite/lettura" if not has_write_access else "Crea una nuova fase finale da un torneo preliminare",
                        on_click=lambda: st.error("⛔ Accesso negato. Solo gli utenti con permessi di scrittura possono creare nuove fasi finali.") if not has_write_access else None
                    ):
                        if has_write_access:
                            st.session_state['opzione_selezione'] = "Creare una nuova fase finale"
                            st.rerun()
                        else:
                            st.error("⛔ Accesso in sola lettura. Non è possibile creare una nuova fase finale.")
            
            st.markdown("---")
            return
        
        # Se è stata fatta una selezione, mostra il form appropriato
        opzione_selezione = st.session_state['opzione_selezione']
        
        st.markdown("---")
        
        # Pulsante per tornare indietro alla selezione iniziale
        if st.button("⬅️ Torna alla selezione iniziale", key="back_to_selection"):
            st.session_state['opzione_selezione'] = None
            st.rerun()
            
        st.markdown("---")
        
        # Mostra il form appropriato in base alla selezione
        if opzione_selezione == "Creare una nuova fase finale":
                tornei_trovati = carica_tornei_da_db(tournaments_collection, prefix=["completato_"])
                st.subheader("Seleziona un torneo preliminare completato")
                if not tornei_trovati:
                    st.warning("⚠️ Nessun torneo 'COMPLETATO' trovato nel database.")
                    st.markdown("---")
                    st.markdown("### Crea un nuovo torneo")
                    st.markdown("Per creare una nuova fase finale, è necessario prima completare un torneo preliminare.")
                    # Lo stile CSS è già stato aggiunto in precedenza
                    st.link_button("🏠 Vai alla gestione tornei", "https://farm-tornei-subbuteo-piercrew-all-db.streamlit.app/", use_container_width=True)
                    return
                else:
                    tornei_opzioni = {t['nome_torneo']: str(t['_id']) for t in tornei_trovati}
                    scelta_torneo = st.selectbox(
                        "Seleziona il torneo da cui iniziare le fasi finali:",
                        options=list(tornei_opzioni.keys())
                    )
                    if scelta_torneo:
                        st.session_state['tournament_name'] = scelta_torneo
                        st.session_state['tournament_id'] = tornei_opzioni[scelta_torneo]
                        # Check if user has write access for creating new phase
                        has_write_access = st.session_state.get("user", {}).get("role") not in ["ospite", "lettura"]
                        
                        if st.button(
                            "Continua con questo torneo (Nuova Fase Finale)",
                            disabled=not has_write_access,
                            help="Crea una nuova fase finale" + ("" if has_write_access else " (accesso in sola lettura)")
                        ):
                            if has_write_access:
                                torneo_data = carica_torneo_da_db(tournaments_collection, st.session_state['tournament_id'])
                                if torneo_data:
                                    df_torneo = pd.DataFrame(torneo_data['calendario'])
                                    
                                    is_complete, msg = tournament_is_complete(df_torneo)
                                if not is_complete:
                                    st.error(f"❌ Il torneo preliminare selezionato non è completo: {msg}")
                                    problematic_rows = df_torneo[
                                        ~to_bool_series(df_torneo['Valida'])
                                    ]
                                    st.warning("Di seguito le partite non validate:")
                                    st.dataframe(problematic_rows[['Girone', 'Giornata', 'Casa', 'Ospite', 'GolCasa', 'GolOspite', 'Valida']])
                                else:
                                    # ✅ NUOVA LOGICA: Controlla se le colonne esistono e le aggiunge se mancano
                                    if 'GiocatoreCasa' not in df_torneo.columns:
                                        df_torneo['GiocatoreCasa'] = ""
                                    if 'GiocatoreOspite' not in df_torneo.columns:
                                        df_torneo['GiocatoreOspite'] = ""
                                    
                                    # Genera player map e classifica qui
                                    player_map = pd.concat([df_torneo[['Casa', 'GiocatoreCasa']].rename(columns={'Casa':'Squadra', 'GiocatoreCasa':'Giocatore'}),
                                                            df_torneo[['Ospite', 'GiocatoreOspite']].rename(columns={'Ospite':'Squadra', 'GiocatoreOspite':'Giocatore'})])
                                    player_map = player_map.drop_duplicates().set_index('Squadra')['Giocatore'].to_dict()
                                    st.session_state['player_map'] = player_map
                                    
                                    df_classifica = classifica_complessiva(df_torneo)
                                    df_classifica['Giocatore'] = df_classifica['Squadra'].map(player_map)
                                    st.session_state['df_classifica_preliminare'] = df_classifica
                                    
                                    new_name = f"fasefinale{get_base_name(torneo_data['nome_torneo'])}"
                                    new_id, new_name = clona_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], new_name)
                                    
                                    if new_id:
                                        st.session_state['tournament_id'] = str(new_id)
                                        st.session_state['tournament_name'] = new_name
                                        st.session_state['ui_show_pre'] = False
                                        st.rerun()
                                    else:
                                        st.error("❌ Errore nella clonazione del torneo. Riprova.")
                            else:
                                st.error("❌ Errore nel caricamento del torneo. Riprova.")

            #elif opzione_selezione == "Continuare una fase finale esistente":
        elif opzione_selezione == "Continuare una fase finale esistente":
            tornei_trovati = carica_tornei_da_db(tournaments_collection, prefix=["fasefinaleEliminazionediretta", "finito_Eliminazionediretta"])
            st.subheader("Seleziona una fase finale esistente")
            if not tornei_trovati:
                st.warning("⚠️ Nessuna fase finale esistente trovata nel database.")
                st.markdown("---")
                st.markdown("### Crea una nuova fase finale")
                st.markdown("Per creare una nuova fase finale, seleziona l'opzione 'Crea nuova fase finale' dal menu principale.")
                # Lo stile CSS è stato spostato all'inizio del file per essere applicato globalmente
                
                st.link_button("🏠 Vai alla gestione tornei", "https://farm-tornei-subbuteo-piercrew-all-db.streamlit.app/", use_container_width=True)
                return
            else:
                    tornei_opzioni = {t['nome_torneo']: str(t['_id']) for t in tornei_trovati}
                    scelta_torneo = st.selectbox(
                        "Seleziona la fase finale da continuare:",
                        options=list(tornei_opzioni.keys()),
                        key="select_torneo_esistente"
                    )
                    if scelta_torneo:
                        st.session_state['tournament_name'] = scelta_torneo
                        tournament_id = tornei_opzioni[scelta_torneo]
                        st.session_state['tournament_id'] = tournament_id
                        if st.button("Continua con questo torneo"):
                            torneo_data = carica_torneo_da_db(tournaments_collection, tournament_id)
                            
                            if torneo_data:
                                # Assicurati che l'ID del torneo sia salvato nella sessione
                                st.session_state['tournament_id'] = str(torneo_data.get('_id', tournament_id))
                                st.session_state['tournament_name'] = torneo_data.get('nome_torneo', scelta_torneo)
                                df_torneo_completo = pd.DataFrame(torneo_data['calendario'])
                                st.session_state['df_torneo_preliminare'] = df_torneo_completo
                                
                                # Carica il torneo preliminare per ottenere i nomi dei giocatori
                                base_name = get_base_name(st.session_state['tournament_name'])
                                preliminary_data = tournaments_collection.find_one({"nome_torneo": f"completato_{base_name}"})
                                
                                if preliminary_data and 'calendario' in preliminary_data:
                                    df_preliminary = pd.DataFrame(preliminary_data['calendario'])
                                    
                                    # ✅ NUOVA LOGICA: Controlla se le colonne esistono prima di usarle
                                    if 'GiocatoreCasa' in df_preliminary.columns and 'GiocatoreOspite' in df_preliminary.columns:
                                        player_map_df = pd.concat([df_preliminary[['Casa', 'GiocatoreCasa']].rename(columns={'Casa': 'Squadra', 'GiocatoreCasa': 'Giocatore'}),
                                                                df_preliminary[['Ospite', 'GiocatoreOspite']].rename(columns={'Ospite': 'Squadra', 'GiocatoreOspite': 'Giocatore'})])
                                        player_map = player_map_df.drop_duplicates().set_index('Squadra')['Giocatore'].to_dict()
                                        st.session_state['player_map'] = player_map
                                    else:
                                        st.warning("⚠️ Dati del torneo preliminare non trovati, o le colonne 'GiocatoreCasa' e 'GiocatoreOspite' non esistono.")
                                        st.session_state['player_map'] = {}
                                
                                else:
                                    st.warning("⚠️ Dati del torneo preliminare non trovati, i nomi dei giocatori potrebbero mancare.")
                                    st.session_state['player_map'] = {}
                                
                                is_ko_tournament = (df_torneo_completo['Girone'].astype(str) == 'Eliminazione Diretta').any()
                                
                                #if is_ko_tournament:
                                if is_ko_tournament:
                                    st.session_state['ko_setup_complete'] = True
                                    df_ko_esistente = df_torneo_completo[df_torneo_completo['Girone'] == 'Eliminazione Diretta'].copy()
                                    
                                    # Aggiungi i nomi dei giocatori al dataframe KO
                                    df_ko_esistente['GiocatoreCasa'] = df_ko_esistente['Casa'].map(st.session_state['player_map'])
                                    df_ko_esistente['GiocatoreOspite'] = df_ko_esistente['Ospite'].map(st.session_state['player_map'])

                                    # Ricostruzione rounds_ko senza duplicati
                                    rounds_list = []
                                    accoppiamenti_visti = set()
                                    for r in sorted(df_ko_esistente['Giornata'].unique()):
                                        df_round = df_ko_esistente[df_ko_esistente['Giornata'] == r].copy()
                                        df_round.rename(columns={'Casa': 'SquadraA', 'Ospite': 'SquadraB', 'GolCasa': 'GolA', 'GolOspite': 'GolB', 'GiocatoreCasa': 'GiocatoreA', 'GiocatoreOspite': 'GiocatoreB'}, inplace=True)
                                        # Crea una tupla ordinata degli accoppiamenti per questo round
                                        accoppiamenti = tuple(sorted((row['SquadraA'], row['SquadraB']) for _, row in df_round.iterrows()))
                                        if accoppiamenti in accoppiamenti_visti:
                                            continue  # Salta round duplicato
                                        accoppiamenti_visti.add(accoppiamenti)
                                        # Determine round name based on the number of matches
                                        num_matches = len(df_round)
                                        if num_matches == 8: round_name = "Ottavi di finale"
                                        elif num_matches == 4: round_name = "Quarti di finale"
                                        elif num_matches == 2: round_name = "Semifinali"
                                        elif num_matches == 1: round_name = "Finale"
                                        else: round_name = f"Round {int(r)}"
                                        df_round['Round'] = round_name
                                        df_round['Match'] = range(1, len(df_round) + 1)
                                        df_round['Vincitore'] = df_round.apply(lambda row: row['SquadraA'] if pd.notna(row['GolA']) and row['GolA'] > row['GolB'] else row['SquadraB'] if pd.notna(row['GolB']) and row['GolB'] > row['GolA'] else None, axis=1)
                                        rounds_list.append(df_round)

                                    # Ricostruisci la lista completa dei round KO senza duplicati
                                    st.session_state['rounds_ko'] = rounds_list
                                    
                                    # Trova l'ultimo turno non validato, o l'ultimissimo turno se tutti sono validati
                                    last_unvalidated_round = None
                                    if rounds_list:
                                        for _df_round in reversed(rounds_list):
                                            if not _df_round['Valida'].fillna(False).all():
                                                last_unvalidated_round = _df_round
                                                break
                                        if last_unvalidated_round is None:
                                            last_unvalidated_round = rounds_list[-1]
                                    
                                    # Ricostruisci la lista completa dei round KO
                                    if rounds_list:
                                        st.session_state['rounds_ko'] = rounds_list
                                    else:
                                        st.session_state['rounds_ko'] = []
                                    
                                    st.session_state['giornate_mode'] = 'ko'
                                    st.session_state['fase_modalita'] = "Eliminazione diretta"
                                    st.session_state['ui_show_pre'] = False
                                    st.rerun()
                                
                                else:
                                    st.error("❌ La fase finale a gironi non è gestita da questa web app.")
                                    st.info(f"Utilizza l'altra web app per la gestione del torneo '{st.session_state['tournament_name']}'.")

                            else:
                                st.error("❌ Errore nel caricamento del torneo. Riprova.")
    else:
        if 'df_torneo_preliminare' not in st.session_state and 'df_classifica_preliminare' not in st.session_state:
            st.error("Dati del torneo non caricati. Riprova a selezionare un torneo.")
            st.button("Torna indietro", on_click=reset_to_setup)
        else:
            # Questa sezione è visibile solo prima che sia selezionata una modalità di torneo
            if not st.session_state.get('ko_setup_complete'):
                if 'df_torneo_preliminare' in st.session_state and st.session_state['df_torneo_preliminare'] is not None:
                    df_classifica = classifica_complessiva(st.session_state['df_torneo_preliminare'])
                    player_map = pd.concat([st.session_state['df_torneo_preliminare'][['Casa', 'GiocatoreCasa']].rename(columns={'Casa': 'Squadra', 'GiocatoreCasa': 'Giocatore'}),
                                            st.session_state['df_torneo_preliminare'][['Ospite', 'GiocatoreOspite']].rename(columns={'Ospite': 'Squadra', 'GiocatoreOspite': 'Giocatore'})])
                    player_map = player_map.drop_duplicates().set_index('Squadra')['Giocatore'].to_dict()
                    df_classifica['Giocatore'] = df_classifica['Squadra'].map(player_map)
                else:
                    df_classifica = st.session_state['df_classifica_preliminare']
                
                st.markdown("<h3 style='text-align: center;'>Classifica Fase Preliminare</h3>", unsafe_allow_html=True)
                st.dataframe(df_classifica, use_container_width=True)
                st.divider()

                st.header("🎲 Scegli la fase finale")
                
                fase_finale_scelta = st.radio(
                    "Seleziona la modalità della fase finale:",
                    ["Gironi finali", "Eliminazione diretta"]
                )
                    
                if fase_finale_scelta == "Gironi finali":
                    st.session_state['fase_scelta'] = "gironi"
                    st.session_state['fase_modalita'] = "Gironi"

                    st.subheader("🗂️ Configura i gironi")
                    num_partecipanti_gironi = st.number_input(
                        "Quante squadre partecipano a questa fase finale?",
                        min_value=4,
                        value=min(16, len(df_classifica)),
                        max_value=len(df_classifica),
                        step=1
                    )
                    
                    num_gironi = st.number_input(
                        "In quanti gironi vuoi suddividere le squadre?",
                        min_value=1,
                        value=1,
                        max_value=max(1, num_partecipanti_gironi // 4),
                        step=1
                    )
                    
                    if num_partecipanti_gironi % num_gironi != 0:
                        st.warning("⚠️ Il numero di partecipanti deve essere divisibile per il numero di gironi per una distribuzione equa.")
                        st.stop()
                    
                    andata_ritorno = st.checkbox("📅 Partite di andata e ritorno?", value=False)
                    
                    # Ottieni le squadre qualificate in ordine di classifica
                    qualificati = list(df_classifica.head(num_partecipanti_gironi)['Squadra'])
                    
                    # Calcola quante squadre per girone (arrotondando per eccesso)
                    squadre_per_girone = (num_partecipanti_gironi + num_gironi - 1) // num_gironi
                    
                    # Inizializza i gironi
                    gironi_auto = {f'Girone {i+1}': [] for i in range(num_gironi)}
                    
                    # Distribuisci le squadre in ordine di classifica
                    # Le prime squadre vanno tutte nel primo girone, le successive nel secondo, ecc.
                    squadre_per_girone = num_partecipanti_gironi // num_gironi
                    squadre_rimanenti = num_partecipanti_gironi % num_gironi
                    
                    idx_squadra = 0
                    for girone_idx in range(num_gironi):
                        # Calcola quante squadre vanno in questo girone
                        num_in_girone = squadre_per_girone + (1 if girone_idx < squadre_rimanenti else 0)
                        
                        # Aggiungi le squadre al girone corrente
                        for _ in range(num_in_girone):
                            if idx_squadra < len(qualificati):
                                gironi_auto[f'Girone {girone_idx + 1}'].append(qualificati[idx_squadra])
                                idx_squadra += 1
                    
                    # Inizializza i gironi nella sessione se non esistono o se è cambiato il numero di gironi
                    if 'gironi_manuali' not in st.session_state or len(st.session_state.gironi_manuali) != num_gironi:
                        st.session_state.gironi_manuali = gironi_auto
                    
                    # Mostra le multi-select box per ogni girone
                    st.subheader("👥Composizione gironi")
                    st.info("Modifica la composizione dei gironi se necessario")
                    
                    # Crea due colonne per mostrare i gironi in modo più ordinato
                    col1, col2 = st.columns(2)
                    
                    # Mostra i gironi in due colonne
                    for i, (girone, squadre) in enumerate(st.session_state.gironi_manuali.items()):
                        with (col1 if i % 2 == 0 else col2):
                            st.markdown(f"#### {girone}")
                            
                            # Mostra le squadre già nel girone
                            for squadra in squadre:
                                st.markdown(f"- {squadra}")
                            
                            # Mostra le squadre disponibili per l'aggiunta
                            altre_squadre = [s for s in qualificati 
                                          if s not in [sq for g, sqs in st.session_state.gironi_manuali.items() 
                                                     for sq in sqs] or s in squadre]
                            
                            # Seleziona le squadre da aggiungere/rimuovere
                            squadre_selezionate = st.multiselect(
                                f"Modifica {girone}",
                                options=altre_squadre,
                                default=squadre,
                                key=f"girone_{i}",
                                format_func=lambda x: f"{x} (già in altro girone)" 
                                                   if x not in squadre and x in [sq for g, sqs in st.session_state.gironi_manuali.items() 
                                                                              for sq in sqs] 
                                                   else x
                            )
                            
                            # Aggiorna il girone con le squadre selezionate
                            st.session_state.gironi_manuali[girone] = squadre_selezionate
                            
                            # Mostra il numero di squadre nel girone
                            st.caption(f"{len(squadre_selezionate)} squadre selezionate")
                    
                    # Pulsante per generare i gironi con la configurazione attuale
                    if st.button("🔄 Genera calendario gironi"):
                        # Log dell'azione di generazione calendario gironi
                        username = st.session_state.get('user', {}).get('username', 'sconosciuto')
                        tournament_id = st.session_state.get('tournament_id', 'sconosciuto')
                        
                        # Prepara i dettagli dei gironi per il log
                        gironi_dettaglio = []
                        for girone, squadre in st.session_state.gironi_manuali.items():
                            gironi_dettaglio.append({
                                'nome_girone': girone,
                                'squadre': squadre,
                                'num_squadre': len(squadre)
                            })
                        
                        # Log dell'azione
                        log.log_action(
                            username=username,
                            action="genera_calendario_gironi",
                            torneo=tournament_id,
                            details={
                                "tipo_operazione": "generazione_calendario_gironi",
                                "num_gironi": num_gironi,
                                "andata_ritorno": andata_ritorno,
                                "gironi": gironi_dettaglio,
                                "timestamp": dt.now().isoformat()
                            }
                        )
                        
                        st.session_state['giornate_mode'] = 'gironi'
                        st.session_state['gironi_num'] = num_gironi
                        st.session_state['gironi_ar'] = andata_ritorno
                        
                        # Crea il calendario in base alla configurazione dei gironi
                        df_final_gironi = pd.DataFrame()
                        
                        # Verifica che tutte le squadre siano assegnate a un girone
                        squadre_assegnate = [s for squadre in st.session_state.gironi_manuali.values() for s in squadre]
                        squadre_mancanti = [s for s in qualificati if s not in squadre_assegnate]
                        
                        if squadre_mancanti:
                            st.warning(f"Attenzione: le seguenti squadre non sono assegnate a nessun girone: {', '.join(squadre_mancanti)}")
                            st.stop()
                        
                        # Genera il calendario per ogni girone
                        for girone_nome, squadre in st.session_state.gironi_manuali.items():
                            if not squadre:  # Salta i gironi vuoti
                                continue
                                
                            # Genera il calendario per il girone
                            df_girone = round_robin(squadre, andata_ritorno)
                            if not df_girone.empty:
                                df_girone.insert(0, 'Girone', girone_nome)
                                df_final_gironi = pd.concat([df_final_gironi, df_girone], ignore_index=True)
                        
                        df_to_save = df_final_gironi.copy()
                        df_to_save['GolCasa'] = None
                        df_to_save['GolOspite'] = None
                        df_to_save['Valida'] = False
                        df_to_save['GiocatoreCasa'] = df_to_save['Casa'].map(st.session_state['player_map'])
                        df_to_save['GiocatoreOspite'] = df_to_save['Ospite'].map(st.session_state['player_map'])
                        
                        tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], db_name, col_name)
                        
                        tournaments_collection.update_one(
                            {"_id": ObjectId(st.session_state["tournament_id"])},
                            {"$set": {"calendario": df_to_save.to_dict('records')}}
                        )

                        nuovo_nome = f"fasefinaleAGironi_{get_base_name(st.session_state['tournament_name'])}"
                        if rinomina_torneo_su_db(tournaments_collection, st.session_state["tournament_id"], nuovo_nome):
                                st.toast("✅ Torneo rinominato e gironi generati con successo!")
                                st.session_state["tournament_name"] = nuovo_nome
                                st.session_state['df_finale_gironi'] = df_to_save
                                st.rerun()
                        else:
                            st.error("❌ Errore nella ridenominazione. Riprova.")

                elif fase_finale_scelta == "Eliminazione diretta":
                    st.session_state['fase_scelta'] = "ko"
                    st.session_state['fase_modalita'] = "Eliminazione diretta"
                    n_squadre_ko = st.number_input("Quante squadre partecipano all'eliminazione diretta?", min_value=2, value=min(16, len(df_classifica)), step=1)
                    if not n_squadre_ko or (n_squadre_ko & (n_squadre_ko - 1) != 0):
                        st.warning("Il numero di squadre deve essere una potenza di 2 (es. 2, 4, 8, 16...).")
                        st.stop()
                    st.session_state['n_inizio_ko'] = n_squadre_ko
                    
                    st.info("L'accoppiamento seguirà il criterio 'più forte contro più debole' (1ª vs ultima, 2ª vs penultima, ecc.).")
                    
                    if st.button("Genera tabellone"):
                        matches = bilanciato_ko_seed(df_classifica, n_squadre_ko)
                        if not matches:
                            st.warning("Non ci sono abbastanza squadre per generare un tabellone.")
                            st.stop()
                        
                        round_name = "Ottavi di finale (di 16)" if n_squadre_ko == 16 else "Quarti di finale (di 8)" if n_squadre_ko == 8 else "Semifinali (di 4)" if n_squadre_ko == 4 else "Finale (di 2)"
                        
                        df_initial_round = pd.DataFrame(matches)
                        df_initial_round.insert(0, 'Round', round_name)
                        df_initial_round.insert(1, 'Match', range(1, len(df_initial_round) + 1))
                        df_initial_round['GolA'] = None
                        df_initial_round['GolB'] = None
                        df_initial_round['Valida'] = False
                        df_initial_round['Vincitore'] = None

                        st.session_state['rounds_ko'] = [df_initial_round]
                        st.session_state['giornate_mode'] = 'ko'
                    
                        df_to_save_initial = df_initial_round.rename(columns={'SquadraA': 'Casa', 'SquadraB': 'Ospite', 'GolA': 'GolCasa', 'GolB': 'GolOspite', 'GiocatoreA': 'GiocatoreCasa', 'GiocatoreB': 'GiocatoreOspite'})
                        df_to_save_initial['Girone'] = 'Eliminazione Diretta'
                        df_to_save_initial['Giornata'] = 1
                    
                        phase_id = str(uuid.uuid4())
                        df_to_save_initial["PhaseID"] = phase_id
                        df_to_save_initial["PhaseMode"] = "KO"
                    
                        df_final_torneo = pd.concat([pd.DataFrame(), df_to_save_initial], ignore_index=True)
                        tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], db_name, col_name)
                        
                        if tournaments_collection is None:
                            st.error("❌ Impossibile stabilire una connessione al database. Verifica la connessione e riprova.")
                            st.stop()
                    
                        try:
                            tournaments_collection.update_one(
                                {"_id": ObjectId(st.session_state["tournament_id"])},
                                {"$set": {"phase_metadata": {"phase_id": phase_id, "phase_mode": "KO"}, "calendario": df_final_torneo.to_dict('records')}}
                            )
                        except Exception as e:
                            st.error(f"❌ Errore durante l'aggiornamento del torneo: {e}")
                            st.stop()
                    
                        nuovo_nome = f"fasefinaleEliminazionediretta_{get_base_name(st.session_state['tournament_name'])}"
                        rinomina_torneo_su_db(tournaments_collection, st.session_state["tournament_id"], nuovo_nome)
                        st.session_state["tournament_name"] = nuovo_nome
                        st.session_state['ko_setup_complete'] = True
                    
                        st.session_state['df_torneo_preliminare'] = df_final_torneo
                        st.rerun()
                               
            if st.session_state.get('giornate_mode'):
                st.divider()
                
                if st.session_state['giornate_mode'] == 'gironi':
                    if 'df_finale_gironi' not in st.session_state:
                        st.error("Errore nel caricamento dei dati dei gironi. Riprova.")
                        st.button("Torna indietro", on_click=reset_to_setup)
                        st.stop()
                       
                    st.info("✅ Gironi creati con successo!")
                    torneo_nome = st.session_state["tournament_name"]
                    redirect_url = f"https://torneo-subbuteo-piercrew-ita-all-db.streamlit.app/?torneo={urllib.parse.quote(torneo_nome)}"
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
                
                elif st.session_state['giornate_mode'] == 'ko':
                    if not st.session_state.get('giornate_mode_active', False):
                        st.session_state['giornate_mode_active'] = True
                        st.rerun()
                    
                    st.markdown("<h3 style='text-align: center;'>Tabellone Eliminazione Diretta</h3>", unsafe_allow_html=True)
                    st.divider()

                    if 'rounds_ko' not in st.session_state:
                        st.error("Dati del tabellone KO non trovati. Riprova.")
                        st.button("Torna indietro", on_click=reset_to_setup)
                        st.stop()
                    
                    #inizio
                    if st.session_state.get('show_all_ko_matches', False):
                        # --- SOLO la tabella incontri disputati ---
                        st.markdown("## 🏟️ Tutti gli incontri disputati")
                        records = []
                        rounds_ko = st.session_state.get('rounds_ko', [])
                        rounds_to_show = rounds_ko[:-1] if rounds_ko and not rounds_ko[-1]['Valida'].all() else rounds_ko

                        round_abbr = {
                            "Ottavi di finale": "8️⃣",
                            "Quarti di finale": "4️⃣",
                            "Semifinali": "2️⃣",
                            "Finale": "🏆"
                        }

                        for df_round in rounds_to_show:
                            round_name = df_round['Round'].iloc[0]
                            abbr = round_abbr.get(round_name, "⚽️")
                            df_giocati = df_round[df_round['Valida'] == True]
                            for _, match in df_giocati.iterrows():
                                squadra_a = str(match['SquadraA'])
                                gol_a = int(match['GolA']) if pd.notna(match['GolA']) else ""
                                gol_b = int(match['GolB']) if pd.notna(match['GolB']) else ""
                                squadra_b = str(match['SquadraB'])
                                records.append({
                                    "T": abbr,
                                    "🏠": squadra_a,
                                    "home_goals": gol_a,
                                    "away_goals": gol_b,
                                    "🛫": squadra_b
                                })
                        
                        if records:
                            st.markdown("""
                            <style>
                            .compact-table {
                                font-size: 0.9em;
                                width: auto !important;
                                border-collapse: collapse;
                                margin: 0 auto;
                            }
                            .compact-table th, .compact-table td {
                                padding: 2px 6px !important;
                                text-align: center !important;
                                white-space: nowrap;
                                border: none;
                            }
                            .compact-table th {
                                color: #333 !important;
                                font-weight: bold;
                                border-bottom: 1px solid #ddd;
                            }
                            .compact-table tr {
                                border-bottom: 1px solid #eee;
                            }
                            </style>
                            """, unsafe_allow_html=True)
                            
                            df_disp = pd.DataFrame(records)
                            # Remove duplicate column names by adding a small suffix to duplicates
                            df_disp.columns = [f"{col}_{i}" if list(df_disp.columns).count(col) > 1 and list(df_disp.columns).index(col) != i else col 
                                            for i, col in enumerate(df_disp.columns)]
                            
                            # Generate the HTML table with proper headers and data mapping
                            table_html = "<table class='compact-table'><thead><tr>"
                            headers = ["📅", "🏠", "⚽️", "⚽️", "🛫"]
                            for header in headers:
                                table_html += f"<th>{header}</th>"
                            table_html += "</tr></thead><tbody>"
                            
                            # Table rows - map the data to the correct columns
                            for record in records:
                                table_html += "<tr>"
                                
                                # Column 1: Turno (T)
                                val = record['T']
                                table_html += f"<td style='font-weight: bold; text-align: center;'>{val}</td>"
                                
                                # Column 2: Home team (🏠)
                                val = record['🏠']
                                table_html += f"<td style='text-align: right;'>{val}</td>"
                                
                                # Column 3: Home goals (first ⚽️)
                                val = record['home_goals']
                                table_html += f"<td style='font-weight: bold; text-align: center;'>{val if val != '' else '-'}</td>"
                                
                                # Column 4: Away goals (second ⚽️)
                                val = record['away_goals']
                                table_html += f"<td style='font-weight: bold; text-align: center;'>{val if val != '' else '-'}</td>"
                                
                                # Column 5: Away team (🛫)
                                val = record['🛫']
                                table_html += f"<td style='text-align: left;'>{val}</td>"
                                
                                table_html += "</tr>"
                                
                            table_html += "</tbody></table>"
                            st.markdown(table_html, unsafe_allow_html=True)
                        else:
                            st.info("Nessun incontro KO validato finora.")
                        if st.button("Nascondi incontri disputati"):
                            st.session_state['show_all_ko_matches'] = False
                            st.rerun()
                    else:
                        # --- SOLO round attivo ---
                        if st.session_state['rounds_ko']:
                            current_round_df = st.session_state['rounds_ko'][-1]
                            render_round(current_round_df, len(st.session_state['rounds_ko']) - 1, st.session_state.get("modalita_visualizzazione_ko", "squadre"))
                            
                            # Check if user has write access
                            has_write_access = st.session_state.get("user", {}).get("role") not in ["ospite", "lettura"]
                            
                            if st.button(
                                "💾 Salva risultati e genera prossimo round", 
                                on_click=salva_risultati_ko if has_write_access else None,
                                disabled=not has_write_access,
                                help="Salva i risultati e genera il prossimo round" + ("" if has_write_access else " (accesso in sola lettura)")
                            ):
                                if has_write_access:
                                    # Log dell'azione di salvataggio torneo
                                    username = st.session_state.get('user', {}).get('username', 'sconosciuto')
                                    tournament_id = st.session_state.get('tournament_id', 'sconosciuto')
                                    round_name = st.session_state.get('round_corrente', 'Round sconosciuto')
                                    
                                    log.log_action(
                                        username=username,
                                        action="salva_torneo",
                                        torneo=tournament_id,
                                        details={
                                            "tipo_operazione": "salvataggio_torneo",
                                            "round_corrente": round_name,
                                            "stato": "salvataggio_in_corso"
                                        }
                                    )
                                else:
                                    st.error("⛔ Accesso in sola lettura. Non è possibile salvare i risultati o generare il prossimo round.")
                        
                    if st.session_state['giornate_mode'] == 'ko':
                        st.markdown("<style>#root > div:nth-child(1) > div > div > div > div:nth-child(1) > div > div:nth-child(2) > div:nth-child(1) > div:nth-child(1), #root > div:nth-child(1) > div > div > div > div:nth-child(1) > div > div:nth-child(3) > div:nth-child(1) > div:nth-child(1){display:none;}</style>", unsafe_allow_html=True)
                        st.markdown("<style>#root > div:nth-child(1) > div > div > div > div:nth-child(1) > div > div:nth-child(4) {display:none;}</style>", unsafe_allow_html=True)
                    
                    # Questo è il nuovo blocco da aggiungere in fondo
                    
                    if st.session_state.get('vincitore_torneo'):
                        #st.markdown("<br><br>", unsafe_allow_html=True)
                        #st.success(f"🏆 Il vincitore del torneo è: **{st.session_state['vincitore_torneo']}** 🎉")
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
                                🏆 Il vincitore del torneo {st.session_state['vincitore_torneo']}! 🎉
                             </div>
                             """, unsafe_allow_html=True)                        
                        st.balloons()
                        st.link_button("🏠 Vai alla gestione tornei", "https://farm-tornei-subbuteo-piercrew-all-db.streamlit.app/")
    # Footer leggero
    st.markdown("---")
    st.caption("⚽ Subbuteo Tournament Manager •  Made by Legnaro72")
    
if __name__ == "__main__":
    main()