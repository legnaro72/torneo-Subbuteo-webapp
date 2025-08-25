import streamlit as st
import pandas as pd
import random
from fpdf import FPDF
from datetime import datetime
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
import json

# -------------------------------------------------
# CONFIG PAGINA (deve essere la prima chiamata st.*)
# -------------------------------------------------
st.set_page_config(page_title="⚽ Campionato/Torneo PreliminariSubbuteo", layout="wide")

# -------------------------
# GESTIONE DELLO STATO E FUNZIONI INIZIALI
# -------------------------
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
    'giocatori_selezionati_definitivi': [],
    'gioc_info': {},
    'usa_bottoni': False,
    'filtro_attivo': 'Nessuno'  # stato per i filtri
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
            st.toast(f"Connessione a {db_name}.{collection_name} ok. ✅")
        return col
    except Exception as e:
        st.toast(f"❌ Errore di connessione a {db_name}.{collection_name}: {e}")
        return None

# -------------------------
# UTILITY
# -------------------------
def combined_style(df: pd.DataFrame):
    # Evidenziazione classifiche
    def apply_row_style(row):
        base = [''] * len(row)
        if row.name == 0:
            base = ['background-color: #d4edda; color: black'] * len(row)
        elif row.name <= 2:
            base = ['background-color: #fff3cd; color: black'] * len(row)
        return base

    styled_df = df.style.apply(apply_row_style, axis=1)
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
        st.toast(f"❌ Errore durante la lettura dei giocatori: {e}")
        return pd.DataFrame()

def carica_tornei_da_db(tournaments_collection):
    if tournaments_collection is None:
        return []
    try:
        return list(tournaments_collection.find({}, {"nome_torneo": 1}))
    except Exception as e:
        st.toast(f"❌ Errore caricamento tornei: {e}")
        return []

def normalizza_colonne_gol(df):
    for col in ['GolCasa', 'GolOspite']:
        df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
    return df


def salva_torneo_su_db(tournaments_collection, df_torneo, nome_torneo):
    if tournaments_collection is None:
        return None
    try:
        df_torneo_pulito = df_torneo.where(pd.notna(df_torneo), None)
        data = {"nome_torneo": nome_torneo, "calendario": df_torneo_pulito.to_dict('records')}
        result = tournaments_collection.insert_one(data)
        return result.inserted_id
    except Exception as e:
        st.toast(f"❌ Errore salvataggio torneo: {e}")
        return None

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
            
            df_torneo = normalizza_colonne_gol(df_torneo)
            
            st.session_state['df_torneo'] = df_torneo
            
        return torneo_data
    except Exception as e:
        st.toast(f"❌ Errore caricamento torneo: {e}")
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
        st.toast(f"❌ Errore aggiornamento torneo: {e}")
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
        return pd.DataFrame(columns=['Girone', 'Squadra', 'Punti', 'V', 'P', 'S', 'GF', 'GS', 'DR'])

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
                stats[casa]['Punti'] += 1; stats[ospite]['Punti'] += 1
                stats[casa]['P'] += 1; stats[ospite]['P'] += 1

        for s in squadre:
            stats[s]['DR'] = stats[s]['GF'] - stats[s]['GS']

        df_stat = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index': 'Squadra'})
        df_stat['Girone'] = girone
        classifiche.append(df_stat)

    if not classifiche:
        # ritorna un DataFrame vuoto con le stesse colonne
        return pd.DataFrame(columns=['Girone', 'Squadra', 'Punti', 'V', 'P', 'S', 'GF', 'GS', 'DR'])

    df_classifica = pd.concat(classifiche, ignore_index=True)
    df_classifica = df_classifica.sort_values(by=['Girone', 'Punti', 'DR'], ascending=[True, False, False])
    return df_classifica

# -------------------------
# FUNZIONI DI VISUALIZZAZIONE & EVENTI
# -------------------------
def mostra_calendario_giornata(df, girone_sel, giornata_sel):
    def _to_int_safe(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0    
    df_giornata = df[(df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel)].copy()
    if df_giornata.empty:
        return
    for idx, row in df_giornata.iterrows():
        col1, col2, col3, col4, col5 = st.columns([5, 1.5, 1, 1.5, 1])
        with col1:
            st.markdown(f"**{row['Casa']}** vs **{row['Ospite']}**")
        with col2:
            # Sostituisce i valori None con una stringa vuota
            gol_casa_value = "" if pd.isna(row['GolCasa']) else str(int(row['GolCasa']))
            st.text_input(
                "", key=f"golcasa_{idx}", value=gol_casa_value,
                disabled=row['Valida'], label_visibility="hidden"
            )
        with col3:
            st.markdown("-")
        with col4:
            # Sostituisce i valori None con una stringa vuota
            gol_ospite_value = "" if pd.isna(row['GolOspite']) else str(int(row['GolOspite']))
            st.text_input(
                "", key=f"golospite_{idx}", value=gol_ospite_value,
                disabled=row['Valida'], label_visibility="hidden"
            )
        with col5:
            st.checkbox("Valida", key=f"valida_{idx}", value=row['Valida'])

        # Riga separatrice / stato partita
        if st.session_state.get(f"valida_{idx}", False):
            st.markdown("---")
        else:
            st.markdown('<div style="color:red; margin-bottom: 15px;">Partita non ancora validata ❌</div>', unsafe_allow_html=True)

def salva_risultati_giornata(tournaments_collection, girone_sel, giornata_sel):
    df = st.session_state['df_torneo']
    df_giornata = df[(df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel)].copy()
    for idx, row in df_giornata.iterrows():
        try:
            if st.session_state.get(f"valida_{idx}", False):
                gol_casa = st.session_state.get(f"golcasa_{idx}")
                gol_ospite = st.session_state.get(f"golospite_{idx}")

                # Converte stringa vuota in None e poi in Int64
                df.at[idx, 'GolCasa'] = int(gol_casa) if gol_casa else None
                df.at[idx, 'GolOspite'] = int(gol_ospite) if gol_ospite else None
                df.at[idx, 'Valida'] = True
            else:
                df.at[idx, 'GolCasa'] = None
                df.at[idx, 'GolOspite'] = None
                df.at[idx, 'Valida'] = False
        except (ValueError, TypeError):
            st.toast("❌ Errore: Inserisci solo numeri interi per i gol.")
            df.at[idx, 'Valida'] = False
            continue

    st.session_state['df_torneo'] = df
    if 'tournament_id' in st.session_state:
        aggiorna_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], df)
        st.toast("Risultati salvati su MongoDB ✅")
    else:
        st.toast("❌ Errore: ID del torneo non trovato. Impossibile salvare.")
    st.rerun()

def mostra_classifica_stilizzata(df_classifica, girone_sel):
    

    if df_classifica is None:
        st.toast("⚽ Nessuna classifica disponibile")
        return

    if df_classifica.empty:
        st.toast("⚽ Nessuna partita validata")
        return

    if 'Girone' not in df_classifica.columns:
        st.toast("⚠️ Classifica non valida: manca la colonna 'Girone'")
        return

    df_girone = df_classifica[df_classifica['Girone'] == girone_sel].reset_index(drop=True)
    df_girone_display = df_girone.fillna('-')

    styled = combined_style(df_girone_display)
    st.markdown(styled.to_html(), unsafe_allow_html=True)


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

                gol_casa = str(row['GolCasa']) if pd.notna(row['GolCasa']) else "-"
                gol_ospite = str(row['GolOspite']) if pd.notna(row['GolOspite']) else "-"

                pdf.cell(col_widths[0], 6, str(row['Casa']), border=1)
                pdf.cell(col_widths[1], 6, gol_casa, border=1, align='C')
                pdf.cell(col_widths[2], 6, gol_ospite, border=1, align='C')
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

# -------------------------
# APP
# -------------------------
def main():
    if st.session_state.get('sidebar_state_reset', False):
        reset_app_state()
        st.session_state['sidebar_state_reset'] = False
        st.rerun()

    # Connessioni (senza messaggi verdi)
    players_collection = init_mongo_connection(st.secrets["MONGO_URI"], "giocatori_subbuteo", "superba_players", show_ok=False)
    tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], "subbuteo_tournement", "superba_tournement", show_ok=False)

    # Titolo
    if st.session_state.get('calendario_generato', False) and 'nome_torneo' in st.session_state:
        st.title(f"🏆 {st.session_state['nome_torneo']}")
    else:
        st.title("🏆 Torneo Superba - Gestione Gironi")

    # CSS
    st.markdown("""
        <style>
        ul, li { list-style-type: none !important; padding-left: 0 !important; margin-left: 0 !important; }
        .big-title { text-align: center; font-size: clamp(16px, 4vw, 36px); font-weight: bold; margin-top: 10px; margin-bottom: 20px; color: red; word-wrap: break-word; white-space: normal; }
        </style>
    """, unsafe_allow_html=True)

    df_master = carica_giocatori_da_db(players_collection)

    if players_collection is None and tournaments_collection is None:
        st.toast("❌ Impossibile avviare l'applicazione. La connessione a MongoDB non è disponibile.")
        return

    # Sidebar / Pagina
    if st.session_state.get('calendario_generato', False):
        st.sidebar.subheader("Opzioni Torneo ⚙️")
        df = st.session_state['df_torneo']
        classifica = aggiorna_classifica(df)
        if classifica is not None:
            st.sidebar.download_button(
                label="📄 Esporta in PDF",
                data=esporta_pdf(df, classifica, st.session_state['nome_torneo']),
                file_name=f"torneo_{st.session_state['nome_torneo']}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        if st.sidebar.button("🔙 Torna alla schermata iniziale", key='back_to_start_sidebar', use_container_width=True):
            st.session_state['sidebar_state_reset'] = True
            st.rerun()

        st.sidebar.markdown("---")
        st.sidebar.subheader("🔎 Filtra partite")

        filtro_opzione = st.sidebar.radio("Scegli un filtro", ('Nessuno', 'Giocatore', 'Girone'), key='filtro_selettore')

        if filtro_opzione != st.session_state['filtro_attivo']:
            st.session_state['filtro_attivo'] = filtro_opzione
            st.rerun()

        if st.session_state['filtro_attivo'] == 'Giocatore':
            st.sidebar.markdown("#### Filtra per Giocatore 👤")

            giocatori = sorted(list(set(df['Casa'].unique().tolist() + df['Ospite'].unique().tolist())))
            giocatore_scelto = st.sidebar.selectbox("Seleziona un giocatore", [''] + giocatori, key='filtro_giocatore_sel')
            tipo_andata_ritorno = st.sidebar.radio("Andata/Ritorno", ["Entrambe", "Andata", "Ritorno"], key='tipo_giocatore')

            if giocatore_scelto:
                st.subheader(f"Partite da giocare per {giocatore_scelto} ⚽")
                df_filtrato = df[(df['Valida'] == False) & ((df['Casa'] == giocatore_scelto) | (df['Ospite'] == giocatore_scelto))]

                if tipo_andata_ritorno == "Andata":
                    n_squadre_girone = len(df.groupby('Girone').first().index)
                    df_filtrato = df_filtrato[df_filtrato['Giornata'] <= n_squadre_girone - 1]
                elif tipo_andata_ritorno == "Ritorno":
                    n_squadre_girone = len(df.groupby('Girone').first().index)
                    df_filtrato = df_filtrato[df_filtrato['Giornata'] > n_squadre_girone - 1]

                if not df_filtrato.empty:
                    df_filtrato_show = df_filtrato[['Girone', 'Giornata', 'Casa', 'Ospite', 'GolCasa', 'GolOspite']].fillna('-').rename(
                        columns={'Girone': 'Girone', 'Giornata': 'Giornata', 'Casa': 'Casa', 'Ospite': 'Ospite'}
                    )
                    st.dataframe(df_filtrato_show.reset_index(drop=True), use_container_width=True)
                else:
                    st.toast("🎉 Nessuna partita da giocare trovata per questo giocatore.")

        elif st.session_state['filtro_attivo'] == 'Girone':
            st.sidebar.markdown("#### Filtra per Girone 🌍")

            gironi_disponibili = sorted(df['Girone'].unique().tolist())
            girone_scelto = st.sidebar.selectbox("Seleziona un girone", gironi_disponibili, key='filtro_girone_sel')
            tipo_andata_ritorno = st.sidebar.radio("Andata/Ritorno", ["Entrambe", "Andata", "Ritorno"], key='tipo_girone')

            st.subheader(f"Partite da giocare nel {girone_scelto} ⚽")
            df_filtrato = df[(df['Valida'] == False) & (df['Girone'] == girone_scelto)]

            if tipo_andata_ritorno == "Andata":
                n_squadre_girone = len(df[df['Girone'] == girone_scelto]['Casa'].unique())
                df_filtrato = df_filtrato[df_filtrato['Giornata'] <= n_squadre_girone - 1]
            elif tipo_andata_ritorno == "Ritorno":
                n_squadre_girone = len(df[df['Girone'] == girone_scelto]['Casa'].unique())
                df_filtrato = df_filtrato[df_filtrato['Giornata'] > n_squadre_girone - 1]

            if not df_filtrato.empty:
                df_filtrato_show = df_filtrato[['Giornata', 'Casa', 'Ospite', 'GolCasa', 'GolOspite']].fillna('-').rename(
                    columns={'Giornata': 'Giornata', 'Casa': 'Casa', 'Ospite': 'Ospite'}
                )
                st.dataframe(df_filtrato_show.reset_index(drop=True), use_container_width=True)
            else:
                st.toast("🎉 Tutte le partite di questo girone sono state giocate.")

        st.markdown("---")
        if st.session_state['filtro_attivo'] == 'Nessuno':
            st.subheader("Navigazione Calendario 📅")
            gironi = sorted(df['Girone'].dropna().unique().tolist())
            giornate_correnti = sorted(df[df['Girone'] == st.session_state['girone_sel']]['Giornata'].dropna().unique().tolist())

            nuovo_girone = st.selectbox("Seleziona Girone", gironi, index=gironi.index(st.session_state['girone_sel']))
            if nuovo_girone != st.session_state['girone_sel']:
                st.session_state['girone_sel'] = nuovo_girone
                st.session_state['giornata_sel'] = 1
                st.rerun()

            st.session_state['usa_bottoni'] = st.checkbox("Usa bottoni per la giornata", value=st.session_state.get('usa_bottoni', False), key='usa_bottoni_checkbox')
            if st.session_state['usa_bottoni']:
                navigation_buttons("Giornata", 'giornata_sel', 1, len(giornate_correnti))
            else:
                try:
                    current_index = giornate_correnti.index(st.session_state['giornata_sel'])
                except ValueError:
                    current_index = 0
                    st.session_state['giornata_sel'] = giornate_correnti[0]

                nuova_giornata = st.selectbox("Seleziona Giornata", giornate_correnti, index=current_index)
                if nuova_giornata != st.session_state['giornata_sel']:
                    st.session_state['giornata_sel'] = nuova_giornata
                    st.rerun()

            mostra_calendario_giornata(df, st.session_state['girone_sel'], st.session_state['giornata_sel'])
            if st.button("💾 Salva Risultati Giornata", key="save_giornata_btn"):
                salva_risultati_giornata(
                    tournaments_collection,
                    st.session_state['girone_sel'],
                    st.session_state['giornata_sel']
                )

            
            st.markdown("---")
            st.subheader(f"Classifica {st.session_state['girone_sel']} 📈")
            classifica = aggiorna_classifica(df)
            mostra_classifica_stilizzata(classifica, st.session_state['girone_sel'])

    else:
        st.subheader("📁 Carica un torneo o crea uno nuovo")
        col1, col2 = st.columns(2)
        with col1:
            tornei_disponibili = carica_tornei_da_db(tournaments_collection)
            if tornei_disponibili:
                tornei_map = {t['nome_torneo']: str(t['_id']) for t in tornei_disponibili}
                nome_sel = st.selectbox("Seleziona torneo esistente:", list(tornei_map.keys()))
                if st.button("Carica Torneo Selezionato 📥"):
                    st.session_state['tournament_id'] = tornei_map[nome_sel]
                    st.session_state['nome_torneo'] = nome_sel
                    torneo_data = carica_torneo_da_db(tournaments_collection, st.session_state['tournament_id'])
                    if torneo_data and 'calendario' in torneo_data:
                        st.session_state['calendario_generato'] = True
                        st.toast("Torneo caricato con successo ✅")
                        st.rerun()
                    else:
                        st.toast("❌ Errore durante il caricamento del torneo. Riprova.")
            else:
                st.toast("🔍 Nessun torneo salvato trovato su MongoDB.")

        with col2:
            st.markdown("---")
            if st.button("➕ Crea Nuovo Torneo"):
                st.session_state['mostra_form_creazione'] = True
                st.rerun()

        if st.session_state.get('mostra_form_creazione', False):
            st.markdown("---")
            st.header("Dettagli Nuovo Torneo 📝")
            nome_default = f"TorneoSubbuteo_{datetime.now().strftime('%d%m%Y')}"
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

            num_supplementari = st.session_state["n_giocatori"] - len(amici_selezionati)
            if num_supplementari < 0:
                st.toast(f"⚠️ Hai selezionato più giocatori ({len(amici_selezionati)}) del numero partecipanti ({st.session_state['n_giocatori']}). Riduci la selezione.")
                return

            st.markdown(f"Giocatori ospiti da aggiungere: **{max(0, num_supplementari)}**")
            giocatori_supplementari = []
            if 'giocatori_supplementari_list' not in st.session_state:
                st.session_state['giocatori_supplementari_list'] = [''] * max(0, num_supplementari)

            for i in range(max(0, num_supplementari)):
                nome_ospite = st.text_input(f"Nome ospite {i+1}", value=st.session_state['giocatori_supplementari_list'][i], key=f"ospite_{i}")
                st.session_state['giocatori_supplementari_list'][i] = nome_ospite
                if nome_ospite:
                    giocatori_supplementari.append(nome_ospite.strip())

            if st.button("Conferma Giocatori ✅"):
                giocatori_scelti = amici_selezionati + [g for g in giocatori_supplementari if g]
                if len(set(giocatori_scelti)) < 4:
                    st.toast("⚠️ Inserisci almeno 4 giocatori diversi.")
                    return
                st.session_state['giocatori_selezionati_definitivi'] = list(set(giocatori_scelti))
                st.session_state['mostra_assegnazione_squadre'] = True
                st.session_state['mostra_gironi'] = False
                st.session_state['gironi_manuali_completi'] = False
                st.toast("Giocatori confermati ✅")
                st.rerun()

            if st.session_state.get('mostra_assegnazione_squadre', False):
                st.markdown("---")
                st.markdown("### ⚽ Modifica Squadra e Potenziale")

                if 'gioc_info' not in st.session_state or set(st.session_state['giocatori_selezionati_definitivi']) != set(st.session_state['gioc_info'].keys()):
                    temp_gioc_info = {}
                    for gioc in st.session_state['giocatori_selezionati_definitivi']:
                        if gioc in st.session_state.get('gioc_info', {}):
                            temp_gioc_info[gioc] = st.session_state['gioc_info'][gioc]
                        else:
                            row = df_master[df_master['Giocatore'] == gioc].iloc[0] if gioc in df_master['Giocatore'].values else None
                            squadra_default = row['Squadra'] if row is not None else ""
                            potenziale_default = int(row['Potenziale']) if row is not None else 4
                            temp_gioc_info[gioc] = {"Squadra": squadra_default, "Potenziale": potenziale_default}
                    st.session_state['gioc_info'] = temp_gioc_info

                for gioc in st.session_state['giocatori_selezionati_definitivi']:
                    squadra_nuova = st.text_input(f"Squadra per {gioc}", value=st.session_state['gioc_info'][gioc]['Squadra'], key=f"squadra_{gioc}")
                    potenziale_nuovo = st.slider(f"Potenziale per {gioc}", 1, 10, int(st.session_state['gioc_info'][gioc]['Potenziale']), key=f"potenziale_{gioc}")

                    st.session_state['gioc_info'][gioc]["Squadra"] = squadra_nuova
                    st.session_state['gioc_info'][gioc]["Potenziale"] = potenziale_nuovo

                if st.button("Conferma Squadre e Potenziali ✅"):
                    st.session_state['mostra_gironi'] = True
                    st.toast("Squadre e potenziali confermati ✅")
                    st.rerun()

            if st.session_state.get('mostra_gironi', False):
                st.markdown("---")
                st.markdown("### ➡️ Modalità di creazione dei gironi")
                modalita_gironi = st.radio("Scegli come popolare i gironi", ["Popola Gironi Automaticamente", "Popola Gironi Manualmente"], key="modo_gironi_radio")

                if modalita_gironi == "Popola Gironi Manualmente":
                    st.toast("⚠️ ATTENZIONE: se hai modificato il numero di giocatori, assicurati che i gironi manuali siano coerenti prima di generare il calendario.")
                    gironi_manuali = {}

                    giocatori_disponibili = st.session_state['giocatori_selezionati_definitivi']

                    for i in range(st.session_state['num_gironi']):
                        st.markdown(f"**Girone {i+1}**")

                        giocatori_assegnati_in_questo_girone = st.session_state.get(f"manual_girone_{i+1}", [])

                        giocatori_disponibili_per_selezione = [g for g in giocatori_disponibili if g not in sum(gironi_manuali.values(), [])] + giocatori_assegnati_in_questo_girone

                        giocatori_selezionati = st.multiselect(
                            f"Seleziona giocatori per Girone {i+1}",
                            options=sorted(list(set(giocatori_disponibili_per_selezione))),
                            default=giocatori_assegnati_in_questo_girone,
                            key=f"manual_girone_{i+1}"
                        )
                        gironi_manuali[f"Girone {i+1}"] = giocatori_selezionati

                    if st.button("Valida e Assegna Gironi Manuali 👍"):
                        tutti_i_giocatori_assegnati = sum(gironi_manuali.values(), [])
                        if sorted(tutti_i_giocatori_assegnati) == sorted(st.session_state['giocatori_selezionati_definitivi']):
                            st.session_state['gironi_manuali'] = gironi_manuali
                            st.session_state['gironi_manuali_completi'] = True
                            st.toast("Gironi manuali assegnati ✅")
                            st.rerun()
                        else:
                            st.toast("❌ Assicurati di assegnare tutti i giocatori e che ogni giocatore sia in un solo girone.")

                if st.button("Genera Calendario 🚀"):
                    if modalita_gironi == "Popola Gironi Manualmente" and not st.session_state.get('gironi_manuali_completi', False):
                        st.toast("❌ Per generare il calendario manualmente, clicca prima su 'Valida e Assegna Gironi Manuali'.")
                        return

                    giocatori_formattati = [
                        f"{st.session_state['gioc_info'][gioc]['Squadra']} ({gioc})"
                        for gioc in st.session_state['giocatori_selezionati_definitivi']
                    ]

                    if modalita_gironi == "Popola Gironi Automaticamente":
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

if __name__ == "__main__":
    main()
