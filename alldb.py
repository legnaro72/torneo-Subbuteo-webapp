import streamlit as st
import pandas as pd
import random
from fpdf import FPDF
from datetime import datetime
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
import json
import io

# -------------------------------------------------
# CONFIG PAGINA (deve essere la prima chiamata st.*)
# -------------------------------------------------
st.set_page_config(page_title="⚽Campionato/Torneo Preliminare Subbuteo", layout="wide")

# ------------------------
# GESTIONE DELLO STATO E FUNZIONI INIZIALI
# ------------------------
if 'df_torneo' not in st.session_state:
    st.session_state['df_torneo'] = pd.DataFrame()

DEFAULT_STATE = {
    'calendario_generato': False,
    'mostra_form_creazione': False,
    'girone_sel': "Girone 1",
    'giornata_sel': 1,
    'mostra_assegnazione_squadre': False,
    'mostra_gironi': False,
    'gironi_manuali_completi': False,
    'gironi_manuali': {},
    'giocatori_selezionati_definitivi': [],
    'gioc_info': {},
    'usa_bottoni': False,
    'filtro_attivo': 'Nessuno',
    'nome_torneo': "Torneo All'italiana",
    'tournament_id': None,
    'torneo_completato': False,
    'classifica_finale': None,
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value

def reset_app_state():
    for key in list(st.session_state.keys()):
        if key not in ['df_torneo', 'sidebar_state_reset']:
            st.session_state.pop(key)
    st.session_state.update(DEFAULT_STATE)
    st.session_state['df_torneo'] = pd.DataFrame()

# -------------------------
# FUNZIONI CONNESSIONE MONGO (SENZA SUCCESS VERDI)
# -------------------------
@st.cache_resource
def init_mongo_connection(uri, db_name, collection_name, show_ok: bool = False):
    """
    Se show_ok=True mostra un messaggio di ok.
    Di default è False per evitare i badge verdi.
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

# -------------------------
# UTILITY
# -------------------------
def combined_style(df: pd.DataFrame):
    # Evidenziazione classifiche + nascondi None/NaN nelle celle
    def apply_row_style(row):
        base = [''] * len(row)
        if row.name == 0:
            base = ['background-color: #d4edda; color: black'] * len(row)
        elif row.name <= 2:
            base = ['background-color: #fff3cd; color: black'] * len(row)
        return base

    def hide_none(val):
        sval = str(val).strip().lower()
        if sval in ["none", "nan", ""]:
            return 'color: transparent; text-shadow: none;'
        return ''

    styled_df = df.style.apply(apply_row_style, axis=1)
    styled_df = styled_df.map(hide_none)
    return styled_df

def navigation_buttons(label, value_key, min_val, max_val, key_prefix=""):
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
    if players_collection is None:
        return pd.DataFrame()
    try:
        df = pd.DataFrame(list(players_collection.find({}, {"_id": 0})))
        return df if not df.empty else pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Errore durante la lettura dei giocatori: {e}")
        return pd.DataFrame()

def carica_tornei_da_db(tournaments_collection):
    if tournaments_collection is None:
        return []
    try:
        return list(tournaments_collection.find({}, {"nome_torneo": 1}))
    except Exception as e:
        st.error(f"❌ Errore caricamento tornei: {e}")
        return []

def carica_torneo_da_db(tournaments_collection, tournament_id):
    if tournaments_collection is None:
        return None
    try:
        torneo_data = tournaments_collection.find_one({"_id": ObjectId(tournament_id)})
        if torneo_data and 'calendario' in torneo_data:
            df_torneo = pd.DataFrame(torneo_data['calendario'])
            df_torneo['Valida'] = df_torneo['Valida'].astype(bool)
            df_torneo['GolCasa'] = pd.to_numeric(df_torneo['GolCasa'], errors='coerce').astype('Int64')
            df_torneo['GolOspite'] = pd.to_numeric(df_torneo['GolOspite'], errors='coerce').astype('Int64')
            st.session_state['df_torneo'] = df_torneo
        return torneo_data
    except Exception as e:
        st.error(f"❌ Errore caricamento torneo: {e}")
        return None

def salva_torneo_su_db(tournaments_collection, df_torneo, nome_torneo):
    if tournaments_collection is None:
        return None
    try:
        df_torneo_pulito = df_torneo.where(pd.notna(df_torneo), None)
        data = {"nome_torneo": nome_torneo, "calendario": df_torneo_pulito.to_dict('records')}
        result = tournaments_collection.insert_one(data)
        return result.inserted_id
    except Exception as e:
        st.error(f"❌ Errore salvataggio torneo: {e}")
        return None

def aggiorna_torneo_su_db(tournaments_collection, tournament_id, df_torneo):
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

# -------------------------
# CALENDARIO & CLASSIFICA LOGIC
# -------------------------
def genera_calendario_from_list(gironi, tipo="Solo andata"):
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
                        "Casa": casa, "Ospite": ospite, "GolCasa": None, "GolOspite": None, "Valida": False
                    })
                    if tipo == "Andata e ritorno":
                        partite.append({
                            "Girone": gname, "Giornata": giornata + 1 + n - 1,
                            "Casa": ospite, "Ospite": casa, "GolCasa": None, "GolOspite": None, "Valida": False
                        })
            teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    return pd.DataFrame(partite)

def aggiorna_classifica(df):
    if 'Girone' not in df.columns:
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
            gc, go = int(r['GolCasa'] or 0), int(r['GolOspite'] or 0)
            casa, ospite = r['Casa'], r['Ospite']
            stats[casa]['GF'] += gc; stats[casa]['GS'] += go
            stats[ospite]['GF'] += go; stats[ospite]['GS'] += gc
            if gc > go:
                stats[casa]['Punti'] += 2; stats[casa]['V'] += 1; stats[ospite]['S'] += 1
            elif gc < go:
                stats[ospite]['Punti'] += 2; stats[ospite]['V'] += 1; stats[casa]['S'] += 1
            else:
                stats[casa]['Punti'] += 1; stats[ospite]['Punti'] += 1; stats[casa]['P'] += 1; stats[ospite]['P'] += 1
        for s in squadre:
            stats[s]['DR'] = stats[s]['GF'] - stats[s]['GS']
        df_stat = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index': 'Squadra'})
        df_stat['Girone'] = girone
        classifiche.append(df_stat)
    if not classifiche:
        return None
    df_classifica = pd.concat(classifiche, ignore_index=True)
    df_classifica = df_classifica.sort_values(by=['Girone', 'Punti', 'DR'], ascending=[True, False, False])
    return df_classifica

# -------------------------
# FUNZIONI DI VISUALIZZAZIONE & EVENTI
# -------------------------
def mostra_calendario_stilizzato(df):
    """Mostra il calendario raggruppato per girone e giornata."""
    if df.empty:
        st.info("Nessun calendario generato.")
        return
    gironi_disponibili = sorted(df['Girone'].dropna().unique())
    
    for girone in gironi_disponibili:
        with st.expander(f"**⚽ {girone}**", expanded=True):
            df_girone = df[df['Girone'] == girone]
            giornate_disponibili = sorted(df_girone['Giornata'].dropna().unique())
            
            for giornata in giornate_disponibili:
                st.markdown(f"**Giornata {giornata}**", unsafe_allow_html=True)
                df_giornata = df_girone[df_girone['Giornata'] == giornata]
                
                for idx, row in df_giornata.iterrows():
                    gol_casa = int(row['GolCasa']) if pd.notna(row['GolCasa']) else 0
                    gol_ospite = int(row['GolOspite']) if pd.notna(row['GolOspite']) else 0

                    col1, col2, col3, col4, col5 = st.columns([5, 1.5, 1, 1.5, 1])
                    with col1:
                        st.markdown(f"**{row['Casa']}** vs **{row['Ospite']}**")
                    with col2:
                        st.number_input(
                            "", min_value=0, max_value=20, key=f"golcasa_{idx}", value=gol_casa,
                            disabled=row['Valida'], label_visibility="hidden"
                        )
                    with col3:
                        st.markdown("-")
                    with col4:
                        st.number_input(
                            "", min_value=0, max_value=20, key=f"golospite_{idx}", value=gol_ospite,
                            disabled=row['Valida'], label_visibility="hidden"
                        )
                    with col5:
                        st.checkbox("Valida", key=f"valida_{idx}", value=row['Valida'])

                    if not st.session_state.get(f"valida_{idx}", False):
                        st.markdown('<div style="color:red; margin-bottom: 15px;">Partita non ancora validata ❌</div>', unsafe_allow_html=True)
                    else:
                        st.markdown("<hr>", unsafe_allow_html=True)

def salva_risultati_giornata(tournaments_collection):
    df = st.session_state['df_torneo']
    
    for idx, row in df.iterrows():
        df.at[idx, 'GolCasa'] = st.session_state.get(f"golcasa_{idx}", 0)
        df.at[idx, 'GolOspite'] = st.session_state.get(f"golospite_{idx}", 0)
        df.at[idx, 'Valida'] = st.session_state.get(f"valida_{idx}", False)

    st.session_state['df_torneo'] = df

    if 'tournament_id' in st.session_state:
        aggiorna_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], df)
        st.toast("Risultati salvati su MongoDB ✅")
    else:
        st.error("❌ Errore: ID del torneo non trovato. Impossibile salvare.")

    if df['Valida'].all() and not st.session_state.get('torneo_completato', False):
        nome_completato = f"completato_{st.session_state['nome_torneo']}"
        classifica_finale = aggiorna_classifica(df)

        salva_torneo_su_db(tournaments_collection, df, nome_completato)

        st.session_state['torneo_completato'] = True
        st.session_state['classifica_finale'] = classifica_finale

        st.toast(f"Torneo completato e salvato come {nome_completato} ✅")

    st.rerun()

def mostra_classifica_stilizzata(df_classifica):
    if df_classifica is None or df_classifica.empty:
        st.info("⚽ Nessuna partita validata")
        return
    gironi = df_classifica['Girone'].dropna().unique()
    for girone in gironi:
        with st.expander(f"**Classifica {girone}**", expanded=True):
            df_girone = df_classifica[df_classifica['Girone'] == girone].reset_index(drop=True)
            st.dataframe(combined_style(df_girone), use_container_width=True, hide_index=True)

def esporta_pdf(df_torneo, df_classifica, nome_torneo):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f"Calendario e Classifiche {nome_torneo}", ln=True, align='C')
    line_height = 6
    margin_bottom = 15
    page_height = 297
    gironi = df_torneo['Girone'].dropna().unique()
    for girone in gironi:
        pdf.set_font("Arial", 'B', 14)
        if pdf.get_y() + 8 + margin_bottom > page_height:
            pdf.add_page()
        pdf.cell(0, 8, f"{girone}", ln=True)
        giornate = sorted(df_torneo[df_torneo['Girone'] == girone]['Giornata'].dropna().unique())
        for g in giornate:
            needed_space = 7 + line_height + line_height + margin_bottom
            if pdf.get_y() + needed_space > page_height:
                pdf.add_page()
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
                if pdf.get_y() + line_height + margin_bottom > page_height:
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 7, f"Giornata {g} (continua)", ln=True)
                    pdf.set_font("Arial", 'B', 11)
                    for i, h in enumerate(headers):
                        pdf.cell(col_widths[i], 6, h, border=1, align='C')
                    pdf.ln()
                    pdf.set_font("Arial", '', 11)
                pdf.set_text_color(255, 0, 0) if not row['Valida'] else pdf.set_text_color(0, 0, 0)
                pdf.cell(col_widths[0], 6, str(row['Casa']), border=1)
                pdf.cell(col_widths[1], 6, str(row['GolCasa']) if pd.notna(row['GolCasa']) else "-", border=1, align='C')
                pdf.cell(col_widths[2], 6, str(row['GolOspite']) if pd.notna(row['GolOspite']) else "-", border=1, align='C')
                pdf.cell(col_widths[3], 6, str(row['Ospite']), border=1)
                pdf.ln()
            pdf.ln(3)
        if pdf.get_y() + 40 + margin_bottom > page_height:
            pdf.add_page()
        pdf.set_font("Arial", 'B', 13)
        pdf.cell(0, 8, f"Classifica {girone}", ln=True)
        df_c = df_classifica[df_classifica['Girone'] == girone]
        pdf.set_font("Arial", 'B', 11)
        headers = ["Squadra", "Punti", "V", "P", "S", "GF", "GS", "DR"]
        col_widths = [60, 15, 15, 15, 15, 15, 15, 15]
        for i, h in enumerate(headers):
            pdf.cell(col_widths[i], 6, h, border=1, align='C')
        pdf.ln()
        pdf.set_font("Arial", '', 11)
        for _, r in df_c.iterrows():
            if pdf.get_y() + line_height + margin_bottom > page_height:
                pdf.add_page()
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

def esporta_csv(df_torneo):
    csv_string = df_torneo.to_csv(index=False)
    return csv_string.encode('utf-8')

# -------------------------
# APP
# -------------------------
def main():
    if st.session_state.get('sidebar_state_reset', False):
        reset_app_state()
        st.session_state['sidebar_state_reset'] = False
        st.rerun()

    players_collection = init_mongo_connection(st.secrets["MONGO_URI"], "giocatori_subbuteo", "superba_players", show_ok=False)
    tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], "TorneiSubbuteo", "Superba", show_ok=False)

    # Header grafico - preso dallo script svizzero
    if st.session_state.get('calendario_generato', False) and 'nome_torneo' in st.session_state:
        st.markdown(f"""
            <div style='text-align:center; padding:20px; border-radius:12px; background: linear-gradient(to right, #ffefba, #ffffff);'>
                <h1 style='color:#0B5FFF;'>🏆 {st.session_state['nome_torneo']}</h1>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
            <div style='text-align:center; padding:20px; border-radius:12px; background: linear-gradient(to right, #ffefba, #ffffff);'>
                <h1 style='color:#0B5FFF;'>⚽ Gestione Torneo Subbuteo All'italiana</h1>
            </div>
            """, unsafe_allow_html=True)


    if st.session_state.get('torneo_completato', False) and st.session_state.get('classifica_finale') is not None:
        vincitori = []
        df_classifica = st.session_state['classifica_finale']
        if df_classifica is not None and not df_classifica.empty:
            for girone in df_classifica['Girone'].unique():
                primo = df_classifica[df_classifica['Girone'] == girone].iloc[0]['Squadra']
                vincitori.append(f"🏅 {girone}: {primo}")
            st.success("🎉 Torneo Completato! Vincitori → " + ", ".join(vincitori))
            mostra_classifica_stilizzata(df_classifica)
    
    st.markdown("---")

    # -------------------------
    # MAIN APP LOGIC
    # -------------------------
    if not st.session_state.get('calendario_generato', False):
        st.subheader("1️⃣ Creazione/Caricamento Torneo")
        st.markdown("---")
        
        col1_form, col2_form = st.columns([1,1])
        with col1_form:
            st.markdown("#### Crea un nuovo torneo")
            st.session_state['nome_torneo'] = st.text_input("Nome Torneo", key='nome_torneo_input', value=DEFAULT_STATE['nome_torneo'])
            st.session_state['num_gironi'] = st.number_input("Numero di gironi", min_value=1, max_value=8, value=4)
            st.session_state['tipo_calendario'] = st.selectbox("Modalità calendario", ["Solo andata", "Andata e ritorno"])
            st.session_state['modalita_creazione_gironi'] = st.radio("Modalità creazione gironi", ["Automaticamente", "Manualmente"])
            
            if st.session_state['modalita_creazione_gironi'] == "Manualmente":
                if st.button("Valida e Assegna Gironi Manuali"):
                    st.session_state['mostra_assegnazione_squadre'] = True
                    st.rerun()

            if st.button("Genera Calendario"):
                if not st.session_state['giocatori_selezionati_definitivi']:
                    st.error("❌ Nessun giocatore selezionato. Seleziona i giocatori prima di generare il calendario.")
                    return
                
                giocatori_formattati = [
                    f"{st.session_state['gioc_info'][gioc]['Squadra']} ({gioc})"
                    for gioc in st.session_state['giocatori_selezionati_definitivi']
                ]

                if st.session_state['modalita_creazione_gironi'] == "Manualmente" and not st.session_state['gironi_manuali_completi']:
                    st.error("❌ Per generare il calendario manualmente, clicca prima su 'Valida e Assegna Gironi Manuali'.")
                    return
                
                if st.session_state['modalita_creazione_gironi'] == "Automaticamente":
                    gironi_finali = [[] for _ in range(st.session_state['num_gironi'])]
                    random.shuffle(giocatori_formattati)
                    for i, g in enumerate(giocatori_formattati):
                        gironi_finali[i % st.session_state['num_gironi']].append(g)
                else:
                    gironi_finali = list(st.session_state['gironi_manuali'].values())

                df_torneo = genera_calendario_from_list(gironi_finali, st.session_state['tipo_calendario'])
                tid = salva_torneo_su_db(tournaments_collection, df_torneo, st.session_state['nome_torneo'])
                if tid:
                    st.session_state['df_torneo'] = df_torneo
                    st.session_state['tournament_id'] = str(tid)
                    st.session_state['calendario_generato'] = True
                    st.toast("Calendario generato e salvato su MongoDB ✅")
                    st.rerun()

        with col2_form:
            st.markdown("#### Carica torneo esistente")
            tornei_disponibili = carica_tornei_da_db(tournaments_collection)
            if tornei_disponibili:
                nomi_tornei = [t['nome_torneo'] for t in tornei_disponibili]
                torneo_selezionato = st.selectbox("Seleziona torneo", nomi_tornei, key="torneo_carica_sel")
                if st.button("Carica Torneo"):
                    torneo_data = tournaments_collection.find_one({"nome_torneo": torneo_selezionato})
                    if torneo_data:
                        df_torneo = pd.DataFrame(torneo_data['calendario'])
                        st.session_state['df_torneo'] = df_torneo
                        st.session_state['nome_torneo'] = torneo_selezionato
                        st.session_state['tournament_id'] = str(torneo_data['_id'])
                        st.session_state['calendario_generato'] = True
                        st.toast("Torneo caricato con successo ✅")
                        st.rerun()
            else:
                st.info("Nessun torneo salvato da caricare.")

        st.markdown("---")
        st.subheader("2️⃣ Scelta Giocatori")
        df_giocatori = carica_giocatori_da_db(players_collection)
        if not df_giocatori.empty:
            df_giocatori['Seleziona'] = st.checkbox("Seleziona tutti", value=True, key="sel_all_players")
            edited_df = st.data_editor(df_giocatori, hide_index=True, disabled=["Giocatore", "Club", "Squadra"],
                                        column_order=["Seleziona", "Giocatore", "Squadra"])
            
            giocatori_selezionati = edited_df[edited_df['Seleziona'] == True]['Giocatore'].tolist()
            st.info(f"Giocatori selezionati: **{len(giocatori_selezionati)}**")
            
            st.session_state['giocatori_selezionati_definitivi'] = giocatori_selezionati
            
            # Aggiorna il dizionario info
            st.session_state['gioc_info'] = df_giocatori.set_index('Giocatore').to_dict('index')

        if st.session_state.get('mostra_assegnazione_squadre', False) and st.session_state['modalita_creazione_gironi'] == "Manualmente":
            st.markdown("---")
            st.subheader("3️⃣ Assegnazione Squadre ai Gironi (Manuale)")
            squadre_assegnate = set()
            st.session_state['gironi_manuali'] = {f"Girone {i}": [] for i in range(1, st.session_state['num_gironi'] + 1)}
            
            giocatori_disponibili = sorted(st.session_state['giocatori_selezionati_definitivi'])
            
            with st.form("assegnazione_form"):
                for girone_idx in range(st.session_state['num_gironi']):
                    girone_nome = f"Girone {girone_idx + 1}"
                    st.subheader(f"Gruppo {girone_nome}")
                    squadre_selezionate = st.multiselect(
                        "Seleziona le squadre:",
                        options=giocatori_disponibili,
                        key=f"multiselect_{girone_idx}"
                    )
                    st.session_state['gironi_manuali'][girone_nome] = [
                        f"{st.session_state['gioc_info'][gioc]['Squadra']} ({gioc})"
                        for gioc in squadre_selezionate
                    ]

                submitted = st.form_submit_button("Valida Gironi Manuali")
                if submitted:
                    all_assigned = all(len(g) > 0 for g in st.session_state['gironi_manuali'].values())
                    total_assigned = sum(len(g) for g in st.session_state['gironi_manuali'].values())
                    total_players = len(giocatori_disponibili)
                    
                    if total_assigned != total_players:
                        st.error(f"❌ Errore: hai assegnato {total_assigned} giocatori su {total_players}. Assicurati di assegnare tutti i giocatori.")
                        st.session_state['gironi_manuali_completi'] = False
                    else:
                        st.success("✅ Gironi manuali validati. Puoi generare il calendario.")
                        st.session_state['gironi_manuali_completi'] = True
                        st.session_state['mostra_assegnazione_squadre'] = False
                        st.rerun()

    else:
        # Mostra calendario, classifica e opzioni di salvataggio
        st.subheader("⚽ Calendario e Classifica")
        st.markdown(f"**Torneo: {st.session_state['nome_torneo']}**")
        
        col1, col2 = st.columns([1,1])
        with col1:
            st.subheader("Risultati Partite")
            mostra_calendario_stilizzato(st.session_state['df_torneo'])
            if st.button("Salva Risultati"):
                salva_risultati_giornata(tournaments_collection)
                
        with col2:
            st.subheader("Classifiche Gironi")
            df_classifica = aggiorna_classifica(st.session_state['df_torneo'])
            if df_classifica is not None:
                mostra_classifica_stilizzata(df_classifica)
        
        st.sidebar.download_button(
            label="⬇️ Esporta in CSV",
            data=esporta_csv(st.session_state['df_torneo']),
            file_name=f"calendario_torneo_{st.session_state['nome_torneo']}.csv",
            mime="text/csv"
        )
        pdf_bytes = esporta_pdf(st.session_state['df_torneo'], aggiorna_classifica(st.session_state['df_torneo']), st.session_state['nome_torneo'])
        file_name_pdf = f"calendario_torneo_{st.session_state['nome_torneo']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        st.sidebar.download_button(
            label="⬇️ Esporta in PDF",
            data=pdf_bytes,
            file_name=file_name_pdf,
            mime="application/pdf"
        )

if __name__ == "__main__":
    main()
