import streamlit as st
import pandas as pd
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import certifi

# Import auth utilities
import auth_utils as auth

# Dati di connessione a MongoDB forniti dall'utente
MONGO_URI_PLAYERS = "mongodb+srv://massimilianoferrando:Legnaro21!$@cluster0.t3750lc.mongodb.net/?retryWrites=true&w=majority"
MONGO_URI_TOURNEMENTS = "mongodb+srv://massimilianoferrando:Legnaro21!$@cluster0.t3750lc.mongodb.net/?retryWrites=true&w=majority"
MONGO_URI_TOURNEMENTS_CH = "mongodb+srv://massimilianoferrando:Legnaro21!$@cluster0.t3750lc.mongodb.net/?retryWrites=true&w=majority"

def init_mongo_connections():
    """Inizializza le connessioni MongoDB con gestione degli errori"""
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
    auth.show_auth_screen(club="Superba")
    st.stop()
    

# Inizializza le connessioni MongoDB
client_players, client_italiana, client_svizzera = init_mongo_connections()
if None in (client_players, client_italiana, client_svizzera):
    st.stop()

# Inizializza le collezioni
db_players = client_players["giocatori_subbuteo"]
collection_players = db_players["superba_players"]

# Inizializza lo stato della sessione
if 'edit_index' not in st.session_state:
    st.session_state.edit_index = None

if 'confirm_delete' not in st.session_state:
    st.session_state.confirm_delete = {"type": None, "data": None, "password_required": False}

if 'password_check' not in st.session_state:
    st.session_state.password_check = {"show": False, "password": None, "type": None}

def inject_css():
    st.markdown("""
        <style>
        /* Stili di base */
        ul, li { 
            list-style-type: none !important; 
            padding-left: 0 !important; 
            margin-left: 0 !important; 
        }
        
        /* Titoli */
        .big-title { 
            text-align: center; 
            font-size: clamp(22px, 4vw, 42px); 
            font-weight: 800; 
            margin: 15px 0 10px; 
            color: #e63946; 
            text-shadow: 0 1px 2px #0002; 
        }
        
        .sub-title { 
            font-size: 20px; 
            font-weight: 700; 
            margin-top: 10px; 
            color: #1d3557; 
        }
        
        /* Stile per il titolo principale */
        .button-title {
            background: linear-gradient(90deg, #457b9d, #1d3557);
            color: white !important;
            padding: 15px 25px;
            border-radius: 10px;
            text-align: center;
            margin: 20px 0;
            box-shadow: 0 4px 14px #00000022;
            transition: all 0.3s ease;
            font-size: 2em;
            font-weight: 700;
            text-decoration: none !important;
            display: inline-block;
            width: 100%;
        }
        
        /* Stili per i pulsanti */
        .stButton>button { 
            background: linear-gradient(90deg, #457b9d, #1d3557); 
            color: white; 
            border-radius: 10px; 
            padding: 0.55em 1.0em; 
            font-weight: 700; 
            border: 0; 
            transition: all 0.3s ease;
        }
        
        .stButton>button:hover { 
            transform: translateY(-1px); 
            box-shadow: 0 4px 14px #00000022; 
        }
        
        .stDownloadButton>button { 
            background: linear-gradient(90deg, #2a9d8f, #21867a); 
            color: white; 
            border-radius: 10px; 
            font-weight: 700; 
            border: 0; 
            transition: all 0.3s ease;
        }
        
        .stDownloadButton>button:hover { 
            transform: translateY(-1px); 
            box-shadow: 0 4px 14px #00000022; 
        }
        
        /* Stili per le tabelle */
        .stDataFrame { 
            border: 2px solid #f4a261; 
            border-radius: 10px; 
        }
        
        /* Stile per i badge */
        .pill { 
            display:inline-block; 
            padding: 4px 10px; 
            border-radius: 999px; 
            background:#f1faee; 
            color:#1d3557; 
            font-weight:700; 
            border:1px solid #a8dadc; 
        }
        
        /* Stili per la sidebar */
        [data-testid="stSidebar"] h3 {
            color: #0078D4 !important;
        }
        
        /* Stili per i link nella sidebar */
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
            width: 100% !important;
            margin: 5px 0 !important;
        }
        
        [data-testid="stSidebar"] .stLinkButton:hover,
        [data-testid="stSidebar"] .stLinkButton a:hover {
            transform: translateY(-1px) !important;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15) !important;
        }
        
        [data-testid="stSidebar"] .stLinkButton:active,
        [data-testid="stSidebar"] .stLinkButton a:active {
            transform: translateY(0) !important;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1) !important;
        }
        
        /* Stili per il tema scuro */
        @media (prefers-color-scheme: dark) {
            [data-testid="stSidebar"] h3,
            .css-1d391kg h3,
            [data-testid="stSidebar"] .element-container h3,
            .css-1d391kg .element-container h3 {
                color: #ffffff !important;
                background: none !important;
            }
            
            [data-testid="stSidebar"] h3 {
                color: white !important;
            }
        }
        
        .stApp[data-theme="dark"] [data-testid="stSidebar"] h3,
        .stApp[data-theme="dark"] .css-1d391kg h3,
        .stApp[data-theme="dark"] [data-testid="stSidebar"] .element-container h3,
        .stApp[data-theme="dark"] .css-1d391kg .element-container h3,
        .stApp[data-theme="dark"] [data-testid="stSidebar"] div h3,
        .stApp[data-theme="dark"] .css-1d391kg div h3,
        html[data-theme="dark"] [data-testid="stSidebar"] h3,
        html[data-theme="dark"] .css-1d391kg h3,
        body[data-theme="dark"] [data-testid="stSidebar"] h3,
        body[data-theme="dark"] .css-1d391kg h3,
        [data-testid="stSidebar"] h3[class*="css"],
        .css-1d391kg h3[class*="css"],
        .stApp[data-theme="dark"] [data-testid="stSidebar"] * h3,
        .stApp[data-theme="dark"] .css-1d391kg * h3,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] .stMarkdown h3,
        [data-testid="stSidebar"] div h3 {
            color: #ffffff !important;
            background: none !important;
        }
        
        /* Stili per i pulsanti nella sidebar con tema scuro */
        [data-testid="stSidebar"][data-baseweb="dark"] .stLinkButton,
        [data-testid="stSidebar"][data-baseweb="dark"] .stLinkButton a,
        .stApp[data-theme="dark"] [data-testid="stSidebar"] .stLinkButton,
        .stApp[data-theme="dark"] [data-testid="stSidebar"] .stLinkButton a {
            background: linear-gradient(90deg, #1d3557, #457b9d) !important;
            color: white !important;
        }
        
        [data-testid="stSidebar"][data-baseweb="dark"] .stLinkButton:hover,
        [data-testid="stSidebar"][data-baseweb="dark"] .stLinkButton a:hover,
        .stApp[data-theme="dark"] [data-testid="stSidebar"] .stLinkButton:hover,
        .stApp[data-theme="dark"] [data-testid="stSidebar"] .stLinkButton a:hover {
            background: linear-gradient(90deg, #1d3557, #3a6ea5) !important;
        }
        
        /* Stili per dispositivi mobili */
        @media (max-width: 768px) {
            .st-emotion-cache-1f84s9j, 
            .st-emotion-cache-1j0n4k { 
                flex-direction: row; 
                justify-content: center; 
            }
            .st-emotion-cache-1f84s9j > div, 
            .st-emotion-cache-1j0n4k > div { 
                flex: 1; 
                padding: 0 5px; 
            }
        }
        </style>
        
        <script>
        // Funzione per forzare il colore bianco sui subheader della sidebar
        function forceWhiteSubheaders() {
            const sidebar = document.querySelector('[data-testid="stSidebar"]');
            if (sidebar) {
                const h3Elements = sidebar.querySelectorAll('h3');
                h3Elements.forEach(h3 => {
                    h3.style.color = 'white';
                    h3.style.setProperty('color', 'white', 'important');
                });
            }
        }

        // Esegui la funzione quando la pagina è caricata
        document.addEventListener('DOMContentLoaded', forceWhiteSubheaders);

        // Esegui la funzione ogni volta che Streamlit aggiorna il DOM
        const observer = new MutationObserver(forceWhiteSubheaders);
        observer.observe(document.body, { childList: true, subtree: true });

        // Esegui immediatamente
        forceWhiteSubheaders();
        </script>
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
    collection_players.delete_many({})
    collection_players.insert_many(df.to_dict('records'))

# --- Sezione per la gestione dei tornei ---
def carica_tornei_all_italiana():
    """Carica solo i nomi dei tornei all'italiana dalla collezione Superba."""
    db_tornei = client_italiana["TorneiSubbuteo"]
    collection_tornei = db_tornei["Superba"]
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
    collection_tornei = db_tornei["Superba"]
    collection_tornei.delete_many({})
    collection_tornei.insert_many(df.to_dict('records'))
    st.toast("Dati dei tornei all'italiana salvati con successo!")

def carica_tornei_svizzeri():
    """Carica solo i nomi dei tornei svizzeri dalla collezione SuperbaSvizzero."""
    db_tornei = client_svizzera["TorneiSubbuteo"]
    collection_tornei = db_tornei["SuperbaSvizzero"]
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
    collection_tornei = db_tornei["SuperbaSvizzero"]
    collection_tornei.delete_many({})
    collection_tornei.insert_many(df.to_dict('records'))
    st.toast("Dati dei tornei svizzeri salvati con successo!")


# Mostra la schermata di autenticazione se non si è già autenticati
if not st.session_state.get('authenticated', False):
    auth.show_auth_screen(club="Superba")
    st.stop()

st.set_page_config(
    page_title="Gestione Superba All-in-one", 
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

def reset_app_state():
    """Resetta lo stato dell'applicazione"""
    keys_to_reset = [
        "edit_index", "confirm_delete", "df_giocatori",
        "df_tornei_italiana", "df_tornei_svizzeri"
    ]
    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key]

# Inietta gli stili CSS personalizzati
inject_css()

# Sidebar / Pagina
# ✅ 1. 🕹 Gestione Rapida (sempre in cima)
st.sidebar.subheader("🕹️ Gestione Rapida")
st.markdown("""
    <style>
    /* Stile per i pulsanti */
    .stButton>button, .stSidebar .stButton>button, .stSidebar .stLinkButton>a {
        background-color: #0068c9 !important;
        color: white !important;
        border: none !important;
    }
    
    /* Stile per gli header della sidebar in linea con Fasi Finali */
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
    [data-testid="stSidebar"] .stSubheader h3 {
        color: #0068c9 !important;  /* Blu Streamlit */
        font-weight: 600;
    }
    .stSidebar .stLinkButton>a {
        background-color: #0068c9 !important;
        color: white !important;
        text-decoration: none !important;
        display: block;
        width: 100%;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# Pulsante per l'Hub Tornei
st.sidebar.link_button(
    "➡️ Vai a Hub Tornei",
    "https://farm-tornei-subbuteo-superba-all-db.streamlit.app/",
    use_container_width=True,
    type="primary"  # Usa lo stile primario di Streamlit
)

# Sezione debug autenticazione
# Rimossa la sezione di debug non più necessaria
st.sidebar.markdown("---")

st.markdown("<h1 class='button-title'>👥 Gestione del Club e dei Tornei🏆</h1>", unsafe_allow_html=True)

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
            st.toast(f"Giocatore '{giocatore}' aggiunto!")
        else:
            idx = st.session_state.edit_index
            st.session_state.df_giocatori.at[idx, "Giocatore"] = giocatore.strip()
            st.session_state.df_giocatori.at[idx, "Squadra"] = squadra.strip()
            st.session_state.df_giocatori.at[idx, "Potenziale"] = potenziale
            st.session_state.df_giocatori.at[idx, "Ruolo"] = ruolo
            st.toast(f"Giocatore '{giocatore}' aggiornato!")
            
        st.session_state.df_giocatori = st.session_state.df_giocatori.sort_values(by="Giocatore").reset_index(drop=True)
        salva_dati_su_mongo(st.session_state.df_giocatori)
        st.session_state.edit_index = None
        st.rerun()

def modify_player(idx):
    st.session_state.edit_index = idx

def confirm_delete_player(idx, selected_player):
    st.session_state.confirm_delete = {"type": "player", "data": (idx, selected_player), "password_required": True}
    st.rerun()

def confirm_delete_torneo_italiana(selected_tornei):
    # Controlla se si sta cercando di eliminare un torneo che inizia con 'Campionato'
    password_required = any(isinstance(t, str) and t.startswith("Campionato") for t in selected_tornei)
    st.session_state.confirm_delete = {
        "type": "tornei_ita", 
        "data": selected_tornei, 
        "password_required": password_required
    }
    st.rerun()

def confirm_delete_torneo_svizzero(selected_tornei):
    # Controlla se si sta cercando di eliminare un torneo che inizia con 'Campionato'
    password_required = any(isinstance(t, str) and t.startswith("Campionato") for t in selected_tornei)
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
        if deletion_type == "player":
            idx, selected_player = data
            st.session_state.df_giocatori = st.session_state.df_giocatori.drop(idx).reset_index(drop=True)
            salva_dati_su_mongo(st.session_state.df_giocatori)
            st.toast(f"Giocatore '{selected_player}' eliminato!")

        elif deletion_type == "tornei_ita":
            db_tornei = client_italiana["TorneiSubbuteo"]
            collection_tornei = db_tornei["Superba"]
            for torneo in data:
                collection_tornei.delete_one({"nome_torneo": torneo})
                st.session_state.df_tornei_italiana = st.session_state.df_tornei_italiana[st.session_state.df_tornei_italiana["Torneo"] != torneo].reset_index(drop=True)
                st.toast(f"Torneo '{torneo}' eliminato!")

        elif deletion_type == "tornei_svizz":
            db_tornei = client_svizzera["TorneiSubbuteo"]
            collection_tornei = db_tornei["SuperbaSvizzero"]
            for torneo in data:
                collection_tornei.delete_one({"nome_torneo": torneo})
                st.session_state.df_tornei_svizzeri = st.session_state.df_tornei_svizzeri[st.session_state.df_tornei_svizzeri["Torneo"] != torneo].reset_index(drop=True)
                st.toast(f"Torneo '{torneo}' eliminato!")

        elif deletion_type == "all_ita":
            db_tornei = client_italiana["TorneiSubbuteo"]
            collection_tornei = db_tornei["Superba"]
            tornei_da_cancellare = [t["nome_torneo"] for t in collection_tornei.find({}) if "campionato" not in t["nome_torneo"].lower()]
            for torneo in tornei_da_cancellare:
                collection_tornei.delete_one({"nome_torneo": torneo})
            st.session_state.df_tornei_italiana = carica_tornei_all_italiana()
            st.toast("✅ Tutti i tornei all'italiana (esclusi i campionati) sono stati eliminati!")

        elif deletion_type == "all_svizz":
            db_tornei = client_svizzera["TorneiSubbuteo"]
            collection_tornei = db_tornei["SuperbaSvizzero"]
            tornei_da_cancellare = [t["nome_torneo"] for t in collection_tornei.find({}) if "campionato" not in t["nome_torneo"].lower()]
            for torneo in tornei_da_cancellare:
                collection_tornei.delete_one({"nome_torneo": torneo})
            st.session_state.df_tornei_svizzeri = carica_tornei_svizzeri()
            st.toast("✅ Tutti i tornei svizzeri (esclusi i campionati) sono stati eliminati!")

        elif deletion_type == "all":
            # Chiamiamo le funzioni specifiche per applicare il filtro
            db_tornei_ita = client_italiana["TorneiSubbuteo"]
            collection_tornei_ita = db_tornei_ita["Superba"]
            tornei_da_cancellare_ita = [t["nome_torneo"] for t in collection_tornei_ita.find({}) if "campionato" not in t["nome_torneo"].lower()]
            for torneo in tornei_da_cancellare_ita:
                collection_tornei_ita.delete_one({"nome_torneo": torneo})
            
            db_tornei_svizz = client_svizzera["TorneiSubbuteo"]
            collection_tornei_svizz = db_tornei_svizz["SuperbaSvizzero"]
            tornei_da_cancellare_svizz = [t["nome_torneo"] for t in collection_tornei_svizz.find({}) if "campionato" not in t["nome_torneo"].lower()]
            for torneo in tornei_da_cancellare_svizz:
                collection_tornei_svizz.delete_one({"nome_torneo": torneo})
            
            st.session_state.df_tornei_italiana = carica_tornei_all_italiana()
            st.session_state.df_tornei_svizzeri = carica_tornei_svizzeri()
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
    st.header("👥Gestione Giocatori")
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
                use_container_width=True,
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
                use_container_width=True,
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
                        # Update the dataframe in session state
                        st.session_state.df_giocatori = edited_df
                        # Save to database
                        salva_dati_su_mongo(edited_df)
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
    st.download_button(
        "📥 Scarica CSV giocatori aggiornato",
        data=csv,
        file_name="giocatori_superba_modificato.csv",
        mime="text/csv",
    )

    # ---
    st.markdown("---")
    st.header("🏆Gestione Tornei")

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
        st.dataframe(df_tornei_italiana[["Torneo"]], use_container_width=True)
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
        st.dataframe(df_tornei_svizzeri[["Torneo"]], use_container_width=True)
        tornei_svizzeri = df_tornei_svizzeri["Torneo"].tolist()
        selected_tornei_svizzeri = st.multiselect("Seleziona tornei svizzeri da eliminare", options=tornei_svizzeri, key="del_svizzero_select")
        
        if selected_tornei_svizzeri:
            st.button("🗑️ Elimina Tornei Svizzeri selezionati", on_click=confirm_delete_torneo_svizzero, args=(selected_tornei_svizzeri,), key="del_svizzero_btn")
    else:
        st.info("Nessun torneo svizzero trovato.")


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

    if st.session_state.edit_index != -1:  # Only show in edit mode, not in add mode
        if is_admin:
            if st.button("🔄 Reset Password", help="Resetta la password dell'utente e imposta SetPwd a 0"):
                idx = st.session_state.edit_index
                st.session_state.df_giocatori.at[idx, "Password"] = None
                st.session_state.df_giocatori.at[idx, "SetPwd"] = 0
                salva_dati_su_mongo(st.session_state.df_giocatori)
                st.toast("✅ Password resettata con successo!")
                st.rerun()
        else:
            st.warning("Solo l'amministratore può resettare le password")

    col_save, col_cancel = st.columns(2)
    with col_save:
        if is_guest:
            st.button("✅ Salva", disabled=True, help="Non disponibile per gli ospiti")
        else:
            if st.button("✅ Salva"):
                save_player(giocatore, squadra, potenziale, ruolo)
    with col_cancel:
        if st.button("❌ Annulla"):
            st.session_state.edit_index = None
            st.rerun()

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
    
    # Mostra la richiesta di password solo se richiesta per questo tipo di operazione
    if st.session_state.confirm_delete["password_required"]:
        with col_confirm:
            if st.button("Conferma e procedi"):
                st.session_state.password_check["show"] = True
                st.session_state.password_check["type"] = deletion_type
        with col_cancel:
            st.button("❌ Annulla", on_click=cancel_delete)
        
        if st.session_state.password_check["show"]:
            password = st.text_input("Inserisci la password per confermare", type="password")
            if st.button("Conferma Password"):
                process_deletion_with_password(password, st.session_state.password_check["type"], st.session_state.confirm_delete["data"])
    else:
        # Se non è richiesta la password, procedi direttamente con la conferma
        with col_confirm:
            if st.button("Conferma eliminazione"):
                process_deletion_with_password("", deletion_type, st.session_state.confirm_delete["data"])
        with col_cancel:
            st.button("❌ Annulla", on_click=cancel_delete)

# Footer leggero
st.markdown("---")
st.caption("⚽ Subbuteo Tournament Manager •  Made by Legnaro72")