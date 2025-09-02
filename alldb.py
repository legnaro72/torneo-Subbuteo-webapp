import streamlit as st
import pandas as pd
import random
from fpdf import FPDF
from datetime import datetime
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
import json
import logging

# Configura il logging per l'app
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# -------------------------------------------------
# CONFIG PAGINA (deve essere la prima chiamata st.*)
# -------------------------------------------------
st.set_page_config(page_title="⚽Campionato/Torneo Preliminare Subbuteo", layout="wide")

# -------------------------
# GESTIONE DELLO STATO E FUNZIONI INIZIALI
# -------------------------
# Stato di default per l'applicazione
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
    'df_torneo': pd.DataFrame(),
    'debug_message': None,
    'sidebar_state_reset': False,
    'modalita_navigazione': "Menu a tendina"
}

# Inizializza lo stato della sessione se non esiste
for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value

def reset_app_state():
    """Reset the app state to its default values."""
    logging.info("Resetting app state.")
    for key, value in DEFAULT_STATE.items():
        st.session_state[key] = value

# -------------------------
# FUNZIONI CONNESSIONE MONGO
# -------------------------
@st.cache_resource
def init_mongo_connection(uri, db_name, collection_name):
    """Initializes and caches the MongoDB connection."""
    try:
        client = MongoClient(uri, server_api=ServerApi('1'))
        db = client.get_database(db_name)
        col = db.get_collection(collection_name)
        # Check connection by running a simple command
        client.admin.command('ping')
        logging.info(f"Connessione a {db_name}.{collection_name} ok.")
        return col
    except Exception as e:
        logging.error(f"❌ Errore di connessione a {db_name}.{collection_name}: {e}")
        st.error(f"❌ Errore di connessione a {db_name}.{collection_name}. Controlla le credenziali e la connessione internet.")
        return None

# -------------------------
# UTILITY
# -------------------------
def navigation_buttons(label, value_key, min_val, max_val, key_prefix=""):
    """Creates navigation buttons with a central label."""
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        if st.button("◀️", key=f"{key_prefix}_prev", use_container_width=True):
            st.session_state[value_key] = max(min_val, st.session_state[value_key] - 1)
            st.rerun()
    with col2:
        st.markdown(
            f"<div style='text-align:center; font-weight:bold;'>{label} {st.session_state[value_key]}</div>",
            unsafe_allow_html=True
        )
    with col3:
        if st.button("▶️", key=f"{key_prefix}_next", use_container_width=True):
            st.session_state[value_key] = min(max_val, st.session_state[value_key] + 1)
            st.rerun()

# -------------------------
# FUNZIONI DI GESTIONE DATI SU MONGO
# -------------------------
def carica_giocatori_da_db(players_collection):
    """Loads players data from MongoDB."""
    if players_collection is None:
        return pd.DataFrame()
    try:
        df = pd.DataFrame(list(players_collection.find({}, {"_id": 0})))
        return df if not df.empty else pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Errore durante la lettura dei giocatori: {e}")
        logging.error(f"Errore caricamento giocatori: {e}")
        return pd.DataFrame()

def carica_tornei_da_db(tournaments_collection):
    """Loads a list of tournaments from MongoDB."""
    if tournaments_collection is None:
        return []
    try:
        return list(tournaments_collection.find({}, {"nome_torneo": 1}))
    except Exception as e:
        st.error(f"❌ Errore caricamento tornei: {e}")
        logging.error(f"Errore caricamento tornei: {e}")
        return []

def carica_torneo_da_db(tournaments_collection, tournament_id):
    """Loads a specific tournament's data from MongoDB and prepares the DataFrame."""
    if tournaments_collection is None:
        return None
    try:
        torneo_data = tournaments_collection.find_one({"_id": ObjectId(tournament_id)})
        
        if torneo_data and 'calendario' in torneo_data:
            df_torneo = pd.DataFrame(torneo_data['calendario'])
            
            # Conversione esplicita e pulizia dei tipi di dati
            df_torneo['Valida'] = df_torneo['Valida'].astype(bool)
            df_torneo['GolCasa'] = pd.to_numeric(df_torneo['GolCasa'], errors='coerce').fillna(0).astype('Int64')
            df_torneo['GolOspite'] = pd.to_numeric(df_torneo['GolOspite'], errors='coerce').fillna(0).astype('Int64')
            df_torneo['Girone'] = df_torneo['Girone'].astype('string')
            df_torneo['Casa'] = df_torneo['Casa'].astype('string')
            df_torneo['Ospite'] = df_torneo['Ospite'].astype('string')
            
            st.session_state['df_torneo'] = df_torneo
        return torneo_data
    except Exception as e:
        st.error(f"❌ Errore caricamento torneo: {e}")
        logging.error(f"Errore caricamento torneo: {e}")
        return None

def salva_torneo_su_db(tournaments_collection, df_torneo, nome_torneo):
    """Saves a new tournament to MongoDB."""
    if tournaments_collection is None:
        return None
    try:
        # Converti il DataFrame in un formato adatto per MongoDB
        df_torneo_pulito = df_torneo.where(pd.notna(df_torneo), None)
        data = {"nome_torneo": nome_torneo, "calendario": df_torneo_pulito.to_dict('records')}
        result = tournaments_collection.insert_one(data)
        logging.info(f"Torneo '{nome_torneo}' salvato con ID: {result.inserted_id}")
        return result.inserted_id
    except Exception as e:
        st.error(f"❌ Errore salvataggio torneo: {e}")
        logging.error(f"Errore salvataggio torneo: {e}")
        return None

def aggiorna_torneo_su_db(tournaments_collection, tournament_id, df_torneo):
    """Updates an existing tournament in MongoDB."""
    if tournaments_collection is None:
        return False
    try:
        df_torneo_pulito = df_torneo.where(pd.notna(df_torneo), None)
        tournaments_collection.update_one(
            {"_id": ObjectId(tournament_id)},
            {"$set": {"calendario": df_torneo_pulito.to_dict('records')}}
        )
        logging.info(f"Torneo con ID '{tournament_id}' aggiornato.")
        return True
    except Exception as e:
        st.error(f"❌ Errore aggiornamento torneo: {e}")
        logging.error(f"Errore aggiornamento torneo: {e}")
        return False

# -------------------------
# CALENDARIO & CLASSIFICA LOGIC
# -------------------------
def genera_calendario_from_list(gironi, tipo="Solo andata"):
    """Generates the tournament schedule based on provided groups."""
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
    
    df = pd.DataFrame(partite)
    # Ensure all columns have the correct dtype before saving
    df['GolCasa'] = df['GolCasa'].astype('Int64')
    df['GolOspite'] = df['GolOspite'].astype('Int64')
    df['Valida'] = df['Valida'].astype(bool)
    df['Girone'] = df['Girone'].astype('string')
    df['Casa'] = df['Casa'].astype('string')
    df['Ospite'] = df['Ospite'].astype('string')
    
    return df

def aggiorna_classifica(df):
    """Updates the league table based on the match results in the DataFrame."""
    if 'Girone' not in df.columns or df.empty:
        return pd.DataFrame()
    gironi = df['Girone'].dropna().unique()
    classifiche = []
    for girone in gironi:
        partite = df[(df['Girone'] == girone) & (df['Valida'] == True)]
        if partite.empty:
            continue
        squadre = pd.unique(partite[['Casa', 'Ospite']].values.ravel())
        stats = {s: {'Punti': 0, 'V': 0, 'P': 0, 'S': 0, 'GF': 0, 'GS': 0, 'DR': 0} for s in squadre}
        for _, r in partite.iterrows():
            gc = int(r['GolCasa']) if pd.notna(r['GolCasa']) else 0
            go = int(r['GolOspite']) if pd.notna(r['GolOspite']) else 0
            casa, ospite = r['Casa'], r['Ospite']
            if casa in stats and ospite in stats:
                stats[casa]['GF'] += gc; stats[casa]['GS'] += go
                stats[ospite]['GF'] += go; stats[ospite]['GS'] += gc
                if gc > go:
                    stats[casa]['Punti'] += 2; stats[casa]['V'] += 1; stats[ospite]['S'] += 1
                elif gc < go:
                    stats[ospite]['Punti'] += 2; stats[ospite]['V'] += 1; stats[casa]['S'] += 1
                else:
                    stats[casa]['Punti'] += 1; stats[ospite]['Punti'] += 1; stats[casa]['P'] += 1; stats[ospite]['P'] += 1
        for s in squadre:
            if s in stats:
                stats[s]['DR'] = stats[s]['GF'] - stats[s]['GS']
        df_stat = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index': 'Squadra'})
        df_stat['Girone'] = girone
        classifiche.append(df_stat)
    if not classifiche:
        return pd.DataFrame()
    df_classifica = pd.concat(classifiche, ignore_index=True)
    df_classifica = df_classifica.sort_values(by=['Girone', 'Punti', 'DR', 'GF'], ascending=[True, False, False, False])
    return df_classifica

# -------------------------
# FUNZIONI DI VISUALIZZAZIONE & EVENTI
# -------------------------
def mostra_calendario_giornata(df, girone_sel, giornata_sel):
    """Displays the matches for a selected game day and allows score input."""
    df_giornata = df[(df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel)].copy()
    if df_giornata.empty:
        st.info("⚽ Nessuna partita trovata per questa giornata.")
        return
    for idx, row in df_giornata.iterrows():
        # Ensure values are not None before passing to widgets
        gol_casa = int(row['GolCasa']) if pd.notna(row['GolCasa']) else 0
        gol_ospite = int(row['GolOspite']) if pd.notna(row['GolOspite']) else 0
        valida = bool(row['Valida'])

        col1, col2, col3, col4, col5 = st.columns([5, 1.5, 1, 1.5, 1])
        with col1:
            st.markdown(f"**{row['Casa']}** vs **{row['Ospite']}**")
        with col2:
            st.number_input(
                "Gol Casa",
                min_value=0,
                max_value=20,
                key=f"golcasa_{idx}",
                value=gol_casa,
                disabled=valida,
                label_visibility="hidden"
            )
        with col3:
            st.markdown("-")
        with col4:
            st.number_input(
                "Gol Ospite",
                min_value=0,
                max_value=20,
                key=f"golospite_{idx}",
                value=gol_ospite,
                disabled=valida,
                label_visibility="hidden"
            )
        with col5:
            st.checkbox(
                "Valida",
                key=f"valida_{idx}",
                value=valida
            )
        
        # Display validation status
        if st.session_state.get(f"valida_{idx}", False):
            st.markdown("<div style='color:green; font-weight:bold;'>Partita validata ✅</div>", unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:red;">Partita non ancora validata ❌</div>', unsafe_allow_html=True)
        st.markdown("<hr style='border:1px solid #ccc; margin-top: 5px; margin-bottom: 10px;'>", unsafe_allow_html=True)

def salva_risultati_giornata(tournaments_collection, girone_sel, giornata_sel):
    """Saves the results for a specific game day to both the session state and the database."""
    logging.info(f"Salvataggio risultati per Girone: {girone_sel}, Giornata: {giornata_sel}")
    df = st.session_state['df_torneo'].copy()
    
    df_giornata_indices = df[(df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel)].index

    for idx in df_giornata_indices:
        gol_casa_key = f"golcasa_{idx}"
        gol_ospite_key = f"golospite_{idx}"
        valida_key = f"valida_{idx}"
        
        # Utilizza .get() per gestire chiavi mancanti, che possono verificarsi
        gol_casa = st.session_state.get(gol_casa_key)
        gol_ospite = st.session_state.get(gol_ospite_key)
        valida = st.session_state.get(valida_key, False)
        
        # Aggiorna il DataFrame in base ai valori dei widget
        df.at[idx, 'GolCasa'] = gol_casa if gol_casa is not None else 0
        df.at[idx, 'GolOspite'] = gol_ospite if gol_ospite is not None else 0
        df.at[idx, 'Valida'] = valida

    st.session_state['df_torneo'] = df

    if 'tournament_id' in st.session_state and st.session_state['tournament_id']:
        if aggiorna_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], df):
            st.toast("Risultati salvati su MongoDB ✅")
            logging.info("Risultati salvati su MongoDB.")
        else:
            st.error("❌ Errore: ID del torneo non trovato o aggiornamento fallito.")
            logging.error("Errore: ID del torneo non trovato o aggiornamento fallito.")
    
    # Check for tournament completion
    if df['Valida'].all():
        nome_completato = f"completato_{st.session_state['nome_torneo']}"
        classifica_finale = aggiorna_classifica(df)

        salva_torneo_su_db(tournaments_collection, df, nome_completato)

        st.session_state['torneo_completato'] = True
        st.session_state['classifica_finale'] = classifica_finale

        st.toast(f"Torneo completato e salvato come {nome_completato} ✅")
        logging.info("Torneo completato e salvato.")

def mostra_classifica_stilizzata(df_classifica, girone_sel):    
    """Displays the formatted league table for a specific group."""
    if df_classifica is None or df_classifica.empty:
        st.info("⚽ Nessuna partita validata")
        return
    df_girone = df_classifica[df_classifica['Girone'] == girone_sel].reset_index(drop=True)
    if df_girone.empty:
        st.info(f"Nessuna classifica disponibile per il {girone_sel}.")
        return
    st.dataframe(df_girone, use_container_width=True)

def esporta_pdf(df_torneo, df_classifica, nome_torneo):
    """Generates a PDF of the tournament schedule and league tables."""
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=False)
    
    def add_page_header():
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, f"Calendario e Classifiche {nome_torneo}", ln=True, align='C')
        pdf.ln(5)

    add_page_header()
    
    line_height = 6
    margin_bottom = 15
    page_height = 297
    
    gironi = df_torneo['Girone'].dropna().unique()
    for girone in gironi:
        pdf.set_font("Arial", 'B', 14)
        if pdf.get_y() + 8 + margin_bottom > page_height:
            add_page_header()
        
        pdf.cell(0, 8, f"{girone}", ln=True)
        giornate = sorted(df_torneo[df_torneo['Girone'] == girone]['Giornata'].dropna().unique())
        
        for g in giornate:
            needed_space = 7 + line_height * (len(df_torneo[(df_torneo['Girone'] == girone) & (df_torneo['Giornata'] == g)]) + 1) + margin_bottom
            if pdf.get_y() + needed_space > page_height:
                add_page_header()
            
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 7, f"Giornata {g}", ln=True)
            pdf.set_font("Arial", 'B', 11)
            
            headers = ["Casa", "Gol", "Gol", "Ospite"]
            col_widths = [60, 20, 20, 60]
            for i, h in enumerate(headers):
                pdf.cell(col_widths[i], 6, h, border=1, align='C')
            pdf.ln()
            
            pdf.set_font("Arial", '', 11)
            partite = df_torneo[(df_torneo['Girone'] == girone) & (df_torneo['Giornata'] == g)]
            
            for _, row in partite.iterrows():
                pdf.set_text_color(255, 0, 0) if not row['Valida'] else pdf.set_text_color(0, 0, 0)
                pdf.cell(col_widths[0], 6, str(row['Casa']), border=1)
                pdf.cell(col_widths[1], 6, str(row['GolCasa']) if pd.notna(row['GolCasa']) else "-", border=1, align='C')
                pdf.cell(col_widths[2], 6, str(row['GolOspite']) if pd.notna(row['GolOspite']) else "-", border=1, align='C')
                pdf.cell(col_widths[3], 6, str(row['Ospite']), border=1)
                pdf.ln()
            pdf.ln(3)

        # Classifica
        if df_classifica is not None and not df_classifica.empty:
            if pdf.get_y() + 40 + margin_bottom > page_height:
                add_page_header()
            pdf.set_font("Arial", 'B', 13)
            pdf.cell(0, 8, f"Classifica {girone}", ln=True)
            df_c = df_classifica[df_classifica['Girone'] == girone]
            if not df_c.empty:
                pdf.set_font("Arial", 'B', 11)
                headers = ["Squadra", "Punti", "V", "P", "S", "GF", "GS", "DR"]
                col_widths = [60, 15, 15, 15, 15, 15, 15, 15]
                for i, h in enumerate(headers):
                    pdf.cell(col_widths[i], 6, h, border=1, align='C')
                pdf.ln()
                pdf.set_font("Arial", '', 11)
                for _, r in df_c.iterrows():
                    if pdf.get_y() + line_height + margin_bottom > page_height:
                        add_page_header()
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

# -------------------------
# APP
# -------------------------
def main():
    """Main function to run the Streamlit application."""
    if st.session_state.get('sidebar_state_reset', False):
        reset_app_state()
        st.session_state['sidebar_state_reset'] = False
        st.rerun()
    
    # CSS PERSONALIZZATO
    st.markdown("""
        <style>
        .big-title { text-align: center; font-size: clamp(18px, 4vw, 38px); font-weight: bold; margin: 15px 0; color: #e63946; }
        .sub-title { font-size: 20px; font-weight: 600; margin-top: 15px; color: d3557; }
        .stButton>button { background-color: #457b9d; color: white; border-radius: 8px; padding: 0.5em 1em; font-weight: bold; }
        .stButton>button:hover { background-color: d3557; color: white; }
        .stDownloadButton>button { background-color: #2a9d8f; color: white; border-radius: 8px; font-weight: bold; }
        .stDownloadButton>button:hover { background-color: #21867a; }
        .stDataFrame { border: 2px solid #f4a261; border-radius: 10px; }
        </style>
    """, unsafe_allow_html=True)
    
    # Connection to MongoDB
    players_collection = init_mongo_connection(st.secrets["MONGO_URI"], "giocatori_subbuteo", "superba_players")
    tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], "TorneiSubbuteo", "Superba")

    df_master = carica_giocatori_da_db(players_collection)
    
    if players_collection is None or tournaments_collection is None:
        st.error("❌ Impossibile avviare l'applicazione. La connessione a MongoDB non è disponibile.")
        return

    # Titolo con stile personalizzato
    if st.session_state.get('calendario_generato', False) and 'nome_torneo' in st.session_state:
        st.markdown(f"<div class='big-title'>🏆 {st.session_state['nome_torneo']}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='big-title'>🏆 Torneo Superba- Gestione Gironi</div>", unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Opzioni Torneo")
        if st.button("🔙 Torna alla schermata iniziale", key='back_to_start_sidebar', use_container_width=True):
            reset_app_state()
            st.rerun()

        if st.session_state.get('calendario_generato', False):
            df = st.session_state['df_torneo']
            classifica = aggiorna_classifica(df)
            
            if classifica is not None and not classifica.empty:
                st.download_button(
                    label="📄 Esporta in PDF",
                    data=esporta_pdf(df, classifica, st.session_state['nome_torneo']),
                    file_name=f"torneo_{st.session_state['nome_torneo']}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            else:
                st.info("Nessuna partita valida. Non è possibile generare un PDF.")
            
            st.markdown("---")
            st.subheader("📊 Visualizza Classifica")
            gironi_sidebar = sorted(df['Girone'].dropna().unique().tolist())
            girone_class_sel = st.selectbox(
                "Seleziona Girone", gironi_sidebar, key="sidebar_classifica_girone"
            )
            
            if st.button("Visualizza Classifica", key="btn_classifica_sidebar"):
                st.subheader(f"Classifica {girone_class_sel}")
                mostra_classifica_stilizzata(classifica, girone_class_sel)
            
            st.markdown("---")
            st.subheader("🔎 Filtra partite")
            filtro_opzione = st.radio("Scegli un filtro", ('Nessuno', 'Giocatore', 'Girone'), key='filtro_selettore')
            
            if filtro_opzione != st.session_state['filtro_attivo']:
                st.session_state['filtro_attivo'] = filtro_opzione
                st.rerun()
            
    # Main Page Content
    if st.session_state.get('calendario_generato', False):
        df = st.session_state['df_torneo']
        
        # Banner vincitori
        if st.session_state.get('torneo_completato', False) and st.session_state.get('classifica_finale') is not None:
            vincitori = []
            df_classifica = st.session_state['classifica_finale']
            for girone in df_classifica['Girone'].unique():
                primo = df_classifica[df_classifica['Girone'] == girone].iloc[0]['Squadra']
                vincitori.append(f"🏅 {girone}: {primo}")
            st.success("🎉 Torneo Completato! Vincitori → " + ", ".join(vincitori))
            
        if st.session_state['filtro_attivo'] == 'Giocatore':
            st.markdown("#### Filtra per Giocatore")
            giocatori = sorted(list(set(df['Casa'].unique().tolist() + df['Ospite'].unique().tolist())))
            giocatore_scelto = st.selectbox("Seleziona un giocatore", [''] + giocatori, key='filtro_giocatore_sel')
            tipo_andata_ritorno = st.radio("Andata/Ritorno", ["Entrambe", "Andata", "Ritorno"], key='tipo_giocatore')
            
            if giocatore_scelto:
                st.subheader(f"Partite da giocare per {giocatore_scelto}")
                df_filtrato = df[(df['Valida'] == False) & ((df['Casa'] == giocatore_scelto) | (df['Ospite'] == giocatore_scelto))]
                
                if tipo_andata_ritorno == "Andata":
                    n_squadre_girone = df['Casa'].nunique() # Count unique teams
                    df_filtrato = df_filtrato[df_filtrato['Giornata'] <= (n_squadre_girone - 1)]
                elif tipo_andata_ritorno == "Ritorno":
                    n_squadre_girone = df['Casa'].nunique()
                    df_filtrato = df_filtrato[df_filtrato['Giornata'] > (n_squadre_girone - 1)]
                
                if not df_filtrato.empty:
                    df_filtrato_show = df_filtrato[['Girone', 'Giornata', 'Casa', 'Ospite']].rename(
                        columns={'Girone': 'Girone', 'Giornata': 'Giornata', 'Casa': 'Casa', 'Ospite': 'Ospite'}
                    )
                    st.dataframe(df_filtrato_show.reset_index(drop=True), use_container_width=True)
                else:
                    st.info("🎉 Nessuna partita da giocare trovata per questo giocatore.")
        
        elif st.session_state['filtro_attivo'] == 'Girone':
            st.markdown("#### Filtra per Girone")
            gironi_disponibili = sorted(df['Girone'].unique().tolist())
            girone_scelto = st.selectbox("Seleziona un girone", gironi_disponibili, key='filtro_girone_sel')
            tipo_andata_ritorno = st.radio("Andata/Ritorno", ["Entrambe", "Andata", "Ritorno"], key='tipo_girone')
            
            st.subheader(f"Partite da giocare nel {girone_scelto}")
            df_filtrato = df[(df['Valida'] == False) & (df['Girone'] == girone_scelto)]
            
            if tipo_andata_ritorno == "Andata":
                n_squadre_girone = len(df[df['Girone'] == girone_scelto]['Casa'].unique())
                df_filtrato = df_filtrato[df_filtrato['Giornata'] <= n_squadre_girone - 1]
            elif tipo_andata_ritorno == "Ritorno":
                n_squadre_girone = len(df[df['Girone'] == girone_scelto]['Casa'].unique())
                df_filtrato = df_filtrato[df_filtrato['Giornata'] > n_squadre_girone - 1]
            
            if not df_filtrato.empty:
                df_filtrato_show = df_filtrato[['Giornata', 'Casa', 'Ospite']].rename(
                    columns={'Giornata': 'Giornata', 'Casa': 'Casa', 'Ospite': 'Ospite'}
                )
                st.dataframe(df_filtrato_show.reset_index(drop=True), use_container_width=True)
            else:
                st.info("🎉 Tutte le partite di questo girone sono state giocate.")
        
        elif st.session_state['filtro_attivo'] == 'Nessuno':
            st.subheader("Navigazione Calendario")
            gironi = sorted(df['Girone'].dropna().unique().tolist())
            
            nuovo_girone = st.selectbox(
                "Seleziona Girone",
                gironi,
                index=gironi.index(st.session_state['girone_sel']) if st.session_state['girone_sel'] in gironi else 0
            )
            
            if nuovo_girone != st.session_state['girone_sel']:
                st.session_state['girone_sel'] = nuovo_girone
                st.session_state['giornata_sel'] = 1
                st.rerun()
            
            giornate_correnti = sorted(df[df['Girone'] == st.session_state['girone_sel']]['Giornata'].dropna().unique().tolist())
            
            modalita_nav = st.radio(
                "Modalità navigazione giornata",
                ["Menu a tendina", "Bottoni"],
                index=0,
                key="modalita_navigazione"
            )
            
            if modalita_nav == "Bottoni":
                navigation_buttons("Giornata", 'giornata_sel', 1, len(giornate_correnti))
            else:
                try:
                    current_index = giornate_correnti.index(st.session_state['giornata_sel'])
                except ValueError:
                    current_index = 0
                    if giornate_correnti:
                      st.session_state['giornata_sel'] = giornate_correnti[0]
            
                nuova_giornata = st.selectbox(
                    "Seleziona Giornata",
                    giornate_correnti,
                    index=current_index,
                    key="giornata_selectbox"
                )
                if nuova_giornata != st.session_state['giornata_sel']:
                    st.session_state['giornata_sel'] = nuova_giornata
                    st.rerun()
            
            mostra_calendario_giornata(df, st.session_state['girone_sel'], st.session_state['giornata_sel'])
            
            if st.button(
                "💾 Salva Risultati Giornata",
                on_click=salva_risultati_giornata,
                args=(tournaments_collection, st.session_state['girone_sel'], st.session_state['giornata_sel']),
                use_container_width=True
            ):
                # Rerun after saving to update the display
                st.rerun()
        
    else:
        st.subheader("📁 Carica un torneo o crea uno nuovo")
        col1, col2 = st.columns(2)
        
        with col1:
            tornei_disponibili = carica_tornei_da_db(tournaments_collection)
            if tornei_disponibili:
                tornei_map = {t['nome_torneo']: str(t['_id']) for t in tornei_disponibili}
                nome_sel = st.selectbox("Seleziona torneo esistente:", list(tornei_map.keys()), key="carica_torneo_sel")
                if st.button("Carica Torneo Selezionato", key="btn_carica_torneo"):
                    st.session_state['tournament_id'] = tornei_map[nome_sel]
                    st.session_state['nome_torneo'] = nome_sel
                    torneo_data = carica_torneo_da_db(tournaments_collection, st.session_state['tournament_id'])
                    if torneo_data:
                        st.session_state['calendario_generato'] = True
                        st.toast("Torneo caricato con successo ✅")
                        # Set initial navigation state based on loaded data
                        if 'calendario' in torneo_data and torneo_data['calendario']:
                            df_temp = pd.DataFrame(torneo_data['calendario'])
                            st.session_state['girone_sel'] = df_temp['Girone'].iloc[0]
                            st.session_state['giornata_sel'] = 1
                        st.rerun()
                    else:
                        st.error("❌ Errore durante il caricamento del torneo. Riprova.")
            else:
                st.info("Nessun torneo salvato trovato su MongoDB.")
        
        with col2:
            st.markdown("---")
            if st.button("➕ Crea Nuovo Torneo", key="btn_crea_nuovo"):
                st.session_state['mostra_form_creazione'] = True
                st.session_state['mostra_assegnazione_squadre'] = False
                st.session_state['mostra_gironi'] = False
                st.rerun()
        
        if st.session_state.get('mostra_form_creazione', False):
            st.markdown("---")
            st.header("Dettagli Nuovo Torneo")
            nome_default = f"TorneoSubbuteo_{datetime.now().strftime('%d%m%Y_%H%M%S')}"
            nome_torneo = st.text_input("📝 Nome del torneo:", value=st.session_state.get("nome_torneo", nome_default), key="nome_torneo_input")
            st.session_state["nome_torneo"] = nome_torneo
            num_gironi = st.number_input("🔢 Numero di gironi", 1, 8, value=st.session_state.get("num_gironi", 2), key="num_gironi_input")
            st.session_state["num_gironi"] = num_gironi
            tipo_calendario = st.selectbox("📅 Tipo calendario", ["Solo andata", "Andata e ritorno"], key="tipo_calendario_input")
            st.session_state["tipo_calendario"] = tipo_calendario
            n_giocatori = st.number_input("👥 Numero giocatori", 4, 32, value=st.session_state.get("n_giocatori", 8), key="n_giocatori_input")
            st.session_state["n_giocatori"] = n_giocatori
            
            st.markdown("### 👥 Seleziona Giocatori")
            amici = df_master['Giocatore'].tolist()
            amici_selezionati = st.multiselect("Seleziona giocatori dal database:", amici, default=st.session_state.get("amici_selezionati", []), key="amici_multiselect")
            st.session_state['amici_selezionati'] = amici_selezionati
            
            num_supplementari = st.session_state["n_giocatori"] - len(amici_selezionati)
            if num_supplementari < 0:
                st.warning(f"⚠️ Hai selezionato più giocatori ({len(amici_selezionati)}) del numero partecipanti ({st.session_state['n_giocatori']}). Riduci la selezione.")
            
            giocatori_supplementari = []
            if 'giocatori_supplementari_list' not in st.session_state:
                st.session_state['giocatori_supplementari_list'] = [''] * max(0, num_supplementari)
            
            st.markdown(f"Giocatori ospiti da aggiungere: **{max(0, num_supplementari)}**")
            for i in range(max(0, num_supplementari)):
                nome_ospite = st.text_input(f"Nome ospite {i+1}", value=st.session_state['giocatori_supplementari_list'][i], key=f"ospite_{i}")
                st.session_state['giocatori_supplementari_list'][i] = nome_ospite
                if nome_ospite:
                    giocatori_supplementari.append(nome_ospite.strip())
            
            if st.button("Conferma Giocatori"):
                giocatori_scelti = amici_selezionati + [g for g in giocatori_supplementari if g]
                if len(giocatori_scelti) != st.session_state['n_giocatori']:
                    st.error(f"❌ Devi selezionare o inserire esattamente {st.session_state['n_giocatori']} giocatori.")
                else:
                    st.session_state['giocatori_selezionati_definitivi'] = giocatori_scelti
                    st.session_state['mostra_assegnazione_squadre'] = True
                    st.session_state['mostra_form_creazione'] = False
                    st.rerun()

        if st.session_state.get('mostra_assegnazione_squadre', False):
            st.markdown("---")
            st.header("Assegna le squadre ai giocatori")
            
            giocatori = st.session_state['giocatori_selezionati_definitivi']
            squadre_db = df_master['Squadra'].dropna().unique().tolist()
            
            st.markdown("#### Squadre disponibili")
            squadre_selezionate = st.multiselect(
                "Seleziona le squadre che parteciperanno:",
                squadre_db,
                default=st.session_state.get('squadre_selezionate', []),
                key="squadre_multiselect"
            )
            st.session_state['squadre_selezionate'] = squadre_selezionate
            
            if len(squadre_selezionate) != len(giocatori):
                st.warning(f"⚠️ Numero di squadre ({len(squadre_selezionate)}) e giocatori ({len(giocatori)}) non corrispondono. Devono essere uguali.")
            
            assegnazioni = st.session_state.get('assegnazioni', {g: '' for g in giocatori})
            
            for giocatore in giocatori:
                assegnazioni[giocatore] = st.selectbox(
                    f"Squadra per {giocatore}",
                    [''] + squadre_selezionate,
                    index=squadre_selezionate.index(assegnazioni[giocatore]) + 1 if assegnazioni[giocatore] in squadre_selezionate else 0,
                    key=f"assegna_{giocatore}"
                )
            st.session_state['assegnazioni'] = assegnazioni

            if st.button("Conferma Assegnazione Squadre"):
                if len(set(assegnazioni.values())) != len(giocatori):
                    st.error("❌ Ogni giocatore deve avere una squadra unica assegnata.")
                elif '' in assegnazioni.values():
                    st.error("❌ Assegna una squadra a ogni giocatore prima di continuare.")
                else:
                    st.session_state['gioc_info'] = {v: k for k, v in assegnazioni.items()}
                    st.session_state['mostra_gironi'] = True
                    st.session_state['mostra_assegnazione_squadre'] = False
                    st.rerun()
        
        if st.session_state.get('mostra_gironi', False):
            st.markdown("---")
            st.header("Creazione Gironi")
            
            giocatori = st.session_state['giocatori_selezionati_definitivi']
            squadre_assegnate = list(st.session_state['assegnazioni'].values())
            
            modalita_gironi = st.radio("Modalità creazione gironi:", ["Automatica", "Manuale"], key="modalita_gironi")
            st.session_state['modalita_gironi'] = modalita_gironi
            
            gironi_manuali = st.session_state.get('gironi_manuali', {f"Girone {i+1}": [] for i in range(st.session_state['num_gironi'])})
            
            if st.session_state['modalita_gironi'] == "Manuale":
                st.markdown("#### Configurazione manuale dei gironi")
                
                squadre_rimanenti = squadre_assegnate[:]
                
                for i in range(st.session_state['num_gironi']):
                    girone_nome = f"Girone {i+1}"
                    
                    squadre_girone = st.multiselect(
                        f"Seleziona le squadre per {girone_nome}",
                        options=squadre_rimanenti,
                        default=gironi_manuali.get(girone_nome, []),
                        key=f"manual_girone_{i}"
                    )
                    
                    gironi_manuali[girone_nome] = squadre_girone
                    
                st.session_state['gironi_manuali'] = gironi_manuali
                
                tutte_le_squadre_assegnate = [s for sublist in gironi_manuali.values() for s in sublist]
                st.session_state['gironi_manuali_completi'] = set(tutte_le_squadre_assegnate) == set(squadre_assegnate) and len(tutte_le_squadre_assegnate) == len(squadre_assegnate)
                
                if not st.session_state['gironi_manuali_completi']:
                    st.warning("⚠️ Per procedere, tutte le squadre devono essere assegnate e ciascuna deve essere in un solo girone.")
                else:
                    st.success("✅ Tutti i gironi manuali sono stati completati correttamente.")
            
            if st.button("Genera Calendario"):
                gironi_definitivi = []
                if st.session_state['modalita_gironi'] == "Manuale":
                    if st.session_state['gironi_manuali_completi']:
                        gironi_definitivi = [list(v) for v in st.session_state['gironi_manuali'].values()]
                    else:
                        st.error("❌ Devi prima completare l'assegnazione manuale dei gironi.")
                        st.stop()
                else: # Modalità automatica
                    squadre_shuffled = squadre_assegnate[:]
                    random.shuffle(squadre_shuffled)
                    
                    size_base = len(squadre_shuffled) // st.session_state['num_gironi']
                    resto = len(squadre_shuffled) % st.session_state['num_gironi']
                    
                    start_idx = 0
                    for i in range(st.session_state['num_gironi']):
                        size_girone = size_base + (1 if i < resto else 0)
                        gironi_definitivi.append(squadre_shuffled[start_idx:start_idx + size_girone])
                        start_idx += size_girone
                
                if gironi_definitivi:
                    try:
                        df_torneo = genera_calendario_from_list(gironi_definitivi, tipo=st.session_state['tipo_calendario'])
                        
                        # Salva il torneo su DB
                        tid = salva_torneo_su_db(tournaments_collection, df_torneo, st.session_state['nome_torneo'])
                        
                        if tid:
                            st.session_state['df_torneo'] = df_torneo
                            st.session_state['tournament_id'] = str(tid)
                            st.session_state['calendario_generato'] = True
                            st.toast("Calendario generato e salvato su MongoDB ✅")
                            st.rerun()
                        else:
                            st.error("❌ Errore: Il salvataggio su MongoDB è fallito. Controlla la connessione al database.")
                    
                    except Exception as e:
                        st.error(f"❌ Errore critico durante il salvataggio: {e}")

if __name__ == "__main__":
    main()
