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
    
    # FIX: Aggiunto per gestire il TypeError
    partite['Casa'] = partite['Casa'].astype(str).fillna('')
    partite['Ospite'] = partite['Ospite'].astype(str).fillna('')
    
    out = []
    for gruppo, blocco in partite.groupby(key_group):
        
        # FIX: Aggiunto per gestire il TypeError
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
        rows = []
        for s, d in stats.items():
            d['DR'] = d['GF'] - d['GS']
            rows.append({key_group: gruppo, 'Squadra': s, **d})
    dfc = pd.DataFrame(rows)
    if dfc.empty:
        return dfc
    
    dfc = dfc.sort_values(by=[key_group,'Punti','DR','GF','V','Squadra'], ascending=[True, False, False, False, False, True]).reset_index(drop=True)
    dfc['Pos'] = dfc.groupby(key_group).cumcount() + 1
    return dfc

# ==============================================================================
# 📝 Funzioni di generazione PDF
# ==============================================================================
class PDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_font('DejaVuSansCondensed', '', 'DejaVuSansCondensed.ttf', uni=True)
        self.add_font('DejaVuSansCondensed', 'B', 'DejaVuSansCondensed-Bold.ttf', uni=True)

    def header(self):
        self.set_font('DejaVuSansCondensed', 'B', 15)
        self.cell(0, 10, 'Tabellone Fasi Finali Subbuteo', 0, 1, 'C')
        self.set_font('DejaVuSansCondensed', '', 10)
        self.cell(0, 5, f"Torneo: {st.session_state.get('tournament_name', 'N/A')}", 0, 1, 'C')
        self.ln(10)

    def chapter_title(self, title):
        self.set_font('DejaVuSansCondensed', 'B', 12)
        self.cell(0, 6, title, 0, 1, 'L')
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('DejaVuSansCondensed', '', 12)
        self.multi_cell(0, 5, body)
        self.ln()

def create_pdf_from_df(df, type="Gironi"):
    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_fill_color(240, 240, 240)
    pdf.set_draw_color(180, 180, 180)
    
    if type == "Gironi":
        if 'df_finale_gironi' not in st.session_state:
            return None
        
        df_gironi = st.session_state['df_finale_gironi'].copy()
        gironi = sorted(df_gironi['GironeFinale'].unique())
        
        for girone in gironi:
            pdf.set_font("DejaVuSansCondensed", "B", 14)
            pdf.cell(0, 10, f"Girone {girone}", 0, 1, 'C', fill=True)
            pdf.ln(2)
            
            # Classifica
            classifica = standings_from_matches(df_gironi[df_gironi['GironeFinale'] == girone].rename(columns={'GironeFinale':'Gruppo', 'CasaFinale':'Casa', 'OspiteFinale':'Ospite'}), key_group='Gruppo')
            
            pdf.set_font("DejaVuSansCondensed", "B", 12)
            pdf.cell(0, 7, "Classifica", 0, 1)
            
            if not classifica.empty:
                col_widths = [10, 40, 15, 15, 15, 15, 15, 15, 15]
                headers = ["Pos", "Squadra", "Punti", "V", "P", "S", "GF", "GS", "DR"]
                for i, h in enumerate(headers):
                    pdf.cell(col_widths[i], 7, h, 1, 0, 'C')
                pdf.ln()
                
                pdf.set_font("DejaVuSansCondensed", "", 12)
                for _, r in classifica.iterrows():
                    for i, c in enumerate(headers):
                        val = r.get(c, "N/A")
                        pdf.cell(col_widths[i], 7, str(val), 1, 0, 'C')
                    pdf.ln()
            else:
                pdf.set_font("DejaVuSansCondensed", "", 12)
                pdf.cell(0, 7, "Nessuna partita validata in questo girone.", 0, 1)
            
            pdf.ln(5)
            
            # Calendario
            pdf.set_font("DejaVuSansCondensed", "B", 12)
            pdf.cell(0, 10, "Calendario", 0, 1)
            
            partite_girone = df_gironi[df_gironi['GironeFinale'] == girone]
            if not partite_girone.empty:
                for idx, row in partite_girone.iterrows():
                    pdf.set_font("DejaVuSansCondensed", "", 12)
                    pdf.cell(0, 7, f"Giornata {row['GiornataFinale']}: {row['CasaFinale']} vs {row['OspiteFinale']} ({row['GolCasa']} - {row['GolOspite']})", 0, 1)
            else:
                pdf.set_font("DejaVuSansCondensed", "", 12)
                pdf.cell(0, 7, "Nessun calendario generato per questo girone.", 0, 1)
            pdf.ln(10)
            
    elif type == "KO":
        if 'rounds_ko' not in st.session_state:
            return None
        
        rounds = st.session_state['rounds_ko']
        for i, df_round in enumerate(rounds):
            round_name = "Finale" if i == len(rounds) - 1 else f"Round {i+1}"
            pdf.set_font("DejaVuSansCondensed", "B", 14)
            pdf.cell(0, 10, round_name, 0, 1, 'C', fill=True)
            pdf.ln(2)
            
            if not df_round.empty:
                for idx, row in df_round.iterrows():
                    pdf.set_font("DejaVuSansCondensed", "", 12)
                    gol = f"({row['GolA']} - {row['GolB']})" if pd.notna(row['GolA']) and pd.notna(row['GolB']) else ""
                    pdf.cell(0, 7, f"{row['SquadraA']} vs {row['SquadraB']} {gol}", 0, 1)
            pdf.ln(5)

    pdf_output = pdf.output(dest='S')
    return pdf_output

def get_download_link(data, filename, text):
    b64 = base64.b64encode(data).decode()
    href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}">{text}</a>'
    return href

# ==============================================================================
# 🗄️ Funzioni di gestione dati su MongoDB
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
            st.info(f"Connessione a {db_name}.{col_name} ok.")
        return col
    except Exception as e:
        st.error(f"❌ Errore di connessione a {db_name}.{col_name}: {e}")
        return None

def salva_torneo_su_db(collection, tournament_id, tournament_name, data):
    """ Salva o aggiorna un torneo nel DB. """
    if collection is None:
        st.error("❌ Errore di connessione al DB.")
        return False
    try:
        doc = {
            "nome_torneo": tournament_name,
            "data": data,
            "ultima_modifica": pd.Timestamp.now()
        }
        if tournament_id:
            collection.update_one({"_id": ObjectId(tournament_id)}, {"$set": doc})
            st.success("✅ Torneo aggiornato con successo!")
        else:
            result = collection.insert_one(doc)
            st.session_state['tournament_id'] = str(result.inserted_id)
            st.success(f"✅ Nuovo torneo '{tournament_name}' salvato con successo!")
        return True
    except Exception as e:
        st.error(f"❌ Errore nel salvataggio del torneo: {e}")
        return False

def carica_torneo_da_db(collection, tournament_id):
    """ Carica i dati di un torneo dal DB. """
    if collection is None:
        return None
    try:
        return collection.find_one({"_id": ObjectId(tournament_id)})
    except Exception as e:
        st.error(f"❌ Errore nel caricamento del torneo: {e}")
        return None

def carica_tornei_da_db(collection, prefix=None):
    """ Carica tutti i tornei dal DB, opzionalmente filtrando per prefisso. """
    if collection is None:
        return []
    try:
        query = {}
        if prefix:
            query = {"nome_torneo": {"$in": [re.compile(f"^{p}", re.IGNORECASE) for p in prefix]}}
        return list(collection.find(query).sort("ultima_modifica", -1))
    except Exception as e:
        st.error(f"❌ Errore nel caricamento dei tornei: {e}")
        return []

def rinomina_torneo_in_db(tournaments_collection, tournament_id, new_name):
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

# ==============================================================================
# ⚽ Header dinamico
# ==============================================================================
if 'tournament_name' in st.session_state and not st.session_state.get('ui_show_pre', True):
    cleaned_name = re.sub(r'\(.*\)', '', st.session_state["tournament_name"]).strip()
    st.markdown(f'<h1 class="main-title">🏆 FASE FINALE {cleaned_name}</h1>', unsafe_allow_html=True)
else:
    st.title("⚽ Fasi Finali")
    if 'tournament_name' in st.session_state and st.session_state.get('ui_show_pre', True):
        st.markdown(f"### 🏷️ {st.session_state['tournament_name']}")

# ==============================================================================
# ⚙️ Sidebar (tutti i pulsanti qui)
# ==============================================================================
with st.sidebar:
    st.header("Opzioni 🚀")
    if not st.session_state.get('ui_show_pre', True):
        if st.button("Torna al setup iniziale"):
            del st.session_state['df_finale_gironi']
            st.session_state['ui_show_pre'] = True
            st.session_state['giornate_mode'] = None
            st.rerun()

# ==============================================================================
# 🧠 Gestione dello stato della sessione (la parte più importante!)
# ==============================================================================
def reset_to_setup():
    st.session_state['df_torneo_preliminare'] = pd.DataFrame()
    st.session_state['tournament_id'] = None
    st.session_state['tournament_name'] = ""
    st.session_state['df_finale_gironi'] = pd.DataFrame()
    st.session_state['rounds_ko'] = []
    st.session_state['giornate_mode'] = None
    st.session_state['ui_show_pre'] = True
    st.session_state['step'] = 0
    st.rerun()

# Inizializzazione delle variabili di stato
if 'df_torneo_preliminare' not in st.session_state:
    reset_to_setup()
if 'tournament_id' not in st.session_state:
    st.session_state['tournament_id'] = None
if 'tournament_name' not in st.session_state:
    st.session_state['tournament_name'] = ""
if 'ui_show_pre' not in st.session_state: # Questa è la riga che mancava!
    st.session_state['ui_show_pre'] = True
if 'df_finale_gironi' not in st.session_state:
    st.session_state['df_finale_gironi'] = pd.DataFrame()
if 'rounds_ko' not in st.session_state:
    st.session_state['rounds_ko'] = []
if 'giornate_mode' not in st.session_state:
    st.session_state['giornate_mode'] = None
if 'giornata_nav_mode' not in st.session_state:
    st.session_state['giornata_nav_mode'] = 'Menu a tendina'

# ==============================================================================
# ⚙️ FUNZIONI DI GESTIONE DATI SU MONGO (COPIATE DA alldbsuperbanew.py)
# ==============================================================================
db_name = "superba_subbuteo_tournaments"
col_name = "tournaments"

def salva_risultati_ko():
    if 'rounds_ko' not in st.session_state:
        st.error("Dati KO non trovati.")
        return False
    if 'tournament_id' not in st.session_state or not st.session_state['tournament_id']:
        st.error("ID torneo non trovato.")
        return False

    current_round_df = st.session_state['rounds_ko'][-1].copy()
    current_round_df['GolA'] = pd.to_numeric(current_round_df['GolA'], errors='coerce').fillna(0).astype(int)
    current_round_df['GolB'] = pd.to_numeric(current_round_df['GolB'], errors='coerce').fillna(0).astype(int)

    all_valid = (current_round_df['Valida'] == True).all()

    if not all_valid:
        st.error("❌ Per salvare, tutte le partite del round corrente devono essere validate.")
        return False

    winners = []
    for idx, row in current_round_df.iterrows():
        if row['GolA'] > row['GolB']:
            winners.append(row['SquadraA'])
        elif row['GolA'] < row['GolB']:
            winners.append(row['SquadraB'])

    df_ko_da_salvare = current_round_df.copy()
    df_ko_da_salvare.rename(columns={'SquadraA': 'Casa', 'SquadraB': 'Ospite', 'GolA': 'GolCasa', 'GolB': 'GolOspite'}, inplace=True)
    df_ko_da_salvare['Girone'] = 'Eliminazione Diretta'
    df_ko_da_salvare['Giornata'] = len(st.session_state['rounds_ko'])

    tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], db_name, col_name)
    if tournaments_collection:
        torneo_data = carica_torneo_da_db(tournaments_collection, st.session_state['tournament_id'])
        if torneo_data:
            # Aggiorna il calendario con il nuovo round
            calendario_db = pd.DataFrame(torneo_data.get('calendario', []))
            calendario_db = pd.concat([calendario_db, df_ko_da_salvare], ignore_index=True)
            salva_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], st.session_state['tournament_name'], calendario_db.to_dict('records'))

            # Se ci sono vincitori, genera il prossimo round
            if len(winners) > 1:
                next_round_matches = bilanciato_ko_seed(winners)
                next_round_df = pd.DataFrame(next_round_matches, columns=['SquadraA', 'SquadraB'])
                next_round_df['GolA'] = None
                next_round_df['GolB'] = None
                next_round_df['Valida'] = False
                st.session_state['rounds_ko'].append(next_round_df)
                st.success("✅ Risultati salvati e prossimo round generato!")
            else:
                st.success("✅ Risultati salvati. Torneo concluso!")
                st.session_state['giornate_mode'] = 'gironi' # Forzo il ritorno ai gironi
                st.session_state['ui_show_pre'] = True # e al setup iniziale
                st.session_state['tournament_id'] = None
                st.session_state['tournament_name'] = ""

            st.rerun()

    return True

# Funzione per salvare i risultati dei gironi su DB
def salva_risultati_gironi():
    tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], db_name, col_name)
    if tournaments_collection is None:
        st.error("❌ Errore di connessione al DB.")
        return
    torneo_data = carica_torneo_da_db(tournaments_collection, st.session_state['tournament_id'])
    if torneo_data is None:
        st.error("❌ Errore nel caricamento del torneo corrente.")
        return
    df_torneo_preliminare = pd.DataFrame(torneo_data['calendario'])
    df_finale_gironi = st.session_state['df_finale_gironi'].copy()
    
    # Aggiorna il DataFrame in base ai dati della sessione
    for idx in df_finale_gironi.index:
        df_finale_gironi.loc[idx, 'GolCasa'] = st.session_state[f'gironi_golcasa_{idx}']
        df_finale_gironi.loc[idx, 'GolOspite'] = st.session_state[f'gironi_golospite_{idx}']
        df_finale_gironi.loc[idx, 'Valida'] = st.session_state[f'gironi_valida_{idx}']

    # Sostituisci il vecchio df dei gironi con quello aggiornato
    st.session_state['df_finale_gironi'] = df_finale_gironi
    
    # Rimuovi le vecchie partite della fase finale e aggiungi le nuove
    df_preliminare_pulito = df_torneo_preliminare[~df_torneo_preliminare['Girone'].str.contains("Fase Finale")].copy()
    df_calendario_aggiornato = pd.concat([df_preliminare_pulito, df_finale_gironi.rename(columns={'CasaFinale': 'Casa', 'OspiteFinale': 'Ospite', 'GolCasaFinale': 'GolCasa', 'GolOspiteFinale': 'GolOspite', 'GironeFinale': 'Girone', 'GiornataFinale': 'Giornata'})], ignore_index=True)

    salva_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], st.session_state['tournament_name'], df_calendario_aggiornato.to_dict('records'))
    st.success("✅ Risultati salvati con successo!")
    st.rerun()

# ==============================================================================
# 🎛️ UI Principale
# ==============================================================================

# Area di setup iniziale (visibile solo all'inizio)
if st.session_state.get('ui_show_pre', True):
    st.header("1. Carica il Torneo Preliminare")
    st.info("Carica un file CSV con i risultati della fase preliminare del torneo o seleziona un torneo esistente dal database. Assicurati che il CSV contenga le colonne: 'Girone', 'Giornata', 'Casa', 'Ospite', 'GolCasa', 'GolOspite', 'Valida'.")

    # Opzioni di caricamento
    opzione_selezione = st.radio("Scegli un'opzione di caricamento:", ["Carica da file CSV", "Seleziona da DB", "Clona da DB (con rinomina)"], index=1)

    if opzione_selezione == "Carica da file CSV":
        uploaded_file = st.file_uploader("Scegli un file CSV", type="csv")
        if uploaded_file:
            df = pd.read_csv(uploaded_file)
            st.session_state['df_torneo_preliminare'] = df
            st.success("File CSV caricato con successo!")
            st.session_state['tournament_id'] = None
            st.session_state['tournament_name'] = f"Nuova fase finale da CSV ({uploaded_file.name})"
            if 'ui_show_pre' not in st.session_state:
                st.session_state['ui_show_pre'] = True

    elif opzione_selezione == "Seleziona da DB":
        tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], db_name, col_name)
        tornei_trovati = carica_tornei_da_db(tournaments_collection)
        
        if tornei_trovati:
            nomi_tornei = {t['nome_torneo']: str(t['_id']) for t in tornei_trovati}
            nome_selezionato = st.selectbox("Seleziona un torneo dal database:", list(nomi_tornei.keys()))
            if st.button("Carica Torneo Selezionato"):
                tournament_id = nomi_tornei[nome_selezionato]
                torneo_data = carica_torneo_da_db(tournaments_collection, tournament_id)
                if torneo_data:
                    st.session_state['df_torneo_preliminare'] = pd.DataFrame(torneo_data['calendario'])
                    st.session_state['tournament_id'] = tournament_id
                    st.session_state['tournament_name'] = nome_selezionato
                    st.success(f"Torneo '{nome_selezionato}' caricato con successo!")
                    st.rerun()
                else:
                    st.error("❌ Errore nel caricamento del torneo. Riprova.")
        else:
            st.info("Nessun torneo trovato nel database. Carica un CSV.")

    elif opzione_selezione == "Clona da DB (con rinomina)":
        tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], db_name, col_name)
        tornei_trovati = carica_tornei_da_db(tournaments_collection)
        
        if tornei_trovati:
            nomi_tornei = {t['nome_torneo']: str(t['_id']) for t in tornei_trovati}
            nome_selezionato = st.selectbox("Seleziona il torneo da clonare:", list(nomi_tornei.keys()))
            new_name = st.text_input("Nuovo nome per il torneo clonato:", value=f"Copia di {nome_selezionato}")
            
            if st.button("Clona e carica Torneo"):
                tournament_id = nomi_tornei[nome_selezionato]
                torneo_data = carica_torneo_da_db(tournaments_collection, tournament_id)
                if torneo_data:
                    # Clona il torneo con il nuovo nome
                    cloned_doc = torneo_data.copy()
                    del cloned_doc['_id']
                    cloned_doc['nome_torneo'] = new_name
                    result = tournaments_collection.insert_one(cloned_doc)
                    new_id = result.inserted_id
                    
                    if new_id:
                        cloned_torneo_data = carica_torneo_da_db(tournaments_collection, str(new_id))
                        if cloned_torneo_data:
                            st.session_state['df_torneo_preliminare'] = pd.DataFrame(cloned_torneo_data['calendario'])
                            st.session_state['tournament_id'] = str(new_id)
                            st.session_state['tournament_name'] = new_name
                            st.session_state['ui_show_pre'] = False
                            st.rerun()
                        else:
                            st.error("❌ Errore nel caricamento del torneo clonato. Riprova.")
                    else:
                        st.error("❌ Errore nella clonazione del torneo. Riprova.")
                else:
                    st.error("❌ Errore nel caricamento del torneo. Riprova.")
        else:
            st.info("Nessun torneo trovato nel database per la clonazione.")

    if not st.session_state['df_torneo_preliminare'].empty:
        st.header("2. Seleziona i finalisti")
        df_classifica = classifica_complessiva(st.session_state['df_torneo_preliminare'])
        if not df_classifica.empty:
            st.subheader("Classifica del Torneo Preliminare")
            st.dataframe(df_classifica[['Pos','Squadra','Punti','V','P','S','GF','GS','DR']], hide_index=True)
            st.divider()

            st.session_state['fase_finale_type'] = st.radio("Tipo di fase finale:", ["Gironi", "Eliminazione Diretta (KO)"])

            if st.session_state['fase_finale_type'] == "Gironi":
                st.session_state['n_finalisti'] = st.number_input("Quante squadre partecipano alla fase finale?", min_value=1, max_value=len(df_classifica), value=min(len(df_classifica), 8))
                st.session_state['gironi_num'] = st.number_input("In quanti gironi finali?", min_value=1, max_value=math.ceil(st.session_state['n_finalisti']/2), value=1)
                st.session_state['gironi_ar'] = st.checkbox("Turno andata e ritorno?")
                st.session_state['gironi_seed'] = st.radio("Metodo di distribuzione", ["Fasce (bilanciata)", "Casuale"])
                
                if st.button("Genera gironi e calendario"):
                    qualificati = list(df_classifica.head(st.session_state['n_finalisti'])['Squadra'])
                    if len(qualificati) < st.session_state['n_finalisti']:
                        st.warning("Non ci sono abbastanza squadre qualificate.")
                    else:
                        if st.session_state['gironi_seed'] == "Fasce (bilanciata)":
                            gironi = serpentino_seed(qualificati, st.session_state['gironi_num'])
                        else:
                            import random
                            random.shuffle(qualificati)
                            gironi = serpentino_seed(qualificati, st.session_state['gironi_num'])
                        
                        calendario_gironi = pd.DataFrame()
                        for i, girone_squadre in enumerate(gironi):
                            cal_girone = round_robin(girone_squadre, andata_ritorno=st.session_state['gironi_ar'])
                            cal_girone['GironeFinale'] = f"Girone {chr(65 + i)}"
                            cal_girone = cal_girone.rename(columns={'Giornata': 'GiornataFinale', 'Casa':'CasaFinale','Ospite':'OspiteFinale'})
                            calendario_gironi = pd.concat([calendario_gironi, cal_girone], ignore_index=True)
                        
                        calendario_gironi['GolCasa'] = None
                        calendario_gironi['GolOspite'] = None
                        calendario_gironi['Valida'] = False
                        
                        st.session_state['df_finale_gironi'] = calendario_gironi
                        st.session_state['giornate_mode'] = 'gironi'
                        st.session_state['ui_show_pre'] = False
                        st.success("✅ Calendario della fase a gironi generato!")
                        st.rerun()

            elif st.session_state['fase_finale_type'] == "Eliminazione Diretta (KO)":
                st.session_state['n_finalisti'] = st.number_input("Quante squadre partecipano alla fase finale? (Deve essere una potenza di 2: 2, 4, 8, 16...)", min_value=2, max_value=len(df_classifica), value=min(len(df_classifica), 8))
                
                if st.button("Genera Tabellone KO"):
                    if not (st.session_state['n_finalisti'] > 0 and (st.session_state['n_finalisti'] & (st.session_state['n_finalisti'] - 1) == 0)):
                        st.error("❌ Il numero di squadre deve essere una potenza di 2 (es. 2, 4, 8, 16...).")
                    else:
                        qualificati = list(df_classifica.head(st.session_state['n_finalisti'])['Squadra'])
                        if len(qualificati) < st.session_state['n_finalisti']:
                            st.warning("Non ci sono abbastanza squadre qualificate.")
                        else:
                            matches = bilanciato_ko_seed(qualificati)
                            df_initial_round = pd.DataFrame(matches, columns=['SquadraA', 'SquadraB'])
                            df_initial_round['GolA'] = None
                            df_initial_round['GolB'] = None
                            df_initial_round['Valida'] = False
                            st.session_state['rounds_ko'] = [df_initial_round]
                            st.session_state['giornate_mode'] = 'ko'
                            st.session_state['ui_show_pre'] = False
                            st.success("✅ Tabellone ad eliminazione diretta generato!")
                            st.rerun()

# Area di visualizzazione e gestione risultati (visibile solo dopo aver generato il calendario)
else:
    st.divider()
    if st.session_state.get('giornate_mode'):
        if st.session_state['giornate_mode'] == 'gironi':
            st.markdown("<h3 style='text-align: center;'>Gestione Gironi</h3>", unsafe_allow_html=True)
            st.divider()
            
            if 'df_finale_gironi' not in st.session_state or st.session_state['df_finale_gironi'].empty:
                st.error("Dati dei gironi non trovati. Ritorna al setup iniziale.")
                st.button("Torna indietro", on_click=reset_to_setup)
                st.stop()
            
            # Funzione per renderizzare la giornata
            def render_giornata_gironi(df_finale_gironi, giornata):
                st.write(f"**Giornata {giornata}**")
                partite_giornata = df_finale_gironi[df_finale_gironi['GiornataFinale'] == giornata].sort_values('GironeFinale')
                for idx, row in partite_giornata.iterrows():
                    st.markdown(f"**{row['GironeFinale']}**: {row['CasaFinale']} vs {row['OspiteFinale']}")
                    cols = st.columns(6)
                    with cols[0]: st.write("Risultato:")
                    with cols[1]:
                        st.number_input(
                            "Gol Casa",
                            min_value=0, max_value=20,
                            key=f"gironi_golcasa_{idx}",
                            value=int(row['GolCasa']) if pd.notna(row['GolCasa']) else 0,
                            disabled=row['Valida'], label_visibility="hidden"
                        )
                    with cols[2]: st.write("-")
                    with cols[3]:
                        st.number_input(
                            "Gol Ospite",
                            min_value=0, max_value=20,
                            key=f"gironi_golospite_{idx}",
                            value=int(row['GolOspite']) if pd.notna(row['GolOspite']) else 0,
                            disabled=row['Valida'], label_visibility="hidden"
                        )
                    with cols[5]:
                        st.checkbox("Valida", key=f"gironi_valida_{idx}", value=row['Valida'])

            giornate_unici = sorted(st.session_state['df_finale_gironi']['GiornataFinale'].unique())
            if st.session_state['giornata_nav_mode'] == 'Menu a tendina':
                giornata_selezionata = st.selectbox(
                    "Seleziona la giornata da visualizzare:",
                    options=giornate_unici,
                    key='giornata_sel_select'
                )
                if giornata_selezionata:
                    render_giornata_gironi(st.session_state['df_finale_gironi'], giornata_selezionata)
                    
            else: # Modalità pulsanti
                cols = st.columns(len(giornate_unici))
                giornata_selezionata = st.session_state.get('giornata_selezionata_buttons', giornate_unici[0])
                for col, giornata in zip(cols, giornate_unici):
                    if col.button(f"Giornata {giornata}", key=f"giornata_{giornata}"):
                        st.session_state['giornata_selezionata_buttons'] = giornata
                        st.rerun()
                if giornata_selezionata:
                    render_giornata_gironi(st.session_state['df_finale_gironi'], giornata_selezionata)

            st.button("💾 Salva risultati", on_click=salva_risultati_gironi)

            st.divider()

            # Espansori per visualizzare classifiche e calendario completo
            with st.expander("Visualizza Classifiche e Calendario Completo", expanded=False):
                gironi = sorted(st.session_state['df_finale_gironi']['GironeFinale'].unique())
                for girone in gironi:
                    with st.expander(f"**Girone {girone}**", expanded=False):
                        # Classifica
                        st.subheader("Classifica")
                        classifica = standings_from_matches(st.session_state['df_finale_gironi'][st.session_state['df_finale_gironi']['GironeFinale'] == girone].rename(columns={'GironeFinale':'Gruppo', 'CasaFinale':'Casa', 'OspiteFinale':'Ospite'}), key_group='Gruppo')
                        if not classifica.empty:
                            classifica.index = classifica.index + 1
                            classifica.insert(0, 'Pos', classifica.index)
                            st.dataframe(classifica[['Pos','Squadra','Punti','V','P','S','GF','GS','DR']], hide_index=True)
                        else:
                            st.info("Nessuna partita validata in questo girone.")
                        
                        st.subheader("Calendario")
                        partite_girone = st.session_state['df_finale_gironi'][st.session_state['df_finale_gironi']['GironeFinale'] == girone]
                        for idx, row in partite_girone.iterrows():
                            st.markdown(f"**Giornata {row['GiornataFinale']}**: {row['CasaFinale']} vs {row['OspiteFinale']} ({row['GolCasa']} - {row['GolOspite']})")

            st.divider()
            
            pdf_data = create_pdf_from_df(st.session_state['df_finale_gironi'], type="Gironi")
            if pdf_data:
                st.download_button(
                    label="⬇️ Scarica PDF Gironi",
                    data=pdf_data,
                    file_name=f"fase_finale_gironi_{st.session_state['tournament_name']}.pdf",
                    mime="application/pdf"
                )

        elif st.session_state['giornate_mode'] == 'ko':
            st.markdown("<h3 style='text-align: center;'>Tabellone Eliminazione Diretta</h3>", unsafe_allow_html=True)
            st.divider()

            if 'rounds_ko' not in st.session_state:
                st.error("Dati del tabellone KO non trovati. Riprova.")
                st.button("Torna indietro", on_click=reset_to_setup)
                st.stop()
            
            def render_round(df_round, round_idx):
                if df_round.empty: return
                
                round_name = "Finale" if len(df_round) == 1 else f"Quarti di Finale" if len(df_round) == 4 else f"Semifinale" if len(df_round) == 2 else f"Round {round_idx+1}"
                st.subheader(round_name)
                
                for idx, row in df_round.iterrows():
                    cols = st.columns(6)
                    with cols[0]: st.write(f"**{row['SquadraA']}**")
                    with cols[1]: st.write("vs")
                    with cols[2]: st.write(f"**{row['SquadraB']}**")
                    with cols[3]:
                        st.number_input("Gol A", min_value=0, max_value=20, value=int(row['GolA']) if pd.notna(row['GolA']) else 0, key=f"ko_gola_{round_idx}_{idx}", disabled=row['Valida'])
                    with cols[4]:
                        st.number_input("Gol B", min_value=0, max_value=20, value=int(row['GolB']) if pd.notna(row['GolB']) else 0, key=f"ko_golb_{round_idx}_{idx}", disabled=row['Valida'])
                    with cols[5]:
                        st.checkbox("Valida", value=row['Valida'], key=f"ko_valida_{round_idx}_{idx}")
            
            # Renderizza i round completati
            for i, df_round in enumerate(st.session_state['rounds_ko'][:-1]):
                render_round(df_round, i)
            
            # Renderizza il round corrente con i campi editabili
            if st.session_state['rounds_ko']:
                current_round_df = st.session_state['rounds_ko'][-1]
                render_round(current_round_df, len(st.session_state['rounds_ko']) - 1)
                
                st.button("💾 Salva risultati e genera prossimo round", on_click=salva_risultati_ko)

            st.divider()
            
            pdf_data = create_pdf_from_df(st.session_state['rounds_ko'], type="KO")
            if pdf_data:
                st.download_button(
                    label="⬇️ Scarica PDF Tabellone KO",
                    data=pdf_data,
                    file_name=f"fase_finale_ko_{st.session_state['tournament_name']}.pdf",
                    mime="application/pdf"
                )
