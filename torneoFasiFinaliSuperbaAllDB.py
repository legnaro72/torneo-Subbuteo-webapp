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

def get_vincitori_da_df(df_ko: pd.DataFrame) -> list[str]:
    """
    Estrae i vincitori delle partite validate in un DataFrame KO.
    
    Ritorna:
        Una lista di nomi di squadre vincitrici, ordinate in base all'ordine originale delle partite.
    """
    vincitori = []
    
    df_ko['GolCasa'] = pd.to_numeric(df_ko['GolCasa'], errors='coerce')
    df_ko['GolOspite'] = pd.to_numeric(df_ko['GolOspite'], errors='coerce')
    df_ko['Valida'] = to_bool_series(df_ko['Valida'])

    partite_validate = df_ko[df_ko['Valida']].copy()
    
    if partite_validate.empty:
        return []

    partite_validate = partite_validate.sort_values(by='Giornata')
    
    # Raggruppa per giornata e prendi solo l'ultimo round giocato
    giornate_giocate = sorted(partite_validate['Giornata'].unique())
    if not giornate_giocate:
        return []

    ultimo_round = giornate_giocate[-1]
    df_ultimo_round = partite_validate[partite_validate['Giornata'] == ultimo_round]
    
    if len(df_ultimo_round) % 2 != 0 and len(df_ultimo_round) != 1:
        st.error(f"⚠️ Errore: numero dispari di vincitori ({len(df_ultimo_round)}) nel round {ultimo_round}. Le eliminazioni non possono continuare.")
        return []

    vincitori = []
    for _, row in df_ultimo_round.iterrows():
        gol_casa = row['GolCasa']
        gol_ospite = row['GolOspite']
        casa = row['Casa']
        ospite = row['Ospite']
        
        if pd.notna(gol_casa) and pd.notna(gol_ospite):
            if gol_casa > gol_ospite:
                vincitori.append(casa)
            elif gol_ospite > gol_casa:
                vincitori.append(ospite)
            else:
                # In caso di pareggio, non c'è un vincitore
                pass
    
    # Controlla che i vincitori siano la metà delle partite
    if len(vincitori) * 2 != len(df_ultimo_round):
        st.warning("⚠️ Attenzione: Non tutte le partite dell'ultimo round sono state validate. Non è possibile procedere. Validale prima di continuare.")
        return []
        
    return vincitori


# ==============================================================================
# 📄 FUNZIONI PER EXPORT PDF (Nessuna modifica, come richiesto)
# ==============================================================================

def generate_pdf_gironi(df_finale_gironi: pd.DataFrame) -> bytes:
    """Genera un PDF con calendario e classifica dei gironi."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)

    pdf.cell(0, 10, "Calendario e Classifiche Gironi", 0, 1, 'C')
    pdf.set_font("Helvetica", "", 12)

    gironi = sorted(df_finale_gironi['GironeFinale'].unique())

    for girone in gironi:
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(255, 0, 0)
        
        girone_blocco = df_finale_gironi[df_finale_gironi['GironeFinale'] == girone]
        is_complete = all(girone_blocco['Valida'])
        
        pdf.cell(0, 10, f"Girone {girone}", 0, 1, 'L')
        pdf.set_text_color(0, 0, 0)

        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "Classifica:", 0, 1, 'L')
        pdf.set_font("Helvetica", "", 10)
        
        classifica = standings_from_matches(
            girone_blocco.rename(columns={
                'GironeFinale': 'Gruppo',
                'CasaFinale': 'Casa',
                'OspiteFinale': 'Ospite'
            }), 
            key_group='Gruppo'
        )
        
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

        partite_girone = girone_blocco.sort_values(by='GiornataFinale').reset_index(drop=True)
        for idx, partita in partite_girone.iterrows():
            if not is_complete and not partita['Valida']:
                pdf.set_text_color(255, 0, 0)
            else:
                pdf.set_text_color(0, 0, 0)
            
            res = f"{int(partita['GolCasa'])} - {int(partita['GolOspite'])}" if partita['Valida'] and pd.notna(partita['GolCasa']) and pd.notna(partita['GolOspite']) else " - "
            pdf.cell(0, 7, f"Giornata {int(partita['GiornataFinale'])}: {partita['CasaFinale']} vs {partita['OspiteFinale']} ({res})", 0, 1)

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
    st.session_state['ko_match_data'] = None
    st.session_state['gironi_match_data'] = None

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
if 'giornata_nav_mode' not in st.session_state:
    st.session_state['giornata_nav_mode'] = 'Menu a tendina'

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
        regex_prefix = '|'.join(prefix)
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
    Clona un torneo esistente su MongoDB e gli assegna un nuovo nome.
    Ritorna il nuovo ObjectId e il nuovo nome.
    """
    if tournaments_collection is None:
        return None, None
    try:
        source_data = tournaments_collection.find_one({"_id": ObjectId(source_id)})
        if not source_data:
            st.error(f"❌ Torneo sorgente con ID {source_id} non trovato.")
            return None, None
        
        source_data.pop('_id')
        source_data['nome_torneo'] = new_name
        
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
# 💾 Funzioni di salvataggio dei risultati
# ==============================================================================
def salva_risultati_ko():
    """
    Salva i risultati del round corrente nel DataFrame principale e genera il prossimo round.
    """
    tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], db_name, col_name)
    if tournaments_collection is None:
        return

    df_torneo_completo = st.session_state['df_torneo_preliminare'].copy()
    
    # Aggiorna il DataFrame completo con i risultati del round corrente
    ko_df_to_save = st.session_state['rounds_ko'][-1]
    
    for _, row in ko_df_to_save.iterrows():
        match_id = f"ko_match_{row['Match']}_round_{row['Giornata']}"
        valida = st.session_state.get(f'ko_valida_{match_id}', False)
        if valida:
            gol_casa = st.session_state.get(f'ko_golcasa_{match_id}', 0)
            gol_ospite = st.session_state.get(f'ko_golospite_{match_id}', 0)
            
            # Trova la riga corrispondente nel DataFrame completo e aggiornala
            idx = df_torneo_completo[
                (df_torneo_completo['Casa'] == row['SquadraA']) &
                (df_torneo_completo['Ospite'] == row['SquadraB']) &
                (df_torneo_completo['Girone'] == 'Eliminazione Diretta') &
                (df_torneo_completo['Giornata'] == row['Giornata'])
            ].index
            
            if not idx.empty:
                df_torneo_completo.loc[idx, 'GolCasa'] = gol_casa
                df_torneo_completo.loc[idx, 'GolOspite'] = gol_ospite
                df_torneo_completo.loc[idx, 'Valida'] = True

    # Salva il DataFrame aggiornato sul DB
    if aggiorna_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], df_torneo_completo):
        st.success("✅ Risultati salvati con successo!")
        st.session_state['df_torneo_preliminare'] = df_torneo_completo
    else:
        st.error("❌ Errore nel salvataggio dei risultati.")
        return

    # Logica per generare il prossimo round
    if df_torneo_completo[df_torneo_completo['Girone'] == 'Eliminazione Diretta']['Valida'].all():
        vincitori = get_vincitori_da_df(df_torneo_completo[df_torneo_completo['Girone'] == 'Eliminazione Diretta'])
        if not vincitori:
            st.error("❌ Errore nel calcolo dei vincitori.")
            return

        if len(vincitori) == 1:
            # Torneo terminato, rinomina
            nuovo_nome = f"finito_{st.session_state['tournament_name']}"
            if rinomina_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], nuovo_nome):
                st.session_state['tournament_name'] = nuovo_nome
                st.success(f"🏆 Torneo completato! Il vincitore è **{vincitori[0]}**.")
                st.session_state['ui_show_pre'] = True
                st.session_state['giornate_mode'] = 'ko'
                st.session_state['fase_modalita'] = "Eliminazione diretta"
                st.rerun()
        else:
            prossimo_round = bilanciato_ko_seed(vincitori)
            
            # Crea il DataFrame per il nuovo round
            df_prossimo_round = pd.DataFrame({
                'Girone': 'Eliminazione Diretta',
                'Giornata': df_torneo_completo['Giornata'].max() + 1,
                'Casa': [m[0] for m in prossimo_round],
                'Ospite': [m[1] for m in prossimo_round],
                'GolCasa': None,
                'GolOspite': None,
                'Valida': False
            })
            
            # Aggiungi il nuovo round al DataFrame completo
            df_torneo_completo_nuovo = pd.concat([df_torneo_completo, df_prossimo_round], ignore_index=True)
            
            # Aggiorna il DB con il nuovo round
            if aggiorna_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], df_torneo_completo_nuovo):
                st.session_state['df_torneo_preliminare'] = df_torneo_completo_nuovo
                st.success(f"Prossimo round generato e salvato!")
                st.rerun()
            else:
                st.error("❌ Errore nel salvataggio del prossimo round.")

def salva_risultati_gironi():
    """
    Salva i risultati delle partite per il girone selezionato.
    """
    tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], db_name, col_name)
    if tournaments_collection is None:
        return

    df_finale_gironi = st.session_state['df_finale_gironi'].copy()
    
    for idx, row in df_finale_gironi.iterrows():
        # Usa un identificatore unico per i widget di input
        unique_key = f"gironi_match_{row['GironeFinale']}_{row['GiornataFinale']}_{row['CasaFinale']}_{row['OspiteFinale']}"
        
        gol_casa = st.session_state.get(f'gironi_golcasa_{unique_key}', row['GolCasa'])
        gol_ospite = st.session_state.get(f'gironi_golospite_{unique_key}', row['GolOspite'])
        valida = st.session_state.get(f'gironi_valida_{unique_key}', row['Valida'])

        df_finale_gironi.loc[idx, 'GolCasa'] = gol_casa
        df_finale_gironi.loc[idx, 'GolOspite'] = gol_ospite
        df_finale_gironi.loc[idx, 'Valida'] = valida

    # Aggiorna il DataFrame principale del torneo con i risultati della fase finale
    df_torneo_completo = st.session_state['df_torneo_preliminare'].copy()
    
    # Rimuovi le vecchie righe del girone finale
    df_torneo_completo = df_torneo_completo[~df_torneo_completo['Girone'].str.contains('Girone Finale', na=False)]
    
    # Aggiungi le nuove righe aggiornate del girone finale
    df_finale_gironi_da_salvare = df_finale_gironi.rename(columns={
        'GironeFinale': 'Girone',
        'GiornataFinale': 'Giornata',
        'CasaFinale': 'Casa',
        'OspiteFinale': 'Ospite'
    })
    df_torneo_completo = pd.concat([df_torneo_completo, df_finale_gironi_da_salvare], ignore_index=True)
    
    if aggiorna_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], df_torneo_completo):
        st.session_state['df_finale_gironi'] = df_finale_gironi
        st.session_state['df_torneo_preliminare'] = df_torneo_completo
        st.success("✅ Risultati dei gironi salvati con successo!")
    else:
        st.error("❌ Errore nel salvataggio dei risultati dei gironi.")


def render_round(df_round: pd.DataFrame, round_index: int):
    """Renderizza un singolo round del tabellone KO."""
    st.markdown(f"<h4 style='color: #008080;'>{df_round['Round'].iloc[0]}</h4>", unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5 = st.columns([0.4, 0.1, 0.4, 0.1, 0.05])
    
    is_current_round = (round_index == len(st.session_state['rounds_ko']) - 1)

    for idx, row in df_round.iterrows():
        match_id = f"ko_match_{row['Match']}_round_{row['Giornata']}"
        
        with col1:
            st.markdown(f"**{row['SquadraA']}**")
        with col2:
            st.number_input("", min_value=0, step=1, key=f"ko_golcasa_{match_id}", 
                            value=int(row['GolA']) if pd.notna(row['GolA']) else 0,
                            disabled=not is_current_round, label_visibility="hidden")
        with col3:
            st.markdown(f"**{row['SquadraB']}**")
        with col4:
            st.number_input("", min_value=0, step=1, key=f"ko_golospite_{match_id}", 
                            value=int(row['GolB']) if pd.notna(row['GolB']) else 0,
                            disabled=not is_current_round, label_visibility="hidden")
        with col5:
            st.checkbox("", key=f"ko_valida_{match_id}", value=row['Valida'],
                        disabled=not is_current_round, label_visibility="hidden")
    
    st.divider()

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
if 'ui_show_pre' not in st.session_state:
    st.session_state['ui_show_pre'] = True

if st.session_state['ui_show_pre']:
    st.header("1. Scegli il torneo")
    
    uri = st.secrets["MONGO_URI_TOURNEMENTS"]
    if not uri:
        st.error("Variabile d'ambiente MONGO_URI_TOURNEMENTS non impostata.")
    tournaments_collection = init_mongo_connection(uri, db_name, col_name, show_ok=False)
    
    if tournaments_collection is not None:
        opzione_selezione = st.radio(
            "Cosa vuoi fare?", 
            ["Creare una nuova fase finale", "Continuare una fase finale esistente", "Visualizza tornei completati"]
        )
        
        if opzione_selezione == "Creare una nuova fase finale":
            tornei_trovati = carica_tornei_da_db(tournaments_collection, prefix=["completato_"])
            st.subheader("Seleziona un torneo preliminare completato")
            if not tornei_trovati:
                st.info("⚠️ Nessun torneo 'COMPLETATO' trovato nel database.")
            else:
                tornei_opzioni = {t['nome_torneo']: str(t['_id']) for t in tornei_trovati}
                scelta_torneo = st.selectbox(
                    "Seleziona il torneo da cui iniziare le fasi finali:",
                    options=list(tornei_opzioni.keys()),
                    key="crea_fase_finale"
                )
                if scelta_torneo:
                    if st.button("Continua con questo torneo (Nuova Fase Finale)"):
                        st.session_state['tournament_name'] = scelta_torneo
                        st.session_state['tournament_id'] = tornei_opzioni[scelta_torneo]
                        
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
                                new_name = f"fasefinale_{torneo_data['nome_torneo']}"
                                new_id, new_name = clona_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], new_name)
                                if new_id:
                                    cloned_torneo_data = carica_torneo_da_db(tournaments_collection, str(new_id))
                                    if cloned_torneo_data:
                                        st.session_state['df_torneo_preliminare'] = pd.DataFrame(cloned_torneo_data['calendario'])
                                        st.session_state['tournament_id'] = str(new_id)
                                        st.session_state['tournament_name'] = new_name
                                        st.session_state['ui_show_pre'] = False
                                        st.session_state['fase_modalita'] = "Nuova fase finale"
                                        st.rerun()
                                    else:
                                        st.error("❌ Errore nel caricamento del torneo clonato.")
                        else:
                            st.error("❌ Errore nel caricamento del torneo. Riprova.")

        elif opzione_selezione == "Continuare una fase finale esistente":
            tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], db_name, col_name)
            tornei_trovati = carica_tornei_da_db(tournaments_collection, prefix=["fasefinale_"])
            st.subheader("Seleziona una fase finale esistente")
            if not tornei_trovati:
                st.info("⚠️ Nessuna fase finale esistente trovata nel database.")
            else:
                tornei_opzioni = {t['nome_torneo']: str(t['_id']) for t in tornei_trovati}
                scelta_torneo = st.selectbox(
                    "Seleziona la fase finale da continuare:",
                    options=list(tornei_opzioni.keys()),
                    key="continua_fase_finale"
                )
                if scelta_torneo:
                    if st.button("Continua con questo torneo"):
                        st.session_state['tournament_name'] = scelta_torneo
                        st.session_state['tournament_id'] = tornei_opzioni[scelta_torneo]
                        
                        torneo_data = carica_torneo_da_db(tournaments_collection, st.session_state['tournament_id'])
                        if torneo_data:
                            df_torneo_completo = pd.DataFrame(torneo_data['calendario'])
                            st.session_state['df_torneo_preliminare'] = df_torneo_completo
                            
                            is_ko_tournament = (df_torneo_completo['Girone'] == 'Eliminazione Diretta').any()
                            is_gironi_finale = (df_torneo_completo['Girone'].str.contains('Girone Finale')).any()

                            if is_ko_tournament:
                                df_ko_esistente = df_torneo_completo[df_torneo_completo['Girone'] == 'Eliminazione Diretta'].copy()
                                
                                rounds_list = []
                                for r in sorted(df_ko_esistente['Giornata'].unique()):
                                    df_round = df_ko_esistente[df_ko_esistente['Giornata'] == r].copy()
                                    df_round.rename(columns={'Casa': 'SquadraA', 'Ospite': 'SquadraB', 'GolCasa': 'GolA', 'GolOspite': 'GolB'}, inplace=True)
                                    df_round['Round'] = f"Round {r}"
                                    df_round['Match'] = df_round.index + 1
                                    rounds_list.append(df_round)
                                st.session_state['rounds_ko'] = rounds_list
                                
                                st.session_state['giornate_mode'] = 'ko'
                                st.session_state['fase_modalita'] = "Eliminazione diretta"
                                st.session_state['ui_show_pre'] = False
                                st.rerun()

                            elif is_gironi_finale:
                                df_gironi_esistente = df_torneo_completo[df_torneo_completo['Girone'].str.contains('Girone Finale')].copy()
                                df_gironi_esistente.rename(columns={'Girone': 'GironeFinale', 'Giornata': 'GiornataFinale', 'Casa': 'CasaFinale', 'Ospite': 'OspiteFinale'}, inplace=True)
                                st.session_state['df_finale_gironi'] = df_gironi_esistente
                                st.session_state['giornate_mode'] = 'gironi'
                                st.session_state['fase_modalita'] = "Gironi"
                                st.session_state['ui_show_pre'] = False
                                st.rerun()
                            else:
                                st.error("❌ Il torneo selezionato non è una fase finale valida.")
                        else:
                            st.error("❌ Errore nel caricamento del torneo. Riprova.")
        
        elif opzione_selezione == "Visualizza tornei completati":
            tornei_completati_trovati = carica_tornei_da_db(tournaments_collection, prefix=["finito_"])
            st.subheader("Seleziona un torneo completato da visualizzare")
            if not tornei_completati_trovati:
                st.info("⚠️ Nessun torneo completato trovato nel database.")
            else:
                tornei_opzioni = {t['nome_torneo']: str(t['_id']) for t in tornei_completati_trovati}
                scelta_torneo_completato = st.selectbox(
                    "Seleziona il torneo completato:",
                    options=list(tornei_opzioni.keys()),
                    key="visualizza_completati"
                )
                if scelta_torneo_completato:
                    if st.button("Visualizza torneo"):
                        st.session_state['tournament_name'] = scelta_torneo_completato
                        st.session_state['tournament_id'] = tornei_opzioni[scelta_torneo_completato]
                        
                        torneo_data = carica_torneo_da_db(tournaments_collection, st.session_state['tournament_id'])
                        if torneo_data:
                            df_torneo_completo = pd.DataFrame(torneo_data['calendario'])
                            st.session_state['df_torneo_preliminare'] = df_torneo_completo
                            
                            is_ko_tournament = (df_torneo_completo['Girone'] == 'Eliminazione Diretta').any()
                            is_gironi_finale = (df_torneo_completo['Girone'].str.contains('Girone Finale')).any()

                            if is_ko_tournament:
                                df_ko_esistente = df_torneo_completo[df_torneo_completo['Girone'] == 'Eliminazione Diretta'].copy()
                                rounds_list = []
                                for r in sorted(df_ko_esistente['Giornata'].unique()):
                                    df_round = df_ko_esistente[df_ko_esistente['Giornata'] == r].copy()
                                    df_round.rename(columns={'Casa': 'SquadraA', 'Ospite': 'SquadraB', 'GolCasa': 'GolA', 'GolOspite': 'GolB'}, inplace=True)
                                    df_round['Round'] = f"Round {r}"
                                    df_round['Match'] = df_round.index + 1
                                    rounds_list.append(df_round)
                                st.session_state['rounds_ko'] = rounds_list
                                st.session_state['giornate_mode'] = 'ko'
                                st.session_state['fase_modalita'] = "Eliminazione diretta"
                                st.session_state['ui_show_pre'] = False
                                st.rerun()
                            
                            elif is_gironi_finale:
                                df_gironi_esistente = df_torneo_completo[df_torneo_completo['Girone'].str.contains('Girone Finale')].copy()
                                df_gironi_esistente.rename(columns={'Girone': 'GironeFinale', 'Giornata': 'GiornataFinale', 'Casa': 'CasaFinale', 'Ospite': 'OspiteFinale'}, inplace=True)
                                st.session_state['df_finale_gironi'] = df_gironi_esistente
                                st.session_state['giornate_mode'] = 'gironi'
                                st.session_state['fase_modalita'] = "Gironi"
                                st.session_state['ui_show_pre'] = False
                                st.rerun()
                            else:
                                st.error("❌ Il torneo selezionato non è una fase finale valida.")
                        else:
                            st.error("❌ Errore nel caricamento del torneo. Riprova.")

else: # Logica per la visualizzazione dei tornei
    st.subheader(f"Torneo: {st.session_state['tournament_name']}")
    
    if st.session_state.get('giornate_mode') == "ko":
        st.markdown("<h3 style='text-align: center;'>Tabellone Eliminazione Diretta</h3>", unsafe_allow_html=True)
        st.divider()

        if 'rounds_ko' not in st.session_state:
            st.error("Dati del tabellone KO non trovati. Riprova.")
            st.button("Torna indietro", on_click=reset_to_setup)
            st.stop()
        
        # Renderizza tutti i round
        for i, df_round in enumerate(st.session_state['rounds_ko']):
            render_round(df_round, i)
        
        # Pulsante di salvataggio
        st.button("💾 Salva risultati e genera prossimo round", on_click=salva_risultati_ko)
        
    elif st.session_state.get('giornate_mode') == "gironi":
        st.markdown("<h3 style='text-align: center;'>Gironi Fase Finale</h3>", unsafe_allow_html=True)
        st.divider()

        if 'df_finale_gironi' in st.session_state:
            df_finale_gironi = st.session_state['df_finale_gironi']
            gironi = sorted(df_finale_gironi['GironeFinale'].unique())

            for girone in gironi:
                with st.expander(f"**Girone {girone}**", expanded=True):
                    # Classifica
                    st.markdown("#### Classifica")
                    classifica = standings_from_matches(df_finale_gironi[df_finale_gironi['GironeFinale'] == girone].rename(columns={'GironeFinale':'Gruppo', 'CasaFinale':'Casa', 'OspiteFinale':'Ospite'}), key_group='Gruppo')
                    if not classifica.empty:
                        classifica.index = classifica.index + 1
                        classifica.insert(0, 'Pos', classifica.index)
                        st.dataframe(classifica[['Pos','Squadra','Punti','V','P','S','GF','GS','DR']], hide_index=True)
                    else:
                        st.info("Nessuna partita validata in questo girone.")
                    
                    st.markdown("#### Calendario partite")
                    partite_girone = df_finale_gironi[df_finale_gironi['GironeFinale'] == girone]

                    col1, col2, col3, col4, col5 = st.columns([0.4, 0.1, 0.4, 0.1, 0.05])
                    
                    for idx, row in partite_girone.iterrows():
                        unique_key = f"gironi_match_{row['GironeFinale']}_{row['GiornataFinale']}_{row['CasaFinale']}_{row['OspiteFinale']}"
                        
                        is_disabled = row['Valida']
                        
                        with col1:
                            st.markdown(f"**{row['CasaFinale']}**")
                        with col2:
                            st.number_input("", min_value=0, step=1, key=f"gironi_golcasa_{unique_key}", 
                                            value=int(row['GolCasa']) if pd.notna(row['GolCasa']) else 0,
                                            disabled=is_disabled, label_visibility="hidden")
                        with col3:
                            st.markdown(f"**{row['OspiteFinale']}**")
                        with col4:
                            st.number_input("", min_value=0, step=1, key=f"gironi_golospite_{unique_key}", 
                                            value=int(row['GolOspite']) if pd.notna(row['GolOspite']) else 0,
                                            disabled=is_disabled, label_visibility="hidden")
                        with col5:
                            st.checkbox("", key=f"gironi_valida_{unique_key}", value=row['Valida'],
                                        disabled=is_disabled, label_visibility="hidden")

                    st.button(f"💾 Salva risultati Girone {girone}", key=f"save_gironi_{girone}", on_click=salva_risultati_gironi)

    # Pulsante per tornare al menu principale
    st.button("Torna al menu principale", on_click=reset_to_setup)
