import streamlit as st
from logging_utils import log_action

# Configurazione della pagina DEVE essere la PRIMA operazione Streamlit
st.set_page_config(
    page_title="Torneo Subbuteo Svizzero",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Solo DOPO si possono importare le altre dipendenze
import pandas as pd
from datetime import datetime
import io
from fpdf import FPDF
import numpy as np
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
import requests
import base64
import time
import urllib.parse
import os

# Import auth utilities
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
    setup_player_selection_mode, enable_session_keepalive
)


if not st.session_state.get('authenticated', False):
    auth.show_auth_screen(club="PierCrew")
    st.stop()

# Attiva il sistema di keep-alive per mantenere la sessione durante le partite
enable_session_keepalive()

HUB_URL = "https://farm-tornei-subbuteo-piercrew-all-db.streamlit.app/"

# Configurazione della pagina già impostata all'inizio

def reset_app_state():
    """Resetta lo stato dell'applicazione"""
    keys_to_reset = [
        "df_torneo", "df_squadre", "turno_attivo", "risultati_temp",
        "nuovo_torneo_step", "club_scelto", "giocatori_selezionati_db",
        "giocatori_ospiti", "giocatori_totali", "torneo_iniziato",
        "setup_mode", "torneo_finito", "edited_df_squadre",
        "gioc_info", "modalita_visualizzazione"
    ]
    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key]

# Inizializza lo stato della sessione
if st.session_state.get('sidebar_state_reset', False):
    reset_app_state()
    st.session_state['sidebar_state_reset'] = False

# Inizializza le variabili di stato per la gestione dei turni e visualizzazioni
if 'modalita_turni' not in st.session_state:
    st.session_state.modalita_turni = "illimitati"  # Valore predefinito
if 'max_turni' not in st.session_state:
    st.session_state.max_turni = None  # Valore predefinito
if 'mostra_classifica' not in st.session_state:
    st.session_state.mostra_classifica = False  # Controlla se mostrare la classifica
    
if st.session_state.get('rerun_needed', False):
    st.session_state.rerun_needed = False
    st.rerun()


# -------------------------
# Session state (inizializzazione e aggiornamento nome torneo)
# -------------------------
for key, default in {
    "df_torneo": pd.DataFrame(),
    "df_squadre": pd.DataFrame(),
    "turno_attivo": 0,
    "risultati_temp": {},
    "nuovo_torneo_step": 1,
    "club_scelto": "PierCrew",
    "giocatori_selezionati_db": [],
    "modalita_selezione_giocatori": "Checkbox singole",
    "giocatori_ospiti": [],
    "giocatori_totali": [],
    "torneo_iniziato": False,
    "setup_mode": None,
    "nome_torneo": "Torneo Subbuteo - Sistema Svizzero",
    "torneo_finito": False,
    "edited_df_squadre": pd.DataFrame(),
    "gioc_info": {},
    "modalita_visualizzazione": "Squadre",
    "bg_audio_disabled": False
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Aggiornamento del nome del torneo se è finito
if st.session_state.torneo_finito and not st.session_state.nome_torneo.startswith("finito_"):
    st.session_state.nome_torneo = f"finito_{st.session_state.nome_torneo}"
# -------------------------


# ==============================================================================
# DEFINIZIONE URL AUDIO PERSISTENTE
# ==============================================================================
BACKGROUND_AUDIO_URL = "https://raw.githubusercontent.com/legnaro72/torneo-Subbuteo-webapp/main/Appenzeller%20Jodler.mp3"
# ==============================================================================


# -------------------------
# CSS personalizzato
# -------------------------
st.markdown("""
</style>
""", unsafe_allow_html=True)

# Inietta tutti gli stili dal modulo condiviso
inject_all_styles()

# -------------------------
# Connessione a MongoDB Atlas
# -------------------------
from common.db_utils import check_internet_connection as _check_internet

players_collection = None
tournaments_collection = None

if not _check_internet():
    st.sidebar.error("❌ Nessuna connessione Internet rilevata. Verifica la tua connessione e riprova.")
else:
    # Usa @st.cache_resource per evitare di ricreare il client ad ogni rerun
    @st.cache_resource
    def _get_svizzero_client(uri):
        """Crea e cache il client MongoDB per il torneo svizzero."""
        return MongoClient(uri, 
                          server_api=ServerApi('1'),
                          connectTimeoutMS=5000,
                          socketTimeoutMS=5000,
                          serverSelectionTimeoutMS=5000)
    
    try:
        MONGO_URI = st.secrets.get("MONGO_URI")
        if not MONGO_URI:
            st.sidebar.warning("⚠️ Chiave MONGO_URI non trovata nei segreti di Streamlit.")
        else:
            client = _get_svizzero_client(MONGO_URI)
            
            # Test connessione (leggero)
            client.admin.command('ping')
            
            # Connessione per i giocatori
            db_players = client.get_database("giocatori_subbuteo")
            players_collection = db_players.get_collection("piercrew_players")

            # Connessione per i tornei
            db_tournaments = client.get_database("TorneiSubbuteo")
            tournaments_collection = db_tournaments.get_collection("PierCrewSvizzero")
            
    except Exception as e:
        st.sidebar.error(f"❌ Errore di connessione a MongoDB: {e}")
        st.sidebar.warning("""
        **Risoluzione problemi:**
        1. Verifica la tua connessione Internet
        2. Controlla il file .streamlit/secrets.toml
        3. Assicurati che l'IP sia nella whitelist di MongoDB Atlas
        4. Controlla che il tuo account MongoDB Atlas sia attivo
        
        L'applicazione funzionerà in modalità offline con funzionalità limitate.
        """)

# ==============================================================================
# Le funzioni audio sono ora importate da common.audio
# Avvio audio di sottofondo
start_background_audio(BACKGROUND_AUDIO_URL)

    
def salva_torneo_su_db(action_type="salvataggio", details=None):
    """
    Salva o aggiorna lo stato del torneo su MongoDB.
    
    Args:
        action_type: Tipo di azione da registrare (es. 'salvataggio', 'modifica', 'validazione')
        details: Dettagli aggiuntivi da registrare (opzionale)
    """
    if not verify_write_access():
        st.error("⛔ Accesso in sola lettura. Non è possibile salvare le modifiche.")
        return False
        
    if tournaments_collection is None:
        st.error("❌ Connessione a MongoDB non attiva, impossibile salvare.")
        return False
    
    # Ottieni il nome utente corrente o 'sconosciuto' se non disponibile
    current_user = st.session_state.get('user', {}).get('username', 'sconosciuto')
    
    # Verifica se abbiamo già un ID torneo valido nella sessione
    if 'tournament_id' in st.session_state and st.session_state.tournament_id:
        try:
            # Verifica se il torneo esiste ancora nel database
            existing = tournaments_collection.find_one({"_id": ObjectId(st.session_state.tournament_id)})
            if not existing:
                # Se il torneo non esiste più, rimuoviamo l'ID dalla sessione
                del st.session_state.tournament_id
                # Log dell'errore
                log_action(
                    username=current_user,
                    action="errore_salvataggio",
                    torneo=st.session_state.get('nome_torneo', 'sconosciuto'),
                    details={"errore": "Torneo non trovato nel database"}
                )
        except Exception as e:
            # In caso di errore (es. ID non valido), rimuoviamo l'ID dalla sessione
            del st.session_state.tournament_id
            # Log dell'errore
            log_action(
                username=current_user,
                action="errore_salvataggio",
                torneo=st.session_state.get('nome_torneo', 'sconosciuto'),
                details={"errore": str(e)}
            )

    # Crea una copia del dataframe per la serializzazione
    df_torneo_to_save = st.session_state.df_torneo.copy()
    
    # ----------------------------------------------------
    # NEW PATCH 1: Validazione 0-0 automatica per RIPOSA
    # ----------------------------------------------------
    
    # Trova le righe in cui una delle due squadre è 'RIPOSA'
    riposo_mask = (df_torneo_to_save['Casa'] == 'RIPOSA') | (df_torneo_to_save['Ospite'] == 'RIPOSA')

    # Applica 0-0 e valida tutte le partite di riposo
    if riposo_mask.any():
        df_torneo_to_save.loc[riposo_mask, 'GolCasa'] = 0
        df_torneo_to_save.loc[riposo_mask, 'GolOspite'] = 0
        df_torneo_to_save.loc[riposo_mask, 'Validata'] = True
        
    # ----------------------------------------------------
    
    # Assicurati che la colonna 'Validata' esista e sia booleana
    if 'Validata' not in df_torneo_to_save.columns:
        df_torneo_to_save['Validata'] = False
    df_torneo_to_save['Validata'] = df_torneo_to_save['Validata'].astype(bool)
    
    # Assicurati che le colonne dei goal siano intere
    if 'GolCasa' in df_torneo_to_save.columns:
        df_torneo_to_save['GolCasa'] = df_torneo_to_save['GolCasa'].fillna(0).astype(int)
    if 'GolOspite' in df_torneo_to_save.columns:
        df_torneo_to_save['GolOspite'] = df_torneo_to_save['GolOspite'].fillna(0).astype(int)

    torneo_data = {
        "nome_torneo": st.session_state.nome_torneo,
        "data_salvataggio": datetime.now(),
        "df_torneo": df_torneo_to_save.to_dict('records'),
        "df_squadre": st.session_state.df_squadre.to_dict('records'),
        "turno_attivo": st.session_state.turno_attivo,
        "torneo_iniziato": st.session_state.torneo_iniziato,
        "torneo_finito": st.session_state.get('torneo_finito', False),
        "modalita_turni": st.session_state.get('modalita_turni', 'illimitati'),
        "max_turni": st.session_state.get('max_turni'),
    }

    try:
        # Prepara i dettagli del log
        log_details = {
            "tipo_operazione": "aggiornamento" if 'tournament_id' in st.session_state and st.session_state.tournament_id else "creazione",
            "turno_corrente": st.session_state.get('turno_attivo', 0),
            **({} if details is None else details)
        }
        
        # Se abbiamo un ID torneo nella sessione, aggiorniamo quel documento specifico
        if 'tournament_id' in st.session_state and st.session_state.tournament_id:
            tournaments_collection.update_one(
                {"_id": ObjectId(st.session_state.tournament_id)},
                {"$set": torneo_data}
            )
            log_action(
                username=current_user,
                action=action_type,
                torneo=st.session_state.nome_torneo,
                details=log_details
            )
            pass #st.toast(f"✅ Torneo '{st.session_state.nome_torneo}' aggiornato con successo!")
        else:
            # Altrimenti cerchiamo un torneo esistente con lo stesso nome
            existing_doc = tournaments_collection.find_one({"nome_torneo": st.session_state.nome_torneo})
            
            if existing_doc:
                # Aggiorna il documento esistente e salva l'ID nella sessione
                tournaments_collection.update_one(
                    {"_id": existing_doc["_id"]},
                    {"$set": torneo_data}
                )
                st.session_state.tournament_id = str(existing_doc["_id"])
                log_action(
                    username=current_user,
                    action=action_type,
                    torneo=st.session_state.nome_torneo,
                    details={"tipo_operazione": "aggiornamento_esistente", **log_details}
                )
                st.toast(f"✅ Torneo esistente '{st.session_state.nome_torneo}' aggiornato con successo!")
            else:
                # Crea un nuovo documento e salva l'ID nella sessione
                result = tournaments_collection.insert_one(torneo_data)
                st.session_state.tournament_id = str(result.inserted_id)
                log_action(
                    username=current_user,
                    action=action_type,
                    torneo=st.session_state.nome_torneo,
                    details={"tipo_operazione": "creazione", **log_details}
                )
                st.toast(f"✅ Nuovo torneo '{st.session_state.nome_torneo}' salvato con successo!")
        return True
    except Exception as e:
        st.error(f"❌ Errore durante il salvataggio del torneo: {e}")



@st.cache_data(ttl=300)  # Cache per 5 minuti
def carica_nomi_tornei_da_db():
    """Carica i nomi dei tornei disponibili dal DB."""
    if tournaments_collection is None:
        return []
    try:
        # Usiamo distinct per ottenere direttamente la lista dei nomi senza duplicati
        return sorted(tournaments_collection.distinct("nome_torneo"))
    except Exception as e:
        st.error(f"❌ Errore caricamento tornei: {e}")
        return []

def carica_torneo_da_db(nome_torneo):
    """Carica un singolo torneo dal DB e lo ripristina nello stato della sessione."""
    if tournaments_collection is None:
        st.error("❌ Connessione a MongoDB non disponibile.")
        return False
        
    try:
        # Cerca il torneo per nome
        torneo = tournaments_collection.find_one({"nome_torneo": nome_torneo})
        if not torneo:
            st.error(f"❌ Nessun torneo trovato con il nome '{nome_torneo}'")
            return False
            
        # Ripristina lo stato della sessione
        st.session_state.df_torneo = pd.DataFrame(torneo['df_torneo'])
        st.session_state.df_squadre = pd.DataFrame(torneo['df_squadre'])
        st.session_state.turno_attivo = torneo['turno_attivo']
        st.session_state.torneo_iniziato = torneo['torneo_iniziato']
        st.session_state.torneo_finito = torneo.get('torneo_finito', False)
        st.session_state.tournament_id = str(torneo['_id'])
        
        # Ripristina le impostazioni dei turni
        st.session_state.modalita_turni = torneo.get('modalita_turni', 'illimitati')
        st.session_state.max_turni = torneo.get('max_turni')
        
        # Inizializza i risultati temporanei per tutte le partite del turno corrente
        if 'risultati_temp' not in st.session_state:
            st.session_state.risultati_temp = {}
            
        # Carica i risultati delle partite del turno corrente
        df_turno_corrente = st.session_state.df_torneo[st.session_state.df_torneo['Turno'] == st.session_state.turno_attivo]
        for _, row in df_turno_corrente.iterrows():
            key_gc = f"gc_{st.session_state.turno_attivo}_{row['Casa']}_{row['Ospite']}"
            key_go = f"go_{st.session_state.turno_attivo}_{row['Casa']}_{row['Ospite']}"
            key_val = f"val_{st.session_state.turno_attivo}_{row['Casa']}_{row['Ospite']}"
            
            st.session_state.risultati_temp[key_gc] = int(row.get('GolCasa', 0))
            st.session_state.risultati_temp[key_go] = int(row.get('GolOspite', 0))
            st.session_state.risultati_temp[key_val] = bool(row.get('Validata', False))
        
        # Assicurati che le colonne necessarie esistano e siano del tipo corretto
        # Assicurati che le colonne necessarie esistano prima di accedere
        for col in ['GolCasa', 'GolOspite', 'Validata']:
            if col not in st.session_state.df_torneo.columns:
                st.session_state.df_torneo[col] = 0 if col.startswith('Gol') else False
                
        # Converti esplicitamente i tipi di dati in modo più sicuro
        st.session_state.df_torneo['GolCasa'] = st.session_state.df_torneo['GolCasa'].fillna(0).astype(int)
        st.session_state.df_torneo['GolOspite'] = st.session_state.df_torneo['GolOspite'].fillna(0).astype(int)
        
        # Gestione robusta del flag 'Validata' per ogni riga
        st.session_state.df_torneo['Validata'] = st.session_state.df_torneo['Validata'].apply(lambda x: bool(x) if x is not None else False)
        
        # Inizializza i risultati temporanei
        init_results_temp_from_df(st.session_state.df_torneo)
        # MODIFICA: Salvataggio immediato dopo generazione calendario
        salva_torneo_su_db(action_type="creazione_torneo_generato", details={"turno_generato": 1})
        return True
        
    except Exception as e:
        st.error(f"❌ Errore durante il caricamento del torneo: {str(e)}")
        return False
        
@st.cache_data(ttl=60)
def carica_giocatori_da_db():
    """Carica giocatori dal DB (cached per 60 secondi per fluidità)."""
    if 'players_collection' in globals() and players_collection is not None:
        try:
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
    return pd.DataFrame()

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
        
        # 🛡️ Logo "PierCrew" a sinistra
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
        
        # 🏆 Sottotitolo (Nome del torneo - SVIZZERO)
        self.set_x(start_x)
        self.set_font("Arial", 'I', 11)
        self.set_text_color(220, 225, 235)
        data_stampa = datetime.now().strftime("%d/%m/%Y alle %H:%M")
        self.cell(0, 6, f"Referto Ufficiale: {self.nome_torneo} (Svizzero) | Aggiornato il {data_stampa}", border=0, ln=1, align='L')
        
        self.ln(12)

    def footer(self):
        self.set_y(-15)
        self.set_fill_color(26, 54, 93)  
        self.rect(0, 287, 210, 10, 'F')
        self.set_font('Arial', 'B', 8)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, f'Pagina {self.page_no()} - Generato automaticamente dal Gestionale Tornei Subbuteo', 0, 0, 'C')

def esporta_pdf(df_torneo, nome_torneo):
    try:
        pdf = GazzettaPDF(nome_torneo, orientation='P', unit='mm', format='A4')
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.add_page()
        
        # ======= 📊 SEZIONE CLASSIFICA =======
        classifica_df = aggiorna_classifica(df_torneo)
        if hasattr(classifica_df, "empty") and not classifica_df.empty:
            pdf.set_font("Arial", 'B', 16)
            pdf.set_fill_color(230, 235, 245)
            pdf.set_text_color(26, 54, 93)
            pdf.cell(0, 10, " CLASSIFICA SVIZZA GENERALE ", border=1, ln=True, fill=True, align='C')
            pdf.ln(3)
            
            # Header
            pdf.set_font("Arial", 'B', 11)
            pdf.set_fill_color(26, 54, 93)
            pdf.set_text_color(255, 255, 255)
            header = ['Pos', 'Squadra/Giocatore', 'PTI', 'G', 'V', 'N', 'P', 'GF', 'GS', 'DR']
            col_widths = [10, 65, 15, 10, 10, 10, 10, 10, 10, 15]
            
            for i, h in enumerate(header):
                pdf.cell(col_widths[i], 8, h, border=1, align='C', fill=True)
            pdf.ln()

            # Righe Classifica
            pdf.set_font("Arial", "", 10)
            pdf.set_text_color(0, 0, 0)
            for idx, (_, row) in enumerate(classifica_df.iterrows(), 1):
                fill = (idx % 2 == 0)
                pdf.set_fill_color(245, 248, 250) if fill else pdf.set_fill_color(255, 255, 255)
                
                sq = str(row['Squadra']).encode("latin-1", "ignore").decode("latin-1")
                if len(sq) > 30: sq = sq[:28] + "..."
                
                pdf.cell(col_widths[0], 7, str(idx), border='LR', align='C', fill=fill)
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(col_widths[1], 7, " " + sq, border='LR', align='L', fill=fill)
                pdf.set_font("Arial", "", 10)
                pdf.cell(col_widths[2], 7, str(row.get('Punti', row.get('PTI', ''))), border='LR', align='C', fill=fill)
                pdf.cell(col_widths[3], 7, str(row.get('G', row.get('Partite', ''))), border='LR', align='C', fill=fill)
                pdf.cell(col_widths[4], 7, str(row['Vittorie'] if 'Vittorie' in row else row.get('V', '')), border='LR', align='C', fill=fill)
                pdf.cell(col_widths[5], 7, str(row['Pareggi'] if 'Pareggi' in row else row.get('N', '')), border='LR', align='C', fill=fill)
                pdf.cell(col_widths[6], 7, str(row['Sconfitte'] if 'Sconfitte' in row else row.get('P', '')), border='LR', align='C', fill=fill)
                pdf.cell(col_widths[7], 7, str(row.get('GolFatti', row.get('GF', ''))), border='LR', align='C', fill=fill)
                pdf.cell(col_widths[8], 7, str(row.get('GolSubiti', row.get('GS', ''))), border='LR', align='C', fill=fill)
                pdf.cell(col_widths[9], 7, str(row.get('DifferenzaReti', row.get('DR', ''))), border='LR', align='C', fill=fill)
                pdf.ln()
                
            pdf.cell(sum(col_widths), 0, '', border='T', ln=True)
            pdf.ln(10)

        # ======= 🗓️ SEZIONE PARTITE =======
        turno_corrente = None
        for _, r in df_torneo.sort_values(by="Turno").iterrows():
            if turno_corrente != r["Turno"]:
                turno_corrente = r["Turno"]
                
                if pdf.get_y() > 250:
                    pdf.add_page()
                else:
                    pdf.ln(5)
                    
                pdf.set_font("Arial", 'B', 12)
                pdf.set_fill_color(230, 235, 245)
                pdf.set_text_color(26, 54, 93)
                pdf.cell(0, 8, f" Turno {turno_corrente} ", ln=True, fill=True)
                
                pdf.set_font("Arial", 'B', 10)
                pdf.set_fill_color(240, 240, 240)
                pdf.set_text_color(100, 100, 100)
                w_partite = [75, 40, 75]
                pdf.cell(w_partite[0], 6, "Casa", border=1, align='C', fill=True)
                pdf.cell(w_partite[1], 6, "Risultato", border=1, align='C', fill=True)
                pdf.cell(w_partite[2], 6, "Ospite", border=1, align='C', fill=True)
                pdf.ln()

            if pdf.get_y() > 275:
                pdf.add_page()

            def safe_val(v, default=""):
                if isinstance(v, pd.Series): v = v.iloc[0] if not v.empty else default
                if isinstance(v, (list, tuple)): v = v[0] if len(v) > 0 else default
                try:
                    if pd.isna(v): return default
                except: pass
                s_v = str(v).strip()
                if s_v.lower() in ["none", "nan", "<na>", ""]: return default
                return s_v

            casa = safe_val(r.get("Casa"), "-").encode("latin-1", "ignore").decode("latin-1")
            osp = safe_val(r.get("Ospite"), "-").encode("latin-1", "ignore").decode("latin-1")
            
            if len(casa) > 35: casa = casa[:32] + "..."
            if len(osp) > 35: osp = osp[:32] + "..."
            
            valida = bool(r.get("Validata", False))
            
            gc_val = safe_val(r.get("GolCasa"))
            go_val = safe_val(r.get("GolOspite"))
            gc = str(int(float(gc_val))) if valida and gc_val.replace('.', '', 1).isdigit() else ""
            go = str(int(float(go_val))) if valida and go_val.replace('.', '', 1).isdigit() else ""
            
            res = f"{gc} - {go}" if valida else " - "
            
            pdf.set_fill_color(255, 255, 255)
            
            if valida: pdf.set_font("Arial", '', 10)
            else: pdf.set_font("Arial", 'I', 10)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(w_partite[0], 7, " " + casa, border='LR')
            
            pdf.set_font("Arial", 'B', 11)
            pdf.set_text_color(42, 157, 143) if valida else pdf.set_text_color(128, 128, 128)
            pdf.cell(w_partite[1], 7, res, border='L', align='C')
            
            if valida: pdf.set_font("Arial", '', 10)
            else: pdf.set_font("Arial", 'I', 10)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(w_partite[2], 7, " " + osp, border='LR', align='L')
            
            pdf.ln()
            pdf.cell(sum(w_partite), 0, '', border='T')
            pdf.set_xy(10, pdf.get_y()) # fix after zero height cell

        # Genera il PDF in memoria
        return bytes(pdf.output())
        
    except Exception as e:
        st.error(f"Errore durante la generazione del PDF: {str(e)}")
        return None


def calcola_punti_scontro_diretto(squadra1, squadra2, df):
    """Calcola i punti nello scontro diretto tra due squadre"""
    scontri = df[
        ((df['Casa'] == squadra1) & (df['Ospite'] == squadra2)) |
        ((df['Casa'] == squadra2) & (df['Ospite'] == squadra1))
    ]
    
    punti1 = punti2 = 0
    
    for _, r in scontri.iterrows():
        if not bool(r.get('Validata', False)):
            continue
            
        if r['Casa'] == squadra1:
            gc, go = int(r['GolCasa']), int(r['GolOspite'])
        else:
            go, gc = int(r['GolCasa']), int(r['GolOspite'])
            
        if gc > go:
            punti1 += 2
        elif go > gc:
            punti2 += 2
        else:
            punti1 += 1
            punti2 += 1
            
    return punti1, punti2

def aggiorna_classifica(df):
    # controlla che il df sia valido e abbia le colonne necessarie
    colonne_richieste = {"Casa", "Ospite", "GolCasa", "GolOspite", "Validata"}
    if not isinstance(df, pd.DataFrame) or not colonne_richieste.issubset(set(df.columns)):
        # restituisci classifica vuota se non ci sono ancora partite
        return pd.DataFrame(columns=[
            "Squadra", "Punti", "G", "V", "N", "P",
            "GF", "GS", "DR"
        ])

    stats = {}
    
    # Inizializza le statistiche per ogni squadra
    squadre = set(df['Casa'].unique()).union(set(df['Ospite'].unique()))
    for squadra in squadre:
        stats[squadra] = {'Punti': 0, 'GF': 0, 'GS': 0, 'DR': 0, 'G': 0, 'V': 0, 'N': 0, 'P': 0}
    
    # Calcola le statistiche di base
    for _, r in df.iterrows():
        if not bool(r.get('Validata', False)):
            continue
            
        casa, osp = r['Casa'], r['Ospite']
        gc, go = int(r['GolCasa']), int(r['GolOspite'])
        
        # Aggiorna statistiche generali
        stats[casa]['G'] += 1
        stats[osp]['G'] += 1
        stats[casa]['GF'] += gc
        stats[casa]['GS'] += go
        stats[osp]['GF'] += go
        stats[osp]['GS'] += gc
        
        # Aggiorna punteggi
        if gc > go:
            stats[casa]['Punti'] += 2
            stats[casa]['V'] += 1
            stats[osp]['P'] += 1
        elif gc < go:
            stats[osp]['Punti'] += 2
            stats[osp]['V'] += 1
            stats[casa]['P'] += 1
        else:
            stats[casa]['Punti'] += 1
            stats[osp]['Punti'] += 1
            stats[casa]['N'] += 1
            stats[osp]['N'] += 1
    
    # Calcola la differenza reti per ogni squadra
    for squadra in stats:
        stats[squadra]['DR'] = stats[squadra]['GF'] - stats[squadra]['GS']
    
    # Crea il DataFrame
    if not stats:
        return pd.DataFrame(columns=['Squadra', 'Punti', 'G', 'V', 'N', 'P', 'GF', 'GS', 'DR'])
    
    df_classifica = pd.DataFrame([(k, v['Punti'], v['G'], v['V'], v['N'], v['P'], v['GF'], v['GS'], v['DR']) 
                                for k, v in stats.items()],
                              columns=['Squadra', 'Punti', 'G', 'V', 'N', 'P', 'GF', 'GS', 'DR'])
                              

    # 🔥 Merge con potenziale delle squadre
    if "df_squadre" in st.session_state and not st.session_state.df_squadre.empty:
        df_classifica = df_classifica.merge(
            st.session_state.df_squadre[["Squadra", "Potenziale"]],
            on="Squadra",
            how="left"
        )

    # ----------------------------------------------------
    # NEW PATCH 2 & 3: Correzione Statistica e Nascondimento
    # ----------------------------------------------------
    
    # Correzione statistica per il riposo (Patch 3)
    # Troviamo le partite di riposo e le squadre coinvolte
    df_riposi = df[(df['Ospite'] == 'RIPOSA') | (df['Casa'] == 'RIPOSA')]
    riposi_count = {}

    # 1. Contiamo quante volte ogni squadra ha riposato
    for _, r in df_riposi.iterrows():
        # Identifica la squadra vera che ha riposato
        squadra_vera = r['Casa'] if r['Ospite'] == 'RIPOSA' else r['Ospite']
        riposi_count[squadra_vera] = riposi_count.get(squadra_vera, 0) + 1

    # 2. Applichiamo la correzione a tutte le squadre in classifica che hanno riposato
    # Sottraiamo 1 punto, 1 partita giocata (G), 1 pareggiata (N) per ogni riposo
    for idx in df_classifica.index:
        squadra = df_classifica.loc[idx, 'Squadra']
        num_riposi = riposi_count.get(squadra, 0)
        
        if num_riposi > 0:
            df_classifica.loc[idx, 'Punti'] -= num_riposi
            df_classifica.loc[idx, 'G'] -= num_riposi
            df_classifica.loc[idx, 'N'] -= num_riposi

    # 3. Nascondi la squadra fittizia "RIPOSA" dalla classifica (Patch 2)
    df_classifica = df_classifica[df_classifica['Squadra'] != 'RIPOSA'].reset_index(drop=True)

    # ----------------------------------------------------
    # Ordina usando una chiave personalizzata che include il confronto diretto
    def sort_key(row):
        # Crea una tupla con i criteri di ordinamento
        # 1. Punti (decrescente)
        # 2. Punti negli scontri diretti (se ci sono)
        # 3. Differenza reti (decrescente)
        # 4. Gol fatti (decrescente)
        # 5. Nome squadra (crescente)
        
        punti = -row['Punti']  # Moltiplicato per -1 per ordinamento decrescente
        dr = -row['DR']
        gf = -row['GF']
        squadra = row['Squadra'].lower()  # Converti in minuscolo per ordinamento case-insensitive
        
        # Calcola i punti negli scontri diretti con le squadre con gli stessi punti
        stesse_punti = df_classifica[df_classifica['Punti'] == row['Punti']]['Squadra'].tolist()
        if len(stesse_punti) > 1 and row['Squadra'] in stesse_punti:
            # Calcola la classifica parziale solo tra le squadre a pari punti
            punteggi_scontri = {}
            for s in stesse_punti:
                punteggi_scontri[s] = 0
                
            for i, s1 in enumerate(stesse_punti):
                for s2 in stesse_punti[i+1:]:
                    p1, p2 = calcola_punti_scontro_diretto(s1, s2, df)
                    punteggi_scontri[s1] += p1
                    punteggi_scontri[s2] += p2
            
            # Usa il punteggio negli scontri diretti come secondo criterio
            punti_scontri = -punteggi_scontri.get(row['Squadra'], 0)
        else:
            punti_scontri = 0
            
        # Aggiungi un log per debug
        # st.write(f"{row['Squadra']}: Punti={-punti}, Scontri={-punti_scontri}, DR={-dr}, GF={-gf}")
            
        return (punti, punti_scontri, dr, gf, squadra)
    
    # Applica l'ordinamento personalizzato
    indici_ordinati = sorted(df_classifica.index, key=lambda x: sort_key(df_classifica.loc[x]))
    df_classifica = df_classifica.loc[indici_ordinati].reset_index(drop=True)
    
    #return df_classifica
    # ----------------------------------------------------
    # NEW FIX 4: Applica e finalizza l'ordinamento per la stabilità
    # ----------------------------------------------------
    
    # Applica la chiave di ordinamento (sort_key) a tutte le righe
    df_classifica['sort_key'] = df_classifica.apply(sort_key, axis=1)
    
    # Ordina definitivamente il DataFrame in base alla chiave e rimuovi la colonna temporanea
    df_classifica = df_classifica.sort_values(by='sort_key').drop(columns=['sort_key']).reset_index(drop=True)
    
    return df_classifica

#inizio
# ==============================
# NUOVA FUNZIONE: controllo fine torneo
# ==============================
def controlla_fine_torneo():
    """Controlla se il torneo deve terminare automaticamente."""
    if st.session_state.get("torneo_finito", False):
        return True

    # Caso turni fissi
    if st.session_state.modalita_turni == "fisso":
        if st.session_state.turno_attivo >= st.session_state.max_turni:
            st.session_state.torneo_finito = True
            return True

    # Caso illimitato o numero massimo di turni superiore alle possibili combinazioni
    if "df_torneo" in st.session_state and not st.session_state.df_torneo.empty:
        classifica_corrente = aggiorna_classifica(st.session_state.df_torneo)
        precedenti = set(
            tuple(sorted([row["Casa"], row["Ospite"]]))
            for _, row in st.session_state.df_torneo.iterrows()
        )
        nuovi_accoppiamenti = genera_accoppiamenti(classifica_corrente, precedenti)
        if nuovi_accoppiamenti is None or nuovi_accoppiamenti.empty:
            st.session_state.torneo_finito = True
            return True

    return False
#inizio genera
def genera_accoppiamenti(classifica, precedenti, primo_turno=False):
    import random
    turno_attuale = st.session_state.get("turno_attivo", 1)

    # --- Calcola il numero di turni che usano il potenziale ---
    num_squadre = len(st.session_state.df_squadre)
    
    if st.session_state.modalita_turni == "fisso" and st.session_state.max_turni is not None:
        # Se è impostato un limite di turni, usa il potenziale per metà dei turni (arrotondato per eccesso)
        turni_con_potenziale = (st.session_state.max_turni + 1) // 2
    else:
        # Se non c'è limite, usa il potenziale per metà delle squadre (arrotondato per eccesso)
        turni_con_potenziale = (num_squadre + 1) // 2
    
    # --- Ordinamento ---
    if turno_attuale <= turni_con_potenziale:
        # Ordinamento per Potenziale (discendente)
        classifica = st.session_state.df_squadre.copy()
        classifica = classifica.sort_values(by="Potenziale", ascending=False).reset_index(drop=True)
    else:
        # Dopo i turni con potenziale: per Classifica aggiornata
        classifica = aggiorna_classifica(st.session_state.df_torneo)

    squadre = classifica["Squadra"].tolist()
    riposa = None

    # --- Gestione riposo ---
    if len(squadre) % 2 != 0:
        # Squadre che hanno già riposato
        gia_riposo = set()
        if (
            "df_torneo" in st.session_state
            and not st.session_state.df_torneo.empty
            and "Ospite" in st.session_state.df_torneo.columns
        ):
            gia_riposo = set(
                st.session_state.df_torneo.loc[
                    st.session_state.df_torneo["Ospite"] == "RIPOSA", "Casa"
                ]
            )

        # Candidati = squadre che non hanno ancora riposato
        candidati = [s for s in squadre if s not in gia_riposo]

        if not candidati:
            st.error("⚠️ Tutte le squadre hanno già riposato!")
            return None

        # 💤 Scelta: squadra con POTENZIALE più basso
        df_candidati = classifica[classifica["Squadra"].isin(candidati)]
        riposa = df_candidati.sort_values(by="Potenziale", ascending=True).iloc[0]["Squadra"]

        squadre.remove(riposa)

    # --- Algoritmo backtracking per formare coppie ---
    def backtrack(da_accoppiare, accoppiamenti):
        if not da_accoppiare:
            return accoppiamenti
        s1 = da_accoppiare[0]
        for i, s2 in enumerate(da_accoppiare[1:], 1):
            if (s1, s2) in precedenti or (s2, s1) in precedenti:
                continue
            nuovi_accoppiamenti = accoppiamenti + [(s1, s2)]
            nuove_rimanenti = [x for j, x in enumerate(da_accoppiare) if j not in (0, i)]
            risultato = backtrack(nuove_rimanenti, nuovi_accoppiamenti)
            if risultato is not None:
                return risultato
        return None

    accoppiamenti = backtrack(squadre, [])

    # fallback: shuffle
    if accoppiamenti is None:
        random.shuffle(squadre)
        accoppiamenti = []
        for i in range(0, len(squadre), 2):
            if i + 1 < len(squadre):
                if (squadre[i], squadre[i+1]) not in precedenti and (squadre[i+1], squadre[i]) not in precedenti:
                    accoppiamenti.append((squadre[i], squadre[i+1]))

    if not accoppiamenti and not riposa:
        st.error("⚠️ Non è stato possibile generare accoppiamenti validi!")
        return None

    # --- Costruzione DataFrame ---
    df = pd.DataFrame(
        [{"Casa": c, "Ospite": o, "GolCasa": 0, "GolOspite": 0, "Validata": False} for c, o in accoppiamenti]
    )

    if riposa:
        df = pd.concat(
            [df, pd.DataFrame([{"Casa": riposa, "Ospite": "RIPOSA", "GolCasa": 0, "GolOspite": 0, "Validata": True}])],
            ignore_index=True,
        )

    df["Turno"] = turno_attuale
    return df


#fine genera


    import random

    turno_attuale = st.session_state.get("turno_attivo", 1)

    # --- Ordinamento dinamico in base al turno ---
    if turno_attuale == 1 or turno_attuale == 2:
        # Usa SOLO il potenziale
        classifica = classifica.copy()
        classifica["Potenziale"] = pd.to_numeric(
            classifica["Potenziale"], errors="coerce"
        ).fillna(0)
        classifica = classifica.sort_values(
            by="Potenziale", ascending=False
        ).reset_index(drop=True)

    elif turno_attuale in (3, 4):
        # Media 50% potenziale + 50% posizione classifica
        classifica_corrente = aggiorna_classifica(st.session_state.df_torneo)
        classifica = classifica_corrente.merge(
            st.session_state.df_squadre[["Squadra", "Potenziale"]],
            on="Squadra",
            how="left"
        )
        classifica["Posizione"] = classifica.reset_index().index + 1
        classifica["MixScore"] = (
            classifica["Potenziale"].rank(ascending=False) * 0.5 +
            classifica["Posizione"] * 0.5
        )
        classifica = classifica.sort_values(
            by="MixScore", ascending=True
        ).reset_index(drop=True)

    else:
        # Dal 5° turno in poi: SOLO posizione in classifica
        classifica = aggiorna_classifica(st.session_state.df_torneo)


    squadre = classifica["Squadra"].tolist()

    riposa = None
  
    if len(squadre) % 2 != 0:
        gia_riposo = set()
        # ✅ Controllo robusto: esegui solo se df_torneo non è vuoto e contiene le colonne
        if (
            "df_torneo" in st.session_state 
            and not st.session_state.df_torneo.empty 
            and "Ospite" in st.session_state.df_torneo.columns
        ):
            gia_riposo = set(
                st.session_state.df_torneo.loc[
                    st.session_state.df_torneo["Ospite"] == "RIPOSA", "Casa"
                ]
            )

        # ✅ Candidati = squadre che non hanno ancora riposato
        candidati = [s for s in squadre if s not in gia_riposo]

        # ✅ Candidati = squadre che non hanno ancora riposato
        candidati = [s for s in squadre if s not in gia_riposo]

        if not candidati:
            st.error("⚠️ Tutte le squadre hanno già riposato, impossibile assegnare nuovo riposo!")
            return None

        # 🔄 Scelta casuale fra i candidati (puoi usare candidati[0] per ordine fisso)
        riposa = random.choice(candidati)
        squadre.remove(riposa)

    # 🔗 Algoritmo di backtracking per formare coppie valide
    def backtrack(da_accoppiare, accoppiamenti):
        if not da_accoppiare:
            return accoppiamenti
        s1 = da_accoppiare[0]
        for i, s2 in enumerate(da_accoppiare[1:], 1):
            if (s1, s2) in precedenti or (s2, s1) in precedenti:
                continue
            nuovi_accoppiamenti = accoppiamenti + [(s1, s2)]
            nuove_rimanenti = [
                x for j, x in enumerate(da_accoppiare) if j not in (0, i)
            ]
            risultato = backtrack(nuove_rimanenti, nuovi_accoppiamenti)
            if risultato is not None:
                return risultato
        return None

    accoppiamenti = backtrack(squadre, [])

    # fallback se il backtracking non trova nulla
    # La lista 'squadre' qui è ordinata per classifica (Svizzero "stretto")
    squadre_strette = squadre.copy() 
    accoppiamenti = backtrack(squadre_strette, []) 

    # -----------------------------------
    # INIZIO MODIFICA: LOGICA PERMISSIVA (FALLBACK)
    # -----------------------------------
    # Se l'accoppiamento "stretto" basato sul punteggio non trova soluzioni...
    if accoppiamenti is None:
        st.warning("🔄 Tentativo di accoppiamento stretto (per punteggio) fallito. Riprovo in modalità permissiva.")
        
        # PASS 2: Modalità Permissiva - Mischiamo la lista per eliminare il vincolo sul punteggio.
        # Manteniamo SOLO il vincolo di non-ripetizione (gestito da backtrack).
        squadre_permissive = squadre.copy()
        random.shuffle(squadre_permissive)
        
        # Riprova il backtracking sul nuovo ordine casuale
        accoppiamenti = backtrack(squadre_permissive, [])

    # -----------------------------------
    # FINE MODIFICA: LOGICA PERMISSIVA (FALLBACK)
    # -----------------------------------

    # Il codice prosegue qui con l'assegnazione dell'errore finale
    if accoppiamenti is None and not riposa:
        st.error("⚠️ Non è stato possibile generare accoppiamenti validi anche in modalità permissiva!")
        return None
    if not accoppiamenti and not riposa:
        st.error("⚠️ Non è stato possibile generare accoppiamenti validi!")
        return None

    # Costruisci il DataFrame degli accoppiamenti
    df = pd.DataFrame(
        [
            {"Casa": c, "Ospite": o, "GolCasa": 0, "GolOspite": 0, "Validata": False}
            for c, o in accoppiamenti
        ]
    )

    if riposa:
        df = pd.concat(
            [
                df,
                pd.DataFrame(
                    [
                        {
                            "Casa": riposa,
                            "Ospite": "RIPOSA",
                            "GolCasa": 0,
                            "GolOspite": 0,
                            "Validata": True,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

    # 🔥 Aggiungi la colonna Turno
    df["Turno"] = st.session_state.turno_attivo

    return df

    import random

    # Ordinamento iniziale: per potenziale al primo turno,
    # altrimenti per classifica aggiornata
    if primo_turno:
        classifica = classifica.copy()
        classifica["Potenziale"] = pd.to_numeric(
            classifica["Potenziale"], errors="coerce"
        ).fillna(0)
        classifica = classifica.sort_values(
            by="Potenziale", ascending=False
        ).reset_index(drop=True)
    else:
        classifica = aggiorna_classifica(st.session_state.df_torneo)

    squadre = classifica["Squadra"].tolist()

    riposa = None
    if len(squadre) % 2 != 0:
        # 🔎 Controlla chi ha già riposato
        gia_riposo = set(
            st.session_state.df_torneo.loc[
                st.session_state.df_torneo["Ospite"] == "RIPOSA", "Casa"
            ]
        )
        # ✅ Candidati = squadre che non hanno ancora riposato
        candidati = [s for s in squadre if s not in gia_riposo]

        if not candidati:
            st.error("⚠️ Tutte le squadre hanno già riposato, impossibile assegnare nuovo riposo!")
            return None

        # 🔄 Scelta casuale fra i candidati (puoi usare candidati[0] per ordine fisso)
        riposa = random.choice(candidati)
        squadre.remove(riposa)

    # 🔗 Algoritmo di backtracking per formare coppie valide
    def backtrack(da_accoppiare, accoppiamenti):
        if not da_accoppiare:
            return accoppiamenti
        s1 = da_accoppiare[0]
        for i, s2 in enumerate(da_accoppiare[1:], 1):
            if (s1, s2) in precedenti or (s2, s1) in precedenti:
                continue
            nuovi_accoppiamenti = accoppiamenti + [(s1, s2)]
            nuove_rimanenti = [
                x for j, x in enumerate(da_accoppiare) if j not in (0, i)
            ]
            risultato = backtrack(nuove_rimanenti, nuovi_accoppiamenti)
            if risultato is not None:
                return risultato
        return None

    accoppiamenti = backtrack(squadre, [])

    # fallback se il backtracking non trova nulla
    if accoppiamenti is None:
        # fallback casuale: mescola le squadre e accoppiale
        random.shuffle(squadre)
        accoppiamenti = []
        for i in range(0, len(squadre), 2):
            if i + 1 < len(squadre):
                if (squadre[i], squadre[i + 1]) not in precedenti and (
                    squadre[i + 1], squadre[i]
                ) not in precedenti:
                    accoppiamenti.append((squadre[i], squadre[i + 1]))

    if not accoppiamenti and not riposa:
        st.error("⚠️ Non è stato possibile generare accoppiamenti validi!")
        return None

    # Costruisci il DataFrame degli accoppiamenti
    df = pd.DataFrame(
        [
            {"Casa": c, "Ospite": o, "GolCasa": 0, "GolOspite": 0, "Validata": False}
            for c, o in accoppiamenti
        ]
    )

    # Aggiungi il riposo se previsto
    if riposa:
        df = pd.concat(
            [
                df,
                pd.DataFrame(
                    [
                        {
                            "Casa": riposa,
                            "Ospite": "RIPOSA",
                            "GolCasa": 0,
                            "GolOspite": 0,
                            "Validata": True,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

    return df


def init_results_temp_from_df(df):
    for _, row in df.iterrows():
        T = row.get('Turno', 1)
        casa = row['Casa']
        ospite = row['Ospite']
        key_gc = f"gc_{T}_{casa}_{ospite}"
        key_go = f"go_{T}_{casa}_{ospite}"
        key_val = f"val_{T}_{casa}_{ospite}"
        st.session_state.risultati_temp.setdefault(key_gc, int(row.get('GolCasa', 0)))
        st.session_state.risultati_temp.setdefault(key_go, int(row.get('GolOspite', 0)))
        st.session_state.risultati_temp.setdefault(key_val, bool(row.get('Validata', False)))

def visualizza_incontri_attivi(df_turno_corrente, turno_attivo, modalita_visualizzazione):
    """Visualizza gli incontri del turno attivo e permette di inserire e validare i risultati."""
    tipo_vista = st.session_state.get('tipo_vista_selezionata', 'compact').lower()
    
    if tipo_vista in ['compact', 'premium']:
        st.markdown("""
        <style>
        div[data-testid="stNumberInput"] button { display: none !important; }
        div[data-testid="stNumberInput"] input::-webkit-outer-spin-button,
        div[data-testid="stNumberInput"] input::-webkit-inner-spin-button {
            -webkit-appearance: none !important; margin: 0 !important;
        }
        div[data-testid="stNumberInput"] input[type="number"] { -moz-appearance: textfield !important; }
        div[data-testid="stNumberInput"] { max-width: 48px !important; }
        div[data-testid="stNumberInput"] div[data-baseweb="input"] { padding: 0 !important; }
        div[data-testid="stNumberInput"] input {
            padding: 3px 1px !important; text-align: center !important;
            font-weight: bold !important; font-size: 0.95rem !important;
        }
        div[data-testid="stCheckbox"] { margin-top: 0 !important; }

        .portrait-warning {
            display: none; background: linear-gradient(135deg, #ff6b35, #f7931e);
            color: white; text-align: center; padding: 12px; border-radius: 8px;
            font-weight: 700; font-size: 0.9rem; margin-bottom: 10px; animation: pulse 2s infinite;
        }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
        @media screen and (max-width: 640px) and (orientation: portrait) {
            .portrait-warning { display: block !important; }
        }
        </style>
        <div class="portrait-warning">
            📱🔄 Ruota il telefono in <b>ORIZZONTALE</b> per la vista ottimizzata!
        </div>
        <script>
        try { if (screen.orientation && screen.orientation.lock) { screen.orientation.lock('landscape').catch(()=>{}); } } catch(e) {}
        </script>
        """, unsafe_allow_html=True)
        
        if tipo_vista == 'premium':
            st.markdown("""
            <style>
            .match-header-premium {
                background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
                color: white; text-align: center; padding: 4px; font-size: 0.75rem;
                font-weight: 800; border-radius: 8px 8px 0 0; text-transform: uppercase;
                letter-spacing: 1px; margin-top: -16px; margin-left: -16px; margin-right: -16px; margin-bottom: 15px;
            }
            .team-name-premium { font-weight: 700; font-size: 1.1rem; padding-top: 5px; }
            </style>
            """, unsafe_allow_html=True)

    for i, riga in df_turno_corrente.iterrows():
        casa = riga['Casa']
        ospite = riga['Ospite']
        key_gc = f"gc_{turno_attivo}_{casa}_{ospite}"
        key_go = f"go_{turno_attivo}_{casa}_{ospite}"
        key_val = f"val_{turno_attivo}_{casa}_{ospite}"
        valida_key = f"valida_{turno_attivo}_{casa}_{ospite}"

        # Gestione CASA
        if casa == "RIPOSA" or st.session_state.df_squadre[st.session_state.df_squadre['Squadra'] == casa].empty:
            info_casa = {"Squadra": "RIPOSA", "Giocatore": "—"}
        else:
            info_casa = st.session_state.df_squadre[st.session_state.df_squadre['Squadra'] == casa].iloc[0]

        # Gestione OSPITE
        if ospite == "RIPOSA" or st.session_state.df_squadre[st.session_state.df_squadre['Squadra'] == ospite].empty:
            info_ospite = {"Squadra": "RIPOSA", "Giocatore": "—"}
        else:
            info_ospite = st.session_state.df_squadre[st.session_state.df_squadre['Squadra'] == ospite].iloc[0]

        nome_squadra_casa = info_casa['Squadra']
        nome_giocatore_casa = info_casa['Giocatore']
        nome_squadra_ospite = info_ospite['Squadra']
        nome_giocatore_ospite = info_ospite['Giocatore']

        if modalita_visualizzazione == 'Squadre':
            label_c, label_o = nome_squadra_casa, nome_squadra_ospite
        elif modalita_visualizzazione == 'Giocatori':
            label_c, label_o = nome_giocatore_casa, nome_giocatore_ospite
        else:
            label_c, label_o = f"{nome_squadra_casa} ({nome_giocatore_casa})", f"{nome_squadra_ospite} ({nome_giocatore_ospite})"

        gol_casa_iniziale = riga.get('GolCasa', 0)
        gol_ospite_iniziale = riga.get('GolOspite', 0)
        validata_iniziale = bool(riga.get('Validata', False))

        if key_gc not in st.session_state.risultati_temp:
            st.session_state.risultati_temp[key_gc] = gol_casa_iniziale
        if key_go not in st.session_state.risultati_temp:
            st.session_state.risultati_temp[key_go] = gol_ospite_iniziale
        if key_val not in st.session_state.risultati_temp:
            st.session_state.risultati_temp[key_val] = validata_iniziale

        is_disabled = st.session_state.risultati_temp.get(key_val, False)
        
        # --- UI Rendering in base al tipo di vista ---
        if tipo_vista == 'compact':
            c1, c2, c3, c4, c5, c6 = st.columns([3, 0.8, 0.3, 0.8, 3, 0.7])
            with c1:
                st.markdown(f"<div style='text-align:right; font-weight:700; font-size:0.78rem; padding-top:6px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{label_c}</div>", unsafe_allow_html=True)
            with c2:
                st.session_state.risultati_temp[key_gc] = st.number_input("GC", min_value=0, max_value=20, value=st.session_state.risultati_temp[key_gc], key=key_gc, label_visibility="collapsed", disabled=is_disabled)
            with c3:
                st.markdown("<div style='text-align:center; font-weight:bold; font-size:0.8rem; padding-top:6px;'>-</div>", unsafe_allow_html=True)
            with c4:
                st.session_state.risultati_temp[key_go] = st.number_input("GO", min_value=0, max_value=20, value=st.session_state.risultati_temp[key_go], key=key_go, label_visibility="collapsed", disabled=is_disabled)
            with c5:
                st.markdown(f"<div style='text-align:left; font-weight:700; font-size:0.78rem; padding-top:6px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{label_o}</div>", unsafe_allow_html=True)
            with c6:
                validata_checkbox = st.checkbox("✓", value=st.session_state.risultati_temp.get(key_val, False), key=valida_key, label_visibility="collapsed")
                
        elif tipo_vista == 'premium':
            with st.container(border=True):
                st.markdown(f"<div class='match-header-premium'>TURNO {turno_attivo} • MATCH {i+1}</div>", unsafe_allow_html=True)
                c1, c2, c3, c4 = st.columns([3, 1, 1, 3])
                with c1:
                    st.markdown(f"<div style='text-align:right;' class='team-name-premium'>🏠 {label_c}</div>", unsafe_allow_html=True)
                with c2:
                    st.session_state.risultati_temp[key_gc] = st.number_input("GC", min_value=0, max_value=20, value=st.session_state.risultati_temp[key_gc], key=key_gc, label_visibility="collapsed", disabled=is_disabled)
                with c3:
                    st.session_state.risultati_temp[key_go] = st.number_input("GO", min_value=0, max_value=20, value=st.session_state.risultati_temp[key_go], key=key_go, label_visibility="collapsed", disabled=is_disabled)
                with c4:
                    st.markdown(f"<div style='text-align:left;' class='team-name-premium'>{label_o} 🛫</div>", unsafe_allow_html=True)
                v1, v2 = st.columns([6, 1.5])
                with v2:
                    validata_checkbox = st.checkbox("Valida ✅", value=st.session_state.risultati_temp.get(key_val, False), key=valida_key)
                    
        else: # Standard
            with st.container(border=True):
                st.markdown("<p style='text-align:center; font-size:1.2rem; font-weight:bold;'>⚽ Partita</p>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align:center; font-weight:bold;'>🏠{label_c} 🆚 {label_o}🛫</p>", unsafe_allow_html=True)
                c_score1, c_score2 = st.columns(2)
                with c_score1:
                    st.session_state.risultati_temp[key_gc] = st.number_input(f"Gol {casa}", min_value=0, max_value=20, value=st.session_state.risultati_temp[key_gc], key=key_gc, disabled=is_disabled)
                with c_score2:
                    st.session_state.risultati_temp[key_go] = st.number_input(f"Gol {ospite}", min_value=0, max_value=20, value=st.session_state.risultati_temp[key_go], key=key_go, disabled=is_disabled)
                st.markdown("---")
                validata_checkbox = st.checkbox("✅ Valida Risultato", value=st.session_state.risultati_temp.get(key_val, False), key=valida_key)

        # DB UPDATE LOGIC
        if validata_checkbox != st.session_state.risultati_temp.get(key_val, False):
            if validata_checkbox and not verify_write_access():
                st.error("⛔ Accesso in sola lettura. Non è possibile validare la partita.")
                st.session_state.risultati_temp[key_val] = False
                st.session_state[f"{valida_key}_force_update"] = not st.session_state.get(f"{valida_key}_force_update", False)
                return
                
            st.session_state.risultati_temp[key_val] = validata_checkbox
            partita_idx = df_turno_corrente[df_turno_corrente['Casa'] == casa].index
            
            if validata_checkbox:
                df_turno_corrente.loc[partita_idx, 'GolCasa'] = st.session_state.risultati_temp.get(key_gc, 0)
                df_turno_corrente.loc[partita_idx, 'GolOspite'] = st.session_state.risultati_temp.get(key_go, 0)
                df_turno_corrente.loc[partita_idx, 'Validata'] = True
                st.session_state.df_torneo.loc[partita_idx, ['GolCasa', 'GolOspite', 'Validata']] = df_turno_corrente.loc[partita_idx, ['GolCasa', 'GolOspite', 'Validata']]
                
                if salva_torneo_su_db(
                    action_type="validazione_risultato",
                    details={
                        "partita": f"{casa} vs {ospite}",
                        "risultato": f"{df_turno_corrente.loc[partita_idx, 'GolCasa'].values[0]}-{df_turno_corrente.loc[partita_idx, 'GolOspite'].values[0]}",
                        "turno": st.session_state.turno_attivo
                    }
                ):
                    pass # Success
                else:
                    st.error("❌ Errore durante il salvataggio del risultato")
            else:
                df_turno_corrente.loc[partita_idx, 'Validata'] = False
                st.session_state.df_torneo.loc[partita_idx, 'Validata'] = False
                
                if salva_torneo_su_db(
                    action_type="rimozione_validazione",
                    details={
                        "partita": f"{casa} vs {ospite}",
                        "turno": st.session_state.turno_attivo
                    }
                ):
                    st.info(f"⚠️ Validazione rimossa per {casa} vs {ospite}")
                else:
                    st.error("❌ Errore durante il salvataggio delle modifiche")
            
            st.rerun()
        
        if st.session_state.risultati_temp.get(key_val, False):
            pass
        elif tipo_vista == 'standard':
            st.warning("⚠️ Partita non ancora validata.")

# -------------------------
# Header grafico
# -------------------------
st.markdown(f"""
<div style='text-align:center; padding:20px; border-radius:10px; background: linear-gradient(90deg, #457b9d, #1d3557); box-shadow: 0 4px 14px #00000022;'>
    <h1 style='color:white; font-weight:700; margin:0;'>🇨🇭⚽ {st.session_state.nome_torneo} 🏆🇨🇭</h1>
</div>
""", unsafe_allow_html=True)

# -------------------------
# Se torneo non è iniziato e non è stato ancora selezionato un setup
# -------------------------
if not st.session_state.torneo_iniziato and st.session_state.setup_mode is None:
    st.markdown("### Scegli azione 📝")
    c1, c2 = st.columns([1,1])
    with c1:
        with st.container(border=True):
            st.markdown(
                """<div style='text-align:center'>
                    <h2>📂 Carica torneo</h2>
                    <p style='margin:0.2rem 0 1rem 0'>Visualizza o riprendi un torneo esistente</p>
                    </div>""",
                unsafe_allow_html=True,
            )
            if st.button("Carica torneo 📂", key="btn_carica", width="stretch"):
                st.session_state.setup_mode = "carica_db"
                st.session_state.torneo_finito = False
                st.rerun()
    with c2:
        with st.container(border=True):
            st.markdown(
                """<div style='text-align:center'>
                    <h2>✨ Crea nuovo torneo</h2>
                    <p style='margin:0.2rem 0 1rem 0'>Genera primo turno scegliendo giocatori del Club PierCrew</p>
                    </div>""",
                unsafe_allow_html=True,
            )
            # Convert NumPy boolean to Python boolean for the disabled state
            is_disabled_new = bool(not verify_write_access())
            if st.button("Nuovo torneo ✨", key="btn_nuovo", width="stretch", disabled=is_disabled_new):
                if verify_write_access():
                    st.session_state.setup_mode = "nuovo"
                    st.session_state.nuovo_torneo_step = 0
                    st.session_state.giocatori_selezionati_db = []
                    st.session_state.giocatori_ospiti = []
                    st.session_state.giocatori_totali = []
                    st.session_state.club_scelto = "PierCrew"
                    st.session_state.torneo_finito = False
                    st.session_state.edited_df_squadre = pd.DataFrame()
                    st.session_state.gioc_info = {} # Reset del dizionario per la nuova grafica
                    st.rerun()
                else:
                    st.error("⛔ Accesso in sola lettura. Non è possibile creare nuovi tornei.")
                st.session_state.gioc_info = {} # Reset del dizionario per la nuova grafica
                st.rerun()

    st.markdown("---")

if "mostra_incontri_disputati" not in st.session_state:
    st.session_state["mostra_incontri_disputati"] = False

# -------------------------
# Logica di caricamento o creazione torneo
# -------------------------
if st.session_state.setup_mode == "carica_db":
    # Mostra lo stato di accesso in modo chiaro
    if not verify_write_access():
        st.warning("🔒 Modalità di sola lettura: non è possibile modificare i tornei")
    
    st.markdown("#### 📥 Carica torneo da MongoDB")
    with st.spinner("Caricamento elenco tornei..."):
        tornei_disponibili = carica_nomi_tornei_da_db()
    
    if not tornei_disponibili:
        st.warning("Nessun torneo trovato nel database.")
        if st.button("Torna indietro"):
            st.session_state.setup_mode = None
            st.rerun()
    else:
        torneo_scelto = st.selectbox(
            "Seleziona il torneo da caricare",
            options=tornei_disponibili,
            index=None,
            placeholder="Scegli un torneo..."
        )
        
        if torneo_scelto:
            if st.button("Carica torneo"):
                with st.spinner(f"Caricamento del torneo {torneo_scelto}..."):
                    if carica_torneo_da_db(torneo_scelto):
                        st.session_state.torneo_iniziato = True
                        st.session_state.setup_mode = None
                        st.toast(f"✅ Torneo '{torneo_scelto}' caricato con successo!")
                        st.session_state.torneo_finito = False
                        st.rerun()
            
            # Mostra un messaggio di avviso in modalità sola lettura
            if not verify_write_access():
                st.info("ℹ️ In modalità di sola lettura puoi visualizzare i tornei ma non apportare modifiche.")
                        
            # Aggiungi un pulsante per tornare indietro
            if st.button("Torna indietro"):
                st.session_state.setup_mode = None
                st.rerun()

if st.session_state.setup_mode == "nuovo":
    st.markdown("#### ✨ Crea nuovo torneo — passo per passo")
    if st.session_state.nuovo_torneo_step == 0:
        # Usa st.form per il nome del torneo per evitare rerun durante la digitazione
        with st.form(key="form_nome_torneo"):
            suffisso = st.text_input("Dai un nome al tuo torneo", value="", placeholder="Es. 'Campionato Invernale'")
            submitted = st.form_submit_button("Prossimo passo ➡️", type="primary")
        if submitted:
            st.session_state.nome_torneo = f"Torneo Subbuteo Svizzero - {suffisso.strip()}" if suffisso.strip() else "Torneo Subbuteo - Sistema Svizzero"
            st.session_state.nuovo_torneo_step = 1
            st.rerun()
    elif st.session_state.nuovo_torneo_step == 1:
        st.info(f"**Nome del torneo:** {st.session_state.nome_torneo}")
        st.markdown("### Selezione partecipanti 👥")
        
        col_db, col_num = st.columns([2, 1])
        with col_db:
            #df_gioc = carica_giocatori_da_db()
            df_gioc = carica_giocatori_da_db()
            if not df_gioc.empty:
                if st.session_state.modalita_selezione_giocatori == "Multiselect":
                    # Modalità classica
                    select_all = st.checkbox("Seleziona tutti i giocatori")
                    default_players = df_gioc['Giocatore'].tolist() if select_all else st.session_state.giocatori_selezionati_db
                    st.session_state.giocatori_selezionati_db = st.multiselect(
                        "Seleziona i giocatori (DB):",
                        options=df_gioc['Giocatore'].tolist(),
                        default=default_players,
                        key="player_selector"
                    )
                    pass
                else:
                    # Nuova modalità: checkbox singole - ordinate alfabeticamente
                    st.markdown("### ✅ Seleziona i giocatori")
                    selezionati = []
                    # Ordina i giocatori alfabeticamente
                    giocatori_ordinati = sorted(df_gioc['Giocatore'].tolist())
                    for g in giocatori_ordinati:
                        if st.checkbox(g, value=(g in st.session_state.giocatori_selezionati_db), key=f"chk_{g}"):
                            selezionati.append(g)
                    st.session_state.giocatori_selezionati_db = selezionati
                    pass

        with col_num:
            # Calcola il valore predefinito
            default_value = max(2, len(st.session_state.giocatori_selezionati_db))
            
            num_squadre = st.number_input(
                "Numero totale di partecipanti:",
                min_value=2,
                max_value=100,
                value=default_value,
                step=1,  # Incrementi di 1 per consentire qualsiasi numero
                key="num_partecipanti"
            )

        num_mancanti = num_squadre - len(st.session_state.giocatori_selezionati_db)
        if num_mancanti > 0:
            st.warning(f"⚠️ Mancano **{num_mancanti}** giocatori per raggiungere il numero totale. Aggiungi i nomi dei giocatori ospiti.")
            for i in range(num_mancanti):
                ospite_name = st.text_input(f"Nome Giocatore Ospite {i+1}", key=f"ospite_player_{i}", value=st.session_state.giocatori_ospiti[i] if i < len(st.session_state.giocatori_ospiti) else "")
                if i >= len(st.session_state.giocatori_ospiti):
                    st.session_state.giocatori_ospiti.append(ospite_name)
                else:
                    st.session_state.giocatori_ospiti[i] = ospite_name

        st.session_state.giocatori_totali = st.session_state.giocatori_selezionati_db + [p for p in st.session_state.giocatori_ospiti if p.strip()]
        
        st.markdown(f"**Partecipanti selezionati:** {len(st.session_state.giocatori_totali)} di {num_squadre}")
        
        #inizio
        # Modalità durata torneo
        modalita_turni = st.radio(
            "Durata torneo:",
            ["Numero fisso di round", "Turni illimitati"],
            index=1  # di default "Turni illimitati"
        )

        if modalita_turni == "Numero fisso di round":
            max_turni = st.number_input(
                "Numero massimo di round:",
                min_value=1,
                max_value=50,
                value=5,
                step=1
            )
            st.session_state.modalita_turni = "fisso"
            st.session_state.max_turni = max_turni
        else:
            st.session_state.modalita_turni = "illimitati"
            st.session_state.max_turni = None

        #fine

        col1, col2 = st.columns(2)
        # Aggiungi checkbox per copiare i nomi dei giocatori nei nomi delle squadre
        copia_nomi = st.checkbox("Usa i nomi dei giocatori come nomi delle squadre", 
                                help="Se selezionato, i nomi delle squadre verranno impostati uguali ai nomi dei giocatori")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Accetta giocatori ✅", key="next_step_1", width="stretch", type="primary"):
                if len(st.session_state.giocatori_totali) != num_squadre:
                    st.error(f"❌ Il numero di giocatori selezionati ({len(st.session_state.giocatori_totali)}) non corrisponde al numero totale di partecipanti richiesto ({num_squadre}).")
                else:
                    data_squadre = []
                    giocatori_db_df = carica_giocatori_da_db()
                    for player in st.session_state.giocatori_totali:
                        if player in giocatori_db_df['Giocatore'].tolist() and not copia_nomi:
                            player_info = giocatori_db_df[giocatori_db_df['Giocatore'] == player].iloc[0]
                            squadra = player_info.get('Squadra', player)
                            potenziale = player_info.get('Potenziale', 0)
                            data_squadre.append({'Giocatore': player, 'Squadra': squadra, 'Potenziale': potenziale})
                        else:
                            # Se copia_nomi è True, usa il nome del giocatore come nome squadra
                            # ma mantieni il potenziale dal database se esiste
                            potenziale = 0
                            if player in giocatori_db_df['Giocatore'].tolist():
                                player_info = giocatori_db_df[giocatori_db_df['Giocatore'] == player].iloc[0]
                                potenziale = player_info.get('Potenziale', 0)
                                
                            squadra = player if copia_nomi else player
                            data_squadre.append({'Giocatore': player, 'Squadra': squadra, 'Potenziale': potenziale})
                    
                    st.session_state.df_squadre = pd.DataFrame(data_squadre)
                    st.session_state.nuovo_torneo_step = 2
                    st.rerun()

        with col2:
            if st.button("↩️ Indietro", width="stretch"):
                st.session_state.nuovo_torneo_step = 1
                st.rerun()

    elif st.session_state.nuovo_torneo_step == 2:
        st.info(f"**Nome del torneo:** {st.session_state.nome_torneo}")
        st.markdown("### Modifica i nomi delle squadre e il potenziale 📝")
        st.info("Utilizza i campi sottostanti per assegnare una squadra e un potenziale a ogni partecipante.")
        
        if 'gioc_info' not in st.session_state:
            st.session_state['gioc_info'] = {}

        for gioc_df in st.session_state.df_squadre.to_dict('records'):
            gioc = gioc_df['Giocatore']
            
            if gioc not in st.session_state['gioc_info']:
                st.session_state['gioc_info'][gioc] = {
                    "Squadra": gioc_df['Squadra'],
                    "Potenziale": int(gioc_df['Potenziale'])
                }

            with st.container(border=True):
                st.markdown(f"**Giocatore**: {gioc}")
                
                squadra_nuova = st.text_input(
                    f"Squadra",
                    value=st.session_state['gioc_info'][gioc]["Squadra"],
                    key=f"squadra_input_{gioc}"
                )
                
                potenziale_nuovo = st.slider(
                    f"Potenziale",
                    min_value=0,
                    max_value=10,
                    value=int(st.session_state['gioc_info'][gioc]["Potenziale"]),
                    key=f"potenziale_slider_{gioc}"
                )
                
                st.session_state['gioc_info'][gioc]["Squadra"] = squadra_nuova
                st.session_state['gioc_info'][gioc]["Potenziale"] = potenziale_nuovo

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Genera calendario ▶️", type="primary", width="stretch"):
                df_squadre_aggiornato = []
                for gioc, info in st.session_state['gioc_info'].items():
                    df_squadre_aggiornato.append({
                        "Giocatore": gioc,
                        "Squadra": info["Squadra"],
                        "Potenziale": info["Potenziale"]
                    })
                
                st.session_state.df_squadre = pd.DataFrame(df_squadre_aggiornato)
                
                st.session_state.torneo_iniziato = True
                st.session_state.turno_attivo = 1
                
                # Create initial classification with potential values and position
                num_squadre = len(st.session_state.df_squadre)
                classifica_iniziale = pd.DataFrame({
                    "Squadra": st.session_state.df_squadre['Squadra'].tolist(),
                    "Potenziale": st.session_state.df_squadre['Potenziale'].tolist(),
                    "Pos.": range(1, num_squadre + 1),  # Add position column
                    "Punti": [0] * num_squadre,
                    "G": [0] * num_squadre,
                    "V": [0] * num_squadre,
                    "N": [0] * num_squadre,
                    "P": [0] * num_squadre,
                    "GF": [0] * num_squadre,
                    "GS": [0] * num_squadre,
                    "DR": [0] * num_squadre,
                })

                precedenti = set()
                df_turno = genera_accoppiamenti(classifica_iniziale.reset_index(), precedenti, primo_turno=True)
                df_turno["Turno"] = st.session_state.turno_attivo
                st.session_state.df_torneo = pd.concat([st.session_state.df_torneo, df_turno], ignore_index=True)
                st.session_state.setup_mode = None
                init_results_temp_from_df(st.session_state.df_torneo)
                st.rerun()

        with col2:
            if st.button("↩️ Indietro", width="stretch"):
                st.session_state.nuovo_torneo_step = 1
                st.rerun()

# -------------------------
# Sidebar — usa moduli condivisi
# -------------------------
# User info
setup_common_sidebar(show_user_info=True, show_hub_link=True, hub_url=HUB_URL)

# Audio di sottofondo
setup_audio_sidebar()

# ✅ 1. 🕹 Gestione Rapida + 👤 Mod Selezione Partecipanti
setup_player_selection_mode()
# Mappa il valore per compatibilità interna se necessario (o refactor)
st.session_state.modalita_selezione_giocatori = "Multiselect" if st.session_state.get('usa_multiselect_giocatori', False) else "Checkbox singole"

if st.session_state.torneo_iniziato:
    #st.sidebar.info(f"Torneo in corso: **{st.session_state.nome_torneo}**")
    
    # ✅ 2. ⚙️ Opzioni Torneo
    st.sidebar.subheader("⚙️ Opzioni Torneo")
    if tournaments_collection is not None:
        # Convert NumPy boolean to Python boolean for the disabled state
        is_disabled_save = bool(not verify_write_access())
        if st.sidebar.button("💾 Salva Torneo", 
                            width="stretch", 
                            type="primary",
                            disabled=is_disabled_save,
                            help="Salva il torneo" + ("" if verify_write_access() else " (accesso in sola lettura)")):
            if verify_write_access():
                salva_torneo_su_db(
                    action_type="salvataggio_manuale",
                    details={"tipo": "salvataggio_manuale_da_sidebar"}
                )
            else:
                st.error("⛔ Accesso in sola lettura. Non è possibile salvare le modifiche.")
                log_action(
                    username=st.session_state.get('user', {}).get('username', 'sconosciuto'),
                    action="tentativo_accesso_negato",
                    torneo=st.session_state.get('nome_torneo', 'sconosciuto'),
                    details={"azione": "salvataggio_manuale", "motivo": "sola_lettura"}
                )
        st.sidebar.success("✅ Torneo salvato su DB!")

    # Convert NumPy boolean to Python boolean for the disabled state
    is_disabled_finish = bool(not verify_write_access())

    if st.sidebar.button("🏁 Termina Torneo", 
                        key="reset_app", 
                        width="stretch",
                        disabled=is_disabled_finish,
                        help="Termina il torneo corrente" + ("" if verify_write_access() else " (accesso in sola lettura)")):
        if verify_write_access():
            # Salva lo stato attuale nel DB
            salva_torneo_su_db(
                action_type="fine_torneo_manuale",
                details={"motivo": "terminato_dall_utente"}
            )

            # Segna come terminato senza cancellare/reset
            st.session_state.torneo_finito = True
            st.sidebar.success("✅ Torneo terminato. Dati salvati nel DB.")
        else:
            st.error("⛔ Accesso in sola lettura. Non è possibile terminare il torneo.")


    # --- FUNZIONI DI SINCRONIZZAZIONE ---
    def sync_tipo_vista(source_key):
        val = st.session_state[source_key].lower()
        st.session_state['tipo_vista_selezionata'] = val

    # ✅ 3. 🔧 Utility (sezione principale con sottosezioni)
    st.sidebar.subheader("🔧 Utility")
    
    # 🔎 Visualizzazione incontri
    with st.sidebar.expander("🔎 Visualizzazione incontri", expanded=False):
        st.session_state.modalita_visualizzazione = st.radio(
            "Formato incontri:",
            options=["Squadre", "Giocatori", "Completa"],
            index=["Squadre", "Giocatori", "Completa"].index(st.session_state.modalita_visualizzazione),
            key="radio_sidebar"
        )
        st.markdown("---")
        current_view = st.session_state.get('tipo_vista_selezionata', 'compact').capitalize()
        st.radio(
            "Tipo di vista:",
            ("Compact", "Premium", "Standard"),
            index=("Compact", "Premium", "Standard").index(current_view),
            key="tipo_vista_sidebar_widget",
            on_change=sync_tipo_vista,
            args=("tipo_vista_sidebar_widget",)
        )
    
    # 📅 Visualizzazione incontri giocati e classifica (spostati nella Main UI)
    st.sidebar.markdown("---")

    # ✅ 4. 📤 Esportazione (in fondo)
    st.sidebar.subheader("📤 Esportazione")
    if st.sidebar.button("📄 Prepara PDF", key="prepare_pdf", width="stretch"):
        with st.spinner("Generazione PDF in corso..."):
            pdf_bytes = esporta_pdf(st.session_state.df_torneo, st.session_state.nome_torneo)
            if pdf_bytes:
                st.session_state['pdf_pronto'] = pdf_bytes
                st.sidebar.success("✅ PDF pronto per il download!")
            else:
                st.sidebar.error("❌ Errore durante la generazione del PDF")
    if st.session_state.get('pdf_pronto'):
        st.sidebar.download_button(
            label="📥 Scarica PDF Torneo",
            data=st.session_state['pdf_pronto'],
            file_name=f"{st.session_state.nome_torneo}.pdf".replace(" ", "_"),
            mime="application/octet-stream",
            width="stretch"
        )

    # -------------------------
# Interfaccia Utente Torneo
# -------------------------
if st.session_state.torneo_iniziato and not st.session_state.torneo_finito:
    if st.session_state.get("mostra_incontri_disputati", False):
        st.markdown("## 🏟️ Tutti gli incontri disputati")
        df_giocati = st.session_state.df_torneo[st.session_state.df_torneo['Validata'] == True]
        
        if not df_giocati.empty:
            # Add some CSS for the table
            st.markdown("""
            <style>
            .compact-table {
                font-size: 0.9em;
                width: auto !important;
                border-collapse: collapse;
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
            
            # Generate the HTML table
            table_html = "<table class='compact-table'><thead><tr>"
            headers = ["📅", "🏠", "⚽️", "⚽️", "🛫"]
            for header in headers:
                table_html += f"<th>{header}</th>"
            table_html += "</tr></thead><tbody>"
            
            # Add table rows
            for _, match in df_giocati.iterrows():
                table_html += "<tr>"
                # Column 1: Round with number emoji
                turno_num = match['Turno']
                # Map numbers to emojis
                num_to_emoji = {
                    0: "0️⃣", 1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 
                    4: "4️⃣", 5: "5️⃣", 6: "6️⃣", 
                    7: "7️⃣", 8: "8️⃣", 9: "9️⃣"
                }
                # Get emoji for the turn number, default to 🔵 if not a single digit
                if isinstance(turno_num, (int, float)) and 0 <= turno_num <= 9:
                    turno_emoji = num_to_emoji[int(turno_num)]
                else:
                    turno_emoji = "🔵"  # Default for unknown turn numbers
                table_html += f"<td style='font-weight: bold; text-align: center;'>{turno_emoji}</td>"
                
                # Column 2: Home team
                table_html += f"<td style='text-align: right;'>{match['Casa']}</td>"
                
                # Column 3: Home goals
                gol_casa = match['GolCasa'] if pd.notna(match['GolCasa']) else "-"
                table_html += f"<td style='font-weight: bold; text-align: center;'>{gol_casa}</td>"
                
                # Column 4: Away goals
                gol_ospite = match['GolOspite'] if pd.notna(match['GolOspite']) else "-"
                table_html += f"<td style='font-weight: bold; text-align: center;'>{gol_ospite}</td>"
                
                # Column 5: Away team
                table_html += f"<td style='text-align: left;'>{match['Ospite']}</td>"
                
                table_html += "</tr>"
                
            table_html += "</tbody></table>"
            st.markdown(table_html, unsafe_allow_html=True)
        else:
            st.info("Nessun incontro validato al momento.")
            
        # Pulsante per chiudere la tabella e tornare alla vista classica
        if st.button("🔙 Torna alla vista classica", key="btn_chiudi_incontri", width="stretch"):
            st.session_state["mostra_incontri_disputati"] = False
            st.session_state.rerun_needed = True
    else:
        col_t1, col_t2, col_t3 = st.columns([0.5, 0.25, 0.25], vertical_alignment="bottom")
        with col_t1:
            st.markdown(f"### Turno {st.session_state.turno_attivo}")
        with col_t2:
            if st.button("📋 Incontri", key="btn_mostra_tutti_incontri", width="stretch"):
                st.session_state["mostra_incontri_disputati"] = True
                st.rerun()
        with col_t3:
            class_label = "Nascondi Classifica" if st.session_state.get('mostra_classifica') else "📊 Classifica"
            btn_type = "secondary" if st.session_state.get('mostra_classifica') else "primary"
            if st.button(class_label, key="btn_mostra_classifica", type=btn_type, width="stretch"):
                st.session_state.mostra_classifica = not st.session_state.get('mostra_classifica', False)
                st.rerun()
    
    
    df_turno_corrente = st.session_state.df_torneo[st.session_state.df_torneo['Turno'] == st.session_state.turno_attivo].copy()
    
    if df_turno_corrente.empty:
        st.warning("⚠️ Non ci sono partite in questo turno. Torna indietro per aggiungere giocatori o carica un altro torneo.")
    else:
        st.markdown("---")
        tipo_vista_corrente = st.session_state.get('tipo_vista_selezionata', 'compact').capitalize()
        st.radio(
            "Seleziona la vista del calendario:",
            ("Compact", "Premium", "Standard"),
            index=("Compact", "Premium", "Standard").index(tipo_vista_corrente),
            key="tipo_vista_main_widget",
            horizontal=True,
            label_visibility="collapsed",
            on_change=sync_tipo_vista,
            args=("tipo_vista_main_widget",)
        )

        # Passa il nuovo parametro alla funzione
        visualizza_incontri_attivi(df_turno_corrente, st.session_state.turno_attivo, st.session_state.modalita_visualizzazione)

    st.markdown("---")
    
    partite_giocate_turno = st.session_state.df_torneo[st.session_state.df_torneo['Turno'] == st.session_state.turno_attivo]
    tutte_validate = partite_giocate_turno['Validata'].all()
    
    # Mostra la classifica solo se richiesta
    classifica_attuale = aggiorna_classifica(st.session_state.df_torneo)
    
        
    # Se la classifica è visibile, la mostriamo
    # Usa @st.fragment per aggiornare solo questa sezione senza rerun completo
    @st.fragment
    def mostra_classifica_fragment():
        if st.session_state.mostra_classifica:
            with st.expander("🏆 Classifica Attuale", expanded=True):
                classifica = aggiorna_classifica(st.session_state.df_torneo)
                if not classifica.empty:
                    st.dataframe(classifica, hide_index=True, width="stretch")
                else:
                    st.info("Nessuna partita giocata per aggiornare la classifica.")
    
    mostra_classifica_fragment()
    
    # Manteniamo il layout a due colonne per il prossimo turno
    col_next = st.columns([1])[0]  # Creiamo una colonna singola per il pulsante del prossimo turno
    
    with col_next:
        st.subheader("Prossimo Turno ➡️")
        if tutte_validate:
            precedenti = set(zip(st.session_state.df_torneo['Casa'], st.session_state.df_torneo['Ospite'])) | set(zip(st.session_state.df_torneo['Ospite'], st.session_state.df_torneo['Casa']))
            df_turno_prossimo = genera_accoppiamenti(classifica_attuale, precedenti)

            if df_turno_prossimo is not None and not df_turno_prossimo.empty:
                # Convert NumPy boolean to Python boolean for the disabled state
                is_disabled = bool(
                    (st.session_state.turno_attivo >= st.session_state.df_torneo['Turno'].max().item() 
                     if not st.session_state.df_torneo.empty else True) or 
                    not verify_write_access()
                )
                
                # Anche verifica se torneo è finito
                is_disabled_next = False

                if st.session_state.get("torneo_finito", False):
                    is_disabled_next = True
                if not tutte_validate:
                    is_disabled_next = True
                
                #if st.button("🔄 Genera Prossimo Turno",
                if st.button("▶️ Genera prossimo turno", 
                    width="stretch", 
                    type="primary",
                    disabled=is_disabled_next,
                    help="Genera il prossimo turno" + ("" if verify_write_access() else " (accesso in sola lettura)")):
                    
                    if verify_write_access():
                        # Controlla se abbiamo raggiunto il numero massimo di turni
                        if st.session_state.modalita_turni == "fisso" and st.session_state.max_turni is not None:
                            if st.session_state.turno_attivo >= st.session_state.max_turni:
                                st.info(f"✅ Torneo terminato: raggiunto il limite di {st.session_state.max_turni} round.")
                                st.session_state.torneo_finito = True
                                salva_torneo_su_db(
                                    action_type="fine_torneo_automatico",
                                    details={"motivo": "raggiunto_limite_turni", "turni_giocati": st.session_state.max_turni}
                                )
                                st.rerun()
                        
                        # Incrementa il contatore del turno
                        nuovo_turno = st.session_state.turno_attivo + 1
                        
                        # Salva i risultati del turno corrente
                        if not salva_torneo_su_db(
                            action_type="salvataggio_turno_corrente",
                            details={"turno": st.session_state.turno_attivo}
                        ):
                            st.error("❌ Errore durante il salvataggio del turno corrente")
                            st.stop()
                        
                        # Aggiorna il numero del turno e genera il prossimo
                        st.session_state.turno_attivo = nuovo_turno
                        df_turno_prossimo["Turno"] = st.session_state.turno_attivo
                        st.session_state.df_torneo = pd.concat([st.session_state.df_torneo, df_turno_prossimo], ignore_index=True)
                        st.session_state.risultati_temp = {}
                        init_results_temp_from_df(df_turno_prossimo)
                        
                        # Salva il nuovo turno
                        if salva_torneo_su_db(
                            action_type="generazione_nuovo_turno",
                            details={"nuovo_turno": st.session_state.turno_attivo + 1}
                        ):
                            st.toast("✅ Nuovo turno generato e salvato con successo!")
                            st.rerun()
                        else:
                            st.error("❌ Errore durante il salvataggio del nuovo turno")

                #FINE

            else:
                # Controlla se abbiamo effettivamente esaurito tutti i possibili accoppiamenti
                # Se non si trovano accoppiamenti, chiudi subito il torneo
                st.error("❌ Impossibile trovare accoppiamenti validi per il prossimo turno.")
                
                # Determina il vincitore dalla classifica attuale
                classifica_attuale = aggiorna_classifica(st.session_state.df_torneo)
                if not classifica_attuale.empty:
                    vincitore = classifica_attuale.iloc[0]['Squadra']
                    punti_vincitore = classifica_attuale.iloc[0]['Punti']
                    
                    st.warning(f"🏆 Il torneo è terminato. Vincitore: {vincitore} con {punti_vincitore} punti")
                    
                    # Mostra la classifica completa
                    st.subheader("Classifica Finale")
                    st.dataframe(classifica_attuale, hide_index=True, width="stretch")
                    
                    # Salva lo stato del torneo come terminato
                    st.session_state.torneo_finito = True
                    salva_torneo_su_db(
                        action_type="fine_torneo_automatico",
                        details={"motivo": "impossibile_generare_nuovi_accoppiamenti"}
                    )
                    st.rerun()
                else:
                    # Meno di 2 squadre rimaste, il torneo è finito
                    st.success("🏆 Torneo terminato con successo!")
                    # Determina il vincitore dalla classifica
                    classifica_attuale = aggiorna_classifica(st.session_state.df_torneo)
                    if not classifica_attuale.empty:
                        vincitore = classifica_attuale.iloc[0]['Squadra']
                        st.warning(f"Vincitore finale: {vincitore}")
                    
                    st.session_state.torneo_finito = True
                    salva_torneo_su_db(
                        action_type="fine_torneo_automatico",
                        details={"motivo": "meno_di_due_squadre_rimaste", "vincitore": vincitore}
                    )
                    st.rerun()
        else:
            st.warning("⚠️ Per generare il prossimo turno, devi validare tutti i risultati.")

    
# -------------------------
# Banner vincitore
# -------------------------
if st.session_state.torneo_finito:
    st.subheader("Classifica Finale 🥇")
    df_class = aggiorna_classifica(st.session_state.df_torneo)
    if not df_class.empty:
        st.dataframe(df_class, hide_index=True, width="stretch")
        vincitore = df_class.iloc[0]['Squadra']

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
                🏆 Il vincitore del torneo {st.session_state.nome_torneo} è {vincitore}! 🎉
             </div>
             """, unsafe_allow_html=True)
        st.balloons()
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
# Footer leggero
st.markdown("---")
st.caption("⚽ Subbuteo Tournament Manager •  Made by Legnaro72")
