import streamlit as st
import pandas as pd
import math
import os
import re
from fpdf import FPDF
import base64
from io import BytesIO

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
    squadre = pd.unique(partite[['Casa', 'Ospite']].values.ravel('K'))
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
    out = []
    for gruppo, blocco in partite.groupby(key_group):
        squadre = pd.unique(blocco[['Casa','Ospite']].values.ravel('K'))
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
        'giornate_mode', 'tournament_name_raw', 'filter_player', 'filter_girone'
    ]
    for k in keys:
        if k in st.session_state:
            del st.session_state[k]

def reset_to_setup():
    """Reset completo per tornare alla schermata iniziale."""
    reset_fase_finale()
    st.session_state['ui_show_pre'] = True
    st.session_state['fase_modalita'] = None

# Inizializzazione stato
if 'ui_show_pre' not in st.session_state:
    st.session_state['ui_show_pre'] = True
if 'fase_modalita' not in st.session_state:
    st.session_state['fase_modalita'] = None
if 'filter_player' not in st.session_state:
    st.session_state['filter_player'] = None
if 'filter_girone' not in st.session_state:
    st.session_state['filter_girone'] = None

# ==============================================================================
# ⚽ Header dinamico
# ==============================================================================
if 'tournament_name_raw' in st.session_state and not st.session_state['ui_show_pre']:
    cleaned_name = re.sub(r'\(.*\)', '', st.session_state["tournament_name_raw"]).strip()
    st.markdown(f'<h1 class="main-title">🏆 FASE FINALE {cleaned_name}</h1>', unsafe_allow_html=True)
else:
    st.title("⚽ Fasi Finali")
    if 'tournament_name_raw' in st.session_state and st.session_state['ui_show_pre']:
        st.markdown(f"### 🏷️ {st.session_state['tournament_name_raw']}")

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
            "📄 Esporta PDF tabellone completo",
            data=generate_pdf_ko(st.session_state['rounds_ko']),
            file_name="fase_finale_tabellone.pdf",
            mime="application/pdf",
        )
    
    st.divider()
    
    if not st.session_state['ui_show_pre'] and st.session_state.get('fase_modalita') in ["Gironi", "Eliminazione diretta"]:
        st.subheader("🔍 Filtri Partite")
        
        with st.expander("Filtra per Giocatore"):
            if st.session_state.get('fase_modalita') == "Gironi" and 'df_finale_gironi' in st.session_state:
                df_players = st.session_state['df_finale_gironi']
                players_list = sorted(pd.unique(df_players[['Casa','Ospite']].values.ravel('K')))
            elif st.session_state.get('fase_modalita') == "Eliminazione diretta" and 'rounds_ko' in st.session_state:
                df_players = pd.concat(st.session_state['rounds_ko'], ignore_index=True)
                players_list = sorted(pd.unique(df_players[['SquadraA','SquadraB']].values.ravel('K')))
            else:
                players_list = []
        
            selected_player = st.selectbox("Seleziona Giocatore:", ["Nessuno"] + players_list)
        
            if st.button("Filtra Giocatore"):
                if selected_player != "Nessuno":
                    st.session_state['filter_player'] = selected_player
                    st.session_state['filter_girone'] = None
                else:
                    st.session_state['filter_player'] = None
                st.rerun()

        if st.session_state.get('fase_modalita') == "Gironi" and 'df_finale_gironi' in st.session_state:
            with st.expander("Filtra per Girone"):
                gironi_labels = sorted(st.session_state['df_finale_gironi']['GironeFinale'].unique().tolist())
                girone_filter_sel = st.selectbox("Seleziona Girone:", ["Nessuno"] + gironi_labels)
                if st.button("Filtra Girone"):
                    if girone_filter_sel != "Nessuno":
                        st.session_state['filter_girone'] = girone_filter_sel
                        st.session_state['filter_player'] = None
                    else:
                        st.session_state['filter_girone'] = None
                    st.rerun()
                        
        if st.session_state.get('filter_player') or st.session_state.get('filter_girone'):
            st.warning("Filtri attivi. Premi il pulsante qui sotto per rimuoverli.")
            if st.button("❌ Rimuovi Filtri"):
                st.session_state['filter_player'] = None
                st.session_state['filter_girone'] = None
                st.rerun()

# ==============================================================================
# 📂 Uploader CSV (vista PRE-generazione)
# ==============================================================================
if st.session_state['ui_show_pre']:
    st.subheader("Carica il tuo torneo concluso 🏁")
    file = st.file_uploader("📁 Carica CSV torneo concluso", type=["csv"])
    if file is None:
        st.info("Suggerimento: il CSV deve contenere le colonne: " + ", ".join(REQUIRED_COLS))
        st.stop()
    try:
        df_in = pd.read_csv(file)
    except Exception as e:
        st.error(f"❌ Errore nel caricamento del CSV: {e}")
        st.stop()
    ok, msg = check_csv_structure(df_in)
    if not ok:
        st.error(f"❌ {msg}")
        st.stop()
    complete, why = tournament_is_complete(df_in)
    if not complete:
        st.error(f"❌ Il torneo **non** risulta completamente validato: {why}")
        st.stop()
    filename = os.path.splitext(file.name)[0]
    base = filename
    for suf in ['_calendario_risultati', '_calendario', '_risultati']:
        if base.endswith(suf):
            base = base[: -len(suf)]
    base = base.rstrip('_')
    st.session_state['tournament_name_raw'] = base
    df_class = classifica_complessiva(df_in)
    st.success("✅ Torneo completo e valido! Classifica calcolata qui sotto.")
    st.dataframe(df_class, use_container_width=True)
    st.divider()
    colA, colB = st.columns([1,1])
    with colA:
        fase_scelta = st.radio(
            "Scegli la formula della fase finale:",
            ["Gironi", "Eliminazione diretta"],
            key="fase_scelta",
            horizontal=True
        )
    st.markdown("<span class='small-muted'>Le squadre vengono **estratte dal CSV** e ordinate per piazzamento complessivo. I migliori affrontano i peggiori nelle fasi ad eliminazione; nei gironi la distribuzione è **a serpentina**.</span>", unsafe_allow_html=True)
    if fase_scelta == "Gironi":
        with st.expander("⚙️ Impostazioni Gironi", expanded=True):
            num_gironi = st.number_input("Numero di gironi", min_value=1, max_value=16, value=2, step=1, key="gironi_num")
            andata_ritorno = st.checkbox("Andata e ritorno", value=False, key="gironi_ar")
            totale = len(df_class)
            max_per_girone = math.ceil(totale/num_gironi)
            n_partecipanti = st.slider("Numero partecipanti alla fase finale a gironi", min_value=num_gironi, max_value=totale, value=totale, step=1)
            st.caption(f"Distribuzione massima per girone ~ {max_per_girone} (con {totale} totali).")
        if st.button("🎲 Genera Gironi (serpentina)"):
            seeds = df_class['Squadra'].tolist()[:n_partecipanti]
            gironi = serpentino_seed(seeds, num_gironi)
            labels = [chr(ord('A') + i) for i in range(num_gironi)]
            assegnazione = {f"Girone {labels[i]}": gironi[i] for i in range(num_gironi)}
            rows = []
            for lab, teams in assegnazione.items():
                df_rr = round_robin(teams, andata_ritorno=andata_ritorno)
                if df_rr.empty:
                    continue
                df_rr['GironeFinale'] = lab
                df_rr['GolCasa'] = None
                df_rr['GolOspite'] = None
                df_rr['Valida'] = False
                rows.append(df_rr[['GironeFinale','Giornata','Casa','Ospite','GolCasa','GolOspite','Valida']])
            df_finale = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=['GironeFinale','Giornata','Casa','Ospite','GolCasa','GolOspite','Valida'])
            st.session_state['gironi_seed'] = assegnazione
            st.session_state['df_finale_gironi'] = df_finale
            st.session_state['ui_show_pre'] = False
            st.session_state['fase_modalita'] = "Gironi"
            st.session_state['giornate_mode'] = "Menu a tendina"
            st.rerun()
    if fase_scelta == "Eliminazione diretta":
        round_map = {"Ottavi":16, "Quarti":8, "Semifinali":4, "Finale":2}
        col1, col2 = st.columns([1,1])
        with col1:
            start_round_label = st.selectbox("Parti da", list(round_map.keys()))
        n_start = round_map[start_round_label]
        topN = len(df_class)
        if topN < n_start:
            st.warning(f"⚠️ Servono almeno **{n_start}** squadre per partire da {start_round_label.lower()}. Nel CSV ci sono {topN} squadre.")
            st.stop()
        st.caption(f"Parteciperanno le **prime {n_start}** della classifica complessiva.")
        if st.button("🧩 Genera tabellone iniziale"):
            seeds = df_class['Squadra'].tolist()[:n_start]
            st.session_state['seeds_ko'] = seeds
            st.session_state['n_inizio_ko'] = n_start
            st.session_state['round_corrente'] = start_round_label
            pairs = []
            for i in range(n_start//2):
                a = seeds[i]; b = seeds[-(i+1)]
                pairs.append({'Round': start_round_label, 'Match': i+1, 'SquadraA': a, 'SquadraB': b, 'GolA': None, 'GolB': None, 'Valida': False, 'Vincitore': None})
            st.session_state['rounds_ko'] = [pd.DataFrame(pairs)]
            st.session_state['ui_show_pre'] = False
            st.session_state['fase_modalita'] = "Eliminazione diretta"
            st.rerun()

# ==============================================================================
# 🏟️ VISTA POST-generazione (calendario e tabellone)
# ==============================================================================
if not st.session_state['ui_show_pre']:
    if st.session_state.get('filter_player') or st.session_state.get('filter_girone'):
        st.subheader("Partite da giocare (filtrate) 🔎")
        filtered_df = pd.DataFrame()
        if st.session_state.get('fase_modalita') == "Gironi" and 'df_finale_gironi' in st.session_state:
            df = st.session_state['df_finale_gironi']
            filtered_df = df[~to_bool_series(df['Valida'])]
            if st.session_state.get('filter_player'):
                player = st.session_state['filter_player']
                filtered_df = filtered_df[filtered_df.apply(lambda row: player in (row['Casa'], row['Ospite']), axis=1)]
            if st.session_state.get('filter_girone'):
                girone = st.session_state['filter_girone']
                filtered_df = filtered_df[filtered_df['GironeFinale'] == girone]

        elif st.session_state.get('fase_modalita') == "Eliminazione diretta" and 'rounds_ko' in st.session_state:
            df = pd.concat(st.session_state['rounds_ko'], ignore_index=True)
            filtered_df = df[~to_bool_series(df['Valida'])]
            if st.session_state.get('filter_player'):
                player = st.session_state['filter_player']
                filtered_df = filtered_df[filtered_df.apply(lambda row: player in (row['SquadraA'], row['SquadraB']), axis=1)]

        if filtered_df.empty:
            st.info("No matches to play with the current filters.")
        else:
            st.dataframe(filtered_df, use_container_width=True)
            
    else:
        # ------ Modalità A: Gironi (POST) ------
        if st.session_state.get('fase_modalita') == "Gironi":
            if 'gironi_seed' in st.session_state:
                st.subheader("📋 Assegnazione Gironi (serpentina)")
                col1, col2 = st.columns(2)
                items = list(st.session_state['gironi_seed'].items())
                half = math.ceil(len(items)/2)
                with col1:
                    for lab, teams in items[:half]:
                        st.write(f"**{lab}**: {', '.join(teams)}")
                with col2:
                    for lab, teams in items[half:]:
                        st.write(f"**{lab}**: {', '.join(teams)}")
            if 'df_finale_gironi' in st.session_state and not st.session_state['df_finale_gironi'].empty:
                dfg = st.session_state['df_finale_gironi']
                gironi_labels = sorted(dfg['GironeFinale'].unique().tolist())
                if 'girone_sel' not in st.session_state and gironi_labels:
                    st.session_state['girone_sel'] = gironi_labels[0]
                girone_sel = st.selectbox("Seleziona Girone Finale", gironi_labels, index=gironi_labels.index(st.session_state['girone_sel']))
                st.session_state['girone_sel'] = girone_sel
                if 'giornate_mode' not in st.session_state:
                    st.session_state['giornate_mode'] = "Menu a tendina"
                giornate_mode = st.radio(
                    "Selezione giornata con:",
                    ["Menu a tendina", "Bottoni"],
                    index=0 if st.session_state['giornate_mode'] == "Menu a tendina" else 1,
                    horizontal=True
                )
                st.session_state['giornate_mode'] = giornate_mode
                giornate = sorted(dfg[dfg['GironeFinale']==girone_sel]['Giornata'].unique().tolist())
                if 'giornata_sel' not in st.session_state and giornate:
                    st.session_state['giornata_sel'] = giornate[0]
                if giornate_mode == "Menu a tendina":
                    giornata_sel = st.selectbox(
                        "Seleziona Giornata",
                        giornate,
                        index=giornate.index(st.session_state['giornata_sel']) if giornate else 0
                    )
                else:
                    if giornate:
                        cols = st.columns(len(giornate))
                        for i, g in enumerate(giornate):
                            if cols[i].button(f"G {g}", key=f"giornata_btn_{g}"):
                                st.session_state['giornata_sel'] = g
                    giornata_sel = st.session_state.get('giornata_sel', giornate[0] if giornate else None)
                if giornata_sel is None:
                    st.info("Nessuna giornata disponibile.")
                else:
                    st.session_state['giornata_sel'] = giornata_sel
                    st.markdown(f"### 📅 Giornata selezionata: {giornata_sel}")
                    blocco = dfg[(dfg['GironeFinale']==girone_sel) & (dfg['Giornata']==giornata_sel)].copy()
                    st.markdown("### ✏️ Inserisci i risultati")
                    for idx, row in blocco.iterrows():
                        c1, c2, c3, c4, c5 = st.columns([4,1.2,0.6,1.2,1.6])
                        with c1:
                            st.markdown(f"**{row['Casa']}** 🆚 **{row['Ospite']}**")
                        with c2:
                            _ = st.number_input(" ", min_value=0, max_value=99, value=0 if pd.isna(row['GolCasa']) else int(row['GolCasa']), key=f"f_golc_{idx}", label_visibility="hidden")
                        with c3:
                            st.markdown("—")
                        with c4:
                            _ = st.number_input(" ", min_value=0, max_value=99, value=0 if pd.isna(row['GolOspite']) else int(row['GolOspite']), key=f"f_golo_{idx}", label_visibility="hidden")
                        with c5:
                            _ = st.checkbox("Valida", value=bool(row['Valida']), key=f"f_val_{idx}")
                    def salva_giornata():
                        df_loc = st.session_state['df_finale_gironi']
                        loc_idx = (df_loc['GironeFinale']==girone_sel) & (df_loc['Giornata']==giornata_sel)
                        idxs = df_loc[loc_idx].index.tolist()
                        for i in idxs:
                            df_loc.at[i,'GolCasa'] = st.session_state.get(f"f_golc_{i}", 0)
                            df_loc.at[i,'GolOspite'] = st.session_state.get(f"f_golo_{i}", 0)
                            df_loc.at[i,'Valida'] = st.session_state.get(f"f_val_{i}", False)
                        st.session_state['df_finale_gironi'] = df_loc
                        st.success("✅ Risultati salvati.")
                    st.button("💾 Salva risultati giornata", on_click=salva_giornata)
                    st.markdown("---")
                    st.markdown("### 📊 Classifica del girone selezionato")
                    class_g = standings_from_matches(
                        st.session_state['df_finale_gironi'][st.session_state['df_finale_gironi']['GironeFinale']==girone_sel].rename(columns={'GironeFinale':'Gruppo'}),
                        key_group='Gruppo'
                    )
                    if class_g.empty:
                        st.info("Nessuna partita validata finora nel girone selezionato.")
                    else:
                        st.dataframe(class_g, use_container_width=True)

        # ------ Modalità B: Eliminazione Diretta (POST) ------
        if st.session_state.get('fase_modalita') == "Eliminazione diretta":
            def render_round(df_round: pd.DataFrame):
                st.markdown(f"### 🏁 {df_round['Round'].iloc[0]}")
                for _, row in df_round.iterrows():
                    rnd = row['Round']
                    match_n = int(row['Match'])
                    c1, c2, c3, c4, c5, c6 = st.columns([3,1,0.5,1,1.6,2.2])
                    with c1:
                        st.markdown(f"**{row['SquadraA']}** 🆚 **{row['SquadraB']}**")
                    ga_key = f"ko_ga_{rnd}_{match_n}"
                    gb_key = f"ko_gb_{rnd}_{match_n}"
                    val_key = f"ko_val_{rnd}_{match_n}"
                    win_key = f"ko_w_{rnd}_{match_n}"
                    with c2:
                        _ = st.number_input(" ", min_value=0, max_value=99, value=0 if pd.isna(row['GolA']) else int(row['GolA']), key=ga_key, label_visibility="hidden")
                    with c3:
                        st.markdown("—")
                    with c4:
                        _ = st.number_input(" ", min_value=0, max_value=99, value=0 if pd.isna(row['GolB']) else int(row['GolB']), key=gb_key, label_visibility="hidden")
                    with c5:
                        _ = st.checkbox("Valida", value=bool(row['Valida']), key=val_key)
                    options = [row['SquadraA'], row['SquadraB']]
                    default_index = 0
                    if pd.notna(row.get('Vincitore')) and row.get('Vincitore') in options:
                        default_index = options.index(row.get('Vincitore'))
                    with c6:
                        _ = st.selectbox("Vincitore (se pari)", options=options, index=default_index, key=win_key)
            
            def salva_round():
                if 'rounds_ko' not in st.session_state or not st.session_state['rounds_ko']:
                    return
                df_round = st.session_state['rounds_ko'][-1].copy()
                for _, row in df_round.iterrows():
                    rnd = row['Round']
                    match_n = int(row['Match'])
                    ga_key = f"ko_ga_{rnd}_{match_n}"
                    gb_key = f"ko_gb_{rnd}_{match_n}"
                    val_key = f"ko_val_{rnd}_{match_n}"
                    win_key = f"ko_w_{rnd}_{rnd}"
                    df_round.at[_,'GolA'] = st.session_state.get(ga_key, 0)
                    df_round.at[_,'GolB'] = st.session_state.get(gb_key, 0)
                    df_round.at[_,'Valida'] = st.session_state.get(val_key, False)
                    df_round.at[_,'Vincitore'] = st.session_state.get(win_key, None)

                st.session_state['rounds_ko'][-1] = df_round
                st.success("✅ Risultati salvati.")
            
            # Rendering dei round esistenti
            for df_round in st.session_state['rounds_ko']:
                render_round(df_round)
                
            # Pulsante per salvare
            st.button("💾 Salva Risultati Round", on_click=salva_round)

            # Pulsante per avanzare
            if all(to_bool_series(st.session_state['rounds_ko'][-1]['Valida'])):
                st.divider()
                st.subheader("🎉 Avanti al prossimo round!")
                winners = []
                for _, row in st.session_state['rounds_ko'][-1].iterrows():
                    if row['GolA'] > row['GolB']:
                        winners.append(row['SquadraA'])
                    elif row['GolB'] > row['GolA']:
                        winners.append(row['SquadraB'])
                    else:
                        winners.append(row['Vincitore'])

                next_round_map = {"Ottavi":"Quarti", "Quarti":"Semifinali", "Semifinali":"Finale", "Finale":"Campione!"}
                current_round_name = st.session_state['rounds_ko'][-1]['Round'].iloc[0]
                next_round_name = next_round_map.get(current_round_name)

                if next_round_name == "Campione!":
                    st.success(f"👑 Il vincitore del torneo è: **{winners[0]}**!")
                    st.balloons()
                else:
                    st.info(f"Clicca per generare il tabellone delle **{next_round_name.lower()}**.")
                    def genera_prossimo_round():
                        pairs = []
                        n_next = len(winners) // 2
                        next_seeds = [winners[i] for i in range(n_next)] + [winners[-(i+1)] for i in range(n_next)]
                        for i in range(n_next):
                            a = next_seeds[i]; b = next_seeds[-(i+1)]
                            pairs.append({'Round': next_round_name, 'Match': i+1, 'SquadraA': a, 'SquadraB': b, 'GolA': None, 'GolB': None, 'Valida': False, 'Vincitore': None})
                        st.session_state['rounds_ko'].append(pd.DataFrame(pairs))
                        st.session_state['round_corrente'] = next_round_name
                        st.rerun()

                    st.button(f"➡️ Genera {next_round_name}", on_click=genera_prossimo_round)
            else:
                st.warning("⚠️ Per generare il prossimo round, devi validare tutti i risultati del round corrente.")


