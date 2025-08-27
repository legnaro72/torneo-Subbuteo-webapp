import streamlit as st
import pandas as pd
import math
import os
import re
from fpdf import FPDF
import base64
from io import BytesIO
import json
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId

# ==============================================================================
# ✨ Configurazione e stile di pagina (con nuove emoji e colori)
# ==============================================================================
st.set_page_config(
    page_title="Fasi Finali",
    layout="wide",
    page_icon="⚽"
)

st.markdown("""
<style>
/* Stile base per testi minori */
.small-muted {
    font-size: 0.9rem;
    opacity: 0.8;
}
/* Linea divisoria più sottile */
hr {
    margin: 0.6rem 0 1rem 0;
}

/* Stile per il titolo grande, ora con gradiente */
.main-title {
    font-size: 2.5rem;
    font-weight: bold;
    text-align: center;
    margin-bottom: 2rem;
    background: linear-gradient(45deg, #FF4B4B, #FF0000);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: bounce 1s ease-in-out infinite alternate;
}

/* Animazione per il titolo */
@keyframes bounce {
  from {
    transform: translateY(0px);
  }
  to {
    transform: translateY(-5px);
  }
}

/* Stile per i sub-header */
h3 {
    color: #008080; /* Turchese scuro */
    font-weight: bold;
}
/* Stile per i pulsanti */
.stButton>button {
    background-color: #4CAF50;
    color: white;
    font-weight: bold;
    border-radius: 12px;
    padding: 10px 20px;
    border: 2px solid #4CAF50;
    transition: all 0.3s ease;
}
.stButton>button:hover {
    background-color: #45a049;
    border-color: #45a049;
    transform: scale(1.05);
}
.stDownloadButton>button {
    background-color: #007BFF;
    color: white;
    font-weight: bold;
    border-radius: 12px;
    padding: 10px 20px;
    border: 2px solid #007BFF;
    transition: all 0.3s ease;
}
.stDownloadButton>button:hover {
    background-color: #0056b3;
    border-color: #0056b3;
    transform: scale(1.05);
}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 🛠️ Utilità comuni
# ==============================================================================
REQUIRED_COLS = ['Girone', 'Giornata', 'Casa', 'Ospite', 'GolCasa', 'GolOspite', 'Valida']

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
    
    # FIX: Aggiunto per gestire il TypeError
    partite['Casa'] = partite['Casa'].astype(str).fillna('')
    partite['Ospite'] = partite['Ospite'].astype(str).fillna('')
    
    squadre = pd.unique(partite[['Casa', 'Ospite']].values.ravel())
    stats = {s: {'Punti':0,'V':0,'P':0,'S':0,'GF':0,'GS':0,'DR':0} for s in squadre}
    for _, r in partite.iterrows():
        casa, osp = r['Casa'], r['Ospite']
        gc, go = int(r['GolCasa']), int(r['GolOspite'])
        stats[casa]['GF'] += gc; stats[casa]['GS'] += go
        stats[osp]['GF'] += go; stats[osp]['GS'] += gc
        if gc > go:
            stats[casa]['Punti'] += 2; stats[casa]['V'] += 1; stats[osp]['S'] += 1
        elif gc < go:
            stats[osp]['Punti'] += 2; stats[osp]['V'] += 1; stats[casa]['S'] += 1
        else:
            stats[casa]['Punti'] += 1; stats[osp]['Punti'] += 1
        stats[casa]['P'] += 1; stats[osp]['P'] += 1
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

def bilanciato_ko_seed(squadre_ordinate: list[str]) -> list[tuple[str, str]]:
    """Genera accoppiamenti bilanciati per KO: 1ª vs ultima, 2ª vs penultima, ecc."""
    n = len(squadre_ordinate)
    matches = []
    for i in range(n // 2):
        matches.append((squadre_ordinate[i], squadre_ordinate[n - 1 - i]))
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
    rows = []
    for g in range(1, giornate + 1):
        for i in range(metà):
            a, b = teams[i], teams[n - 1 - i]
            if a != bye and b != bye:
                if g % 2 == 0:
                    rows.append({'Giornata': g, 'Casa': b, 'Ospite': a})
                else:
                    rows.append({'Giornata': g, 'Casa': a, 'Ospite': b})
        teams.insert(1, teams.pop())
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
        return pd.DataFrame(columns=['Squadra', 'Punti', 'V', 'P', 'S', 'GF', 'GS', 'DR'])
    partite_validate = df[to_bool_series(df['Valida'])].copy()
    if partite_validate.empty:
        return pd.DataFrame(columns=['Squadra', 'Punti', 'V', 'P', 'S', 'GF', 'GS', 'DR'])
    partite_validate.loc[:, 'GolCasa'] = pd.to_numeric(partite_validate['GolCasa'], errors='coerce').fillna(0).astype(int)
    partite_validate.loc[:, 'GolOspite'] = pd.to_numeric(partite_validate['GolOspite'], errors='coerce').fillna(0).astype(int)
    squadre = pd.unique(partite_validate[['Casa', 'Ospite']].values.ravel())
    stats = {s: {'Punti':0,'V':0,'P':0,'S':0,'GF':0,'GS':0,'DR':0} for s in squadre}
    for _, r in partite_validate.iterrows():
        casa, osp = r['Casa'], r['Ospite']
        gc, go = int(r['GolCasa']), int(r['GolOspite'])
        stats[casa]['GF'] += gc; stats[casa]['GS'] += go
        stats[osp]['GF'] += go; stats[osp]['GS'] += gc
        if gc > go:
            stats[casa]['Punti'] += 2; stats[casa]['V'] += 1; stats[osp]['S'] += 1; stats[casa]['P'] += 1
        elif gc < go:
            stats[osp]['Punti'] += 2; stats[osp]['V'] += 1; stats[casa]['S'] += 1; stats[osp]['P'] += 1
        else:
            stats[casa]['Punti'] += 1; stats[osp]['Punti'] += 1; stats[casa]['P'] += 1; stats[osp]['P'] += 1
    rows = []
    for s, d in stats.items():
        d['DR'] = d['GF'] - d['GS']
        rows.append({'Squadra': s, **d})
    dfc = pd.DataFrame(rows)
    if dfc.empty:
        return dfc
    return dfc.sort_values(by=['Punti','DR','GF','V','Squadra'], ascending=[False, False, False, False, True]).reset_index(drop=True)
def get_pdf_download_link(pdf_bytes: bytes, filename: str, text: str):
    """Genera un link per scaricare un file PDF."""
    b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
    return f'<a href="data:application/pdf;base64,{b64_pdf}" download="{filename}">{text}</a>'
def crea_pdf_classifica(df_classifica: pd.DataFrame, titolo: str) -> bytes:
    """Crea un PDF con la classifica."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, titolo, 0, 1, 'C')
    pdf.set_font("Arial", 'B', 12)
    col_widths = [20, 40, 15, 15, 15, 15, 15, 15, 15]
    headers = ["Pos", "Squadra", "Punti", "V", "P", "S", "GF", "GS", "DR"]
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 7, h, 1, 0, 'C')
    pdf.ln()
    pdf.set_font("Arial", '', 10)
    for _, r in df_classifica.iterrows():
        for i, c in enumerate(headers):
            val = r.get(c, "N/A")
            if c == 'Pos':
                val = int(val)
            pdf.cell(col_widths[i], 7, str(val), 1, 0, 'C')
        pdf.ln()
    return pdf.output(dest='S').encode('latin1')
def crea_pdf_calendario(df_calendario: pd.DataFrame, titolo: str) -> bytes:
    """Crea un PDF con il calendario."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, titolo, 0, 1, 'C')
    pdf.set_font("Arial", 'B', 12)
    col_widths = [20, 40, 40, 15, 15, 15]
    headers = ["Giornata", "Casa", "Ospite", "Gol Casa", "Gol Ospite", "Valida"]
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 7, h, 1, 0, 'C')
    pdf.ln()
    pdf.set_font("Arial", '', 10)
    for _, r in df_calendario.iterrows():
        for i, c in enumerate(headers):
            val = r.get(c, "N/A")
            pdf.cell(col_widths[i], 7, str(val), 1, 0, 'C')
        pdf.ln()
    return pdf.output(dest='S').encode('latin1')

# ==============================================================================
# 🗃️ Gestione dello stato e inizializzazione
# ==============================================================================
if 'df_torneo_preliminare' not in st.session_state:
    st.session_state['df_torneo_preliminare'] = None
if 'tournament_id' not in st.session_state:
    st.session_state['tournament_id'] = None
if 'tournament_name' not in st.session_state:
    st.session_state['tournament_name'] = None
if 'df_finale_gironi' not in st.session_state:
    st.session_state['df_finale_gironi'] = None
if 'gironi_num' not in st.session_state:
    st.session_state['gironi_num'] = None
if 'n_finalisti' not in st.session_state:
    st.session_state['n_finalisti'] = None
if 'gironi_ar' not in st.session_state:
    st.session_state['gironi_ar'] = None
if 'gironi_seed' not in st.session_state:
    st.session_state['gironi_seed'] = None
if 'giornate_mode' not in st.session_state:
    st.session_state['giornate_mode'] = None
if 'giornata_nav_mode' not in st.session_state:
    st.session_state['giornata_nav_mode'] = 'Menu a tendina'

# ==============================================================================
# ⚙️ FUNZIONI DI GESTIONE DATI SU MONGO (COPIATE DA alldbsuperbanew.py)
# ==============================================================================
@st.cache_resource
def init_mongo_connection(uri, db_name, collection_name, show_ok: bool = False):
    """ Inizializza la connessione a MongoDB. """
    try:
        client = MongoClient(uri, server_api=ServerApi('1'))
        db = client.get_database(db_name)
        col = db.get_collection(collection_name)
        _ = col.find_one({})
        if show_ok:
            st.success("✅ Connessione a MongoDB riuscita!")
        return col
    except Exception as e:
        st.error(f"❌ Impossibile connettersi a MongoDB: {e}")
        return None

def carica_tornei_da_db(tournaments_collection):
    """ Carica la lista dei tornei disponibili dal DB. """
    try:
        if tournaments_collection is None:
            return []
        tornei = list(tournaments_collection.find({}, {"nome_torneo": 1, "tipo_torneo": 1, "data_creazione": 1}))
        return tornei
    except Exception as e:
        st.error(f"❌ Errore nel caricamento dei tornei dal DB: {e}")
        return []

def salva_torneo_su_db(tournaments_collection, nome_torneo, df_calendario, tipo_torneo, rounds_ko=None, parent_id=None):
    """ Salva un nuovo torneo o aggiorna uno esistente su DB. """
    try:
        calendario_json = df_calendario.to_json(orient='records')
        data = {
            "nome_torneo": nome_torneo,
            "tipo_torneo": tipo_torneo,
            "calendario": json.loads(calendario_json),
            "data_creazione": pd.Timestamp.now().isoformat(),
        }
        if rounds_ko is not None:
            data['rounds_ko'] = [r.to_dict(orient='records') for r in rounds_ko]
        if parent_id:
            data['parent_id'] = parent_id
        result = tournaments_collection.insert_one(data)
        st.success(f"✅ Torneo '{nome_torneo}' salvato con successo! ID: {result.inserted_id}")
        return result.inserted_id
    except Exception as e:
        st.error(f"❌ Errore nel salvataggio del torneo: {e}")
        return None

def carica_torneo_da_db(tournaments_collection, tournament_id):
    """ Carica un singolo torneo dal DB. """
    try:
        return tournaments_collection.find_one({"_id": ObjectId(tournament_id)})
    except Exception as e:
        st.error(f"❌ Errore nel caricamento del torneo con ID {tournament_id}: {e}")
        return None

def salva_risultati_ko(is_final_game=False):
    """ Aggiorna i risultati del torneo KO nel DB e prepara il prossimo round. """
    tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], db_name, col_name)
    if tournaments_collection is None:
        st.error("❌ Errore di connessione al DB.")
        return

    # Sostituzione per il DataFrame in session_state, conservando la storia
    if 'rounds_ko' not in st.session_state:
        st.error("❌ Dati KO in sessione non validi.")
        return

    # Aggiorna l'ultimo round con i dati correnti
    last_round_df = st.session_state['rounds_ko'][-1].copy()
    all_valid = True
    for idx, row in last_round_df.iterrows():
        valida = st.session_state.get(f"ko_valida_{idx}", False)
        if valida:
            gol_a = st.session_state.get(f"ko_gol_a_{idx}")
            gol_b = st.session_state.get(f"ko_gol_b_{idx}")
            last_round_df.at[idx, 'GolA'] = gol_a
            last_round_df.at[idx, 'GolB'] = gol_b
            last_round_df.at[idx, 'Valida'] = True
        else:
            all_valid = False
            break

    if not all_valid and not is_final_game:
        st.warning("⚠️ Per poter generare il prossimo round, devi validare tutti i risultati delle partite attuali.")
        return
        
    st.session_state['rounds_ko'][-1] = last_round_df
    
    # Salva lo stato attuale su DB
    rounds_ko_serializable = [r.to_dict(orient='records') for r in st.session_state['rounds_ko']]
    try:
        tournaments_collection.update_one(
            {"_id": ObjectId(st.session_state['tournament_id'])},
            {"$set": {"rounds_ko": rounds_ko_serializable}}
        )
        st.success("✅ Risultati salvati con successo!")
    except Exception as e:
        st.error(f"❌ Errore nel salvataggio dei risultati su DB: {e}")
        return
    
    # Se tutte le partite sono valide e non è la finale, genera il prossimo round
    if all_valid and not is_final_game:
        vincitori = []
        for _, row in last_round_df.iterrows():
            if pd.to_numeric(row['GolA']) > pd.to_numeric(row['GolB']):
                vincitori.append(row['SquadraA'])
            else:
                vincitori.append(row['SquadraB'])

        # Se ci sono vincitori, genera il prossimo round
        if vincitori:
            prossimo_round_df = pd.DataFrame({
                'SquadraA': vincitori[::2],
                'SquadraB': vincitori[1::2],
                'GolA': None,
                'GolB': None,
                'Valida': False,
                'Round': len(st.session_state['rounds_ko'])
            })
            if not prossimo_round_df.empty:
                st.session_state['rounds_ko'].append(prossimo_round_df)
                st.rerun()

def delete_torneo_da_db(tournaments_collection, tournament_id):
    """ Elimina un torneo dal DB. """
    try:
        tournaments_collection.delete_one({"_id": ObjectId(tournament_id)})
        return True
    except Exception as e:
        st.error(f"❌ Errore nell'eliminazione del torneo: {e}")
        return False

def rename_torneo_in_db(tournaments_collection, tournament_id, new_name):
    """ Rinomina un torneo nel DB. """
    if tournaments_collection is None:
        return False
    try:
        tournaments_collection.update_one(
            {"_id": ObjectId(tournament_id)},
            {"$set": {"nome_torneo": new_name}}
        )
        return True
    except Exception as e:
        st.error(f"❌ Errore nella ridenominazione del torneo: {e}")
        return False
    
def clone_torneo_in_db(tournaments_collection, tournament_id, new_name):
    """ Clona un torneo esistente e lo salva con un nuovo nome. """
    torneo_data = carica_torneo_da_db(tournaments_collection, tournament_id)
    if torneo_data:
        del torneo_data['_id']  # Rimuove l'ID per generare un nuovo documento
        torneo_data['nome_torneo'] = new_name
        torneo_data['data_creazione'] = pd.Timestamp.now().isoformat()
        try:
            result = tournaments_collection.insert_one(torneo_data)
            return result.inserted_id
        except Exception as e:
            st.error(f"❌ Errore nella clonazione del torneo: {e}")
            return None
    return None

# ==============================================================================
# ⚽ Header dinamico
# ==============================================================================
if 'tournament_name' in st.session_state and not st.session_state['ui_show_pre']:
    cleaned_name = re.sub(r'\(.*\)', '', st.session_state["tournament_name"]).strip()
    st.markdown(f'<h1 class="main-title">🏆 FASE FINALE {cleaned_name}</h1>', unsafe_allow_html=True)
else:
    st.title("⚽ Fasi Finali")
if 'tournament_name' in st.session_state and st.session_state['ui_show_pre']:
    st.markdown(f"### 🏷️ **{st.session_state['tournament_name']}**")
    st.divider()

# ==============================================================================
# 🚀 Funzioni di navigazione
# ==============================================================================
def reset_state():
    for key in ['df_torneo_preliminare', 'tournament_id', 'tournament_name', 'df_finale_gironi',
                'gironi_num', 'n_finalisti', 'gironi_ar', 'gironi_seed', 'giornate_mode', 'rounds_ko',
                'ui_show_pre']:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

def reset_to_setup():
    st.session_state['ui_show_pre'] = True
    st.session_state['tournament_id'] = None
    st.session_state['tournament_name'] = None
    st.rerun()

# ==============================================================================
# 🎯 Funzione principale per la UI
# ==============================================================================
db_name = st.secrets.get("DB_NAME", "FasiFinali")
col_name = st.secrets.get("COLLECTION_NAME", "Tornei")
tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], db_name, col_name)

if 'ui_show_pre' not in st.session_state:
    st.session_state['ui_show_pre'] = True
    st.session_state['giornate_mode'] = None

if st.session_state['ui_show_pre']:
    st.markdown("### 🛠️ Configurazione Torneo")
    opzione_selezione = st.radio(
        "Scegli un'opzione:",
        ["Creare una nuova fase finale da un torneo preliminare", "Continuare una fase finale esistente"],
        index=None
    )
    st.divider()
    if opzione_selezione == "Creare una nuova fase finale da un torneo preliminare":
        tournaments = carica_tornei_da_db(tournaments_collection)
        tornei_preliminari = [t for t in tournaments if t.get('tipo_torneo') == 'Gironi']
        nomi_tornei = {t['nome_torneo']: str(t['_id']) for t in tornei_preliminari}
        nome_scelto = st.selectbox("Seleziona il torneo preliminare:", [""] + list(nomi_tornei.keys()), index=0)
        if nome_scelto:
            tournament_id = nomi_tornei[nome_scelto]
            torneo_data = carica_torneo_da_db(tournaments_collection, tournament_id)
            if torneo_data:
                st.session_state['df_torneo_preliminare'] = pd.DataFrame(torneo_data['calendario'])
                st.session_state['tournament_id'] = tournament_id
                st.session_state['tournament_name'] = nome_scelto
                st.session_state['ui_show_pre'] = False
                st.rerun()
            else:
                st.error("❌ Errore nel caricamento del torneo. Riprova.")
    elif opzione_selezione == "Continuare una fase finale esistente":
        tournaments = carica_tornei_da_db(tournaments_collection)
        tornei_finali = [t for t in tournaments if t.get('tipo_torneo') in ['Gironi Finali', 'Eliminazione Diretta']]
        nomi_tornei_finali = {t['nome_torneo']: str(t['_id']) for t in tornei_finali}
        if not nomi_tornei_finali:
            st.info("Nessun torneo di fase finale trovato. Creane uno per iniziare.")
        else:
            nome_scelto = st.selectbox("Seleziona la fase finale da continuare:", [""] + list(nomi_tornei_finali.keys()), index=0)
            if nome_scelto:
                tournament_id = nomi_tornei_finali[nome_scelto]
                torneo_data = carica_torneo_da_db(tournaments_collection, tournament_id)
                if torneo_data:
                    st.session_state['tournament_id'] = tournament_id
                    st.session_state['tournament_name'] = nome_scelto
                    st.session_state['ui_show_pre'] = False
                    st.session_state['giornate_mode'] = 'Gironi' if torneo_data.get('tipo_torneo') == 'Gironi Finali' else 'ko'
                    if 'rounds_ko' in torneo_data:
                        # Ricarica i round da MongoDB, convertendoli da dict a DataFrame
                        st.session_state['rounds_ko'] = [pd.DataFrame(r) for r in torneo_data['rounds_ko']]
                    st.rerun()
                else:
                    st.error("❌ Errore nel caricamento del torneo. Riprova.")
else:
    # Mostra le opzioni di gestione torneo solo se un torneo è selezionato
    col_clone, col_rename, col_delete, col_back = st.columns([1, 1, 1, 1])
    with col_clone:
        if st.button("➕ Clona Torneo"):
            new_name = st.text_input("Nome per la copia del torneo:", value=st.session_state['tournament_name'] + " (Copia)")
            if st.button("Conferma Clonazione"):
                new_id = clone_torneo_in_db(tournaments_collection, st.session_state['tournament_id'], new_name)
                if new_id:
                    st.success(f"✅ Torneo clonato con successo! Nuovo ID: {new_id}")
                    # Carica il nuovo torneo clonato per continuare la sessione
                    st.session_state['tournament_id'] = str(new_id)
                    st.session_state['tournament_name'] = new_name
                    st.rerun()
                else:
                    st.error("❌ Errore nella clonazione del torneo.")
    with col_rename:
        if st.button("✏️ Rinomina"):
            new_name = st.text_input("Nuovo nome del torneo:", value=st.session_state['tournament_name'])
            if st.button("Conferma Rinomina"):
                if rename_torneo_in_db(tournaments_collection, st.session_state['tournament_id'], new_name):
                    st.success("✅ Torneo rinominato con successo!")
                    st.session_state['tournament_name'] = new_name
                    st.rerun()
                else:
                    st.error("❌ Errore nella ridenominazione.")
    with col_delete:
        if st.button("🗑️ Elimina"):
            if st.checkbox("Conferma eliminazione"):
                if delete_torneo_da_db(tournaments_collection, st.session_state['tournament_id']):
                    st.success("✅ Torneo eliminato con successo!")
                    reset_to_setup()
                else:
                    st.error("❌ Errore nell'eliminazione.")
    with col_back:
        if st.button("⏪ Torna a Configurazione", on_click=reset_to_setup):
            pass

    st.divider()
    if st.session_state['giornate_mode'] is None:
        st.markdown("### ⚙️ Genera Fase Finale")
        if st.session_state['df_torneo_preliminare'] is not None:
            df_classifica = classifica_complessiva(st.session_state['df_torneo_preliminare'].rename(columns={'Girone':'Gruppo'}))
            st.markdown("#### Classifica Torneo Preliminare")
            df_classifica.index = df_classifica.index + 1
            df_classifica.insert(0, 'Pos', df_classifica.index)
            st.dataframe(df_classifica[['Pos','Squadra','Punti','V','P','S','GF','GS','DR']], hide_index=True)
            st.session_state['n_finalisti'] = st.number_input("Quante squadre si qualificano per la fase finale?", min_value=1, max_value=len(df_classifica), value=min(len(df_classifica), 8))
            st.session_state['giornate_mode'] = st.radio(
                "Modalità Fase Finale:",
                ["Gironi Finali", "Eliminazione Diretta (KO)"],
                index=None
            )
            if st.session_state['giornate_mode'] == 'Gironi Finali':
                st.session_state['gironi_num'] = st.number_input("In quanti gironi finali?", min_value=1, max_value=math.ceil(st.session_state['n_finalisti']/2), value=1)
                st.session_state['gironi_ar'] = st.checkbox("Turno andata e ritorno?")
                st.session_state['gironi_seed'] = st.radio("Metodo di distribuzione", ["Serpentino", "Casuale"])
            
            if st.session_state['giornate_mode'] and st.button("Genera Fase Finale"):
                qualificati = list(df_classifica.head(st.session_state['n_finalisti'])['Squadra'])
                if len(qualificati) < st.session_state['n_finalisti']:
                    st.error("Numero di finalisti selezionato non valido. Seleziona un numero di squadre qualificate pari o inferiore a quelle disponibili.")
                else:
                    if st.session_state['giornate_mode'] == 'Gironi Finali':
                        if st.session_state['gironi_seed'] == 'Serpentino':
                            gironi = serpentino_seed(qualificati, st.session_state['gironi_num'])
                        else:
                            import random
                            random.shuffle(qualificati)
                            gironi = [qualificati[i::st.session_state['gironi_num']] for i in range(st.session_state['gironi_num'])]
                        
                        df_finale_list = []
                        for i, girone in enumerate(gironi):
                            df_girone = round_robin(girone, andata_ritorno=st.session_state['gironi_ar'])
                            df_girone.rename(columns={'Giornata': 'GiornataFinale', 'Casa': 'CasaFinale', 'Ospite': 'OspiteFinale'}, inplace=True)
                            df_girone['GironeFinale'] = f"Girone {chr(65+i)}"
                            df_girone['GolCasa'] = None
                            df_girone['GolOspite'] = None
                            df_girone['Valida'] = False
                            df_finale_list.append(df_girone)
                        
                        df_finale = pd.concat(df_finale_list, ignore_index=True)
                        st.session_state['df_finale_gironi'] = df_finale
                        
                        st.session_state['tournament_name'] += " (Fase Finale a Gironi)"
                        
                        # Salva la fase finale su DB
                        salva_torneo_su_db(tournaments_collection, st.session_state['tournament_name'], df_finale, "Gironi Finali", parent_id=st.session_state['tournament_id'])
                        
                        st.session_state['ui_show_pre'] = False
                        st.rerun()

                    elif st.session_state['giornate_mode'] == 'Eliminazione Diretta (KO)':
                        num_partecipanti = len(qualificati)
                        if (num_partecipanti & (num_partecipanti - 1) == 0) and num_partecipanti != 0:
                            matches = bilanciato_ko_seed(qualificati)
                            rounds_ko = []
                            df_round = pd.DataFrame(matches, columns=['SquadraA', 'SquadraB'])
                            df_round['GolA'] = None
                            df_round['GolB'] = None
                            df_round['Valida'] = False
                            df_round['Round'] = 1
                            rounds_ko.append(df_round)
                            st.session_state['rounds_ko'] = rounds_ko
                            st.session_state['tournament_name'] += " (Eliminazione Diretta)"
                            salva_torneo_su_db(tournaments_collection, st.session_state['tournament_name'], df_round, "Eliminazione Diretta", rounds_ko=rounds_ko, parent_id=st.session_state['tournament_id'])
                            st.session_state['ui_show_pre'] = False
                            st.rerun()
                        else:
                            st.error("Il numero di squadre finaliste deve essere una potenza di 2 per un tabellone a eliminazione diretta (es. 2, 4, 8, 16...).")
        else:
            st.info("Per iniziare, carica un torneo preliminare dal menu in alto.")
    else:
        st.divider()
        if st.session_state['giornate_mode'] == 'Gironi Finali':
            st.markdown("### 📊 Risultati Gironi Finali")
            if 'df_finale_gironi' in st.session_state:
                df_finale_gironi = st.session_state['df_finale_gironi']
                gironi = sorted(df_finale_gironi['GironeFinale'].unique())
                
                for girone in gironi:
                    with st.expander(f"**Girone {girone}**", expanded=True):
                        # Classifica
                        st.subheader("Classifica")
                        classifica = standings_from_matches(df_finale_gironi[df_finale_gironi['GironeFinale'] == girone].rename(columns={'GironeFinale':'Gruppo', 'CasaFinale':'Casa', 'OspiteFinale':'Ospite'}), key_group='Gruppo')
                        if not classifica.empty:
                            classifica.index = classifica.index + 1
                            classifica.insert(0, 'Pos', classifica.index)
                            st.dataframe(classifica[['Pos','Squadra','Punti','V','P','S','GF','GS','DR']], hide_index=True)
                        else:
                            st.info("Nessuna partita validata in questo girone.")
                        
                        st.subheader("Calendario")
                        partite_girone = df_finale_gironi[df_finale_gironi['GironeFinale'] == girone]
                        
                        # Loop per le partite con input dinamico
                        for idx, row in partite_girone.iterrows():
                            with st.container(border=True):
                                col1, col2, col3, col4, col5 = st.columns([0.5, 2, 0.5, 2, 0.8])
                                with col1:
                                    st.markdown(f"**G.{row['GiornataFinale']}**")
                                with col2:
                                    st.markdown(f"**{row['CasaFinale']}**")
                                with col3:
                                    st.number_input(
                                        "Gol Casa",
                                        min_value=0,
                                        max_value=20,
                                        key=f"gironi_golcasa_{idx}",
                                        value=int(row['GolCasa']) if pd.notna(row['GolCasa']) else 0,
                                        disabled=row['Valida'],
                                        label_visibility="hidden"
                                    )
                                with col4:
                                    st.number_input(
                                        "Gol Ospite",
                                        min_value=0,
                                        max_value=20,
                                        key=f"gironi_golospite_{idx}",
                                        value=int(row['GolOspite']) if pd.notna(row['GolOspite']) else 0,
                                        disabled=row['Valida'],
                                        label_visibility="hidden"
                                    )
                                with col5:
                                    st.checkbox("Valida", key=f"gironi_valida_{idx}", value=row['Valida'])

                        if st.button(f"💾 Salva risultati Girone {girone}", key=f"save_gironi_{girone}"):
                            # Aggiorna il DataFrame in session_state
                            for idx, row in partite_girone.iterrows():
                                if st.session_state.get(f"gironi_valida_{idx}", False):
                                    st.session_state['df_finale_gironi'].at[idx, 'GolCasa'] = st.session_state[f"gironi_golcasa_{idx}"]
                                    st.session_state['df_finale_gironi'].at[idx, 'GolOspite'] = st.session_state[f"gironi_golospite_{idx}"]
                                    st.session_state['df_finale_gironi'].at[idx, 'Valida'] = True
                            
                            # Salva lo stato su DB
                            df_to_save = st.session_state['df_finale_gironi'].copy()
                            df_to_save.rename(columns={'GironeFinale': 'Girone', 'GiornataFinale': 'Giornata', 'CasaFinale': 'Casa', 'OspiteFinale': 'Ospite'}, inplace=True)
                            
                            try:
                                tournaments_collection.update_one(
                                    {"_id": ObjectId(st.session_state['tournament_id'])},
                                    {"$set": {"calendario": df_to_save.to_dict(orient='records')}}
                                )
                                st.success("✅ Risultati salvati con successo!")
                                st.rerun() # Forza un re-run per aggiornare i widget
                            except Exception as e:
                                st.error(f"❌ Errore nel salvataggio dei risultati su DB: {e}")
            else:
                st.info("Nessun torneo di fase finale a gironi caricato.")

        elif st.session_state['giornate_mode'] == 'ko':
            st.markdown("<h3 style='text-align: center;'>Tabellone Eliminazione Diretta</h3>", unsafe_allow_html=True)
            st.divider()

            if 'rounds_ko' not in st.session_state:
                st.error("Dati del tabellone KO non trovati. Riprova.")
                st.button("Torna indietro", on_click=reset_to_setup)
                st.stop()
            
            # --- Funzione per il rendering di un singolo round ---
            def render_round(df_round, round_num):
                st.subheader(f"Round {round_num + 1}")
                is_current_round = (round_num == len(st.session_state['rounds_ko']) - 1)
                
                if df_round.empty:
                    st.info(f"Nessuna partita in questo round. Il torneo è completo.")
                    return

                for idx, row in df_round.iterrows():
                    with st.container(border=True):
                        col1, col2, col3, col4, col5 = st.columns([2, 1, 0.5, 1, 0.8])
                        with col1:
                            st.markdown(f"**{row['SquadraA']}**")
                        if is_current_round:
                            with col2:
                                st.number_input(
                                    "Gol A",
                                    min_value=0,
                                    max_value=20,
                                    key=f"ko_gol_a_{idx}",
                                    value=int(row['GolA']) if pd.notna(row['GolA']) else 0,
                                    disabled=row['Valida'],
                                    label_visibility="hidden"
                                )
                            with col3:
                                st.markdown("vs")
                            with col4:
                                st.number_input(
                                    "Gol B",
                                    min_value=0,
                                    max_value=20,
                                    key=f"ko_gol_b_{idx}",
                                    value=int(row['GolB']) if pd.notna(row['GolB']) else 0,
                                    disabled=row['Valida'],
                                    label_visibility="hidden"
                                )
                            with col5:
                                st.checkbox("Valida", key=f"ko_valida_{idx}", value=row['Valida'])
                        else:
                            # Visualizza solo i risultati per i round completati
                            with col2:
                                st.markdown(f"### {row['GolA']}")
                            with col3:
                                st.markdown("vs")
                            with col4:
                                st.markdown(f"### {row['GolB']}")
                            with col5:
                                st.checkbox("Valida", value=True, disabled=True)

            # Renderizza tutti i round
            for i, df_round in enumerate(st.session_state['rounds_ko']):
                render_round(df_round, i)
            
            # Controlla se il round corrente è completo
            current_round_df = st.session_state['rounds_ko'][-1]
            is_final_game = len(current_round_df) == 1
            all_valid_current_round = all(st.session_state.get(f"ko_valida_{idx}", False) for idx in current_round_df.index)

            if is_final_game and all_valid_current_round:
                st.success("🎉 Il torneo è completo!")
                vincitore = current_round_df.loc[current_round_df.index[0], 'SquadraA'] if pd.to_numeric(current_round_df.loc[current_round_df.index[0], 'GolA']) > pd.to_numeric(current_round_df.loc[current_round_df.index[0], 'GolB']) else current_round_df.loc[current_round_df.index[0], 'SquadraB']
                st.balloons()
                st.markdown(f"<h1 style='text-align: center;'>🏆 Il vincitore è {vincitore}!</h1>", unsafe_allow_html=True)
                st.button("💾 Salva risultati finali", on_click=lambda: salva_risultati_ko(is_final_game=True))
            else:
                st.button("💾 Salva risultati e genera prossimo round", on_click=salva_risultati_ko)
