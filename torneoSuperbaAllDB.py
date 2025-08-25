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
st.set_page_config(page_title="⚽Campionato/Torneo PreliminariSubbuteo", layout="wide")

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
def mostra_calendario_giornata(df, girone_sel, giornata_sel):
    df_giornata = df[(df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel)].copy()
    if df_giornata.empty:
        return
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

        if st.session_state.get(f"valida_{idx}", False):
            st.markdown("<hr>", unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:red; margin-bottom: 15px;">Partita non ancora validata ❌</div>', unsafe_allow_html=True)

def salva_risultati_giornata(tournaments_collection, girone_sel, giornata_sel):
    df = st.session_state['df_torneo']
    df_giornata = df[(df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel)].copy()
    for idx, row in df_giornata.iterrows():
        df.at[idx, 'GolCasa'] = st.session_state.get(f"golcasa_{idx}", 0)
        df.at[idx, 'GolOspite'] = st.session_state.get(f"golospite_{idx}", 0)
        df.at[idx, 'Valida'] = st.session_state.get(f"valida_{idx}", False)
    st.session_state['df_torneo'] = df
    if 'tournament_id' in st.session_state:
        aggiorna_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], df)
        st.toast("Risultati salvati su MongoDB ✅")
    else:
        st.error("❌ Errore: ID del torneo non trovato. Impossibile salvare.")
    st.rerun()

def mostra_classifica_stilizzata(df_classifica, girone_sel):
    if df_classifica is None or df_classifica.empty:
        st.info("⚽ Nessuna partita validata")
        return
    df_girone = df_classifica[df_classifica['Girone'] == girone_sel].reset_index(drop=True)
    st.dataframe(combined_style(df_girone), use_container_width=True)

# -------------------------
# APP
# -------------------------
def main():
    if st.session_state.get('sidebar_state_reset', False):
        reset_app_state()
        st.session_state['sidebar_state_reset'] = False
        st.rerun()

    players_collection = init_mongo_connection(st.secrets["MONGO_URI"], "giocatori_subbuteo", "superba_players", show_ok=False)
    tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], "subbuteo_tournement", "superba_tournement", show_ok=False)

    if st.session_state.get('calendario_generato', False) and 'nome_torneo' in st.session_state:
        st.title(f"🏆 {st.session_state['nome_torneo']}")
    else:
        st.title("🏆 Torneo Superba - Gestione Gironi")

    df_master = carica_giocatori_da_db(players_collection)

    if players_collection is None and tournaments_collection is None:
        st.error("❌ Impossibile avviare l'applicazione. La connessione a MongoDB non è disponibile.")
        return

    # --- [resto codice invariato fino a mostra_assegnazione_squadre] ---

            if st.session_state.get('mostra_assegnazione_squadre', False):
                st.markdown("---")
                st.markdown("### ⚽ Modifica Squadra e Potenziale")

                for gioc in st.session_state['giocatori_selezionati_definitivi']:
                    # Inizializza valori default se mancanti
                    if gioc not in st.session_state['gioc_info']:
                        row = df_master[df_master['Giocatore'] == gioc].iloc[0] if gioc in df_master['Giocatore'].values else None
                        squadra_default = row['Squadra'] if row is not None else ""
                        potenziale_default = int(row['Potenziale']) if row is not None else 4
                        st.session_state['gioc_info'][gioc] = {
                            "Squadra": squadra_default,
                            "Potenziale": potenziale_default
                        }

                    squadra_corrente = st.session_state['gioc_info'][gioc].get("Squadra", "")
                    potenziale_corrente = int(st.session_state['gioc_info'][gioc].get("Potenziale", 4))

                    squadra_nuova = st.text_input(f"Squadra per {gioc}", value=squadra_corrente, key=f"squadra_{gioc}")
                    potenziale_nuovo = st.slider(f"Potenziale per {gioc}", 1, 10, potenziale_corrente, key=f"potenziale_{gioc}")

                    st.session_state['gioc_info'][gioc]["Squadra"] = squadra_nuova
                    st.session_state['gioc_info'][gioc]["Potenziale"] = potenziale_nuovo

                if st.button("Conferma Squadre e Potenziali"):
                    st.session_state['mostra_gironi'] = True
                    st.toast("Squadre e potenziali confermati ✅")
                    st.rerun()

    # --- [resto invariato come nel tuo file originale] ---

if __name__ == "__main__":
    main()
