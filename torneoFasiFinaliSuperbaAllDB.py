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
        return False, "Sono presenti partite non validate."
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
        
        classifica = standings_from_matches(girone_blocco.rename(columns={'GironeFinale': 'Gruppo'}), key_group='Gruppo')
        
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

        partite_girone = girone_blocco.sort_values(by=['Giornata']).reset_index(drop=True)
        for _, partita in partite_girone.iterrows():
            if not is_complete and not partita['Valida']:
                pdf.set_text_color(255, 0, 0)
            else:
                pdf.set_text_color(0, 0, 0)
            
            res = f"{int(partita['GolCasa'])} - {int(partita['GolOspite'])}" if partita['Valida'] and pd.notna(partita['GolCasa']) and pd.notna(partita['GolOspite']) else " - "
            pdf.cell(0, 7, f"Giornata {int(partita['Giornata'])}: {partita['Casa']} vs {partita['Ospite']} ({res})", 0, 1)

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
            st.info(f"Connessione a {db_name}.{collection_name} ok.")
        return col
    except Exception as e:
        st.error(f"❌ Errore di connessione a {db_name}.{collection_name}: {e}")
        return None

def carica_tornei_da_db(tournaments_collection, prefix: str):
    """Carica l'elenco dei tornei dal DB filtrando per prefisso."""
    if tournaments_collection is None:
        return []
    try:
        tornei = tournaments_collection.find({"nome_torneo": {"$regex": f"^{prefix}"}}, {"nome_torneo": 1})
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
        if st.session_state.get('fase_modalita') == "Gironi" and 'df_finale_gironi' in st.session_state:
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
        if st.session_state.get('fase_modalita') == "Eliminazione diretta" and 'rounds_ko' in st.session_state:
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

# ==============================================================================
# 🚀 LOGICA APPLICAZIONE PRINCIPALE
# ==============================================================================

if st.session_state['ui_show_pre']:
    st.header("1. Scegli il torneo preliminare da cui partire")
    
    # Connessione e caricamento tornei dal DB
    uri = os.environ.get("MONGODB_URI") # Assumi che la URI sia in una variabile d'ambiente
    if not uri:
        st.error("Variabile d'ambiente MONGODB_URI non impostata.")
    
    db_name = "TorneiSubbuteo"
    col_name = "Superba"
    tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], "TorneiSubbuteo", "Superba", show_ok=False)
    
    if tournaments_collection:
        tornei_trovati = carica_tornei_da_db(tournaments_collection, prefix="COMPLETATO UNDERSCORE")
        
        if not tornei_trovati:
            st.info("⚠️ Nessun torneo 'COMPLETATO UNDERSCORE' trovato nel database.")
        else:
            tornei_opzioni = {t['nome_torneo']: str(t['_id']) for t in tornei_trovati}
            
            scelta_torneo = st.selectbox(
                "Seleziona il torneo da cui iniziare le fasi finali:",
                options=list(tornei_opzioni.keys())
            )
            
            if scelta_torneo:
                st.session_state['tournament_name'] = scelta_torneo
                st.session_state['tournament_id'] = tornei_opzioni[scelta_torneo]
                
                if st.button("Continua con questo torneo"):
                    torneo_data = carica_torneo_da_db(tournaments_collection, st.session_state['tournament_id'])
                    if torneo_data:
                        st.session_state['df_torneo_preliminare'] = pd.DataFrame(torneo_data['calendario'])
                        is_complete, msg = tournament_is_complete(st.session_state['df_torneo_preliminare'])
                        if not is_complete:
                            st.error(f"❌ Il torneo preliminare selezionato non è completo: {msg}")
                        else:
                            st.session_state['ui_show_pre'] = False
                            st.rerun()

else:
    if 'df_torneo_preliminare' not in st.session_state or st.session_state['df_torneo_preliminare'] is None:
        st.error("Dati del torneo non caricati. Riprova a selezionare un torneo.")
        st.button("Torna indietro", on_click=reset_to_setup)
    else:
        df_torneo = st.session_state['df_torneo_preliminare']
        df_classifica = classifica_complessiva(df_torneo)
        if df_classifica.empty:
            st.error("Nessuna partita valida trovata nel torneo preliminare.")
            st.button("Torna indietro", on_click=reset_to_setup)
            st.stop()
        
        st.markdown("<h3 style='text-align: center;'>Classifica Fase Preliminare</h3>", unsafe_allow_html=True)
        st.dataframe(df_classifica, use_container_width=True)
        st.divider()

        st.header("2. Scegli la fase finale")
        if st.session_state['fase_modalita'] is None:
            # Opzioni fase finale
            fase_finale_scelta = st.radio(
                "Seleziona la modalità della fase finale:",
                ["Gironi finali", "Eliminazione diretta"]
            )
            
            if fase_finale_scelta == "Gironi finali":
                # Logica per la fase a gironi
                st.session_state['fase_scelta'] = "gironi"
                st.session_state['fase_modalita'] = "Gironi"
                st.session_state['n_finalisti'] = st.number_input("Quante squadre partecipano alla fase finale?", min_value=1, max_value=len(df_classifica), value=min(len(df_classifica), 8))
                st.session_state['gironi_num'] = st.number_input("In quanti gironi finali?", min_value=1, max_value=math.ceil(st.session_state['n_finalisti']/2), value=1)
                st.session_state['gironi_ar'] = st.checkbox("Turno andata e ritorno?")
                st.session_state['gironi_seed'] = st.radio("Metodo di distribuzione", ["Serpentino", "Casuale"])
                
                if st.button("Genera gironi e calendario"):
                    qualificati = list(df_classifica.head(st.session_state['n_finalisti'])['Squadra'])
                    if len(qualificati) < st.session_state['n_finalisti']:
                        st.warning("Non ci sono abbastanza squadre qualificate.")
                    else:
                        gironi = serpentino_seed(qualificati, st.session_state['gironi_num']) if st.session_state['gironi_seed'] == "Serpentino" else [qualificati]
                        df_finale_gironi = pd.DataFrame()
                        for i, teams in enumerate(gironi, 1):
                            if len(teams) > 1:
                                df_girone = round_robin(teams, st.session_state['gironi_ar'])
                                df_girone.rename(columns={'Giornata': 'GiornataFinale', 'Casa': 'CasaFinale', 'Ospite': 'OspiteFinale'}, inplace=True)
                                df_girone['GironeFinale'] = f"Girone {i}"
                                df_finale_gironi = pd.concat([df_finale_gironi, df_girone], ignore_index=True)
                        
                        df_finale_gironi['GolCasa'] = None; df_finale_gironi['GolOspite'] = None; df_finale_gironi['Valida'] = False
                        df_finale_gironi.insert(0, 'GironeFinale', df_finale_gironi.pop('GironeFinale'))
                        df_finale_gironi.insert(1, 'GiornataFinale', df_finale_gironi.pop('GiornataFinale'))
                        st.session_state['df_finale_gironi'] = df_finale_gironi
                        st.session_state['giornate_mode'] = 'gironi'
                        st.rerun()

            elif fase_finale_scelta == "Eliminazione diretta":
                # Logica per l'eliminazione diretta
                st.session_state['fase_scelta'] = "ko"
                st.session_state['fase_modalita'] = "Eliminazione diretta"
                n_squadre_ko = st.number_input("Quante squadre partecipano all'eliminazione diretta?", min_value=2, value=min(16, len(df_classifica)), step=1)
                if not n_squadre_ko or (n_squadre_ko & (n_squadre_ko - 1) != 0):
                    st.warning("Il numero di squadre deve essere una potenza di 2 (es. 2, 4, 8, 16...).")
                    st.stop()
                st.session_state['n_inizio_ko'] = n_squadre_ko
                
                ko_seed = st.radio("Metodo di accoppiamento", ["Serpentino", "Casuale"])
                
                if st.button("Genera tabellone"):
                    qualificati = list(df_classifica.head(n_squadre_ko)['Squadra'])
                    if ko_seed == "Casuale":
                        import random
                        random.shuffle(qualificati)
                    
                    st.session_state['seeds_ko'] = qualificati
                    st.session_state['round_corrente'] = f"Ottavi di finale (di {n_squadre_ko})" if n_squadre_ko == 16 else f"Quarti di finale (di {n_squadre_ko})" if n_squadre_ko == 8 else f"Semifinali (di {n_squadre_ko})" if n_squadre_ko == 4 else f"Finale (di {n_squadre_ko})"
                    
                    matches = []
                    for i in range(0, n_squadre_ko, 2):
                        matches.append({
                            'Round': st.session_state['round_corrente'],
                            'Match': (i//2) + 1,
                            'SquadraA': qualificati[i],
                            'SquadraB': qualificati[i+1],
                            'GolA': None, 'GolB': None, 'Valida': False, 'Vincitore': None
                        })
                    
                    st.session_state['rounds_ko'] = [pd.DataFrame(matches)]
                    st.session_state['giornate_mode'] = 'ko'
                    st.rerun()

        # Renderizza il calendario/tabellone se già generato
        if st.session_state.get('giornate_mode'):
            st.divider()
            
            # Funzione per salvare i risultati dei gironi su DB
            def salva_risultati_gironi():
                df_finale = st.session_state['df_finale_gironi']
                
                for idx, row in df_finale.iterrows():
                    valida_val = st.session_state.get(f"gironi_valida_{idx}", False)
                    if valida_val:
                        gol_casa_val = st.session_state.get(f"gironi_golcasa_{idx}")
                        gol_ospite_val = st.session_state.get(f"gironi_golospite_{idx}")
                        
                        df_finale.at[idx, 'GolCasa'] = int(gol_casa_val) if pd.notna(gol_casa_val) else None
                        df_finale.at[idx, 'GolOspite'] = int(gol_ospite_val) if pd.notna(gol_ospite_val) else None
                    df_finale.at[idx, 'Valida'] = valida_val
                
                st.session_state['df_finale_gironi'] = df_finale
                st.session_state['df_torneo_preliminare'] = pd.concat([
                    st.session_state['df_torneo_preliminare'],
                    df_finale.rename(columns={
                        'GironeFinale': 'Girone',
                        'GiornataFinale': 'Giornata',
                        'CasaFinale': 'Casa',
                        'OspiteFinale': 'Ospite'
                    })
                ], ignore_index=True)
                
                tournaments_collection = init_mongo_connection(os.environ.get("MONGODB_URI"), db_name, col_name)
                if tournaments_collection and aggiorna_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], st.session_state['df_torneo_preliminare']):
                    st.success("✅ Risultati dei gironi finali salvati su DB!")
                    st.rerun()
                else:
                    st.error("❌ Errore nel salvataggio su DB.")

            # Funzione per salvare i risultati KO su DB
            def salva_risultati_ko():
                current_round_df = st.session_state['rounds_ko'][-1]
                winners = []
                all_valid = True
                for idx, row in current_round_df.iterrows():
                    valid_key = f"ko_valida_{len(st.session_state['rounds_ko']) - 1}_{idx}"
                    
                    if st.session_state.get(valid_key, False):
                        gol_a = st.session_state.get(f"ko_gola_{len(st.session_state['rounds_ko']) - 1}_{idx}")
                        gol_b = st.session_state.get(f"ko_golb_{len(st.session_state['rounds_ko']) - 1}_{idx}")
                        
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
                            st.error("❌ I pareggi non sono consentiti in un tabellone a eliminazione diretta!")
                            return
                    else:
                        all_valid = False

                if not all_valid:
                    st.error("❌ Per generare il prossimo round, tutte le partite devono essere validate.")
                    return
                
                # Salva i risultati del round corrente su DB
                df_ko_da_salvare = current_round_df.copy()
                df_ko_da_salvare.rename(columns={'SquadraA': 'Casa', 'SquadraB': 'Ospite', 'GolA': 'GolCasa', 'GolB': 'GolOspite'}, inplace=True)
                df_ko_da_salvare['Girone'] = 'Eliminazione Diretta'
                df_ko_da_salvare['Giornata'] = st.session_state['rounds_ko'].index(current_round_df) + 1
                
                st.session_state['df_torneo_preliminare'] = pd.concat([st.session_state['df_torneo_preliminare'], df_ko_da_salvare], ignore_index=True)
                
                tournaments_collection = init_mongo_connection(os.environ.get("MONGODB_URI"), db_name, col_name)
                if tournaments_collection and aggiorna_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], st.session_state['df_torneo_preliminare']):
                    st.success("✅ Risultati salvati su DB!")
                else:
                    st.error("❌ Errore nel salvataggio su DB.")

                if len(winners) > 1:
                    next_round_name = ""
                    if len(winners) == 8:
                        next_round_name = "Quarti di finale"
                    elif len(winners) == 4:
                        next_round_name = "Semifinali"
                    elif len(winners) == 2:
                        next_round_name = "Finale"
                    else:
                        next_round_name = "Fine torneo"

                    if next_round_name != "Fine torneo":
                        next_matches = []
                        for i in range(0, len(winners), 2):
                            next_matches.append({
                                'Round': next_round_name,
                                'Match': (i//2) + 1,
                                'SquadraA': winners[i],
                                'SquadraB': winners[i+1],
                                'GolA': None, 'GolB': None, 'Valida': False, 'Vincitore': None
                            })
                        st.session_state['rounds_ko'].append(pd.DataFrame(next_matches))
                        st.session_state['round_corrente'] = next_round_name
                        st.success(f"Prossimo turno: {next_round_name} generato!")
                    else:
                        st.balloons()
                        st.success(f"🏆 Il torneo è finito! Il vincitore è: **{winners[0]}**")
                else:
                    st.balloons()
                    st.success(f"🏆 Il torneo è finito! Il vincitore è: **{winners[0]}**")
                
                st.rerun()

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

            if st.session_state['giornate_mode'] == 'gironi':
                if 'df_finale_gironi' in st.session_state:
                    st.markdown("<h3 style='text-align: center;'>Calendario e Classifica Gironi Finali</h3>", unsafe_allow_html=True)
                    st.divider()
                    
                    df_finale_gironi = st.session_state['df_finale_gironi']
                    gironi = sorted(df_finale_gironi['GironeFinale'].unique())
                    
                    for girone in gironi:
                        st.subheader(f"Girone: {girone}")
                        df_girone_attivo = df_finale_gironi[df_finale_gironi['GironeFinale'] == girone].copy()
                        
                        df_classifica_girone = standings_from_matches(df_girone_attivo.rename(columns={'GironeFinale': 'Gruppo'}), key_group='Gruppo')
                        if not df_classifica_girone.empty:
                            st.markdown("#### Classifica")
                            st.dataframe(df_classifica_girone)
                        
                        st.markdown("#### Calendario partite")
                        for idx, row in df_girone_attivo.iterrows():
                            col1, col2, col3, col4, col5 = st.columns([5, 1.5, 1, 1.5, 1])
                            with col1:
                                st.markdown(f"**{row['CasaFinale']}** vs **{row['OspiteFinale']}**")
                            with col2:
                                st.number_input(
                                    "", min_value=0, max_value=20, key=f"gironi_golcasa_{idx}",
                                    value=int(row['GolCasa']) if pd.notna(row['GolCasa']) else 0,
                                    disabled=row['Valida'], label_visibility="hidden"
                                )
                            with col3:
                                st.markdown("-")
                            with col4:
                                st.number_input(
                                    "", min_value=0, max_value=20, key=f"gironi_golospite_{idx}",
                                    value=int(row['GolOspite']) if pd.notna(row['GolOspite']) else 0,
                                    disabled=row['Valida'], label_visibility="hidden"
                                )
                            with col5:
                                st.checkbox("Valida", key=f"gironi_valida_{idx}", value=row['Valida'])

                        if st.button(f"💾 Salva risultati Girone {girone}", key=f"save_gironi_{girone}", on_click=salva_risultati_gironi):
                            pass

            elif st.session_state['giornate_mode'] == 'ko':
                st.markdown("<h3 style='text-align: center;'>Tabellone Eliminazione Diretta</h3>", unsafe_allow_html=True)
                st.divider()

                if 'rounds_ko' not in st.session_state:
                    st.error("Dati del tabellone KO non trovati. Riprova.")
                    st.button("Torna indietro", on_click=reset_to_setup)
                    st.stop()
                
                # Renderizza i round completati
                for i, df_round in enumerate(st.session_state['rounds_ko'][:-1]):
                    render_round(df_round, i)
                
                # Renderizza il round corrente con i campi editabili
                if st.session_state['rounds_ko']:
                    current_round_df = st.session_state['rounds_ko'][-1]
                    render_round(current_round_df, len(st.session_state['rounds_ko']) - 1)
                    
                    st.button("💾 Salva risultati e genera prossimo round", on_click=salva_risultati_ko)
