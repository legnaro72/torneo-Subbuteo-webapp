baimport streamlit as st
import pandas as pd
import random
from fpdf import FPDF
from datetime import datetime
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
import json
import base64

st.markdown("""
<style>
.stTextInput input[type="text"] {
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

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
    'filtro_attivo': 'Nessuno',
    'usa_bottoni': False,
    'torneo_salvato': False,
    'sidebar_state_reset': False
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value

@st.cache_data
def load_master_df():
    try:
        df = pd.read_csv('master_players.csv')
        df['Potenziale'] = pd.to_numeric(df['Potenziale'], errors='coerce').fillna(0).astype(int)
        return df
    except FileNotFoundError:
        return pd.DataFrame(columns=['Giocatore', 'Squadra', 'Potenziale'])

df_master = load_master_df()

# -------------------------
# CONNESSO A MONGODB
# -------------------------
@st.cache_resource
def init_connection():
    uri = st.secrets["mongo"]["uri"]
    client = MongoClient(uri, server_api=ServerApi('1'))
    try:
        client.admin.command('ping')
        return client
    except Exception as e:
        st.error(f"Errore di connessione a MongoDB: {e}")
        return None

client = init_connection()
if client:
    db = client.get_database("subbuteo_tournements")
    tournaments_collection = db.get_collection("superba_tournements")

# -------------------------
# FUNZIONI
# -------------------------
def carica_torneo_da_db(collection, nome_torneo):
    document = collection.find_one({"nome": nome_torneo})
    if document:
        df = pd.DataFrame(document['calendario'])
        df['GolCasa'] = pd.to_numeric(df['GolCasa'], errors='coerce').astype('Int64')
        df['GolOspite'] = pd.to_numeric(df['GolOspite'], errors='coerce').astype('Int64')
        return df, str(document['_id'])
    return None, None

def salva_torneo_su_db(collection, df_torneo, nome_torneo):
    data_to_save = {
        "nome": nome_torneo,
        "data_creazione": datetime.now(),
        "calendario": df_torneo.to_dict('records')
    }
    
    existing_doc = collection.find_one({"nome": nome_torneo})
    if existing_doc:
        collection.replace_one({"_id": existing_doc["_id"]}, data_to_save)
        return existing_doc["_id"]
    else:
        result = collection.insert_one(data_to_save)
        return result.inserted_id

def carica_tornei_da_db(collection):
    tornei = list(collection.find({}, {'nome': 1}))
    return tornei

def genera_calendario_da_lista_squadre(squadre, tipo_calendario):
    partite = []
    if tipo_calendario == "Solo andata":
        for i in range(len(squadre)):
            for j in range(i + 1, len(squadre)):
                partite.append({'Casa': squadre[i], 'Ospite': squadre[j]})
    else:
        for i in range(len(squadre)):
            for j in range(i + 1, len(squadre)):
                partite.append({'Casa': squadre[i], 'Ospite': squadre[j]})
                partite.append({'Casa': squadre[j], 'Ospite': squadre[i]})
    
    random.shuffle(partite)
    return pd.DataFrame(partite)

def genera_calendario_from_list(gironi_lista, tipo_calendario):
    df_gironi = []
    
    for i, g in enumerate(gironi_lista):
        df_girone = genera_calendario_da_lista_squadre(g, tipo_calendario)
        df_girone['Girone'] = f"Girone {i+1}"
        df_gironi.append(df_girone)
    
    df_calendario = pd.concat(df_gironi, ignore_index=True)
    df_calendario['GolCasa'] = pd.NA
    df_calendario['GolOspite'] = pd.NA
    df_calendario['Valida'] = False
    df_calendario['Giornata'] = 0
    
    for girone in df_calendario['Girone'].unique():
        df_girone_temp = df_calendario[df_calendario['Girone'] == girone].copy()
        squadre_girone = df_girone_temp['Casa'].unique()
        n_squadre = len(squadre_girone)
        
        giornate_num = []
        if n_squadre % 2 == 1:
            squadre_girone = list(squadre_girone) + ['Riposo']
            n_squadre += 1
        
        gironi_andata = n_squadre - 1
        gironi_totali = gironi_andata
        if tipo_calendario == "Andata e ritorno":
            gironi_totali *= 2
        
        schedule = [[] for _ in range(gironi_totali)]
        
        teams_list = list(squadre_girone)
        pivot = teams_list[0]
        other_teams = teams_list[1:]
        
        for g in range(gironi_andata):
            matchups = []
            
            half = len(other_teams) // 2
            for i in range(half):
                matchups.append((other_teams[i], other_teams[len(other_teams) - 1 - i]))
                
            matchups.append((pivot, other_teams[half]))
            
            for match in matchups:
                if 'Riposo' not in match:
                    schedule[g].append({'Casa': match[0], 'Ospite': match[1]})
            
            other_teams = [other_teams[-1]] + other_teams[:-1]
        
        if tipo_calendario == "Andata e ritorno":
            for g in range(gironi_andata):
                for match in schedule[g]:
                    schedule[g + gironi_andata].append({'Casa': match['Ospite'], 'Ospite': match['Casa']})
                    
        for g_idx, giornata_schedule in enumerate(schedule, 1):
            for match in giornata_schedule:
                giornate_num.append({**match, 'Giornata': g_idx, 'Girone': girone})
                
        df_girone_ordinato = pd.DataFrame(giornate_num)
        
        df_calendario.loc[df_calendario['Girone'] == girone, 'Giornata'] = df_girone_ordinato['Giornata']

    df_calendario.sort_values(by=['Girone', 'Giornata'], inplace=True)
    return df_calendario

def aggiorna_classifica(df):
    if 'Girone' not in df.columns:
        return pd.DataFrame(columns=['Girone', 'Squadra', 'Punti', 'V', 'P', 'S', 'GF', 'GS', 'DR'])

    gironi = df['Girone'].dropna().unique()
    classifiche = []
    
    for girone in gironi:
        partite = df[(df['Girone'] == girone) & (df['Valida'] == True)].copy()
        if partite.empty:
            continue
        
        # --- FIX: Converte i valori dei gol in numerico e gestisce i NaN ---
        partite['GolCasa'] = pd.to_numeric(partite['GolCasa'], errors='coerce').fillna(0).astype(int)
        partite['GolOspite'] = pd.to_numeric(partite['GolOspite'], errors='coerce').fillna(0).astype(int)
        # --- FINE FIX ---

        squadre = pd.unique(partite[['Casa', 'Ospite']].values.ravel())
        stats = {s: {'Punti': 0, 'V': 0, 'P': 0, 'S': 0, 'GF': 0, 'GS': 0, 'DR': 0} for s in squadre}

        for _, r in partite.iterrows():
            gc, go = r['GolCasa'], r['GolOspite']
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
        return pd.DataFrame(columns=['Girone', 'Squadra', 'Punti', 'V', 'P', 'S', 'GF', 'GS', 'DR'])

    df_classifica = pd.concat(classifiche, ignore_index=True)
    df_classifica = df_classifica.sort_values(by=['Girone', 'Punti', 'DR'], ascending=[True, False, False])
    return df_classifica

def mostra_classifica_stilizzata(df_classifica, girone_sel):
    st.markdown("### Classifica")
    df_classifica_filtrata = df_classifica[df_classifica['Girone'] == girone_sel]
    
    st.dataframe(df_classifica_filtrata.reset_index(drop=True).style.set_properties(
        **{'background-color': '#424242', 'color': 'white'}), use_container_width=True
    )
    
def mostra_calendario_giornata(df, girone, giornata):
    partite_giornata = df[(df['Girone'] == girone) & (df['Giornata'] == giornata)]
    
    for idx, row in partite_giornata.iterrows():
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.markdown(f"**{row['Casa']}**", help="Squadra in casa")
        with col2:
            st.text_input(
                "Gol Casa",
                key=f"golcasa_{idx}",
                value=str(row['GolCasa']) if not pd.isna(row['GolCasa']) else "",
                disabled=row['Valida'],
                label_visibility="hidden"
            )
        with col3:
            st.markdown(":blue[vs]", help="Matchday", unsafe_allow_html=True)
        with col4:
            st.text_input(
                "Gol Ospite",
                key=f"golospite_{idx}",
                value=str(row['GolOspite']) if not pd.isna(row['GolOspite']) else "",
                disabled=row['Valida'],
                label_visibility="hidden"
            )
        with col5:
            st.markdown(f"**{row['Ospite']}**", help="Squadra in trasferta")

def salva_risultati_giornata(df, giornata):
    for idx, row in df[(df['Giornata'] == giornata)].iterrows():
        gol_casa = st.session_state.get(f"golcasa_{idx}")
        gol_ospite = st.session_state.get(f"golospite_{idx}")

        if gol_casa is not None and gol_ospite is not None:
            st.session_state['df_torneo'].loc[idx, 'GolCasa'] = gol_casa
            st.session_state['df_torneo'].loc[idx, 'GolOspite'] = gol_ospite
            st.session_state['df_torneo'].loc[idx, 'Valida'] = True

    # Salva il torneo aggiornato su MongoDB
    salva_torneo_su_db(tournaments_collection, st.session_state['df_torneo'], st.session_state['nome_torneo'])

def navigation_buttons(type, key, min_val, max_val):
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⏪", key=f"prev_{key}", disabled=st.session_state.get(key, min_val) <= min_val, use_container_width=True):
            st.session_state[key] -= 1
            st.experimental_rerun()
    with col2:
        st.markdown(f"<h3 style='text-align: center;'>{type} {st.session_state.get(key, min_val)}</h3>", unsafe_allow_html=True)
    with col3:
        if st.button("⏩", key=f"next_{key}", disabled=st.session_state.get(key, min_val) >= max_val, use_container_width=True):
            st.session_state[key] += 1
            st.experimental_rerun()

def esporta_pdf(df_calendario, df_classifica, nome_torneo):
    # Resto del codice per esporta_pdf...
    # (Includi la tua logica esistente qui)
    pass

# -------------------------
# MAIN
# -------------------------
def main():
    if 'carica_torneo_esistente' not in st.session_state:
        st.session_state['carica_torneo_esistente'] = False

    if st.sidebar.button("➕ Crea un nuovo Torneo"):
        st.session_state['mostra_form_creazione'] = True
        st.session_state['carica_torneo_esistente'] = False
        st.experimental_rerun()
    
    if st.sidebar.button("💾 Carica un Torneo esistente"):
        st.session_state['carica_torneo_esistente'] = True
        st.session_state['mostra_form_creazione'] = False
        st.session_state['calendario_generato'] = False
        st.session_state.df_torneo = pd.DataFrame()
        st.experimental_rerun()

    if st.session_state.get('mostra_form_creazione', False):
        st.title("⚽ Crea un nuovo Torneo")
        with st.form("form_crea_torneo"):
            st.session_state['nome_torneo'] = st.text_input("Nome Torneo", key="nome_torneo")
            st.session_state['num_giocatori'] = st.number_input("Numero Giocatori", min_value=2, max_value=64, value=2, step=1, key="num_giocatori")
            st.session_state['num_gironi'] = st.number_input("Numero Gironi", min_value=1, max_value=8, value=1, step=1, key="num_gironi", disabled=st.session_state['num_giocatori'] <= 2)
            st.session_state['tipo_calendario'] = st.radio("Tipo di Calendario", ["Tutti contro Tutti (solo Gironi)", "Solo Fase Finale"], key="tipo_calendario")
            
            modalita_gironi = st.radio(
                "Modalità assegnazione gironi",
                ["Popola Gironi Automaticamente", "Assegna Gironi Manualmente"],
                key="modalita_gironi",
                disabled=st.session_state['num_giocatori'] <= 2 or st.session_state['num_gironi'] <= 1
            )
            
            submitted = st.form_submit_button("Genera Calendario 🚀")
            
            if submitted:
                if not st.session_state['nome_torneo']:
                    st.toast("⚠️ Inserisci un nome per il torneo!")
                elif st.session_state['num_giocatori'] < 2:
                    st.toast("⚠️ Il numero di giocatori deve essere almeno 2!")
                elif modalita_gironi == "Assegna Gironi Manualmente":
                    st.session_state['mostra_assegnazione_squadre'] = True
                    st.session_state['giocatori_per_gironi'] = [[] for _ in range(st.session_state['num_gironi'])]
                    st.experimental_rerun()
                else:
                    if not st.session_state.get('giocatori_selezionati_definitivi'):
                        st.session_state['giocatori_selezionati_definitivi'] = [f"Giocatore {i+1}" for i in range(st.session_state['num_giocatori'])]
                        st.session_state['gioc_info'] = {f"Giocatore {i+1}": {"Squadra": f"Squadra {i+1}"} for i in range(st.session_state['num_giocatori'])}

                    gironi_finali = [[] for _ in range(st.session_state['num_gironi'])]
                    random.shuffle(st.session_state['giocatori_selezionati_definitivi'])
                    for i, g in enumerate(st.session_state['giocatori_selezionati_definitivi']):
                        gironi_finali[i % st.session_state['num_gironi']].append(g)

                    df_torneo = genera_calendario_from_list(gironi_finali, st.session_state['tipo_calendario'])
                    tid = salva_torneo_su_db(tournaments_collection, df_torneo, st.session_state['nome_torneo'])
                    if tid:
                        st.session_state['df_torneo'] = df_torneo
                        st.session_state['tournament_id'] = str(tid)
                        st.session_state['calendario_generato'] = True
                        st.toast("Calendario generato... 🎉")
                    else:
                        st.toast("❌ Errore nel salvataggio del torneo!")

    if st.session_state.get('carica_torneo_esistente', False):
        st.title("💾 Carica Torneo esistente")
        tournaments = list(tournaments_collection.find({}, {"nome": 1}))
        
        nomi_tornei = [t['nome'] for t in tournaments]
        
        if not nomi_tornei:
            st.warning("Nessun torneo salvato. Crea un nuovo torneo.")
        else:
            nome_selezionato = st.selectbox("Seleziona un Torneo", nomi_tornei, key='torneo_selezionato')
            if st.button("Carica Torneo"):
                st.session_state['nome_torneo'] = nome_selezionato
                df_caricato, tid_caricato = carica_torneo_da_db(tournaments_collection, st.session_state['nome_torneo'])
                if df_caricato is not None:
                    st.session_state['df_torneo'] = df_caricato
                    st.session_state['tournament_id'] = tid_caricato
                    st.session_state['calendario_generato'] = True
                    st.session_state['carica_torneo_esistente'] = False
                    st.toast("Torneo caricato con successo! 🎉")
                else:
                    st.toast("❌ Errore nel caricamento del torneo!")

    if st.session_state.get('calendario_generato', False):
        st.sidebar.subheader("Opzioni Torneo ⚙️")
        df = st.session_state['df_torneo']

        # Questo blocco calcola la classifica e la pulisce PRIMA dei filtri
        classifica = aggiorna_classifica(df)

        classifica_per_visualizzazione = pd.DataFrame()

        if classifica is not None and not classifica.empty:
            classifica_per_visualizzazione = classifica.fillna('-')
        else:
            cols = ['Girone', 'Squadra', 'Punti', 'V', 'P', 'S', 'GF', 'GS', 'DR']
            classifica_per_visualizzazione = pd.DataFrame(columns=cols).fillna('-')

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

        if st.session_state['filtro_attivo'] == 'Nessuno':
            st.markdown("---")
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
        mostra_classifica_stilizzata(classifica_per_visualizzazione, st.session_state['girone_sel'])
            
    else:
        st.subheader("📁 Carica un torneo o crea uno nuovo")
        col1, col2 = st.columns(2)
        with col1:
            tornei_disponibili = carica_tornei_da_db(tournaments_collection)
            if tornei_disponibili:
                tornei_map = {t['nome']: str(t['_id']) for t in tornei_disponibili}
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
