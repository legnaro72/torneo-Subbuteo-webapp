import streamlit as st

# Configurazione pagina (DEVE essere il primo comando Streamlit)
# Configurazione pagina spostata all'inizio
st.set_page_config(
    page_title="Gestione Club PierCrew",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

import pandas as pd
from pymongo import MongoClient, UpdateOne, InsertOne
from pymongo.server_api import ServerApi
import certifi
from fpdf import FPDF
from datetime import datetime
import os
import io

# Import custom utilities
import auth_utils as auth
import logging_utils as log

# Importa moduli comuni per stili, audio e componenti UI
from common.styles import inject_all_styles
from common.audio import (
    autoplay_background_audio, toggle_audio_callback,
    start_background_audio, setup_audio_sidebar
)
from common.ui_components import setup_common_sidebar, enable_session_keepalive

# Dati di connessione a MongoDB forniti dall'utente
MONGO_URI_PLAYERS = "mongodb+srv://massimilianoferrando:Legnaro21!$@cluster0.t3750lc.mongodb.net/?retryWrites=true&w=majority"
MONGO_URI_TOURNEMENTS = "mongodb+srv://massimilianoferrando:Legnaro21!$@cluster0.t3750lc.mongodb.net/?retryWrites=true&w=majority"
MONGO_URI_TOURNEMENTS_CH = "mongodb+srv://massimilianoferrando:Legnaro21!$@cluster0.t3750lc.mongodb.net/?retryWrites=true&w=majority"

# ==============================================================================
# ISTRUZIONE DEFINITIVA: AVVIO AUDIO DI SOTTOFONDO PERSISTENTE
# ==============================================================================
# Definisci la tua URL raw per l'audio di sfondo
BACKGROUND_AUDIO_URL = "https://raw.githubusercontent.com/legnaro72/torneo-Subbuteo-webapp/main/Gli%20Amici%20(Remastered%202007).mp3"


@st.cache_resource
def init_mongo_connections():
    """Inizializza le connessioni MongoDB con gestione degli errori (cached per sessione)"""
    try:
        client_players = MongoClient(MONGO_URI_PLAYERS, server_api=ServerApi('1'), tlsCAFile=certifi.where())
        client_italiana = MongoClient(MONGO_URI_TOURNEMENTS, server_api=ServerApi('1'), tlsCAFile=certifi.where())
        client_svizzera = MongoClient(MONGO_URI_TOURNEMENTS_CH, server_api=ServerApi('1'), tlsCAFile=certifi.where())
        
        # Verifica le connessioni
        client_players.admin.command('ping')
        client_italiana.admin.command('ping')
        client_svizzera.admin.command('ping')
        
        return client_players, client_italiana, client_svizzera
    except Exception as e:
        st.error(f"Errore di connessione a MongoDB: {e}")
        return None, None, None

# Mostra la schermata di autenticazione se non si è già autenticati
if not st.session_state.get('authenticated', False):
    auth.show_auth_screen(club="PierCrew")
    st.stop()
    
# Attiva il keep-alive per evitare il timeout della sessione
enable_session_keepalive()
    

# Inizializza le connessioni MongoDB
client_players, client_italiana, client_svizzera = init_mongo_connections()
if None in (client_players, client_italiana, client_svizzera):
    st.stop()

# Inizializza le collezioni
db_players = client_players["giocatori_subbuteo"]
collection_players = db_players["piercrew_players"]

# Inizializza lo stato della sessione
if 'edit_index' not in st.session_state:
    st.session_state.edit_index = None

if 'confirm_delete' not in st.session_state:
    st.session_state.confirm_delete = {"type": None, "data": None, "password_required": False}

if 'password_check' not in st.session_state:
    st.session_state.password_check = {"show": False, "password": None, "type": None}

def inject_css():
    """CSS centralizzato — delega al modulo condiviso + stili specifici di questa app."""
    inject_all_styles()
    # Stile specifico solo per questa pagina con supporto Dark Mode
    st.markdown("""
        <style>
        .button-title {
            background: linear-gradient(90deg, var(--color-primary-mid), var(--color-primary-dark));
            color: white !important;
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            margin: 20px 0;
            box-shadow: var(--card-shadow);
            border: 1px solid var(--card-border);
            font-size: 2.2em;
            font-weight: 800;
            text-decoration: none !important;
            display: block;
            width: 100%;
            animation: fadeInUp 0.8s ease-out;
        }
        
        /* Override locale ultra-aggressivo per rimuovere lo spazio vuoto in alto (solo PierCrew) */
        .stAppViewBlockContainer {
            padding-top: 1rem !important;
        }
        .stMainBlockContainer {
            padding-top: 1rem !important;
        }
        </style>
    """, unsafe_allow_html=True)
        

def carica_dati_da_mongo():
    data = list(collection_players.find())
    if data:
        df = pd.DataFrame(data)
        df = df.drop(columns=["_id"], errors="ignore")
        if "Giocatore" in df.columns:
            return df.sort_values(by="Giocatore").reset_index(drop=True)
    return pd.DataFrame(columns=["Giocatore", "Squadra", "Potenziale"])

def salva_dati_su_mongo(df):
    # Assicurati che le colonne obbligatorie siano presenti
    colonne_obbligatorie = ["Giocatore", "Squadra", "Potenziale", "Ruolo", "Password", "SetPwd"]
    for col in colonne_obbligatorie:
        if col not in df.columns:
            df[col] = None if col != "SetPwd" else 0
            
    # Prendi i dati esistenti per il confronto
    dati_esistenti = {d["Giocatore"]: d for d in collection_players.find({})}
    
    # Prepara i dati per l'aggiornamento
    operazioni = []
    for record in df.to_dict('records'):
        giocatore = record["Giocatore"]
        if giocatore in dati_esistenti:
            # Prendi il record esistente
            record_esistente = dati_esistenti[giocatore]
            
            # Mantieni il valore esistente di SetPwd se è 1
            if record_esistente.get("SetPwd") == 1:
                record["SetPwd"] = 1
            else:
                record["SetPwd"] = record.get("SetPwd", 0)
                
            # Mantieni i valori delle altre colonne nascoste se non specificate
            for col in ["Squadra", "Potenziale", "Ruolo", "Password"]:
                if col not in record or record[col] is None:
                    record[col] = record_esistente.get(col, "")
            
            # Aggiorna solo i campi modificati
            operazioni.append(UpdateOne(
                {"Giocatore": giocatore},
                {"$set": record}
            ))
        else:
            # Inserisci un nuovo record con valori di default
            record["SetPwd"] = record.get("SetPwd", 0)
            for col in ["Squadra", "Potenziale", "Ruolo", "Password"]:
                if col not in record or record[col] is None:
                    record[col] = ""
            operazioni.append(InsertOne(record))
    
    # Esegui le operazioni in batch
    if operazioni:
        collection_players.bulk_write(operazioni, ordered=False)

# --- Sezione per la gestione dei tornei ---
def carica_tornei_all_italiana():
    """Carica solo i nomi dei tornei all'italiana dalla collezione PierCrew."""
    db_tornei = client_italiana["TorneiSubbuteo"]
    collection_tornei = db_tornei["PierCrew"]
    data = list(collection_tornei.find({}, {"nome_torneo": 1}))
    if data:
        df = pd.DataFrame(data)
        df = df.drop(columns=["_id"], errors="ignore")
        if "nome_torneo" in df.columns:
            df.rename(columns={"nome_torneo": "Torneo"}, inplace=True)
            return df.sort_values(by="Torneo").reset_index(drop=True)
    return pd.DataFrame(columns=["Torneo"])

def salva_tornei_all_italiana(df):
    db_tornei = client_italiana["TorneiSubbuteo"]
    collection_tornei = db_tornei["PierCrew"]
    collection_tornei.delete_many({})
    collection_tornei.insert_many(df.to_dict('records'))
    st.toast("Dati dei tornei all'italiana salvati con successo!")

def carica_tornei_svizzeri():
    """Carica solo i nomi dei tornei svizzeri dalla collezione PierCrewSvizzero."""
    db_tornei = client_svizzera["TorneiSubbuteo"]
    collection_tornei = db_tornei["PierCrewSvizzero"]
    data = list(collection_tornei.find({}, {"nome_torneo": 1}))
    if data:
        df = pd.DataFrame(data)
        df = df.drop(columns=["_id"], errors="ignore")
        if "nome_torneo" in df.columns:
            df.rename(columns={"nome_torneo": "Torneo"}, inplace=True)
            return df.sort_values(by="Torneo").reset_index(drop=True)
    return pd.DataFrame(columns=["Torneo"])

def salva_tornei_svizzeri(df):
    db_tornei = client_svizzera["TorneiSubbuteo"]
    collection_tornei = db_tornei["PierCrewSvizzero"]
    collection_tornei.delete_many({})
    collection_tornei.insert_many(df.to_dict('records'))
    st.toast("Dati dei tornei svizzeri salvati con successo!")


# Mostra la schermata di autenticazione se non si è già autenticati
if not st.session_state.get('authenticated', False):
    auth.show_auth_screen(club="PierCrew")
    st.stop()

# Configurazione pagina già impostata all'inizio

def reset_app_state():
    """Resetta lo stato dell'applicazione"""
    keys_to_reset = [
        "edit_index", "confirm_delete", "df_giocatori",
        "df_tornei_italiana", "df_tornei_svizzeri"
    ]
    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key]
            
# Le funzioni audio (toggle_audio_callback, autoplay_background_audio)
# sono ora importate da common.audio

# Avvio audio di sottofondo
start_background_audio(BACKGROUND_AUDIO_URL)
            
# (Audio gestito tramite start_background_audio sopra — nessuna funzione locale duplicata)

# Inietta gli stili CSS personalizzati
inject_css()

# Debug: mostra utente autenticato e ruolo manualmete per metterlo in cima alla sidebar
if st.session_state.get("authenticated"):
    user = st.session_state.get("user", {})
    st.sidebar.markdown(f"**👤 Utente:** {user.get('username', '??')}")
    st.sidebar.markdown(f"**🔑 Ruolo:** {user.get('role', '??')}")

HUB_URL = "https://farm-tornei-subbuteo-piercrew-all-db.streamlit.app/"

# Sidebar — usa moduli condivisi
setup_common_sidebar(show_user_info=False, show_hub_link=True, hub_url=HUB_URL)
setup_audio_sidebar()

# ==============================================================================
# PDF EXPORT — La Gazzetta della PierCrew (Composizione Club)
# ==============================================================================

class GazzettaClubPDF(FPDF):
    """PDF con stile 'La Gazzetta della PierCrew' per la composizione del club."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def header(self):
        # Sfondo Header (Blu Navy)
        self.set_fill_color(26, 54, 93)
        self.rect(0, 0, 210, 32, 'F')
        # Linea dorata di accento
        self.set_fill_color(212, 175, 55)
        self.rect(0, 32, 210, 1.5, 'F')
        # Logo PierCrew
        logo_path = "logo_piercrew.jpg"
        start_x = 10
        if os.path.exists(logo_path):
            self.image(logo_path, 12, 5, 22)
            start_x = 40
        # Titolo
        self.set_xy(start_x, 8)
        self.set_font("Arial", 'B', 24)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, "IL GAZZETTINO DEL PIER CREW", border=0, ln=1, align='L')
        # Sottotitolo
        self.set_x(start_x)
        self.set_font("Arial", 'I', 11)
        self.set_text_color(220, 225, 235)
        data_stampa = datetime.now().strftime("%d/%m/%Y alle %H:%M")
        self.cell(0, 6, f"Composizione Club PierCrew | Aggiornato il {data_stampa}", border=0, ln=1, align='L')
        self.ln(12)

    def footer(self):
        self.set_y(-15)
        self.set_fill_color(26, 54, 93)
        self.rect(0, 287, 210, 10, 'F')
        self.set_font('Arial', 'B', 8)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, f'Pagina {self.page_no()} - La Gazzetta della PierCrew - Gestionale Club Subbuteo', 0, 0, 'C')


def _safe(text):
    """Sanitizza testo per FPDF (Latin-1 safe)."""
    if text is None:
        return "-"
    s = str(text).strip()
    if s.lower() in ['none', 'nan', '<na>', '']:
        return "-"
    # Sostituzioni caratteri problematici
    replacements = {
        '\u2019': "'", '\u2018': "'",  # smart quotes
        '\u201c': '"', '\u201d': '"',  # smart double quotes
        '\u2013': '-', '\u2014': '-',  # en/em dash
        '\u2026': '...',               # ellipsis
        '\u20ac': 'EUR',               # euro
    }
    for old, new in replacements.items():
        s = s.replace(old, new)
    # Forza encoding Latin-1 con fallback
    try:
        s.encode('latin-1')
    except UnicodeEncodeError:
        s = s.encode('latin-1', errors='replace').decode('latin-1')
    return s


def genera_pdf_club(df_giocatori, df_tornei_ita, df_tornei_svizzeri):
    """Genera un PDF con la composizione completa del club in stile Gazzetta."""
    pdf = GazzettaClubPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # ======= SEZIONE ROSA GIOCATORI =======
    pdf.set_font("Arial", 'B', 18)
    pdf.set_fill_color(230, 235, 245)
    pdf.set_text_color(26, 54, 93)
    pdf.cell(0, 12, " ROSA GIOCATORI ", border=1, ln=True, fill=True, align='C')
    pdf.ln(3)

    num_giocatori = len(df_giocatori)
    pot_medio = df_giocatori['Potenziale'].mean() if not df_giocatori.empty and 'Potenziale' in df_giocatori.columns else 0

    pdf.set_font("Arial", 'I', 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, f"Totale tesserati: {num_giocatori} | Potenziale medio: {pot_medio:.1f}/10", ln=True, align='C')
    pdf.ln(3)

    if not df_giocatori.empty:
        # Header tabella
        pdf.set_font("Arial", 'B', 11)
        pdf.set_fill_color(26, 54, 93)
        pdf.set_text_color(255, 255, 255)
        headers = ["#", "Giocatore", "Squadra", "Pot."]
        widths = [12, 68, 78, 18]
        for i, h in enumerate(headers):
            pdf.cell(widths[i], 8, h, border=1, align='C', fill=True)
        pdf.ln()

        # Body tabella (ordinato per potenziale decrescente)
        pdf.set_font("Arial", '', 10)
        pdf.set_text_color(0, 0, 0)
        df_sorted = df_giocatori.sort_values(by=['Potenziale', 'Giocatore'], ascending=[False, True]).reset_index(drop=True)

        for idx, (_, r) in enumerate(df_sorted.iterrows()):
            fill = (idx % 2 == 0)
            pdf.set_fill_color(245, 248, 250) if fill else pdf.set_fill_color(255, 255, 255)
            giocatore = _safe(r.get('Giocatore', '-'))[:32]
            squadra = _safe(r.get('Squadra', '-'))[:38]
            pot_val = int(r.get('Potenziale', 0)) if pd.notna(r.get('Potenziale')) else 0

            pdf.cell(widths[0], 7, str(idx + 1), border='LR', align='C', fill=fill)
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(widths[1], 7, " " + giocatore, border='LR', align='L', fill=fill)
            pdf.set_font("Arial", '', 10)
            pdf.cell(widths[2], 7, " " + squadra, border='LR', align='L', fill=fill)

            # Colore potenziale
            if pot_val >= 8:
                pdf.set_text_color(212, 175, 55)
            elif pot_val >= 6:
                pdf.set_text_color(42, 157, 143)
            elif pot_val >= 4:
                pdf.set_text_color(100, 100, 100)
            else:
                pdf.set_text_color(200, 80, 80)
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(widths[3], 7, str(pot_val), border='LR', align='C', fill=fill)
            pdf.set_font("Arial", '', 10)
            pdf.set_text_color(0, 0, 0)
            pdf.ln()

        pdf.cell(sum(widths), 0, '', border='T', ln=True)
    else:
        pdf.set_font("Arial", 'I', 11)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 10, "Nessun giocatore registrato.", ln=True, align='C')

    pdf.ln(8)

    # ======= DISTRIBUZIONE POTENZIALE =======
    if not df_giocatori.empty and 'Potenziale' in df_giocatori.columns:
        if pdf.get_y() > 230:
            pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.set_fill_color(230, 235, 245)
        pdf.set_text_color(26, 54, 93)
        pdf.cell(0, 10, " DISTRIBUZIONE POTENZIALE ", border=1, ln=True, fill=True, align='C')
        pdf.ln(3)
        pdf.set_text_color(0, 0, 0)
        pot_counts = df_giocatori['Potenziale'].value_counts().sort_index(ascending=False)
        for pot, count in pot_counts.items():
            bar_width = min(count * 12, 140)
            if int(pot) >= 8:
                pdf.set_fill_color(212, 175, 55)
            elif int(pot) >= 6:
                pdf.set_fill_color(42, 157, 143)
            elif int(pot) >= 4:
                pdf.set_fill_color(150, 160, 175)
            else:
                pdf.set_fill_color(200, 80, 80)
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(20, 7, f"  {int(pot)}/10", border=0, align='L')
            pdf.cell(bar_width, 7, '', border=0, fill=True)
            pdf.set_font("Arial", '', 9)
            pdf.cell(30, 7, f"  {count} giocator{'e' if count == 1 else 'i'}", border=0, align='L')
            pdf.ln()
        pdf.ln(5)

    # ======= SEZIONE TORNEI =======
    pdf.add_page()
    pdf.set_font("Arial", 'B', 18)
    pdf.set_fill_color(230, 235, 245)
    pdf.set_text_color(26, 54, 93)
    pdf.cell(0, 12, " ARCHIVIO TORNEI ", border=1, ln=True, fill=True, align='C')
    pdf.ln(5)

    # Tornei All'Italiana
    pdf.set_font("Arial", 'B', 14)
    pdf.set_fill_color(26, 54, 93)
    pdf.set_text_color(255, 255, 255)
    num_ita = len(df_tornei_ita) if not df_tornei_ita.empty else 0
    pdf.cell(0, 9, f"  TORNEI ALL'ITALIANA ({num_ita})", border=1, ln=True, fill=True, align='L')
    pdf.ln(2)
    if not df_tornei_ita.empty:
        pdf.set_font("Arial", '', 10)
        pdf.set_text_color(0, 0, 0)
        for idx, (_, r) in enumerate(df_tornei_ita.iterrows()):
            fill = (idx % 2 == 0)
            pdf.set_fill_color(245, 248, 250) if fill else pdf.set_fill_color(255, 255, 255)
            nome = _safe(r.get('Torneo', '-'))[:85]
            if 'campionato' in nome.lower():
                pdf.set_font("Arial", 'B', 10)
                pdf.set_text_color(212, 175, 55)
            else:
                pdf.set_font("Arial", '', 10)
                pdf.set_text_color(0, 0, 0)
            pdf.cell(12, 7, str(idx + 1), border='LR', align='C', fill=fill)
            pdf.cell(164, 7, "  " + nome, border='LR', align='L', fill=fill)
            pdf.ln()
            pdf.set_text_color(0, 0, 0)
        pdf.cell(176, 0, '', border='T', ln=True)
    else:
        pdf.set_font("Arial", 'I', 10)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 8, "Nessun torneo all'italiana registrato.", ln=True, align='C')
    pdf.ln(8)

    # Tornei Svizzeri
    if pdf.get_y() > 230:
        pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.set_fill_color(26, 54, 93)
    pdf.set_text_color(255, 255, 255)
    num_svizz = len(df_tornei_svizzeri) if not df_tornei_svizzeri.empty else 0
    pdf.cell(0, 9, f"  TORNEI SVIZZERI ({num_svizz})", border=1, ln=True, fill=True, align='L')
    pdf.ln(2)
    if not df_tornei_svizzeri.empty:
        pdf.set_font("Arial", '', 10)
        pdf.set_text_color(0, 0, 0)
        for idx, (_, r) in enumerate(df_tornei_svizzeri.iterrows()):
            fill = (idx % 2 == 0)
            pdf.set_fill_color(245, 248, 250) if fill else pdf.set_fill_color(255, 255, 255)
            nome = _safe(r.get('Torneo', '-'))[:85]
            if 'campionato' in nome.lower():
                pdf.set_font("Arial", 'B', 10)
                pdf.set_text_color(212, 175, 55)
            else:
                pdf.set_font("Arial", '', 10)
                pdf.set_text_color(0, 0, 0)
            pdf.cell(12, 7, str(idx + 1), border='LR', align='C', fill=fill)
            pdf.cell(164, 7, "  " + nome, border='LR', align='L', fill=fill)
            pdf.ln()
            pdf.set_text_color(0, 0, 0)
        pdf.cell(176, 0, '', border='T', ln=True)
    else:
        pdf.set_font("Arial", 'I', 10)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 8, "Nessun torneo svizzero registrato.", ln=True, align='C')
    pdf.ln(8)

    # ======= RIEPILOGO FINALE =======
    if pdf.get_y() > 240:
        pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.set_fill_color(212, 175, 55)
    pdf.set_text_color(26, 54, 93)
    pdf.cell(0, 10, " RIEPILOGO CLUB ", border=1, ln=True, fill=True, align='C')
    pdf.ln(3)
    pdf.set_text_color(0, 0, 0)
    stats = [
        ("Giocatori tesserati", str(num_giocatori)),
        ("Potenziale medio", f"{pot_medio:.1f}/10"),
        ("Tornei All'Italiana", str(num_ita)),
        ("Tornei Svizzeri", str(num_svizz)),
        ("Totale Tornei", str(num_ita + num_svizz)),
    ]
    for label, value in stats:
        pdf.set_font("Arial", '', 11)
        pdf.cell(100, 7, "  " + label, border='LTB', align='L')
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(76, 7, value + "  ", border='RTB', align='R')
        pdf.ln()

    # Output: old fpdf restituisce stringa con dest='S'
    return pdf.output(dest='S').encode('latin-1')


st.markdown("<div class='button-title'>⚽ Gestione Club e Tornei PierCrew 🏆</div>", unsafe_allow_html=True)

# Check user status and permissions
current_user = auth.get_current_user()
is_admin = current_user and current_user.get('role') == 'A'
is_guest = current_user and current_user.get('role') == 'G'

# Inizializza i dataframe nel session state
if "df_giocatori" not in st.session_state:
    st.session_state.df_giocatori = carica_dati_da_mongo()
if "df_tornei_italiana" not in st.session_state:
    st.session_state.df_tornei_italiana = carica_tornei_all_italiana()
if "df_tornei_svizzeri" not in st.session_state:
    st.session_state.df_tornei_svizzeri = carica_tornei_svizzeri()

# Funzioni per la logica dell'app
def add_player():
    st.session_state.edit_index = -1

def save_player(giocatore, squadra, potenziale, ruolo="R"):
    if giocatore.strip() == "":
        st.error("Il nome del giocatore non può essere vuoto!")
    else:
        username = st.session_state.get('user', {}).get('username', 'sconosciuto')
        if st.session_state.edit_index == -1:
            new_row = {
                "Giocatore": giocatore,
                "Squadra": squadra,
                "Potenziale": potenziale,
                "Ruolo": ruolo,
                "Password": None,
                "SetPwd": 0
            }
            st.session_state.df_giocatori = pd.concat([st.session_state.df_giocatori, pd.DataFrame([new_row])], ignore_index=True)
            action = "aggiunta_giocatore"
            st.toast(f"Giocatore '{giocatore}' aggiunto!")
        else:
            idx = st.session_state.edit_index
            old_name = st.session_state.df_giocatori.at[idx, "Giocatore"]
            old_squadra = st.session_state.df_giocatori.at[idx, "Squadra"]
            old_potenziale = st.session_state.df_giocatori.at[idx, "Potenziale"]
            old_ruolo = st.session_state.df_giocatori.at[idx, "Ruolo"]
            
            st.session_state.df_giocatori.at[idx, "Giocatore"] = giocatore.strip()
            st.session_state.df_giocatori.at[idx, "Squadra"] = squadra.strip()
            st.session_state.df_giocatori.at[idx, "Potenziale"] = potenziale
            st.session_state.df_giocatori.at[idx, "Ruolo"] = ruolo
            action = "modifica_giocatore"
            st.toast(f"Giocatore '{giocatore}' aggiornato!")
            
        st.session_state.df_giocatori = st.session_state.df_giocatori.sort_values(by="Giocatore").reset_index(drop=True)
        salva_dati_su_mongo(st.session_state.df_giocatori)
        
        # Log dell'azione
        log_details = {
            "tipo_operazione": action,
            "giocatore": giocatore,
            "squadra": squadra,
            "potenziale": potenziale,
            "ruolo": ruolo
        }
        
        # Aggiungi i vecchi valori se è una modifica
        if action == "modifica_giocatore":
            changes = {}
            if old_name != giocatore.strip():
                changes["nome"] = {"da": old_name, "a": giocatore.strip()}
            if old_squadra != squadra.strip():
                changes["squadra"] = {"da": old_squadra, "a": squadra.strip()}
            if old_potenziale != potenziale:
                changes["potenziale"] = {"da": old_potenziale, "a": potenziale}
            if old_ruolo != ruolo:
                changes["ruolo"] = {"da": old_ruolo, "a": ruolo}
                
            log_details["modifiche"] = changes
            log_details["riassunto_modifiche"] = ", ".join([f"{k}: {v['da']} → {v['a']}" for k, v in changes.items()])
        
        log.log_action(
            username=username,
            action=action,
            torneo="gestione_giocatori",
            details=log_details
        )
        
        st.session_state.edit_index = None
        st.rerun()

def modify_player(idx):
    st.session_state.edit_index = idx

def confirm_delete_player(idx, selected_player):
    st.session_state.confirm_delete = {"type": "player", "data": (idx, selected_player), "password_required": False}
    st.rerun()

def confirm_delete_torneo_italiana(selected_tornei):
    # Richiede la password per qualsiasi torneo che contenga 'campionato' nel nome
    # anche se è una cancellazione singola
    tornei_list = [selected_tornei] if isinstance(selected_tornei, str) else selected_tornei
    password_required = any(isinstance(t, str) and "campionato" in t.lower() for t in tornei_list)
    
    st.session_state.confirm_delete = {
        "type": "tornei_ita", 
        "data": selected_tornei, 
        "password_required": password_required
    }
    st.rerun()

def confirm_delete_torneo_svizzero(selected_tornei):
    # Richiede la password per qualsiasi torneo che contenga 'campionato' nel nome
    # anche se è una cancellazione singola
    tornei_list = [selected_tornei] if isinstance(selected_tornei, str) else selected_tornei
    password_required = any(isinstance(t, str) and "campionato" in t.lower() for t in tornei_list)
    
    st.session_state.confirm_delete = {
        "type": "tornei_svizz", 
        "data": selected_tornei, 
        "password_required": password_required
    }
    st.rerun()
    
def confirm_delete_all_tornei_italiana():
    st.session_state.confirm_delete = {"type": "all_ita", "data": None, "password_required": True}
    st.rerun()

def confirm_delete_all_tornei_svizzeri():
    st.session_state.confirm_delete = {"type": "all_svizz", "data": None, "password_required": True}
    st.rerun()

def confirm_delete_all_tornei_all():
    st.session_state.confirm_delete = {"type": "all", "data": None, "password_required": True}
    st.rerun()

def cancel_delete():
    st.session_state.confirm_delete = {"type": None, "data": None, "password_required": False}
    st.session_state.password_check = {"show": False, "password": None, "type": None}
    st.info("Operazione di eliminazione annullata.")
    st.rerun()

def process_deletion_with_password(password, deletion_type, data):
    # Non richiedere la password per l'eliminazione di tornei singoli
    if deletion_type in ["tornei_ita", "tornei_svizz"]:
        correct_password = password  # Accetta qualsiasi password
    # Richiedi la password solo per l'eliminazione di tutti i tornei o tornei che iniziano con 'Campionato'
    elif deletion_type in ["all_ita", "all_svizz", "all"] or \
         (isinstance(data, tuple) and len(data) > 1 and data[1].startswith("Campionato")):
        correct_password = "Legnaro72"
    else:
        # Per le altre operazioni non è richiesta password
        correct_password = password  # Accetta qualsiasi password
    
    if deletion_type not in ["player", "tornei_ita", "tornei_svizz", "all_ita", "all_svizz", "all"]:
        st.error("Tipo di cancellazione non valido.")
        return

    if password == correct_password:
        username = st.session_state.get('user', {}).get('username', 'sconosciuto')
        if deletion_type == "player":
            idx, selected_player = data
            player_data = st.session_state.df_giocatori.iloc[idx].to_dict()
            st.session_state.df_giocatori = st.session_state.df_giocatori.drop(idx).reset_index(drop=True)
            salva_dati_su_mongo(st.session_state.df_giocatori)
            
            # Log player deletion
            log.log_action(
                username=username,
                action="eliminazione_giocatore",
                torneo="gestione_giocatori",
                details={
                    "tipo_operazione": "eliminazione_giocatore",
                    "giocatore": selected_player,
                    "dettagli_giocatore": {
                        "squadra": player_data.get("Squadra", ""),
                        "ruolo": player_data.get("Ruolo", ""),
                        "potenziale": player_data.get("Potenziale", "")
                    }
                }
            )
            st.toast(f"Giocatore '{selected_player}' eliminato!")

        elif deletion_type == "tornei_ita":
            db_tornei = client_italiana["TorneiSubbuteo"]
            collection_tornei = db_tornei["PierCrew"]
            for torneo in data:
                # Log before deletion
                torneo_data = collection_tornei.find_one({"nome_torneo": torneo})
                collection_tornei.delete_one({"nome_torneo": torneo})
                st.session_state.df_tornei_italiana = st.session_state.df_tornei_italiana[st.session_state.df_tornei_italiana["Torneo"] != torneo].reset_index(drop=True)
                
                # Log tournament deletion
                log.log_action(
                    username=username,
                    action="eliminazione_torneo_italiano",
                    torneo=torneo,
                    details={
                        "tipo_operazione": "eliminazione_torneo_singolo",
                        "torneo": torneo,
                        "tornei_eliminati": 1,
                        "dettagli_torneo": {
                            "tipo": "italiano",
                            "partecipanti": torneo_data.get("partite", []) if torneo_data else []
                        }
                    }
                )
                st.toast(f"Torneo '{torneo}' eliminato!")

        elif deletion_type == "tornei_svizz":
            db_tornei = client_svizzera["TorneiSubbuteo"]
            collection_tornei = db_tornei["PierCrewSvizzero"]
            for torneo in data:
                # Log before deletion
                torneo_data = collection_tornei.find_one({"nome_torneo": torneo})
                collection_tornei.delete_one({"nome_torneo": torneo})
                st.session_state.df_tornei_svizzeri = st.session_state.df_tornei_svizzeri[st.session_state.df_tornei_svizzeri["Torneo"] != torneo].reset_index(drop=True)
                
                # Log tournament deletion
                log.log_action(
                    username=username,
                    action="eliminazione_torneo_svizzero",
                    torneo=torneo,
                    details={
                        "tipo_operazione": "eliminazione_torneo_singolo",
                        "torneo": torneo,
                        "tornei_eliminati": 1,
                        "dettagli_torneo": {
                            "tipo": "svizzero",
                            "partecipanti": torneo_data.get("partite", []) if torneo_data else []
                        }
                    }
                )
                st.toast(f"Torneo '{torneo}' eliminato!")

        elif deletion_type == "all_ita":
            db_tornei = client_italiana["TorneiSubbuteo"]
            collection_tornei = db_tornei["PierCrew"]
            tornei_da_cancellare = [t["nome_torneo"] for t in collection_tornei.find({}) if "campionato" not in t["nome_torneo"].lower()]
            
            # Get count before deletion for logging
            count_before = collection_tornei.count_documents({})
            
            for torneo in tornei_da_cancellare:
                collection_tornei.delete_one({"nome_torneo": torneo})
                
            count_after = collection_tornei.count_documents({})
            st.session_state.df_tornei_italiana = carica_tornei_all_italiana()
            
            # Log mass deletion
            if tornei_da_cancellare:
                log.log_action(
                    username=username,
                    action="eliminazione_massiva_tornei_italiani",
                    torneo="tutti_tornei_italiani",
                    details={
                        "tipo_operazione": "eliminazione_massiva_tornei",
                        "tornei_eliminati": len(tornei_da_cancellare),
                        "tornei_rimasti": count_after,
                        "esclusi_campionati": True,
                        "tornei_esclusi": [t for t in collection_tornei.find({}) if "campionato" in t["nome_torneo"].lower()]
                    }
                )
            
            st.toast("✅ Tutti i tornei all'italiana (esclusi i campionati) sono stati eliminati!")

        elif deletion_type == "all_svizz":
            db_tornei = client_svizzera["TorneiSubbuteo"]
            collection_tornei = db_tornei["PierCrewSvizzero"]
            tornei_da_cancellare = [t["nome_torneo"] for t in collection_tornei.find({}) if "campionato" not in t["nome_torneo"].lower()]
            
            # Get count before deletion for logging
            count_before = collection_tornei.count_documents({})
            
            for torneo in tornei_da_cancellare:
                collection_tornei.delete_one({"nome_torneo": torneo})
                
            count_after = collection_tornei.count_documents({})
            st.session_state.df_tornei_svizzeri = carica_tornei_svizzeri()
            
            # Log mass deletion
            if tornei_da_cancellare:
                log.log_action(
                    username=username,
                    action="eliminazione_massiva_tornei_svizzeri",
                    torneo="tutti_tornei_svizzeri",
                    details={
                        "tipo_operazione": "eliminazione_massiva_tornei",
                        "tornei_eliminati": len(tornei_da_cancellare),
                        "tornei_rimasti": count_after,
                        "esclusi_campionati": True,
                        "tornei_esclusi": [t for t in collection_tornei.find({}) if "campionato" in t["nome_torneo"].lower()]
                    }
                )
            
            st.toast("✅ Tutti i tornei svizzeri (esclusi i campionati) sono stati eliminati!")

        elif deletion_type == "all":
            # Chiamiamo le funzioni specifiche per applicare il filtro
            db_tornei_ita = client_italiana["TorneiSubbuteo"]
            collection_tornei_ita = db_tornei_ita["PierCrew"]
            tornei_prima_ita = list(collection_tornei_ita.find({}))
            tornei_da_cancellare_ita = [t["nome_torneo"] for t in tornei_prima_ita if "campionato" not in t["nome_torneo"].lower()]
            
            db_tornei_svizz = client_svizzera["TorneiSubbuteo"]
            collection_tornei_svizz = db_tornei_svizz["PierCrewSvizzero"]
            tornei_prima_svizz = list(collection_tornei_svizz.find({}))
            tornei_da_cancellare_svizz = [t["nome_torneo"] for t in tornei_prima_svizz if "campionato" not in t["nome_torneo"].lower()]
            
            # Esecuzione delle cancellazioni
            for torneo in tornei_da_cancellare_ita:
                collection_tornei_ita.delete_one({"nome_torneo": torneo})
            
            for torneo in tornei_da_cancellare_svizz:
                collection_tornei_svizz.delete_one({"nome_torneo": torneo})
            
            # Aggiornamento degli stati
            st.session_state.df_tornei_italiana = carica_tornei_all_italiana()
            st.session_state.df_tornei_svizzeri = carica_tornei_svizzeri()
            
            # Log dell'operazione di cancellazione completa
            log.log_action(
                username=username,
                action="eliminazione_completa_tornei",
                torneo="tutti_tornei",
                details={
                    "tipo_operazione": "eliminazione_massiva_tutti_tornei",
                    "tornei_italiani_eliminati": len(tornei_da_cancellare_ita),
                    "tornei_svizzeri_eliminati": len(tornei_da_cancellare_svizz),
                    "tornei_italiani_rimasti": collection_tornei_ita.count_documents({}),
                    "tornei_svizzeri_rimasti": collection_tornei_svizz.count_documents({}),
                    "esclusi_campionati": True,
                    "tornei_esclusi_ita": [t["nome_torneo"] for t in tornei_prima_ita if "campionato" in t["nome_torneo"].lower()],
                    "tornei_esclusi_svizz": [t["nome_torneo"] for t in tornei_prima_svizz if "campionato" in t["nome_torneo"].lower()]
                }
            )
            
            st.toast("✅ TUTTI i tornei (esclusi i campionati) sono stati eliminati!")

        # Reset state after successful deletion
        st.session_state.confirm_delete = {"type": None, "data": None, "password_required": False}
        st.session_state.password_check = {"show": False, "password": None, "type": None}
        st.rerun()
    else:
        st.error("❌ Password errata. Operazione annullata.")
        st.session_state.password_check["show"] = True # Keep password field open on error

# Logica di visualizzazione basata sullo stato
if st.session_state.edit_index is None and st.session_state.confirm_delete["type"] is None:
    st.markdown("<div class='section-container'>", unsafe_allow_html=True)
    st.header("👥 Gestione Giocatori")
    st.subheader("Lista giocatori")
    
    # Create a copy of the dataframe for editing
    df = st.session_state.df_giocatori.copy()
    
    # Add role legend
    with st.expander("Legenda Ruoli"):
        st.markdown("""
        - **R**: Reader (sola lettura)
        - **W**: Writer (lettura e scrittura)
        - **A**: Amministratore (tutti i permessi)
        """)
        
    if not df.empty:
        # Create a copy of the dataframe with the columns we want to show
        display_columns = ["Giocatore", "Squadra", "Potenziale", "Ruolo"]
        display_df = df[display_columns].copy()
        
        # Format the role for display
        role_display_map = {
            "R": "Reader",
            "W": "Writer",
            "A": "Admin"
        }
        
        # Create a display version of the role column for non-admins
        # First ensure the column exists and fill any NaN values with 'R' (Reader)
        if "Ruolo" not in display_df.columns:
            display_df["Ruolo"] = "R"
        display_df["Ruolo"] = display_df["Ruolo"].fillna("R")
        
        # Create a copy of the role column for display
        display_df["Ruolo_Display"] = display_df["Ruolo"].map(lambda x: role_display_map.get(str(x).strip(), "Reader"))
        
        # Make the dataframe editable - show different columns based on admin status
        if is_admin:
            # For admins, show the editable role column
            edited_df = st.data_editor(
                display_df[display_columns],  # Show original columns
                disabled=["id"],
                num_rows="dynamic",
                width="stretch",
                column_config={
                    "Giocatore": "Giocatore",
                    "Squadra": "Squadra",
                    "Potenziale": st.column_config.NumberColumn("Potenziale", min_value=1, max_value=10, step=1, format="%d"),
                    "Ruolo": st.column_config.SelectboxColumn(
                        "Ruolo",
                        help="Ruolo del giocatore (R=Reader, W=Writer, A=Admin)",
                        width="medium",
                        options=["R", "W", "A"],
                        required=True
                    )
                }
            )
        else:
            # For non-admins, show the display version of the role
            display_columns_non_admin = ["Giocatore", "Squadra", "Potenziale", "Ruolo_Display"]
            edited_df = st.data_editor(
                display_df[display_columns_non_admin],
                disabled=display_columns_non_admin,  # Make all columns read-only
                width="stretch",
                column_config={
                    "Giocatore": "Giocatore",
                    "Squadra": "Squadra",
                    "Potenziale": "Potenziale",
                    "Ruolo_Display": st.column_config.TextColumn("Ruolo")
                }
            )
        
        # Add save button - only for non-guest users
        
        if is_guest:
            st.warning("Gli ospiti possono solo visualizzare i dati. Effettua il login per modificare.")
        else:
            if st.button("💾 Salva Modifiche Tabella"):
                st.session_state.show_password_dialog = True
            
        # Password dialog
        if st.session_state.get('show_password_dialog', False):
            password = st.text_input("Inserisci la password per salvare le modifiche:", type="password")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Conferma Salvataggio"):
                    if password == "Legnaro72":
                        # Log delle modifiche prima di aggiornare
                        if not st.session_state.df_giocatori.equals(edited_df):
                            # Trova le differenze
                            changes = []
                            for idx in range(len(edited_df)):
                                old_row = st.session_state.df_giocatori.iloc[idx]
                                new_row = edited_df.iloc[idx]
                                if not old_row.equals(new_row):
                                    changes.append({
                                        'giocatore': new_row['Giocatore'],
                                        'campi_modificati': [
                                            col for col in edited_df.columns 
                                            if col in st.session_state.df_giocatori.columns 
                                            and old_row[col] != new_row[col]
                                        ]
                                    })
                            
                            # Aggiorna il dataframe in session state
                            st.session_state.df_giocatori = edited_df
                            # Salva nel database
                            salva_dati_su_mongo(edited_df)
                            
                            # Log delle modifiche
                            username = st.session_state.get('user', {}).get('username', 'sconosciuto')
                            log.log_action(
                                username=username,
                                action="modifica_massiva_giocatori",
                                torneo="gestione_giocatori",
                                details={
                                    "tipo_operazione": "modifica_massiva_giocatori",
                                    "modifiche": changes,
                                    "totale_giocatori_modificati": len(changes)
                                }
                            )
                            
                            st.success("✅ Modifiche salvate con successo!")
                            st.session_state.show_password_dialog = False
                            st.rerun()
                    else:
                        st.error("❌ Password errata. Le modifiche non sono state salvate.")
            with col2:
                if st.button("❌ Annulla"):
                    st.session_state.show_password_dialog = False
                    st.rerun()
    else:
        st.info("Nessun giocatore trovato. Aggiungine uno per iniziare!")

    col1, col2 = st.columns(2)
    with col1:
        st.button("➕ Aggiungi nuovo giocatore", on_click=add_player)
    with col2:
        if not df.empty and "Giocatore" in df.columns:
            giocatori = df["Giocatore"].tolist()
            selected = st.selectbox("Seleziona giocatore per Modifica o Elimina", options=[""] + giocatori)

            if selected:
                idx = df.index[df["Giocatore"] == selected][0]
                mod_col, del_col = st.columns(2)
                with mod_col:
                    st.button("✏️ Modifica", on_click=modify_player, args=(idx,), key=f"mod_{idx}")
                with del_col:
                    st.button("🗑️ Elimina", on_click=confirm_delete_player, args=(idx, selected), key=f"del_{idx}")

    csv = st.session_state.df_giocatori.to_csv(index=False).encode("utf-8")
    st.sidebar.download_button(
        "📥 Scarica CSV giocatori aggiornato",
        data=csv,
        file_name="giocatori_piercrew_modificato.csv",
        mime="text/csv",
    )

    # --- Esportazione PDF Gazzetta ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("📰 La Gazzetta della PierCrew")
    
    if st.sidebar.button("📄 Prepara PDF Composizione Club", key="prepare_pdf_club", width="stretch"):
        pdf_bytes = genera_pdf_club(
            st.session_state.df_giocatori,
            st.session_state.df_tornei_italiana,
            st.session_state.df_tornei_svizzeri
        )
        st.session_state['pdf_club_pronto'] = pdf_bytes

    if 'pdf_club_pronto' in st.session_state and st.session_state['pdf_club_pronto'] is not None:
        st.sidebar.download_button(
            label="📥 Scarica PDF Club PierCrew",
            data=st.session_state['pdf_club_pronto'],
            file_name=f"Gazzetta_Club_PierCrew_{datetime.now().strftime('%d%m%Y')}.pdf",
            mime="application/pdf",
            width="stretch"
        )
        st.sidebar.success("✅ PDF pronto!")

    st.markdown("</div>", unsafe_allow_html=True) # Chiudi contenitore solo se siamo in questa vista

    # ---
    st.markdown("<div class='section-container'>", unsafe_allow_html=True)
    st.header("🏆 Gestione Tornei")

    col_del_all_ita, col_del_all_svizz, col_del_all = st.columns(3)
    with col_del_all_ita:
        st.button("❌ Cancella tutti i tornei all'italiana 🇮🇹", on_click=confirm_delete_all_tornei_italiana)
    with col_del_all_svizz:
        st.button("❌ Cancella tutti i tornei svizzeri 🇨🇭", on_click=confirm_delete_all_tornei_svizzeri)
    with col_del_all:
        st.button("❌ Cancella TUTTI i tornei", on_click=confirm_delete_all_tornei_all)

    # Sezione per i tornei all'italiana
    st.subheader("🇮🇹 Tornei all'italiana 🇮🇹")
    df_tornei_italiana = st.session_state.df_tornei_italiana.copy()
    if not df_tornei_italiana.empty:
        st.dataframe(df_tornei_italiana[["Torneo"]], width="stretch")
        tornei = df_tornei_italiana["Torneo"].tolist()
        selected_tornei_italiana = st.multiselect("Seleziona tornei all'italiana da eliminare", options=tornei, key="del_italiana_select")
        
        if selected_tornei_italiana:
            st.button("🗑️ Elimina Tornei selezionati", on_click=confirm_delete_torneo_italiana, args=(selected_tornei_italiana,), key="del_italiana_btn")
    else:
        st.info("Nessun torneo all'italiana trovato.")

    # ---
    st.markdown("---")

    # Sezione per i tornei svizzeri
    st.subheader("🇨🇭 Tornei svizzeri 🇨🇭")
    df_tornei_svizzeri = st.session_state.df_tornei_svizzeri.copy()
    if not df_tornei_svizzeri.empty:
        st.dataframe(df_tornei_svizzeri[["Torneo"]], width="stretch")
        tornei_svizzeri = df_tornei_svizzeri["Torneo"].tolist()
        selected_tornei_svizzeri = st.multiselect("Seleziona tornei svizzeri da eliminare", options=tornei_svizzeri, key="del_svizzero_select")
        
        if selected_tornei_svizzeri:
            st.button("🗑️ Elimina Tornei Svizzeri selezionati", on_click=confirm_delete_torneo_svizzero, args=(selected_tornei_svizzeri,), key="del_svizzero_btn")
    else:
        st.info("Nessun torneo svizzero trovato.")
    st.markdown("</div>", unsafe_allow_html=True) # Chiudi contenitore tornei


elif st.session_state.edit_index is not None: # Logica di modifica/aggiunta giocatore
    st.header("Gestione Giocatori")
    if st.session_state.edit_index == -1:
        st.subheader("➕ Nuovo giocatore")
        default_giocatore = ""
        default_squadra = ""
        default_potenziale = 4
        default_ruolo = "R"
    else:
        st.subheader("✏️ Modifica giocatore")
        idx = st.session_state.edit_index
        default_giocatore = st.session_state.df_giocatori.at[idx, "Giocatore"]
        default_squadra = st.session_state.df_giocatori.at[idx, "Squadra"]
        default_potenziale = st.session_state.df_giocatori.at[idx, "Potenziale"]
        default_ruolo = st.session_state.df_giocatori.at[idx, "Ruolo"]

    # Usa st.form per evitare rerun ad ogni modifica degli input
    with st.form(key="form_giocatore"):
        giocatore = st.text_input("Nome Giocatore", value=default_giocatore, key="giocatore_input")
        squadra = st.text_input("Squadra", value=default_squadra, key="squadra_input")
        potenziale = st.slider("Potenziale", 1, 10, default_potenziale, key="potenziale_input")
        # Get valid role or default to 'R' if invalid
        valid_roles = ["R", "W", "A"]
        default_role = default_ruolo if pd.notna(default_ruolo) and str(default_ruolo).strip() in valid_roles else "R"
        
        # Only show role selector for admins
        if is_admin:
            ruolo = st.selectbox(
                "Ruolo", 
                options=valid_roles, 
                format_func=lambda x: {"R": "Reader (sola lettura)", "W": "Writer (lettura/scrittura)", "A": "Amministratore"}[x],
                index=valid_roles.index(default_role),
                key="ruolo_input"
            )
        else:
            # Non-admin users see the role as read-only text
            ruolo = default_role
            ruolo_display = {"R": "Reader (sola lettura)", "W": "Writer (lettura/scrittura)", "A": "Amministratore"}.get(default_role, "Reader (sola lettura)")
            st.text_input("Ruolo", value=ruolo_display, disabled=True)

        col_save, col_cancel = st.columns(2)
        with col_save:
            if is_guest:
                submitted = st.form_submit_button("✅ Salva", disabled=True, help="La modifica non è permessa agli ospiti")
            else:
                submitted = st.form_submit_button("✅ Salva")
        with col_cancel:
            cancelled = st.form_submit_button("❌ Annulla")

    # Azioni post-form (fuori dal form per evitare problemi)
    if submitted and not is_guest:
        save_player(giocatore, squadra, potenziale, ruolo)
    if cancelled:
        st.session_state.edit_index = None
        st.rerun()

    if st.session_state.edit_index != -1:  # Only show in edit mode, not in add mode
        if is_admin:
            if st.button("🔑 Reset Password", help="Resetta la password dell'utente e imposta SetPwd a 0"):
                idx = st.session_state.edit_index
                giocatore = st.session_state.df_giocatori.iloc[idx]["Giocatore"]
                
                # Salva i vecchi valori per il log
                vecchio_setpwd = st.session_state.df_giocatori.at[idx, "SetPwd"] if "SetPwd" in st.session_state.df_giocatori.columns else 0
                
                # Esegui il reset
                st.session_state.df_giocatori.at[idx, "Password"] = None
                # Assicurati che la colonna SetPwd esista
                if "SetPwd" not in st.session_state.df_giocatori.columns:
                    st.session_state.df_giocatori["SetPwd"] = 0
                st.session_state.df_giocatori.at[idx, "SetPwd"] = 0
                salva_dati_su_mongo(st.session_state.df_giocatori)
                
                # Log dell'azione
                username = st.session_state.get('user', {}).get('username', 'sconosciuto')
                log.log_action(
                    username=username,
                    action="reset_password",
                    torneo="gestione_giocatori",
                    details={
                        "tipo_operazione": "reset_password",
                        "giocatore": giocatore,
                        "vecchi_valori": {
                            "SetPwd": vecchio_setpwd
                        },
                        "nuovi_valori": {
                            "SetPwd": 0,
                            "Password": "Resettata"
                        }
                    }
                )
                
                st.toast("🔑 Password resettata con successo!")
                st.rerun()
        else:
            st.warning("Solo l'amministratore può resettare le password")

elif st.session_state.confirm_delete["type"] is not None:
    # Confirmation and password logic for deletions
    deletion_type = st.session_state.confirm_delete["type"]

    if deletion_type == "player":
        _, selected_player = st.session_state.confirm_delete["data"]
        st.warning(f"Sei sicuro di voler eliminare il giocatore '{selected_player}'?")
    elif deletion_type == "tornei_ita":
        st.warning("Sei sicuro di voler eliminare i tornei all'italiana selezionati?")
    elif deletion_type == "tornei_svizz":
        st.warning("Sei sicuro di voler eliminare i tornei svizzeri selezionati?")
    elif deletion_type == "all_ita":
        st.warning("Sei sicuro di voler eliminare TUTTI i tornei all'italiana? I tornei che contengono la parola 'campionato' nel nome non verranno eliminati.")
    elif deletion_type == "all_svizz":
        st.warning("Sei sicuro di voler eliminare TUTTI i tornei svizzeri? I tornei che contengono la parola 'campionato' nel nome non verranno eliminati.")
    elif deletion_type == "all":
        st.warning("Sei sicuro di voler eliminare TUTTI i tornei? I tornei che contengono la parola 'campionato' nel nome non verranno eliminati.")

    col_confirm, col_cancel = st.columns(2)
    
    # Se è richiesta la password, mostra la finestra di dialogo
    if st.session_state.confirm_delete["password_required"]:
        # Mostra il pulsante di conferma che aprirà il campo password
        with col_confirm:
            if st.button("Conferma e procedi"):
                st.session_state.password_check["show"] = True
                st.session_state.password_check["type"] = deletion_type
                st.rerun()
        
        # Mostra il campo password solo se è stato cliccato Conferma
        if st.session_state.password_check.get("show", False):
            password = st.text_input("Inserisci la password per confermare", type="password")
            if st.button("Conferma Password"):
                process_deletion_with_password(password, st.session_state.password_check["type"], st.session_state.confirm_delete["data"])
    else:
        # Se non è richiesta la password, procedi direttamente con la conferma
        with col_confirm:
            if st.button("Conferma eliminazione"):
                # Esegui direttamente la cancellazione senza chiedere la password
                process_deletion_with_password("non_richiesta", deletion_type, st.session_state.confirm_delete["data"])
    
    # Pulsante Annulla (comune a entrambi i casi)
    with col_cancel:
        st.button("❌ Annulla", on_click=cancel_delete)

# Footer leggero
st.markdown("---")
st.caption("⚽ Subbuteo Tournament Manager •  Made by Legnaro72")
