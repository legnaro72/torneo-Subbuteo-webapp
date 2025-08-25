import streamlit as st
import pandas as pd
import random
from fpdf import FPDF
from datetime import datetime
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId

# -------------------------------------------------
# CONFIG PAGINA
# -------------------------------------------------

st.set_page_config(page_title="⚽Campionato/Torneo Subbuteo", layout="wide")

# -------------------------
# STATO
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
    'filtro_attivo': 'Nessuno'
}
for k, v in DEFAULT_STATE.items():
    if k not in st.session_state:
        st.session_state[k] = v

def reset_app_state():
    for k in list(st.session_state.keys()):
        if k not in ['df_torneo', 'sidebar_state_reset']:
            st.session_state.pop(k)
    st.session_state.update(DEFAULT_STATE)
    st.session_state['df_torneo'] = pd.DataFrame()

# -------------------------
# UTILS
# -------------------------

def safe_int(val):
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0

# -------------------------
# MONGO
# -------------------------

@st.cache_resource
def init_mongo_connection(uri, db_name, collection_name):
    try:
        client = MongoClient(uri, server_api=ServerApi('1'))
        db = client[db_name]
        return db[collection_name]
    except Exception:
        return None

def carica_giocatori_da_db(players_collection):
    if players_collection is None:
        return pd.DataFrame()
    try:
        df = pd.DataFrame(list(players_collection.find({}, {"_id": 0})))
        return df if not df.empty else pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Errore lettura giocatori: {e}")
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
# CLASSIFICA
# -------------------------

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
            gc = safe_int(r['GolCasa'])
            go = safe_int(r['GolOspite'])
            casa, ospite = r['Casa'], r['Ospite']
            stats[casa]['GF'] += gc
            stats[casa]['GS'] += go
            stats[ospite]['GF'] += go
            stats[ospite]['GS'] += gc
            if gc > go:
                stats[casa]['Punti'] += 2
                stats[casa]['V'] += 1
                stats[ospite]['S'] += 1
            elif gc < go:
                stats[ospite]['Punti'] += 2
                stats[ospite]['V'] += 1
                stats[casa]['S'] += 1
            else:
                stats[casa]['Punti'] += 1
                stats[ospite]['Punti'] += 1
                stats[casa]['P'] += 1
                stats[ospite]['P'] += 1
        for s in squadre:
            stats[s]['DR'] = stats[s]['GF'] - stats[s]['GS']
        df_stat = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index': 'Squadra'})
        df_stat['Girone'] = girone
        classifiche.append(df_stat)
    if not classifiche:
        return pd.DataFrame()
    return pd.concat(classifiche).sort_values(by=['Girone', 'Punti', 'DR'], ascending=[True, False, False])

# -------------------------
# CALENDARIO
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
                    partite.append({"Girone": gname, "Giornata": giornata + 1, "Casa": casa, "Ospite": ospite, "GolCasa": None, "GolOspite": None, "Valida": False})
            if tipo == "Andata e ritorno":
                for i in range(half):
                    casa, ospite = teams[-(i + 1)], teams[i]
                    if casa != "Riposo" and ospite != "Riposo":
                        partite.append({"Girone": gname, "Giornata": giornata + 1 + n - 1, "Casa": casa, "Ospite": ospite, "GolCasa": None, "GolOspite": None, "Valida": False})
            teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    return pd.DataFrame(partite)

# -------------------------
# VIEW
# -------------------------

def navigation_buttons(label, key, min_val, max_val):
    c1, c2, c3 = st.columns([1, 3, 1])
    with c1:
        if st.button("◀️", key=f"{key}_prev"):
            st.session_state[key] = max(min_val, st.session_state[key] - 1)
            st.rerun()
    with c2:
        st.markdown(f"<div style='text-align:center;font-weight:bold;'>{label} {st.session_state[key]}</div>", unsafe_allow_html=True)
    with c3:
        if st.button("▶️", key=f"{key}_next"):
            st.session_state[key] = min(max_val, st.session_state[key] + 1)
            st.rerun()

def mostra_calendario_giornata(df, girone_sel, giornata_sel):
    df_g = df[(df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel)]
    if df_g.empty:
        st.info("Nessuna partita trovata")
        return
    for idx, row in df_g.iterrows():
        gc = safe_int(row['GolCasa'])
        go = safe_int(row['GolOspite'])
        c1, c2, c3, c4, c5 = st.columns([5, 1.5, 1, 1.5, 1])
        with c1:
            st.markdown(f"{row['Casa']} vs {row['Ospite']}")
        with c2:
            st.number_input("", 0, 20, gc, key=f"golcasa_{idx}", disabled=row['Valida'], label_visibility="hidden")
        with c3:
            st.markdown("-")
        with c4:
            st.number_input("", 0, 20, go, key=f"golospite_{idx}", disabled=row['Valida'], label_visibility="hidden")
        with c5:
            st.checkbox("Valida", key=f"valida_{idx}", value=row['Valida'])

def salva_risultati_giornata(tournaments_collection, girone, giornata):
    df = st.session_state['df_torneo']
    df_g = df[(df['Girone'] == girone) & (df['Giornata'] == giornata)]
    for idx, _ in df_g.iterrows():
        df.at[idx, 'GolCasa'] = st.session_state.get(f"golcasa_{idx}", 0)
        df.at[idx, 'GolOspite'] = st.session_state.get(f"golospite_{idx}", 0)
        df.at[idx, 'Valida'] = st.session_state.get(f"valida_{idx}", False)
    st.session_state['df_torneo'] = df
    if 'tournament_id' in st.session_state:
        aggiorna_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], df)
        st.toast("Risultati salvati su MongoDB ✅")
    else:
        st.error("❌ ID torneo non trovato")
    _ = aggiorna_classifica(df)
    st.rerun()

def mostra_classifica(df_classifica, girone):
    if df_classifica.empty:
        st.info("⚽ Nessuna partita validata")
        return
    st.dataframe(df_classifica[df_classifica['Girone'] == girone], use_container_width=True)

# -------------------------
# MAIN
# -------------------------

def main():
    players_collection = init_mongo_connection(st.secrets["MONGO_URI"], "giocatori_subbuteo", "superba_players")
    tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], "subbuteo_tournament", "tournament")

    if st.session_state['calendario_generato']:
        df = st.session_state['df_torneo']
        gironi = sorted(df['Girone'].unique().tolist())
        giornate_correnti = sorted(df[df['Girone'] == st.session_state['girone_sel']]['Giornata'].unique())
        
        # Sezione per la classifica nella sidebar
        with st.sidebar:
            st.header("Classifiche Gironi")
            if gironi:
                girone_classifica_sel = st.selectbox("Seleziona Girone", gironi, key="girone_classifica_sel")
                st.subheader(f"Classifica {girone_classifica_sel}")
                classifica = aggiorna_classifica(df)
                mostra_classifica(classifica, girone_classifica_sel)
            else:
                st.info("Nessun girone trovato.")
        
        # Contenuto principale
        g_sel = st.selectbox("Seleziona Girone", gironi, index=gironi.index(st.session_state['girone_sel']))
        if g_sel != st.session_state['girone_sel']:
            st.session_state['girone_sel'] = g_sel
            if giornate_correnti:
                st.session_state['giornata_sel'] = giornate_correnti[0]
            st.rerun()

        st.session_state['usa_bottoni'] = st.checkbox("Usa bottoni giornata", value=st.session_state['usa_bottoni'])
        if st.session_state['usa_bottoni']:
            if giornate_correnti:
                navigation_buttons("Giornata", "giornata_sel", min(giornate_correnti), max(giornate_correnti))
            else:
                st.info("Nessuna giornata disponibile per questo girone.")
        else:
            if giornate_correnti:
                try:
                    idx = giornate_correnti.index(st.session_state['giornata_sel'])
                except ValueError:
                    idx = 0
                    st.session_state['giornata_sel'] = giornate_correnti[0]
                nuova = st.selectbox("Seleziona Giornata", giornate_correnti, index=idx)
                if nuova != st.session_state['giornata_sel']:
                    st.session_state['giornata_sel'] = nuova
                    st.rerun()
            else:
                st.info("Nessuna giornata disponibile per questo girone.")

        mostra_calendario_giornata(df, st.session_state['girone_sel'], st.session_state['giornata_sel'])
        st.button("💾 Salva Risultati", on_click=salva_risultati_giornata, args=(tournaments_collection, st.session_state['girone_sel'], st.session_state['giornata_sel']))

    else:
        st.subheader("📁 Carica o crea torneo")
        tornei_disponibili = carica_tornei_da_db(tournaments_collection)
        if tornei_disponibili:
            tornei_map = {t['nome_torneo']: str(t['_id']) for t in tornei_disponibili}
            nome_sel = st.selectbox("Seleziona torneo", list(tornei_map.keys()))
            if st.button("Carica Torneo"):
                st.session_state['tournament_id'] = tornei_map[nome_sel]
                st.session_state['nome_torneo'] = nome_sel
                torneo_data = carica_torneo_da_db(tournaments_collection, st.session_state['tournament_id'])
                if torneo_data:
                    st.session_state['calendario_generato'] = True
                    st.rerun()
        st.markdown("---")
        nome = st.text_input("Nome nuovo torneo", f"Torneo_{datetime.now().strftime('%d%m%Y')}")
        n_gioc = st.number_input("Numero giocatori", 4, 32, 8)
        n_gironi = st.number_input("Numero gironi", 1, 8, 2)
        tipo = st.selectbox("Tipo calendario", ["Solo andata", "Andata e ritorno"])
        giocatori = [f"Gioc{i+1}" for i in range(n_gioc)]
        random.shuffle(giocatori)
        gironi = [giocatori[i::n_gironi] for i in range(n_gironi)]
        if st.button("Genera Calendario"):
            df_torneo = genera_calendario_from_list(gironi, tipo)
            tid = salva_torneo_su_db(tournaments_collection, df_torneo, nome)
            if tid:
                st.session_state['df_torneo'] = df_torneo
                st.session_state['tournament_id'] = str(tid)
                st.session_state['nome_torneo'] = nome
                st.session_state['calendario_generato'] = True
                st.rerun()

if __name__ == "__main__":
    main()
