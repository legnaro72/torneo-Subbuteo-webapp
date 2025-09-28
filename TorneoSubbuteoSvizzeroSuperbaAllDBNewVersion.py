
import streamlit as st

# Configurazione della pagina DEVE essere la PRIMA operazione Streamlit
st.set_page_config(
    page_title="Torneo Subbuteo - Svizzero",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
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



# Aggiungi lo script JavaScript per il keep-alive
def add_keep_alive():
    js = """
    <script>
    // Individua l'URL corretto dell'app Streamlit
    const target = document.referrer || window.location.origin;

    // Esegui un ping ogni 4 minuti (240000 ms)
    setInterval(function() {
        fetch(target, {
            method: 'HEAD',
            cache: 'no-store',
            credentials: 'same-origin',
            mode: 'no-cors'
        }).then(() => {
            console.log("Keep-alive sent:", new Date().toLocaleTimeString());
        }).catch((err) => console.log("Keep-alive error", err));
    }, 240000);
    </script>
    """
    st.components.v1.html(js, height=0, width=0)

# Inizializza il keep-alive
#add_keep_alive()




# Mostra la schermata di autenticazione se non si è già autenticati
if not st.session_state.get('authenticated', False):
    auth.show_auth_screen(club="Superba")
    st.stop()

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
    "club_scelto": "Superba",
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
    "modalita_visualizzazione": "Squadre"
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# Aggiornamento del nome del torneo se è finito
if st.session_state.torneo_finito and not st.session_state.nome_torneo.startswith("finito_"):
    st.session_state.nome_torneo = f"finito_{st.session_state.nome_torneo}"
# -------------------------
# CSS personalizzato
# -------------------------
st.markdown("""
<style>
    /* Stili per il contenitore principale */
    .appview-container .main .block-container {
        padding-top: 0rem;
        padding-right: 1rem;
        padding-left: 1rem;
        padding-bottom: 0rem;
    }

    /* Stili per i pulsanti */
    .stButton>button, 
    .stDownloadButton>button {
        background: linear-gradient(90deg, #457b9d, #1d3557); 
        color: white; 
        border-radius: 10px; 
        padding: 0.55em 1.0em; 
        font-weight: 700; 
        border: 0; 
        box-shadow: 0 4px 14px #00000022;
        transition: all 0.2s ease;
    }

    .stButton>button:hover,
    .stDownloadButton>button:hover { 
        transform: translateY(-1px); 
        box-shadow: 0 6px 18px #00000033; 
    }

    /* Stili per i link nella sidebar */
    [data-testid="stSidebar"] .stLinkButton a {
        color: white !important;
        background: linear-gradient(90deg, #457b9d, #1d3557) !important;
        border-radius: 10px !important;
        padding: 0.55em 1.0em !important;
        font-weight: 700 !important;
        text-decoration: none !important;
        transition: all 0.2s ease !important;
        display: inline-block !important;
        width: 100% !important;
        text-align: center !important;
        border: none !important;
        box-shadow: 0 4px 14px #00000022 !important;
    }

    [data-testid="stSidebar"] .stLinkButton a:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 18px #00000033 !important;
    }

    [data-testid="stSidebar"] .stLinkButton a:active {
        transform: translateY(0) !important;
    }

    /* Stili per gli header */
    .main .block-container h3 { 
        color: white; 
        font-weight: 700;
        background: linear-gradient(90deg, #457b9d, #1d3557);
        border-radius: 10px;
        box-shadow: 0 4px 14px #00000022;
        padding: 10px;
        text-align: center;
    }

    /* Stili per la sidebar */
    .css-1d391kg h3, 
    [data-testid="stSidebar"] h3 {
        color: #1d3557;
        font-weight: 700;
        background: none !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        padding: 0 !important;
        text-align: left !important;
    }

    /* Gestione temi scuri */
    @media (prefers-color-scheme: dark),
           .stApp[data-theme="dark"],
           html[data-theme="dark"],
           body[data-theme="dark"] {
        [data-testid="stSidebar"] h3,
        .css-1d391kg h3,
        [data-testid="stSidebar"] .element-container h3,
        .css-1d391kg .element-container h3,
        [data-testid="stSidebar"] div h3,
        .css-1d391kg div h3,
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
        [data-testid="stSidebar"] .stTitle h3 {
            color: #0078D4 !important;
            font-weight: 700;
            background: none !important;
            border-radius: 0 !important;
            box-shadow: none !important;
            padding: 0 !important;
            text-align: left !important;
        }

        /* Stili per hover/focus nella sidebar */
        [data-testid="stSidebar"] h3:hover,
        [data-testid="stSidebar"] h3:focus,
        [data-testid="stSidebar"] h3:active,
        [data-testid="stSidebar"] h3[style*="color"],
        [data-testid="stSidebar"] h3[style*="color"]:hover,
        [data-testid="stSidebar"] h3[style*="color"]:focus {
            color: #0078D4 !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# -------------------------
# Connessione a MongoDB Atlas
# -------------------------

def check_internet_connection():
    try:
        import socket
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        return True
    except OSError:
        return False

players_collection = None
tournaments_collection = None

if not check_internet_connection():
    st.sidebar.error("❌ Nessuna connessione Internet rilevata. Verifica la tua connessione e riprova.")
else:
    with st.spinner("Connessione a MongoDB..."):
        try:
            MONGO_URI = st.secrets.get("MONGO_URI")
            if not MONGO_URI:
                st.sidebar.warning("⚠️ Chiave MONGO_URI non trovata nei segreti di Streamlit.")
            else:
                server_api = ServerApi('1')
                client = MongoClient(MONGO_URI, 
                                  server_api=server_api,
                                  connectTimeoutMS=5000,  # 5 secondi di timeout
                                  socketTimeoutMS=5000,
                                  serverSelectionTimeoutMS=5000)
                
                # Test connessione
                client.admin.command('ping')
                
                # Connessione per i giocatori
                db_players = client.get_database("giocatori_subbuteo")
                players_collection = db_players.get_collection("superba_players")
                _ = players_collection.find_one()

                # Connessione per i tornei
                db_tournaments = client.get_database("TorneiSubbuteo")
                tournaments_collection = db_tournaments.get_collection("SuperbaSvizzero")
                _ = tournaments_collection.find_one()
                
                #st.sidebar.success("✅ Connessione a MongoDB Atlas riuscita!")
                
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

# -------------------------
# Funzioni di utilità
# -------------------------

def autoplay_audio(audio_data: bytes):
    b64 = base64.b64encode(audio_data).decode("utf-8")
    md = f"""
        <audio autoplay="true">
        <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        """
    st.markdown(md, unsafe_allow_html=True)
    
def salva_torneo_su_db():
    """Salva o aggiorna lo stato del torneo su MongoDB."""
    if not verify_write_access():
        st.error("⛔ Accesso in sola lettura. Non è possibile salvare le modifiche.")
        return False
        
    if tournaments_collection is None:
        st.error("❌ Connessione a MongoDB non attiva, impossibile salvare.")
        return False
        
    # Verifica se abbiamo già un ID torneo valido nella sessione
    if 'tournament_id' in st.session_state and st.session_state.tournament_id:
        try:
            # Verifica se il torneo esiste ancora nel database
            existing = tournaments_collection.find_one({"_id": ObjectId(st.session_state.tournament_id)})
            if not existing:
                # Se il torneo non esiste più, rimuoviamo l'ID dalla sessione
                del st.session_state.tournament_id
        except:
            # In caso di errore (es. ID non valido), rimuoviamo l'ID dalla sessione
            del st.session_state.tournament_id

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
        # Se abbiamo un ID torneo nella sessione, aggiorniamo quel documento specifico
        if 'tournament_id' in st.session_state and st.session_state.tournament_id:
            tournaments_collection.update_one(
                {"_id": ObjectId(st.session_state.tournament_id)},
                {"$set": torneo_data}
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
                st.toast(f"✅ Torneo esistente '{st.session_state.nome_torneo}' aggiornato con successo!")
            else:
                # Crea un nuovo documento e salva l'ID nella sessione
                result = tournaments_collection.insert_one(torneo_data)
                st.session_state.tournament_id = str(result.inserted_id)
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
        
        return True
        
    except Exception as e:
        st.error(f"❌ Errore durante il caricamento del torneo: {str(e)}")
        return False
        
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

def esporta_pdf(df_torneo, nome_torneo):
    try:
        pdf = FPDF()
        pdf.add_page()
        
        # Titolo del torneo
        pdf.set_font("Arial", "B", 16)
        titolo = nome_torneo.encode("latin-1", "ignore").decode("latin-1")
        pdf.cell(0, 15, titolo, ln=True, align="C")
        
        # Data di generazione
        pdf.set_font("Arial", "I", 10)
        pdf.cell(0, 8, f"Generato il: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
        pdf.ln(10)

        # Sezione Partite
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Partite", ln=True)
        pdf.set_font("Arial", "", 11)
        
        turno_corrente = None
        for _, r in df_torneo.sort_values(by="Turno").iterrows():
            if turno_corrente != r["Turno"]:
                turno_corrente = r["Turno"]
                pdf.ln(5)
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 8, f"Turno {turno_corrente}", ln=True)
                pdf.set_font("Arial", "", 11)

            casa = str(r["Casa"])
            osp = str(r["Ospite"])
            gc = str(r["GolCasa"])
            go = str(r["GolOspite"])
            
            # Gestione caratteri speciali
            casa = casa.encode("latin-1", "ignore").decode("latin-1")
            osp = osp.encode("latin-1", "ignore").decode("latin-1")
            
            match_text = f"{casa} {gc} - {go} {osp}"
            
            # Colore in base allo stato della partita
            if bool(r.get("Validata", False)):
                pdf.set_text_color(0, 100, 0)  # Verde scuro per partite validate
            else:
                pdf.set_text_color(128, 128, 128)  # Grigio per partite non validate
            
            pdf.cell(0, 8, match_text, ln=True)

        # Sezione Classifica
        pdf.ln(15)
        pdf.set_text_color(0, 0, 0)  # Ripristina il colore nero
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Classifica", ln=True)
        
        classifica = aggiorna_classifica(df_torneo)
        if not classifica.empty:
            # Intestazione tabella
            pdf.set_font("Arial", "B", 10)
            header = ['Pos', 'Squadra', 'Punti', 'G', 'V', 'N', 'P', 'GF', 'GS', 'DR']
            col_widths = [12, 50, 12, 8, 8, 8, 8, 8, 8, 8]
            
            # Intestazione con bordi
            for i, h in enumerate(header):
                pdf.cell(col_widths[i], 8, h, border=1, align='C')
            pdf.ln()

            # Dettagli classifica
            pdf.set_font("Arial", "", 10)
            for idx, (_, row) in enumerate(classifica.iterrows(), 1):
                pdf.cell(col_widths[0], 8, str(idx), border=1, align='C')
                pdf.cell(col_widths[1], 8, str(row['Squadra']).encode("latin-1", "ignore").decode("latin-1"), border=1)
                pdf.cell(col_widths[2], 8, str(row['Punti']), border=1, align='C')
                pdf.cell(col_widths[3], 8, str(row['G']), border=1, align='C')
                pdf.cell(col_widths[4], 8, str(row['V']), border=1, align='C')
                pdf.cell(col_widths[5], 8, str(row['N']), border=1, align='C')
                pdf.cell(col_widths[6], 8, str(row['P']), border=1, align='C')
                pdf.cell(col_widths[7], 8, str(row['GF']), border=1, align='C')
                pdf.cell(col_widths[8], 8, str(row['GS']), border=1, align='C')
                pdf.cell(col_widths[9], 8, str(row['DR']), border=1, align='C')
                pdf.ln()

        # Genera il PDF in memoria
        return pdf.output(dest='S').encode('latin-1')
        
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
            "Squadra", "Punti", "Partite", "Vittorie", "Pareggi", "Sconfitte",
            "GolFatti", "GolSubiti", "DifferenzaReti"
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
                              

    # 🔥 Merge con potenziali delle squadre
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

    # --- Ordinamento ---
    if turno_attuale in (1, 2, 3):
        # Ordinamento per Potenziale (discendente)
        classifica = st.session_state.df_squadre.copy()
        classifica = classifica.sort_values(by="Potenziale", ascending=False).reset_index(drop=True)
    else:
        # Dal 3° turno in poi: per Classifica aggiornata
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

    import random

    if primo_turno:
        classifica = classifica.copy()
        classifica["Potenziale"] = pd.to_numeric(classifica["Potenziale"], errors="coerce").fillna(0)
        classifica = classifica.sort_values(by="Potenziale", ascending=False).reset_index(drop=True)
    else:
        classifica = aggiorna_classifica(st.session_state.df_torneo)

    squadre = classifica["Squadra"].tolist()

    riposa = None
    if len(squadre) % 2 != 0:
        riposa = squadre.pop()

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
    if accoppiamenti is None:
        # fallback casuale: mescola le squadre e accoppiale
        random.shuffle(squadre)
        accoppiamenti = []
        for i in range(0, len(squadre), 2):
            if i + 1 < len(squadre):
                if (squadre[i], squadre[i+1]) not in precedenti and (squadre[i+1], squadre[i]) not in precedenti:
                    accoppiamenti.append((squadre[i], squadre[i+1]))

    if not accoppiamenti:
        st.error("⚠️ Non è stato possibile generare accoppiamenti validi!")
        return None

    df = pd.DataFrame([{"Casa": c, "Ospite": o, "GolCasa": 0, "GolOspite": 0, "Validata": False} for c, o in accoppiamenti])
    if riposa:
        df = pd.concat([df, pd.DataFrame([{"Casa": riposa, "Ospite": "RIPOSA", "GolCasa": 0, "GolOspite": 0, "Validata": True}])], ignore_index=True)
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
    for i, riga in df_turno_corrente.iterrows():
        with st.container(border=True):
            casa = riga['Casa']
            ospite = riga['Ospite']
            key_gc = f"gc_{turno_attivo}_{casa}_{ospite}"
            key_go = f"go_{turno_attivo}_{casa}_{ospite}"
            key_val = f"val_{turno_attivo}_{casa}_{ospite}"
            valida_key = f"valida_{turno_attivo}_{casa}_{ospite}"

            # Recupera i dati di squadra e giocatore per la visualizzazione
            # Gestione CASA
            if casa == "RIPOSA" or st.session_state.df_squadre[st.session_state.df_squadre['Squadra'] == casa].empty:
                info_casa = {"Squadra": "RIPOSA", "Giocatore": "—"}
            else:
                info_casa = st.session_state.df_squadre[
                    st.session_state.df_squadre['Squadra'] == casa
                ].iloc[0]

            # Gestione OSPITE
            if ospite == "RIPOSA" or st.session_state.df_squadre[st.session_state.df_squadre['Squadra'] == ospite].empty:
                info_ospite = {"Squadra": "RIPOSA", "Giocatore": "—"}
            else:
                info_ospite = st.session_state.df_squadre[
                    st.session_state.df_squadre['Squadra'] == ospite
                ].iloc[0]



            nome_squadra_casa = info_casa['Squadra']
            nome_giocatore_casa = info_casa['Giocatore']
            nome_squadra_ospite = info_ospite['Squadra']
            nome_giocatore_ospite = info_ospite['Giocatore']
            
            st.markdown(f"<p style='text-align:center; font-size:1.2rem; font-weight:bold;'>⚽ Partita</p>", unsafe_allow_html=True)
            
            match_string = ""
            if modalita_visualizzazione == 'Squadre':
                match_string = f"{nome_squadra_casa} 🆚 {nome_squadra_ospite}"
            elif modalita_visualizzazione == 'Giocatori':
                match_string = f"{nome_giocatore_casa} 🆚 {nome_giocatore_ospite}"
            elif modalita_visualizzazione == 'Completa':
                match_string = f"{nome_squadra_casa} ({nome_giocatore_casa}) 🆚 {nome_squadra_ospite} ({nome_giocatore_ospite})"
                
            st.markdown(f"<p style='text-align:center; font-weight:bold;'>🏠{match_string}🛫</p>", unsafe_allow_html=True)

            # 💡 MODIFICA QUI 💡
            # Usa il valore del DataFrame per inizializzare l'input se non è già nello stato temporaneo
            gol_casa_iniziale = riga.get('GolCasa', 0)
            gol_ospite_iniziale = riga.get('GolOspite', 0)
            validata_iniziale = bool(riga.get('Validata', False))

            if key_gc not in st.session_state.risultati_temp:
                st.session_state.risultati_temp[key_gc] = gol_casa_iniziale
            if key_go not in st.session_state.risultati_temp:
                st.session_state.risultati_temp[key_go] = gol_ospite_iniziale
            if key_val not in st.session_state.risultati_temp:
                st.session_state.risultati_temp[key_val] = validata_iniziale
            
            c_score1, c_score2 = st.columns(2)
            with c_score1:
                st.session_state.risultati_temp[key_gc] = st.number_input(
                    f"Gol {casa}",
                    min_value=0,
                    value=st.session_state.risultati_temp[key_gc], # Usa il valore salvato in session_state
                    key=key_gc,
                    disabled=st.session_state.risultati_temp.get(key_val, False)
                )
            with c_score2:
                st.session_state.risultati_temp[key_go] = st.number_input(
                    f"Gol {ospite}",
                    min_value=0,
                    value=st.session_state.risultati_temp[key_go], # Usa il valore salvato in session_state
                    key=key_go,
                    disabled=st.session_state.risultati_temp.get(key_val, False)
                )
            
            st.markdown("---")
            validata_checkbox = st.checkbox(
                "✅ Valida Risultato",
                value=st.session_state.risultati_temp.get(key_val, False),
                key=valida_key
            )
            
            # Aggiorna il risultato quando la checkbox cambia stato
            if validata_checkbox != st.session_state.risultati_temp.get(key_val, False):
                # Controlla i permessi di scrittura prima di procedere
                if validata_checkbox and not verify_write_access():
                    st.error("⛔ Accesso in sola lettura. Non è possibile validare la partita.")
                    # Ripristina lo stato precedente della checkbox senza fare refresh
                    st.session_state.risultati_temp[key_val] = False
                    # Usa una chiave unica per forzare il refresh solo della checkbox
                    st.session_state[f"{valida_key}_force_update"] = not st.session_state.get(f"{valida_key}_force_update", False)
                    # Esci senza fare rerun()
                    return
                    
                # Aggiorna solo lo stato di questa partita
                st.session_state.risultati_temp[key_val] = validata_checkbox
                
                # Trova l'indice esatto della partita corrente
                partita_idx = df_turno_corrente[df_turno_corrente['Casa'] == casa].index
                
                if validata_checkbox:
                    # Salva i risultati nel DataFrame quando viene validato
                    df_turno_corrente.loc[partita_idx, 'GolCasa'] = st.session_state.risultati_temp.get(key_gc, 0)
                    df_turno_corrente.loc[partita_idx, 'GolOspite'] = st.session_state.risultati_temp.get(key_go, 0)
                    df_turno_corrente.loc[partita_idx, 'Validata'] = True
                    st.session_state.df_torneo.loc[partita_idx, ['GolCasa', 'GolOspite', 'Validata']] = df_turno_corrente.loc[partita_idx, ['GolCasa', 'GolOspite', 'Validata']]
                    
                    if salva_torneo_su_db():
                        pass #st.toast(f"✅ Partita {casa} vs {ospite} validata e salvata!")
                    else:
                        st.error("❌ Errore durante il salvataggio del risultato")
                else:
                    # Rimuovi la validazione se deselezionata
                    df_turno_corrente.loc[partita_idx, 'Validata'] = False
                    st.session_state.df_torneo.loc[partita_idx, 'Validata'] = False
                    
                    if salva_torneo_su_db():
                        st.info(f"⚠️ Validazione rimossa per {casa} vs {ospite}")
                    else:
                        st.error("❌ Errore durante il salvataggio delle modifiche")
                
                # Forza l'aggiornamento dell'interfaccia
                st.rerun()
            
            # Mostra stato validazione
            if st.session_state.risultati_temp.get(key_val, False):
                pass #st.toast("✅ Partita validata!")
            else:
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
            if st.button("Carica torneo 📂", key="btn_carica", use_container_width=True):
                st.session_state.setup_mode = "carica_db"
                st.session_state.torneo_finito = False
                st.rerun()
    with c2:
        with st.container(border=True):
            st.markdown(
                """<div style='text-align:center'>
                    <h2>✨ Crea nuovo torneo</h2>
                    <p style='margin:0.2rem 0 1rem 0'>Genera primo turno scegliendo giocatori del Club Superba</p>
                    </div>""",
                unsafe_allow_html=True,
            )
            # Convert NumPy boolean to Python boolean for the disabled state
            is_disabled_new = bool(not verify_write_access())
            if st.button("Nuovo torneo ✨", key="btn_nuovo", use_container_width=True, disabled=is_disabled_new):
                if verify_write_access():
                    st.session_state.setup_mode = "nuovo"
                    st.session_state.nuovo_torneo_step = 0
                    st.session_state.giocatori_selezionati_db = []
                    st.session_state.giocatori_ospiti = []
                    st.session_state.giocatori_totali = []
                    st.session_state.club_scelto = "Superba"
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
        suffisso = st.text_input("Dai un nome al tuo torneo", value="", placeholder="Es. 'Campionato Invernale'")
        if st.button("Prossimo passo ➡️", key="next_step_0", type="primary"):
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
            if st.button("Accetta giocatori ✅", key="next_step_1", use_container_width=True, type="primary"):
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
            if st.button("↩️ Indietro", use_container_width=True):
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
            if st.button("Genera calendario ▶️", type="primary", use_container_width=True):
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
            if st.button("↩️ Indietro", use_container_width=True):
                st.session_state.nuovo_torneo_step = 1
                st.rerun()

# -------------------------
# Sidebar
# -------------------------
# Debug: mostra utente autenticato e ruolo
if st.session_state.get("authenticated"):
    user = st.session_state.get("user", {})
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**👤 Utente:** {user.get('username', '??')}")
    st.sidebar.markdown(f"**🔑 Ruolo:** {user.get('role', '??')}")
    st.sidebar.markdown("---")

# ✅ 1. 🕹️ Gestione Rapida (in cima)
st.sidebar.subheader("🕹️ Gestione Rapida")
st.sidebar.link_button("➡️ Vai a Hub Tornei", "https://farm-tornei-subbuteo-superba-all-db.streamlit.app/", use_container_width=True)
st.sidebar.markdown("---")

st.sidebar.subheader("👤 Mod Selezione Partecipanti")

# 🔀 Modalità selezione giocatori
if "modalita_selezione_giocatori" not in st.session_state:
    st.session_state.modalita_selezione_giocatori = "Checkbox singole"
# Crea la checkbox per attivare la modalità Multiselect
# Il valore di default è False, corrispondente a "Checkbox singole"
use_multiselect = st.sidebar.checkbox(
    "Utilizza 'Multiselect'",
    value=(st.session_state.modalita_selezione_giocatori == "Multiselect")
)

# Se cambia rispetto allo stato salvato → aggiorna e forza rerun
nuova_modalita = "Multiselect" if use_multiselect else "Checkbox singole"
if nuova_modalita != st.session_state.modalita_selezione_giocatori:
    st.session_state.modalita_selezione_giocatori = nuova_modalita
    st.rerun()



if st.session_state.torneo_iniziato:
    #st.sidebar.info(f"Torneo in corso: **{st.session_state.nome_torneo}**")
    
    # ✅ 2. ⚙️ Opzioni Torneo
    st.sidebar.subheader("⚙️ Opzioni Torneo")
    if tournaments_collection is not None:
        # Convert NumPy boolean to Python boolean for the disabled state
        is_disabled_save = bool(not verify_write_access())
        if st.sidebar.button("💾 Salva Torneo", 
                            use_container_width=True, 
                            type="primary",
                            disabled=is_disabled_save,
                            help="Salva il torneo" + ("" if verify_write_access() else " (accesso in sola lettura)")):
            if verify_write_access():
                salva_torneo_su_db()
            else:
                st.error("⛔ Accesso in sola lettura. Non è possibile salvare le modifiche.")
        st.sidebar.success("✅ Torneo salvato su DB!")

    # Convert NumPy boolean to Python boolean for the disabled state
    is_disabled_finish = bool(not verify_write_access())

    if st.sidebar.button("🏁 Termina Torneo", 
                        key="reset_app", 
                        use_container_width=True,
                        disabled=is_disabled_finish,
                        help="Termina il torneo corrente" + ("" if verify_write_access() else " (accesso in sola lettura)")):
        if verify_write_access():
            # Salva lo stato attuale nel DB
            salva_torneo_su_db()

            # Segna come terminato senza cancellare/reset
            st.session_state.torneo_finito = True
            st.sidebar.success("✅ Torneo terminato. Dati salvati nel DB.")
        else:
            st.error("⛔ Accesso in sola lettura. Non è possibile terminare il torneo.")


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
    
    # 📅 Visualizzazione incontri giocati e classifica
    with st.sidebar.expander("📅 Visualizzazione incontri giocati e classifica", expanded=False):
        if st.button("📋 Mostra tutti gli incontri disputati", key="btn_mostra_tutti_incontri", use_container_width=True):
            st.session_state["mostra_incontri_disputati"] = True
            st.rerun()
            
        # Aggiungi il pulsante per mostrare/nascondere la classifica
        if st.button("📊 Mostra/Nascondi Classifica", key="btn_mostra_classifica", use_container_width=True):
            st.session_state.mostra_classifica = not st.session_state.get('mostra_classifica', False)
            st.rerun()

    st.sidebar.markdown("---")

    # ✅ 4. 📤 Esportazione (in fondo)
    st.sidebar.subheader("📤 Esportazione")
    if st.sidebar.button("📄 Prepara PDF", key="prepare_pdf", use_container_width=True):
        with st.spinner("Generazione PDF in corso..."):
            pdf_bytes = esporta_pdf(st.session_state.df_torneo, st.session_state.nome_torneo)
            if pdf_bytes:
                st.sidebar.success("✅ PDF pronto per il download!")
                st.sidebar.download_button(
                    label="📥 Scarica PDF Torneo",
                    data=pdf_bytes,
                    file_name=f"{st.session_state.nome_torneo}.pdf".replace(" ", "_"),
                    mime="application/octet-stream",
                    use_container_width=True
                )
            else:
                st.sidebar.error("❌ Errore durante la generazione del PDF")


    # Inizializza il keep-alive
    #add_keep_alive()

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
        if st.button("🔙 Torna alla vista classica", key="btn_chiudi_incontri", use_container_width=True):
            st.session_state["mostra_incontri_disputati"] = False
            st.session_state.rerun_needed = True
    else:
        st.markdown(f"### Turno {st.session_state.turno_attivo}")
    
    
    df_turno_corrente = st.session_state.df_torneo[st.session_state.df_torneo['Turno'] == st.session_state.turno_attivo].copy()
    
    if df_turno_corrente.empty:
        st.warning("⚠️ Non ci sono partite in questo turno. Torna indietro per aggiungere giocatori o carica un altro torneo.")
    else:
        # Passa il nuovo parametro alla funzione
        visualizza_incontri_attivi(df_turno_corrente, st.session_state.turno_attivo, st.session_state.modalita_visualizzazione)

    st.markdown("---")
    
    partite_giocate_turno = st.session_state.df_torneo[st.session_state.df_torneo['Turno'] == st.session_state.turno_attivo]
    tutte_validate = partite_giocate_turno['Validata'].all()
    
    # Mostra la classifica solo se richiesta
    classifica_attuale = aggiorna_classifica(st.session_state.df_torneo)
    
        
    # Se la classifica è visibile, la mostriamo in un espandibile
    if st.session_state.mostra_classifica:
        with st.expander("🏆 Classifica Attuale", expanded=True):
            if not classifica_attuale.empty:
                st.dataframe(classifica_attuale, hide_index=True, use_container_width=True)
            else:
                st.info("Nessuna partita giocata per aggiornare la classifica.")
    
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
                    use_container_width=True, 
                    type="primary",
                    disabled=is_disabled_next,
                    help="Genera il prossimo turno" + ("" if verify_write_access() else " (accesso in sola lettura)")):
                    
                    if verify_write_access():
                        # Controlla se abbiamo raggiunto il numero massimo di turni
                        if st.session_state.modalita_turni == "fisso" and st.session_state.max_turni is not None:
                            if st.session_state.turno_attivo >= st.session_state.max_turni:
                                st.info(f"✅ Torneo terminato: raggiunto il limite di {st.session_state.max_turni} round.")
                                st.session_state.torneo_finito = True
                                salva_torneo_su_db()
                                st.rerun()
                        
                        # Incrementa il contatore del turno
                        nuovo_turno = st.session_state.turno_attivo + 1
                        
                        # Salva i risultati del turno corrente
                        if not salva_torneo_su_db():
                            st.error("❌ Errore durante il salvataggio del turno corrente")
                            st.stop()
                        
                        # Aggiorna il numero del turno e genera il prossimo
                        st.session_state.turno_attivo = nuovo_turno
                        df_turno_prossimo["Turno"] = st.session_state.turno_attivo
                        st.session_state.df_torneo = pd.concat([st.session_state.df_torneo, df_turno_prossimo], ignore_index=True)
                        st.session_state.risultati_temp = {}
                        init_results_temp_from_df(df_turno_prossimo)
                        
                        # Salva il nuovo turno
                        if salva_torneo_su_db():
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
                    st.dataframe(classifica_attuale, hide_index=True, use_container_width=True)
                    
                    # Salva lo stato del torneo come terminato
                    st.session_state.torneo_finito = True
                    salva_torneo_su_db()
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
                    salva_torneo_su_db()
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
        st.dataframe(df_class, hide_index=True, use_container_width=True)
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

# Non è necessario il blocco if __name__ == "__main__" in un'app Streamlit
