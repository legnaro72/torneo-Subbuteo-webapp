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
# FUNZIONI UTILI
# -------------------------

@st.cache_resource
def get_db_client():
    """Connessione al database MongoDB."""
    uri = st.secrets["mongo"]["uri"]
    return MongoClient(uri, server_api=ServerApi('1'))

def create_df_torneo():
    """Crea e inizializza il DataFrame del torneo."""
    columns = [
        'Giocatore 1', 'Squadra 1', 'Punti 1', 'Punti 2', 'Squadra 2', 'Giocatore 2', 'Girone',
        'Giornata', 'Concluso', 'DataCreazione', 'IDPartita'
    ]
    st.session_state['df_torneo'] = pd.DataFrame(columns=columns)

def generate_calendario(players, n_gironi):
    """Genera il calendario delle partite per il torneo."""
    st.session_state['df_torneo'] = pd.DataFrame() # Inizializza un DataFrame vuoto
    st.session_state['calendario_generato'] = True

def assegna_squadre(num_gironi, giocatori_selezionati):
    """Assegna le squadre casualmente ai giocatori e divide in gironi."""
    st.session_state['mostra_gironi'] = True

def salva_torneo_db():
    """Salva il torneo nel database MongoDB."""
    if not st.session_state['df_torneo'].empty:
        try:
            db_client = get_db_client()
            db = db_client.Superba_Cup
            collection = db.Tornei
            
            nome_torneo = st.session_state.get('nome_torneo_selezionato', f"Torneo_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            # Prepara i dati per il salvataggio
            dati_torneo = {
                "Nome Torneo": nome_torneo,
                "Data Creazione": datetime.now(),
                "Partite": st.session_state['df_torneo'].to_dict('records')
            }
            
            # Se esiste già un torneo con questo nome, lo aggiorna, altrimenti ne crea uno nuovo
            if collection.find_one({"Nome Torneo": nome_torneo}):
                collection.update_one({"Nome Torneo": nome_torneo}, {"$set": dati_torneo})
                st.success(f"Torneo '{nome_torneo}' aggiornato con successo nel database.")
            else:
                collection.insert_one(dati_torneo)
                st.session_state['nome_torneo_selezionato'] = nome_torneo
                st.success(f"Torneo '{nome_torneo}' salvato con successo nel database.")
            
        except Exception as e:
            st.error(f"Errore durante il salvataggio del torneo: {e}")

def carica_tornei_db():
    """Carica la lista dei tornei salvati nel database."""
    try:
        db_client = get_db_client()
        db = db_client.Superba_Cup
        collection = db.Tornei
        tornei = list(collection.find({}, {"Nome Torneo": 1}))
        return tornei
    except Exception as e:
        st.error(f"Errore durante il caricamento dei tornei dal database: {e}")
        return []

def carica_torneo_selezionato(nome_torneo_selezionato):
    """Carica un torneo selezionato dal database."""
    try:
        db_client = get_db_client()
        db = db_client.Superba_Cup
        collection = db.Tornei
        
        torneo_caricato = collection.find_one({"Nome Torneo": nome_torneo_selezionato})
        if torneo_caricato:
            st.session_state['df_torneo'] = pd.DataFrame(torneo_caricato['Partite'])
            # Aggiorna lo stato per visualizzare il torneo caricato
            st.session_state['mostra_form_creazione'] = False
            st.session_state['mostra_gironi'] = True
            st.session_state['calendario_generato'] = True
            
            # Resetta lo stato di navigazione
            st.session_state['giornata_sel'] = 1
            st.session_state['girone_sel'] = st.session_state['df_torneo']['Girone'].unique()[0]
            st.rerun()
            st.success(f"Torneo '{nome_torneo_selezionato}' caricato con successo.")
        else:
            st.warning("Torneo non trovato nel database.")
    except Exception as e:
        st.error(f"Errore durante il caricamento del torneo selezionato: {e}")

def get_classifica_girone(girone, df_gironi):
    """Calcola la classifica per un girone specifico."""
    df_girone = df_gironi[df_gironi['Girone'] == girone]
    classifica = {}
    for _, row in df_girone.iterrows():
        g1, g2 = row['Giocatore 1'], row['Giocatore 2']
        p1, p2 = row['Punti 1'], row['Punti 2']
        if g1 not in classifica: classifica[g1] = {'Pt': 0, 'V': 0, 'N': 0, 'P': 0, 'GF': 0, 'GS': 0}
        if g2 not in classifica: classifica[g2] = {'Pt': 0, 'V': 0, 'N': 0, 'P': 0, 'GF': 0, 'GS': 0}

        if pd.notna(p1) and pd.notna(p2):
            classifica[g1]['GF'] += p1
            classifica[g1]['GS'] += p2
            classifica[g2]['GF'] += p2
            classifica[g2]['GS'] += p1

            if p1 > p2:
                classifica[g1]['Pt'] += 3
                classifica[g1]['V'] += 1
                classifica[g2]['P'] += 1
            elif p1 < p2:
                classifica[g2]['Pt'] += 3
                classifica[g2]['V'] += 1
                classifica[g1]['P'] += 1
            else:
                classifica[g1]['Pt'] += 1
                classifica[g2]['Pt'] += 1
                classifica[g1]['N'] += 1
                classifica[g2]['N'] += 1
    
    df_classifica = pd.DataFrame.from_dict(classifica, orient='index')
    df_classifica.index.name = 'Giocatore'
    if not df_classifica.empty:
        df_classifica['DR'] = df_classifica['GF'] - df_classifica['GS']
        df_classifica = df_classifica.sort_values(by=['Pt', 'DR', 'GF'], ascending=[False, False, False])

    return df_classifica

def check_torneo_completo_e_aggiorna():
    """Controlla se tutte le partite sono concluse e aggiorna il database."""
    if 'df_torneo' in st.session_state and not st.session_state['df_torneo'].empty:
        if st.session_state['df_torneo']['Concluso'].all():
            st.session_state['torneo_completato'] = True
            
            db_client = get_db_client()
            db = db_client.Superba_Cup
            collection = db.Tornei
            current_name = st.session_state.get('nome_torneo_selezionato', 'Nuovo Torneo')
            if not current_name.startswith("Completato_"):
                new_name = f"Completato_{current_name}"
                collection.update_one(
                    {"Nome Torneo": current_name},
                    {"$set": {"Nome Torneo": new_name}}
                )
                st.session_state['nome_torneo_selezionato'] = new_name
            
            vincitori = {}
            for girone in st.session_state['gironi_unici']:
                classifica = get_classifica_girone(girone, st.session_state['df_torneo'])
                if not classifica.empty:
                    vincitore = classifica.index[0]
                    vincitori[girone] = vincitore
            st.session_state['vincitori'] = vincitori
            st.rerun()

# -------------------------
# STATO
# -------------------------

if 'df_torneo' not in st.session_state:
    create_df_torneo()

if 'vincitori' not in st.session_state:
    st.session_state['vincitori'] = {}
    
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
    'torneo_completato': False,
    'filtro_attivo': 'Nessuno'
}
for k, v in DEFAULT_STATE.items():
    if k not in st.session_state:
        st.session_state[k] = v

if 'df_torneo' in st.session_state and not st.session_state['df_torneo'].empty:
    st.session_state['gironi_unici'] = sorted(st.session_state['df_torneo']['Girone'].unique())
    st.session_state['giornate_unici'] = sorted(st.session_state['df_torneo']['Giornata'].unique())
    # Sincronizza lo stato 'giornata_sel' con i dati caricati
    if st.session_state['giornata_sel'] not in st.session_state['giornate_unici']:
        st.session_state['giornata_sel'] = st.session_state['giornate_unici'][0]

# -------------------------
# INTERFACCIA UTENTE
# -------------------------

st.title("⚽ Campionato/Torneo Subbuteo")

# -------------------------
# SIDEBAR
# -------------------------

with st.sidebar:
    st.header("Menu")
    
    st.button("Nuovo Torneo", on_click=lambda: (
        st.session_state.update(DEFAULT_STATE),
        create_df_torneo(),
        st.session_state.update({'mostra_form_creazione': True, 'torneo_completato': False})
    ))
    
    if 'tornei_db' not in st.session_state:
        st.session_state['tornei_db'] = carica_tornei_db()
        
    tornei_db_nomi = [t['Nome Torneo'] for t in st.session_state['tornei_db']]
    nome_torneo_selezionato = st.selectbox("Carica Torneo esistente", [''] + tornei_db_nomi, key="nome_torneo_selezionato")
    if nome_torneo_selezionato:
        carica_torneo_selezionato(nome_torneo_selezionato)

    if not st.session_state['df_torneo'].empty:
        if st.button("Mostra Classifica"):
            st.session_state['filtro_attivo'] = 'Classifica'
    
    if st.session_state['filtro_attivo'] == 'Classifica' and 'gironi_unici' in st.session_state:
        st.session_state['girone_classifica_sel'] = st.selectbox("Seleziona Girone per Classifica", st.session_state['gironi_unici'])

# -------------------------
# VISUALIZZAZIONE PRINCIPALE
# -------------------------

if st.session_state.get('torneo_completato', False) and st.session_state.get('vincitori'):
    st.balloons()
    st.header("🏆 Torneo Completato! 🏆")
    for girone, vincitore in st.session_state['vincitori'].items():
        st.subheader(f"🥇 Vincitore del {girone}: **{vincitore}**")
    
# Form di creazione torneo
if st.session_state['mostra_form_creazione']:
    with st.expander("Crea un nuovo torneo"):
        st.write("Inserisci i dettagli per il tuo nuovo torneo.")
        # ... (Logica del form di creazione)
        # Esempio:
        numero_gironi = st.number_input("Numero di gironi", min_value=1, value=1)
        giocatori = st.text_area("Inserisci i nomi dei giocatori, separati da una virgola")
        if st.button("Genera Calendario"):
            players_list = [p.strip() for p in giocatori.split(',') if p.strip()]
            if players_list:
                generate_calendario(players_list, numero_gironi)
                st.success("Calendario generato! Procedi con l'assegnazione delle squadre.")
                assegna_squadre(numero_gironi, players_list)
            else:
                st.error("Inserisci almeno due giocatori per creare un torneo.")

# Mostra i gironi e il calendario
if st.session_state['mostra_gironi'] and not st.session_state['df_torneo'].empty:
    
    check_torneo_completo_e_aggiorna()
    
    if not st.session_state.get('torneo_completato', False) and st.session_state['filtro_attivo'] != 'Classifica':
        st.header(f"Torneo: {st.session_state.get('nome_torneo_selezionato', 'Nuovo Torneo')}")
        
        col1_filtri, col2_filtri = st.columns([1, 1])
        with col1_filtri:
            st.session_state['girone_sel'] = st.selectbox("Seleziona Girone", st.session_state['gironi_unici'], key='girone_selectbox')
        with col2_filtri:
            nav_mode = st.radio(
                "Modalità Navigazione Giornate",
                ("Menu a tendina", "Bottoni"),
                index=0 if not st.session_state.get('usa_bottoni', False) else 1
            )
            st.session_state['usa_bottoni'] = (nav_mode == "Bottoni")
        
        if st.session_state['usa_bottoni']:
            col1_nav, col2_nav, col3_nav = st.columns([1, 1, 1])
            with col1_nav:
                if st.button("<< Precedente"):
                    if st.session_state['giornata_sel'] > 1:
                        st.session_state['giornata_sel'] -= 1
                        st.rerun()
            with col2_nav:
                st.session_state['giornata_sel'] = st.number_input(
                    "Giornata",
                    min_value=1,
                    max_value=len(st.session_state['giornate_unici']),
                    value=st.session_state['giornata_sel'],
                    key="giornata_input"
                )
            with col3_nav:
                if st.button("Successiva >>"):
                    if st.session_state['giornata_sel'] < len(st.session_state['giornate_unici']):
                        st.session_state['giornata_sel'] += 1
                        st.rerun()
        else:
            st.session_state['giornata_sel'] = st.selectbox("Seleziona Giornata", st.session_state['giornate_unici'], key='giornata_selectbox')

        df_display = st.session_state['df_torneo'][
            (st.session_state['df_torneo']['Girone'] == st.session_state['girone_sel']) &
            (st.session_state['df_torneo']['Giornata'] == st.session_state['giornata_sel'])
        ].copy()
        
        if not df_display.empty:
            for i, row in df_display.iterrows():
                with st.container(border=True):
                    col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 3])
                    
                    with col1:
                        st.write(f"**{row['Giocatore 1']}**")
                        st.write(f"⚽ {row['Squadra 1']}")
                    
                    with col2:
                        punti1 = st.number_input(
                            "",
                            min_value=0,
                            value=int(row['Punti 1']) if pd.notna(row['Punti 1']) else 0,
                            key=f"p1_{i}"
                        )
                    
                    with col3:
                        st.markdown("<h2 style='text-align: center; color: grey;'>-</h2>", unsafe_allow_html=True)
                    
                    with col4:
                        punti2 = st.number_input(
                            "",
                            min_value=0,
                            value=int(row['Punti 2']) if pd.notna(row['Punti 2']) else 0,
                            key=f"p2_{i}"
                        )
                    
                    with col5:
                        st.write(f"**{row['Giocatore 2']}**")
                        st.write(f"⚽ {row['Squadra 2']}")
                    
                    btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 1])
                    with btn_col2:
                        if st.button("Convalida", key=f"btn_{i}"):
                            st.session_state['df_torneo'].loc[i, 'Punti 1'] = punti1
                            st.session_state['df_torneo'].loc[i, 'Punti 2'] = punti2
                            st.session_state['df_torneo'].loc[i, 'Concluso'] = True
                            st.success(f"Risultato convalidato per la partita {row['Giocatore 1']} vs {row['Giocatore 2']}")
                            st.rerun()
                            
        st.divider()

    if st.session_state['filtro_attivo'] == 'Classifica':
        st.header(f"Classifica - {st.session_state['girone_classifica_sel']}")
        df_classifica = get_classifica_girone(st.session_state['girone_classifica_sel'], st.session_state['df_torneo'])
        st.dataframe(df_classifica, use_container_width=True)
        st.divider()
        st.button("Nascondi Classifica", on_click=lambda: st.session_state.update({'filtro_attivo': 'Nessuno'}))
        
    st.button("Salva Torneo su DB", on_click=salva_torneo_db)
