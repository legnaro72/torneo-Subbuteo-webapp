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
        
        # FIX: Renaming delle colonne 'CasaFinale' e 'OspiteFinale' per la funzione di classifica
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
            pdf.cell(0, 7, f"{match['SquadraA']} vs {match['SquadraB']} ({res})", 0, 1)
        pdf.set_text_color(0, 0, 0)
    
    return pdf.output(dest='S').encode('latin1')

def get_mongo_collection():
    """Connessione a MongoDB e recupero collezione."""
    try:
        # Aggiungi st.secrets per le credenziali
        user = st.secrets["mongodb"]["user"]
        pwd = st.secrets["mongodb"]["password"]
        cluster_name = st.secrets["mongodb"]["cluster_name"]
        uri = f"mongodb+srv://{user}:{pwd}@{cluster_name}.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
        
        client = MongoClient(uri, server_api=ServerApi('1'))
        db = client['TorneiDB']
        collection = db['fasiFinali']
        return collection
    except Exception as e:
        st.error(f"Errore di connessione a MongoDB: {e}")
        return None

# ==============================================================================
# 🎯 Funzioni principali dell'app
# ==============================================================================

def salva_torneo_mongodb(torneo_df, nome_torneo):
    """Salva il DataFrame del torneo su MongoDB."""
    collection = get_mongo_collection()
    if collection is None:
        return
    try:
        # Pulisce i dati esistenti per evitare duplicati
        collection.delete_many({'NomeTorneo': nome_torneo})
        
        # Converte il DataFrame in un formato che può essere salvato in MongoDB
        records = torneo_df.to_dict('records')
        
        # Salva i record nella collezione
        document = {
            'NomeTorneo': nome_torneo,
            'DataCaricamento': pd.Timestamp.now().isoformat(),
            'Partite': records,
            'TipoFase': 'gironi' if 'GironeFinale' in torneo_df.columns else 'ko'
        }
        collection.insert_one(document)
        st.success(f"Torneo '{nome_torneo}' salvato con successo su MongoDB! ✅")
    except Exception as e:
        st.error(f"Errore durante il salvataggio del torneo su MongoDB: {e}")

def carica_tornei_disponibili():
    """Carica la lista dei tornei disponibili da MongoDB."""
    collection = get_mongo_collection()
    if collection is None:
        return []
    try:
        tornei = collection.find({}, {'NomeTorneo': 1, 'DataCaricamento': 1, 'TipoFase': 1})
        return list(tornei)
    except Exception as e:
        st.error(f"Errore durante il caricamento dei tornei: {e}")
        return []

def carica_torneo_selezionato(nome_torneo):
    """Carica un torneo specifico da MongoDB in st.session_state."""
    collection = get_mongo_collection()
    if collection is None:
        return
    
    try:
        document = collection.find_one({'NomeTorneo': nome_torneo})
        if document:
            st.session_state['nome_torneo'] = nome_torneo
            st.session_state['Partite'] = pd.DataFrame(document['Partite'])
            st.session_state['giornate_mode'] = document['TipoFase']
            st.session_state['fase_corrente_caricata'] = True
            
            if st.session_state['giornate_mode'] == 'gironi':
                st.session_state['df_finale_gironi'] = st.session_state['Partite']
            elif st.session_state['giornate_mode'] == 'ko':
                st.session_state['rounds_ko'] = parse_ko_rounds(st.session_state['Partite'])

            st.rerun()

        else:
            st.error(f"Torneo '{nome_torneo}' non trovato.")
    except Exception as e:
        st.error(f"Errore durante il caricamento del torneo: {e}")
        
def parse_ko_rounds(df: pd.DataFrame) -> list[pd.DataFrame]:
    """Trasforma un DataFrame KO salvato in una lista di DataFrame per ogni round."""
    rounds = sorted(df['RoundNumber'].unique())
    rounds_ko_list = []
    for r in rounds:
        round_df = df[df['RoundNumber'] == r].copy()
        rounds_ko_list.append(round_df)
    return rounds_ko_list

def create_ko_table(rounds_ko: list[pd.DataFrame]) -> pd.DataFrame:
    """Combina la lista di DataFrame dei round KO in un unico DataFrame per il salvataggio."""
    return pd.concat(rounds_ko, ignore_index=True)

def home_page():
    """Pagina iniziale per caricare o creare un torneo."""
    st.title("⚽ Fasi Finali Torneo ⚽")
    st.markdown("""
        Questa applicazione ti aiuta a gestire le fasi finali di un torneo, sia a gironi che a eliminazione diretta.
        Carica un file CSV con l'elenco delle squadre o riprendi un torneo salvato.
    """)
    st.divider()

    col1, col2 = st.columns(2)
    
    with col1:
        st.header("1️⃣ Carica un torneo esistente")
        tornei_disponibili = carica_tornei_disponibili()
        if tornei_disponibili:
            nomi_tornei = [t['NomeTorneo'] for t in tornei_disponibili]
            selected_torneo = st.selectbox(
                "Seleziona un torneo da caricare:",
                nomi_tornei,
                index=None,
                placeholder="Scegli un torneo salvato..."
            )
            if selected_torneo and st.button("▶️ Riprendi il torneo"):
                carica_torneo_selezionato(selected_torneo)
        else:
            st.info("Nessun torneo salvato su MongoDB. Crea un nuovo torneo.")

    with col2:
        st.header("2️⃣ Inizia un nuovo torneo")
        uploaded_file = st.file_uploader("Carica un file CSV (solo squadre)", type="csv")
        if uploaded_file is not None:
            try:
                df_squadre = pd.read_csv(uploaded_file)
                if 'Squadre' in df_squadre.columns:
                    st.session_state['squadre_iniziali'] = df_squadre['Squadre'].dropna().tolist()
                    st.success(f"{len(st.session_state['squadre_iniziali'])} squadre caricate con successo! Clicca 'Procedi' per configurare il torneo.")
                    if st.button("Procedi con la configurazione"):
                        st.session_state['fase_corrente'] = 'setup'
                        st.rerun()
                else:
                    st.error("Il file CSV deve contenere una colonna chiamata 'Squadre'.")
            except Exception as e:
                st.error(f"Errore nel leggere il file CSV. Assicurati che sia formattato correttamente. Errore: {e}")

    if 'fase_corrente' in st.session_state and st.session_state['fase_corrente'] == 'home' and not ('fase_corrente_caricata' in st.session_state and st.session_state['fase_corrente_caricata']):
        st.info("Se hai caricato un file CSV, usa il pulsante 'Procedi' per continuare.")


def setup_page():
    """Pagina di configurazione del torneo (numero gironi o KO)."""
    st.title("⚙️ Configurazione Fasi Finali")
    st.markdown(f"**Squadre caricate:** {len(st.session_state['squadre_iniziali'])} in totale.")
    
    st.session_state['nome_torneo'] = st.text_input(
        "Dai un nome al tuo torneo:",
        value=st.session_state.get('nome_torneo', 'Nuovo Torneo Finale')
    )

    tipo_fase = st.radio(
        "Scegli il tipo di fase finale:",
        ['Fase a Gironi', 'Eliminazione Diretta (KO)'],
        index=0 if st.session_state.get('giornate_mode') == 'gironi' else 1,
        key='tipo_fase'
    )
    
    st.session_state['giornate_mode'] = 'gironi' if tipo_fase == 'Fase a Gironi' else 'ko'

    if st.session_state['giornate_mode'] == 'gironi':
        max_gironi = len(st.session_state['squadre_iniziali']) // 2
        st.session_state['num_gironi'] = st.slider(
            "Numero di gironi:",
            min_value=2,
            max_value=max_gironi if max_gironi > 1 else 2,
            value=st.session_state.get('num_gironi', 2)
        )
        if len(st.session_state['squadre_iniziali']) % st.session_state['num_gironi'] != 0:
            st.warning("Il numero di squadre non è divisibile per il numero di gironi. Le squadre verranno distribuite in modo diseguale.")
            
    if st.button("Genera Calendario"):
        st.session_state['fase_corrente'] = 'play'
        st.session_state['fase_corrente_caricata'] = False # Per distinguere tra generazione e caricamento
        st.rerun()

    st.button("Torna indietro", on_click=reset_to_home)

def reset_to_home():
    """Resetta lo stato per tornare alla pagina iniziale."""
    for key in ['fase_corrente', 'squadre_iniziali', 'df_finale_gironi', 'rounds_ko', 'giornate_mode', 'fase_corrente_caricata', 'nome_torneo']:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state['fase_corrente'] = 'home'
    st.rerun()

def reset_to_setup():
    """Resetta lo stato per tornare alla pagina di configurazione."""
    for key in ['df_finale_gironi', 'rounds_ko', 'fase_corrente_caricata', 'nome_torneo']:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state['fase_corrente'] = 'setup'
    st.rerun()

def salva_risultati_gironi():
    """Salva i risultati delle partite a gironi."""
    if 'df_finale_gironi' not in st.session_state:
        st.error("Nessun torneo a gironi trovato nello stato della sessione.")
        return
    
    df = st.session_state['df_finale_gironi'].copy()
    
    for idx, row in df.iterrows():
        try:
            valida_key = f"gironi_valida_{idx}"
            gol_casa_key = f"gironi_golcasa_{idx}"
            gol_ospite_key = f"gironi_golospite_{idx}"
            
            if st.session_state[valida_key]:
                df.at[idx, 'Valida'] = True
                df.at[idx, 'GolCasa'] = int(st.session_state[gol_casa_key])
                df.at[idx, 'GolOspite'] = int(st.session_state[gol_ospite_key])
            else:
                df.at[idx, 'Valida'] = False
        except (KeyError, ValueError):
            # In caso di errore (es. campi vuoti), continua ignorando
            continue
            
    st.session_state['df_finale_gironi'] = df
    salva_torneo_mongodb(df, st.session_state['nome_torneo'])
    st.rerun()

def salva_risultati_ko():
    """Salva i risultati del round KO e genera il prossimo round."""
    if 'rounds_ko' not in st.session_state or not st.session_state['rounds_ko']:
        st.error("Nessun torneo KO trovato nello stato della sessione.")
        return
        
    current_round_df = st.session_state['rounds_ko'][-1].copy()
    
    vincitori_round = []
    
    for idx, row in current_round_df.iterrows():
        try:
            valida_key = f"ko_valida_{idx}"
            gol_a_key = f"ko_gola_{idx}"
            gol_b_key = f"ko_golb_{idx}"
            
            valida = st.session_state[valida_key]
            current_round_df.at[idx, 'Valida'] = valida
            
            if valida:
                gola = int(st.session_state[gol_a_key])
                golb = int(st.session_state[gol_b_key])
                current_round_df.at[idx, 'GolA'] = gola
                current_round_df.at[idx, 'GolB'] = golb
                
                # Determina il vincitore
                if gola > golb:
                    vincitori_round.append(row['SquadraA'])
                elif golb > gola:
                    vincitori_round.append(row['SquadraB'])
                else:
                    st.warning(f"Partita tra {row['SquadraA']} e {row['SquadraB']} è un pareggio. Le partite KO devono avere un vincitore. Considera i calci di rigore.")
                    return
        except (KeyError, ValueError):
            st.error("Assicurati di inserire i gol per tutte le partite del round corrente.")
            return

    # Se tutte le partite del round corrente sono validate
    if len(vincitori_round) == len(current_round_df):
        st.session_state['rounds_ko'][-1] = current_round_df
        
        # Genera il prossimo round se ci sono più di 1 vincitore
        if len(vincitori_round) > 1:
            prossimo_round_df = generate_ko_round(vincitori_round, len(st.session_state['rounds_ko']) + 1)
            st.session_state['rounds_ko'].append(prossimo_round_df)
        else:
            st.success(f"🏆 Torneo concluso! Il vincitore è: **{vincitori_round[0]}**")

    # Salva il tabellone completo su MongoDB
    full_ko_df = create_ko_table(st.session_state['rounds_ko'])
    salva_torneo_mongodb(full_ko_df, st.session_state['nome_torneo'])
    st.rerun()
    
def generate_gironi_calendar():
    """Genera il calendario per la fase a gironi."""
    squadre = st.session_state['squadre_iniziali']
    num_gironi = st.session_state['num_gironi']
    
    classifica_iniziale = classifica_complessiva(pd.DataFrame(columns=REQUIRED_COLS)) # Classifica vuota
    if not classifica_iniziale.empty:
        squadre.sort(key=lambda s: classifica_iniziale[classifica_iniziale['Squadra'] == s]['Punti'].iloc[0], reverse=True)
    
    gironi_teams = serpentino_seed(squadre, num_gironi)
    
    final_df_list = []
    for i, teams in enumerate(gironi_teams):
        girone_name = f"Girone {chr(65+i)}"
        girone_df = round_robin(teams)
        girone_df['GironeFinale'] = girone_name
        girone_df['CasaFinale'] = girone_df['Casa']
        girone_df['OspiteFinale'] = girone_df['Ospite']
        girone_df['GiornataFinale'] = girone_df['Giornata']
        girone_df['GolCasa'] = pd.NA
        girone_df['GolOspite'] = pd.NA
        girone_df['Valida'] = False
        final_df_list.append(girone_df)
        
    df_finale_gironi = pd.concat(final_df_list, ignore_index=True)
    st.session_state['df_finale_gironi'] = df_finale_gironi
    
def generate_ko_round(squadre: list[str], round_num: int) -> pd.DataFrame:
    """Genera un singolo round KO a partire da una lista di squadre."""
    if len(squadre) % 2 != 0:
        st.error("Il numero di squadre per il round KO deve essere pari.")
        st.stop()
    
    ko_matches = bilanciato_ko_seed(squadre)
    rows = []
    round_name = ""
    if len(squadre) == 16:
        round_name = "Ottavi di Finale"
    elif len(squadre) == 8:
        round_name = "Quarti di Finale"
    elif len(squadre) == 4:
        round_name = "Semifinali"
    elif len(squadre) == 2:
        round_name = "Finale"
    else:
        round_name = f"Round {round_num}"

    for i, (sq_a, sq_b) in enumerate(ko_matches):
        rows.append({
            'RoundNumber': round_num,
            'Round': round_name,
            'MatchID': f"R{round_num}M{i+1}",
            'SquadraA': sq_a,
            'SquadraB': sq_b,
            'GolA': pd.NA,
            'GolB': pd.NA,
            'Valida': False
        })
    return pd.DataFrame(rows)
    
def render_round(df_round: pd.DataFrame, round_idx: int):
    """Renderizza un singolo round di partite, con campi modificabili o meno."""
    st.markdown(f"**{df_round['Round'].iloc[0]}**")
    for idx, row in df_round.iterrows():
        col1, col2, col3, col4, col5 = st.columns([0.4, 0.1, 0.1, 0.3, 0.1])
        
        is_valida = to_bool_series(pd.Series([row['Valida']])).iloc[0]

        with col1:
            st.markdown(f"**{row['SquadraA']}**")
        with col2:
            st.number_input(
                "Gol A",
                min_value=0,
                step=1,
                key=f"ko_gola_{idx}",
                value=int(row['GolA']) if pd.notna(row['GolA']) else 0,
                disabled=is_valida,
                label_visibility="hidden"
            )
        with col3:
            st.number_input(
                "Gol B",
                min_value=0,
                step=1,
                key=f"ko_golb_{idx}",
                value=int(row['GolB']) if pd.notna(row['GolB']) else 0,
                disabled=is_valida,
                label_visibility="hidden"
            )
        with col4:
            st.markdown(f"**{row['SquadraB']}**")
        with col5:
            st.checkbox(
                "Valida",
                key=f"ko_valida_{idx}",
                value=is_valida,
                disabled=is_valida
            )
    st.divider()

def play_page():
    """Pagina di gestione del torneo in corso."""
    st.title(f"▶️ Torneo in Corso: {st.session_state.get('nome_torneo', 'N/A')}")
    st.markdown(f"<p class='small-muted'>Ultimo salvataggio: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}</p>", unsafe_allow_html=True)

    if st.session_state['giornate_mode'] == 'gironi':
        if 'df_finale_gironi' not in st.session_state or ('fase_corrente_caricata' in st.session_state and not st.session_state['fase_corrente_caricata']):
            generate_gironi_calendar()
        
        df_finale_gironi = st.session_state['df_finale_gironi']
        gironi = sorted(df_finale_gironi['GironeFinale'].unique())

        st.markdown("<h3 style='text-align: center;'>Calendario e Classifiche Gironi</h3>", unsafe_allow_html=True)
        st.divider()
        
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
                for original_idx, row in partite_girone.iterrows():
                    col1, col2, col3, col4, col5 = st.columns([0.4, 0.1, 0.1, 0.3, 0.1])
                    
                    with col1:
                        st.markdown(f"**{row['CasaFinale']}**")
                    with col2:
                        st.number_input(
                            f"Gol Casa {original_idx}",
                            min_value=0,
                            step=1,
                            key=f"gironi_golcasa_{original_idx}",
                            value=int(row['GolCasa']) if pd.notna(row['GolCasa']) else 0,
                            disabled=row['Valida'], label_visibility="hidden"
                        )
                    with col3:
                        st.number_input(
                            f"Gol Ospite {original_idx}",
                            min_value=0,
                            step=1,
                            key=f"gironi_golospite_{original_idx}",
                            value=int(row['GolOspite']) if pd.notna(row['GolOspite']) else 0,
                            disabled=row['Valida'], label_visibility="hidden"
                        )
                    with col4:
                        st.markdown(f"**{row['OspiteFinale']}**")
                    with col5:
                        st.checkbox("Valida", key=f"gironi_valida_{original_idx}", value=row['Valida'])

                st.button(f"💾 Salva risultati Girone {girone}", key=f"save_gironi_{girone}", on_click=salva_risultati_gironi)

    elif st.session_state['giornate_mode'] == 'ko':
        st.markdown("<h3 style='text-align: center;'>Tabellone Eliminazione Diretta</h3>", unsafe_allow_html=True)
        st.divider()

        if 'rounds_ko' not in st.session_state or ('fase_corrente_caricata' in st.session_state and not st.session_state['fase_corrente_caricata']):
            # Genera il primo round se non esiste
            st.session_state['rounds_ko'] = [generate_ko_round(st.session_state['squadre_iniziali'], 1)]
            
        if st.session_state['rounds_ko']:
            # Renderizza i round completati
            for i, df_round in enumerate(st.session_state['rounds_ko'][:-1]):
                st.markdown(f"**{df_round['Round'].iloc[0]}** (completato)")
                for _, row in df_round.iterrows():
                    vincitore = row['SquadraA'] if row['GolA'] > row['GolB'] else row['SquadraB']
                    st.markdown(f"**{row['SquadraA']}** {int(row['GolA'])} - {int(row['GolB'])} **{row['SquadraB']}** - Vincitore: **{vincitore}**")
                st.divider()

            # Renderizza il round corrente con i campi editabili
            current_round_df = st.session_state['rounds_ko'][-1]
            render_round(current_round_df, len(st.session_state['rounds_ko']) - 1)
            
            st.button("💾 Salva risultati e genera prossimo round", on_click=salva_risultati_ko)
    
    st.button("Torna al menu principale", on_click=reset_to_home)
    
    # Download dei PDF
    if st.session_state['giornate_mode'] == 'gironi' and 'df_finale_gironi' in st.session_state and not st.session_state['df_finale_gironi'].empty:
        pdf_data = generate_pdf_gironi(st.session_state['df_finale_gironi'])
        st.download_button(
            label="Scarica PDF Gironi",
            data=pdf_data,
            file_name="fase_a_gironi.pdf",
            mime="application/pdf"
        )

    if st.session_state['giornate_mode'] == 'ko' and 'rounds_ko' in st.session_state:
        pdf_data = generate_pdf_ko(st.session_state['rounds_ko'])
        st.download_button(
            label="Scarica PDF Tabellone KO",
            data=pdf_data,
            file_name="tabellone_ko.pdf",
            mime="application/pdf"
        )
# ==============================================================================
# 🚀 Punto di ingresso dell'app
# ==============================================================================

if 'fase_corrente' not in st.session_state:
    st.session_state['fase_corrente'] = 'home'
    st.session_state['fase_corrente_caricata'] = False

if st.session_state['fase_corrente'] == 'home':
    home_page()
elif st.session_state['fase_corrente'] == 'setup':
    setup_page()
elif st.session_state['fase_corrente'] == 'play':
    play_page()
