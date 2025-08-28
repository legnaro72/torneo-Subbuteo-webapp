import streamlit as st
import pandas as pd
import math
import os
import re
import uuid
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

    gironi = sorted(df_finale_gironi['Girone'].unique()) # Modificato: 'GironeFinale' -> 'Girone'

    for girone in gironi:
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(255, 0, 0)
        
        girone_blocco = df_finale_gironi[df_finale_gironi['Girone'] == girone] # Modificato: 'GironeFinale' -> 'Girone'
        is_complete = all(girone_blocco['Valida'])
        
        pdf.cell(0, 10, f"Girone {girone}", 0, 1, 'L')
        pdf.set_text_color(0, 0, 0)

        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "Classifica:", 0, 1, 'L')
        pdf.set_font("Helvetica", "", 10)
        
        # Le colonne 'Casa' e 'Ospite' sono già corrette
        classifica = standings_from_matches(girone_blocco, key_group='Girone') # Modificato: key_group='Girone'
        
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

        partite_girone = girone_blocco.sort_values(by='Giornata').reset_index(drop=True) # Modificato: 'GiornataFinale' -> 'Giornata'
        for idx, partita in partite_girone.iterrows():
            if not is_complete and not partita['Valida']:
                pdf.set_text_color(255, 0, 0)
            else:
                pdf.set_text_color(0, 0, 0)
            
            res = f"{int(partita['GolCasa'])} - {int(partita['GolOspite'])}" if partita['Valida'] and pd.notna(partita['GolCasa']) and pd.notna(partita['GolOspite']) else " - "
            pdf.cell(0, 7, f"Giornata {int(partita['Giornata'])}: {partita['Casa']} vs {partita['Ospite']} ({res})", 0, 1) # Modificati i nomi delle colonne
        
        pdf.set_text_color(0, 0, 0)
        pdf.ln(5)

    return pdf.output(dest='S').encode('latin1')

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
    return pdf.output(dest='S').encode('latin1')

# ==============================================================================
# 🧠 Gestione stato applicazione
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

# Inizializzazione stato
if 'ui_show_pre' not in st.session_state:
    st.session_state['ui_show_pre'] = True
if 'fase_modalita' not in st.session_state:
    st.session_state['fase_modalita'] = None
if 'filter_player' not in st.session_state:
    st.session_state['filter_player'] = None
if 'filter_girone' not in st.session_state:
    st.session_state['filter_girone'] = None
if 'df_torneo_preliminare' not in st.session_state:
    st.session_state['df_torneo_preliminare'] = None
if 'tournament_id' not in st.session_state:
    st.session_state['tournament_id'] = None
if 'tournament_name' not in st.session_state:
    st.session_state['tournament_name'] = None
if 'giornate_mode' not in st.session_state:
    st.session_state['giornate_mode'] = None
# Nuovo stato per la modalità di navigazione
if 'giornata_nav_mode' not in st.session_state:
    st.session_state['giornata_nav_mode'] = 'Menu a tendina'

# Aggiunto per pulire il nome del torneo
def get_base_name(name):
    """Rimuove i prefissi noti dal nome del torneo per avere un nome base pulito."""
    prefixes = ['completato_', 'fasefinaleAGironi_', 'fasefinaleEliminazionediretta_', 'finito_', 'fasefinale', 'Eliminazionediretta_']
    
    # Crea un pattern regex che corrisponde a uno dei prefissi all'inizio della stringa
    # e gestisce le ripetizioni
    pattern = r'^(?:' + '|'.join(re.escape(p) for p in prefixes) + r')+'
    
    # Sostituisce i prefissi con una stringa vuota
    cleaned_name = re.sub(pattern, '', name)
    
    return cleaned_name.strip('_')

# ==============================================================================
# ⚙️ FUNZIONI DI GESTIONE DATI SU MONGO (COPIATE DA alldbsuperbanew.py)
# ==============================================================================
@st.cache_resource
def init_mongo_connection(uri, db_name, collection_name, show_ok: bool = False):
    """
    Inizializza la connessione a MongoDB.
    """
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
        # Pulisci il DataFrame per il salvataggio
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
    """
    Clona un torneo esistente su MongoDB, gli assegna un nuovo nome e ne ripulisce il calendario.
    Ritorna il nuovo ObjectId e il nuovo nome.
    """
    if tournaments_collection is None:
        return None, None
    try:
        source_data = tournaments_collection.find_one({"_id": ObjectId(source_id)})
        if not source_data:
            st.error(f"❌ Torneo sorgente con ID {source_id} non trovato.")
            return None, None
        
        # Rimuovi l'ID e il nome per creare un nuovo documento
        source_data.pop('_id')
        source_data['nome_torneo'] = new_name
        
        # Svuota il calendario per la nuova fase finale
        source_data['calendario'] = []
        
        # Inserisci il nuovo documento e ottieni il nuovo ID
        result = tournaments_collection.insert_one(source_data)
        st.success(f"✅ Torneo clonato con successo! Nuovo nome: **{new_name}**")
        return result.inserted_id, new_name
        
    except Exception as e:
        st.error(f"❌ Errore nella clonazione del torneo: {e}")
        return None, None

def rinomina_torneo_su_db(tournaments_collection, tournament_id, new_name):
    """
    Rinomina un torneo esistente su MongoDB.
    """
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
if 'tournament_name' in st.session_state and not st.session_state['ui_show_pre']:
    cleaned_name = re.sub(r'\(.*\)', '', st.session_state["tournament_name"]).strip()
    st.markdown(f'<h1 class="main-title">🏆 FASE FINALE {cleaned_name}</h1>', unsafe_allow_html=True)
else:
    st.title("⚽ Fasi Finali")
    if 'tournament_name' in st.session_state and st.session_state['ui_show_pre']:
        st.markdown(f"### 🏷️ {st.session_state['tournament_name']}")

# ==============================================================================
# ⚙️ Sidebar (tutti i pulsanti qui)
# ==============================================================================
with st.sidebar:
    st.header("Opzioni 🚀")
    if not st.session_state['ui_show_pre']:
        if st.button("⬅️ Torna a classifica e scelta fase finale"):
            reset_to_setup()
            st.rerun()
        st.divider()
        st.subheader("📤 Esportazione")
        if st.session_state.get('giornate_mode') == "gironi" and 'df_finale_gironi' in st.session_state:
            # Questa parte non verrà più usata, ma la teniamo per coerenza se si volesse ripristinarla
            st.download_button(
                "📥 Esporta calendario gironi (CSV)",
                data=st.session_state['df_finale_gironi'].to_csv(index=False).encode('utf-8'),
                file_name="fase_finale_gironi_calendario.csv",
                mime="text/csv",
            )
            st.download_button(
                "📄 Esporta PDF calendario e classifica",
                data=generate_pdf_gironi(st.session_state['df_finale_gironi']),
                file_name="fase_finale_gironi.pdf",
                mime="application/pdf",
            )
        if st.session_state.get('giornate_mode') == "ko" and 'rounds_ko' in st.session_state:
            all_rounds_df = pd.concat(st.session_state['rounds_ko'], ignore_index=True)
            st.download_button(
                "📥 Esporta tabellone (CSV)",
                data=all_rounds_df.to_csv(index=False).encode('utf-8'),
                file_name="fase_finale_tabellone.csv",
                mime="text/csv",
            )
            st.download_button(
                "📄 Esporta PDF tabellone KO",
                data=generate_pdf_ko(st.session_state['rounds_ko']),
                file_name="fase_finale_tabellone_ko.pdf",
                mime="application/pdf",
            )

# Definisci db_name e col_name a livello globale
db_name = "TorneiSubbuteo"
col_name = "Superba"

# ==============================================================================
# 🚀 LOGICA APPLICAZIONE PRINCIPALE
# ==============================================================================
if st.session_state['ui_show_pre']:
    st.header("1. Scegli il torneo")
    
    # Connessione e caricamento tornei dal DB
    uri = os.environ.get("MONGO_URI_TOURNEMENTS") # Assumi che la URI sia in una variabile d'ambiente
    if not uri:
        st.error("Variabile d'ambiente MONGO_URI_TOURNEMENTS non impostata.")
    
    tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], db_name, col_name, show_ok=False)
    
    if tournaments_collection is not None:
        
        opzione_selezione = st.radio("Cosa vuoi fare?", ["Creare una nuova fase finale", "Continuare una fase finale esistente"])
        
        if opzione_selezione == "Creare una nuova fase finale":
            tornei_trovati = carica_tornei_da_db(tournaments_collection, prefix=["completato_"])
            st.subheader("Seleziona un torneo preliminare completato")
            if not tornei_trovati:
                st.info("⚠️ Nessun torneo 'COMPLETATO' trovato nel database.")
            else:
                tornei_opzioni = {t['nome_torneo']: str(t['_id']) for t in tornei_trovati}
                scelta_torneo = st.selectbox(
                    "Seleziona il torneo da cui iniziare le fasi finali:",
                    options=list(tornei_opzioni.keys())
                )
                if scelta_torneo:
                    st.session_state['tournament_name'] = scelta_torneo
                    st.session_state['tournament_id'] = tornei_opzioni[scelta_torneo]
                    if st.button("Continua con questo torneo (Nuova Fase Finale)"):
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
                                # Modifica: usa la funzione get_base_name per un nome pulito
                                new_name = f"fasefinale{get_base_name(torneo_data['nome_torneo'])}"
                                new_id, new_name = clona_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], new_name)
                                
                                if new_id:
                                    # Carica la classifica dalla fase preliminare per il display
                                    st.session_state['df_classifica_preliminare'] = classifica_complessiva(df_torneo)
                                    st.session_state['tournament_id'] = str(new_id)
                                    st.session_state['tournament_name'] = new_name
                                    st.session_state['ui_show_pre'] = False
                                    st.rerun()
                                else:
                                    st.error("❌ Errore nella clonazione del torneo. Riprova.")
                        else:
                            st.error("❌ Errore nel caricamento del torneo. Riprova.")

        elif opzione_selezione == "Continuare una fase finale esistente":
            tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], db_name, col_name)
            # Modifica: filtra solo i tornei a eliminazione diretta
            tornei_trovati = carica_tornei_da_db(tournaments_collection, prefix=["fasefinaleEliminazionediretta", "finito_Eliminazionediretta"])
            st.subheader("Seleziona una fase finale esistente")
            if not tornei_trovati:
                st.info("⚠️ Nessuna fase finale esistente trovata nel database.")
            else:
                # CORREZIONE: 'tornei_trozioni' è stato cambiato in 'tornei_trovati'
                tornei_opzioni = {t['nome_torneo']: str(t['_id']) for t in tornei_trovati}
                scelta_torneo = st.selectbox(
                    "Seleziona la fase finale da continuare:",
                    options=list(tornei_opzioni.keys())
                )
                if scelta_torneo:
                    st.session_state['tournament_name'] = scelta_torneo
                    st.session_state['tournament_id'] = tornei_opzioni[scelta_torneo]
                    if st.button("Continua con questo torneo"):
                        torneo_data = carica_torneo_da_db(tournaments_collection, st.session_state['tournament_id'])
                        if torneo_data:
                            df_torneo_completo = pd.DataFrame(torneo_data['calendario'])
                            st.session_state['df_torneo_preliminare'] = df_torneo_completo
                            
                            is_ko_tournament = (df_torneo_completo['Girone'].astype(str) == 'Eliminazione Diretta').any()
                            
                            if is_ko_tournament:
                                df_ko_esistente = df_torneo_completo[df_torneo_completo['Girone'] == 'Eliminazione Diretta'].copy()
                                rounds_list = []
                                for r in sorted(df_ko_esistente['Giornata'].unique()):
                                    df_round = df_ko_esistente[df_ko_esistente['Giornata'] == r].copy()
                                    df_round.rename(columns={'Casa': 'SquadraA', 'Ospite': 'SquadraB', 'GolCasa': 'GolA', 'GolOspite': 'GolB'}, inplace=True)
                                    df_round['Round'] = f"Round {int(r)}"
                                    df_round['Match'] = df_round.index + 1
                                    df_round['Vincitore'] = df_round.apply(lambda row: row['SquadraA'] if pd.notna(row['GolA']) and row['GolA'] > row['GolB'] else row['SquadraB'] if pd.notna(row['GolB']) and row['GolB'] > row['GolA'] else None, axis=1)
                                    rounds_list.append(df_round)
                                
                                rounds_filtrati = []
                                for _df_round in rounds_list:
                                    rounds_filtrati.append(_df_round)
                                    if 'Valida' in _df_round.columns and not _df_round['Valida'].fillna(False).all():
                                        break
                                
                                if rounds_filtrati and ('Valida' in rounds_filtrati[-1].columns) and rounds_filtrati[-1]['Valida'].fillna(False).all():
                                    winners = rounds_filtrati[-1].get('Vincitore')
                                    if winners is None or winners.isna().all():
                                        last_round = rounds_filtrati[-1]
                                        winners = last_round.apply(lambda row: row['SquadraA'] if pd.notna(row.get('GolA')) and pd.notna(row.get('GolB')) and row.get('GolA') > row.get('GolB') else (row['SquadraB'] if pd.notna(row.get('GolA')) and pd.notna(row.get('GolB')) and row.get('GolB') > row.get('GolA') else None), axis=1)
                                    winners = [w for w in winners.tolist() if pd.notna(w)]
                                    if len(winners) > 1:
                                        next_round_name = 'Semifinali' if len(winners) == 4 else ('Finale' if len(winners) == 2 else 'Quarti di finale')
                                        next_matches = []
                                        for i in range(0, len(winners), 2):
                                            if i+1 < len(winners):
                                                next_matches.append({
                                                    'Round': next_round_name,
                                                    'Match': (i//2) + 1,
                                                    'SquadraA': winners[i],
                                                    'SquadraB': winners[i+1],
                                                    'GolA': None, 'GolB': None, 'Valida': False, 'Vincitore': None
                                                })
                                        if next_matches:
                                            rounds_filtrati.append(pd.DataFrame(next_matches))
        
                                st.session_state['rounds_ko'] = rounds_filtrati
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
        # Se i dati del torneo preliminare non sono stati caricati, usa la classifica salvata in sessione
        if 'df_torneo_preliminare' in st.session_state and st.session_state['df_torneo_preliminare'] is not None:
            df_classifica = classifica_complessiva(st.session_state['df_torneo_preliminare'])
        else:
            df_classifica = st.session_state['df_classifica_preliminare']
        
        st.markdown("<h3 style='text-align: center;'>Classifica Fase Preliminare</h3>", unsafe_allow_html=True)
        st.dataframe(df_classifica, use_container_width=True)
        st.divider()

        st.header("2. Scegli la fase finale")
        
        if st.session_state.get('giornate_mode') is None:
            fase_finale_scelta = st.radio(
                "Seleziona la modalità della fase finale:",
                ["Gironi finali", "Eliminazione diretta"]
            )
            
            if fase_finale_scelta == "Gironi finali":
                st.session_state['fase_scelta'] = "gironi"
                st.session_state['fase_modalita'] = "Gironi"

                st.subheader("Configura i gironi")
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
                
                andata_ritorno = st.checkbox("Partite di andata e ritorno?", value=False)
                
                if st.button("Genera gironi e continua"):
                    st.session_state['giornate_mode'] = 'gironi'
                    st.session_state['gironi_num'] = num_gironi
                    st.session_state['gironi_ar'] = andata_ritorno
                    
                    qualificati = list(df_classifica.head(num_partecipanti_gironi)['Squadra'])
                    
                    gironi_assegnati = serpentino_seed(qualificati, num_gironi)
                    
                    df_final_gironi = pd.DataFrame()
                    for i, girone in enumerate(gironi_assegnati, 1):
                        df_girone_calendar = round_robin(girone, andata_ritorno)
                        if not df_girone_calendar.empty:
                            df_girone_calendar.insert(0, 'Girone', f"Girone {i}")
                            df_final_gironi = pd.concat([df_final_gironi, df_girone_calendar], ignore_index=True)
                    
                    df_to_save = df_final_gironi.copy()
                    #df_to_save.rename(columns={'Girone': 'GironeFinale', 'Giornata': 'GiornataFinale', 'Casa': 'CasaFinale', 'Ospite': 'OspiteFinale'}, inplace=True)
                    df_to_save['GolCasa'] = None
                    df_to_save['GolOspite'] = None
                    df_to_save['Valida'] = False
                    
                    # Salva i dati iniziali su DB
                    tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], db_name, col_name)
                    
                    tournaments_collection.update_one(
                        {"_id": ObjectId(st.session_state["tournament_id"])},
                        {"$set": {"calendario": df_to_save.to_dict('records')}}
                    )

                    # Rinominazione del torneo per renderlo gestibile dall'altra web app
                    # Modifica: usa la funzione get_base_name
                    nuovo_nome = f"fasefinaleAGironi_{get_base_name(st.session_state['tournament_name'])}"
                    if rinomina_torneo_su_db(tournaments_collection, st.session_state["tournament_id"], nuovo_nome):
                         st.success("✅ Torneo rinominato e gironi generati con successo!")
                         st.session_state["tournament_name"] = nuovo_nome
                         #st.session_state['df_finale_gironi'] = df_final_gironi
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
                    qualificati = list(df_classifica.head(n_squadre_ko)['Squadra'])
                
                    matches = []
                    if len(qualificati) > 1:
                        accoppiamenti = bilanciato_ko_seed(qualificati)
                        for i, (sq_a, sq_b) in enumerate(accoppiamenti, 1):
                            matches.append({
                                'Round': f"Ottavi di finale (di {n_squadre_ko})" if n_squadre_ko == 16 else f"Quarti di finale (di {n_squadre_ko})" if n_squadre_ko == 8 else f"Semifinali (di {n_squadre_ko})" if n_squadre_ko == 4 else f"Finale (di {n_squadre_ko})",
                                'Match': i,
                                'SquadraA': sq_a,
                                'SquadraB': sq_b,
                                'GolA': None, 'GolB': None, 'Valida': False, 'Vincitore': None
                            })
                    else:
                        st.warning("Non ci sono abbastanza squadre per generare un tabellone.")
                        st.stop()
                
                    df_initial_round = pd.DataFrame(matches)
                    st.session_state['rounds_ko'] = [df_initial_round]
                    st.session_state['giornate_mode'] = 'ko'
                
                    # Salva i dati iniziali su DB
                    df_to_save_initial = df_initial_round.rename(columns={'SquadraA': 'Casa', 'SquadraB': 'Ospite', 'GolA': 'GolCasa', 'GolB': 'GolOspite'})
                    df_to_save_initial['Girone'] = 'Eliminazione Diretta'
                    df_to_save_initial['Giornata'] = 1
                
                    # 🔑 PhaseID e PhaseMode
                    phase_id = str(uuid.uuid4())
                    df_to_save_initial["PhaseID"] = phase_id
                    df_to_save_initial["PhaseMode"] = "KO"
                
                    df_final_torneo = pd.concat([pd.DataFrame(), df_to_save_initial], ignore_index=True)
                    tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], db_name, col_name)
                
                    tournaments_collection.update_one(
                        {"_id": ObjectId(st.session_state["tournament_id"])},
                        {"$set": {"phase_metadata": {"phase_id": phase_id, "phase_mode": "KO"}, "calendario": df_final_torneo.to_dict('records')}}
                    )
                
                    # 🔄 Rinominazione torneo
                    # Modifica: usa la funzione get_base_name
                    nuovo_nome = f"fasefinaleEliminazionediretta_{get_base_name(st.session_state['tournament_name'])}"
                    rinomina_torneo_su_db(tournaments_collection, st.session_state["tournament_id"], nuovo_nome)
                    st.session_state["tournament_name"] = nuovo_nome
                
                    st.session_state['df_torneo_preliminare'] = df_final_torneo
                    st.rerun()

                       
        # Renderizza il calendario/tabellone se già generato
        if st.session_state.get('giornate_mode'):
            st.divider()
            
            def salva_risultati_ko():
                """Aggiorna il DataFrame e lo stato della sessione con i risultati del round corrente KO."""
                tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], db_name, col_name)
                if tournaments_collection is None:
                    st.error("❌ Errore di connessione al DB.")
                    return
                
                current_round_df = st.session_state['rounds_ko'][-1].copy()
                winners = []
                all_valid = True
                
                # Primo ciclo di validazione e salvataggio dei dati in session_state
                for idx, row in current_round_df.iterrows():
                    valid_key = f"ko_valida_{len(st.session_state['rounds_ko']) - 1}_{idx}"
                    
                    if st.session_state.get(valid_key, False):
                        gol_a = st.session_state.get(f"ko_gola_{len(st.session_state['rounds_ko']) - 1}_{idx}")
                        gol_b = st.session_state.get(f"ko_golb_{len(st.session_state['rounds_ko']) - 1}_{idx}")
                        
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
            
                # Verifica se tutte le partite sono validate prima di procedere
                if not all_valid:
                    st.error("❌ Per generare il prossimo round, tutte le partite devono essere validate.")
                    return
                
                st.session_state['rounds_ko'][-1] = current_round_df.copy()
            
                df_ko_da_salvare = current_round_df.copy()
                df_ko_da_salvare.rename(columns={'SquadraA': 'Casa', 'SquadraB': 'Ospite', 'GolA': 'GolCasa', 'GolB': 'GolOspite'}, inplace=True)
                df_ko_da_salvare['Girone'] = 'Eliminazione Diretta'
                df_ko_da_salvare['Giornata'] = len(st.session_state['rounds_ko'])
            
                # Aggiornamento del DB
                # Questa logica ora funziona in modo più semplice
                df_final_torneo = pd.concat([df_ko_da_salvare], ignore_index=True)
            
                if aggiorna_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], df_final_torneo):
                    st.success("✅ Risultati salvati su DB!")
                    st.session_state['df_torneo_preliminare'] = df_final_torneo
                else:
                    st.error("❌ Errore nel salvataggio su DB.")
            
                # Generazione del prossimo round o conclusione del torneo
                if len(winners) > 1:
                    next_round_name = ""
                    if len(winners) == 8:
                        next_round_name = "Quarti di finale"
                    elif len(winners) == 4:
                        next_round_name = "Semifinali"
                    elif len(winners) == 2:
                        next_round_name = "Finale"
            
                    next_matches = []
                    for i in range(0, len(winners), 2):
                        next_matches.append({
                            'Round': next_round_name,
                            'Match': (i // 2) + 1,
                            'SquadraA': winners[i],
                            'SquadraB': winners[i + 1],
                            'GolA': None, 'GolB': None, 'Valida': False, 'Vincitore': None
                        })
                    st.session_state['rounds_ko'].append(pd.DataFrame(next_matches))
                    st.session_state['round_corrente'] = next_round_name
                    st.success(f"Prossimo turno: {next_round_name} generato!")
                
                elif len(winners) == 1:
                    st.balloons()
                    st.success(f"🏆 Il torneo è finito! Il vincitore è: **{winners[0]}**")
                    
                    if not st.session_state['tournament_name'].startswith('finito_'):
                        # MODIFICA: Come richiesto, non usare get_base_name per questo caso
                        nuovo_nome = f"finito_Eliminazionediretta_{st.session_state['tournament_name']}"
                        rinomina_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], nuovo_nome)
                        st.session_state['tournament_name'] = nuovo_nome
            
            
            def render_round(df_round, round_idx):
                st.markdown(f"### {df_round['Round'].iloc[0]}")
                for idx, match in df_round.iterrows():
                    col1, col2, col3, col4, col5 = st.columns([5, 1.5, 1, 1.5, 1])
                    with col1:
                        st.markdown(f"**{match['SquadraA']}** vs **{match['SquadraB']}**")
                    with col2:
                        st.number_input(
                            "", min_value=0, max_value=20, key=f"ko_gola_{round_idx}_{idx}",
                            value=int(match['GolA']) if pd.notna(match['GolA']) else 0,
                            disabled=match['Valida'], label_visibility="hidden"
                        )
                    with col3:
                        st.markdown("-")
                    with col4:
                        st.number_input(
                            "", min_value=0, max_value=20, key=f"ko_golb_{round_idx}_{idx}",
                            value=int(match['GolB']) if pd.notna(match['GolB']) else 0,
                            disabled=match['Valida'], label_visibility="hidden"
                        )
                    with col5:
                        st.checkbox("Valida", key=f"ko_valida_{round_idx}_{idx}", value=match['Valida'])
            
            def update_giornata_sel(giornata):
                st.session_state['giornata_selezionata'] = giornata
                
            if st.session_state['giornate_mode'] == 'gironi':
                 if 'df_finale_gironi' not in st.session_state:
                     st.error("Errore nel caricamento dei dati dei gironi. Riprova.")
                     st.button("Torna indietro", on_click=reset_to_setup)
                     st.stop()
                 
                 st.info("✅ Gironi creati con successo!")
                 
                 st.markdown(f"""
                 <div style="text-align: center; padding: 20px; border: 2px solid #008080; border-radius: 10px; margin-top: 20px;">
                    <h3>Gestisci il tuo torneo a gironi!</h3>
                    <p>Ora che la fase finale a gironi è stata creata, puoi utilizzare l'altra web app per proseguire.</p>
                    <a href="https://tornospalldb.streamlit.app/" target="_blank" style="background-color: #008080; color: white; padding: 10px 20px; text-decoration: none; border-radius: 8px; font-weight: bold;">Vai alla Web App dei Tornei</a>
                    <p style="font-size: 0.8rem; margin-top: 10px;">(Il nome del torneo da cercare è **{st.session_state['tournament_name']}**)</p>
                 </div>
                 """, unsafe_allow_html=True)


            elif st.session_state['giornate_mode'] == 'ko':
                st.markdown("<h3 style='text-align: center;'>Tabellone Eliminazione Diretta</h3>", unsafe_allow_html=True)
                st.divider()

                if 'rounds_ko' not in st.session_state:
                    st.error("Dati del tabellone KO non trovati. Riprova.")
                    st.button("Torna indietro", on_click=reset_to_setup)
                    st.stop()
                
                for i, df_round in enumerate(st.session_state['rounds_ko'][:-1]):
                    render_round(df_round, i)
                
                if st.session_state['rounds_ko']:
                    current_round_df = st.session_state['rounds_ko'][-1]
                    render_round(current_round_df, len(st.session_state['rounds_ko']) - 1)
                    
                    st.button("💾 Salva risultati e genera prossimo round", on_click=salva_risultati_ko)
