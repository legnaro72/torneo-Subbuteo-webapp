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
    'filtro_attivo': 'Nessuno',
    'nome_torneo': None,
    'tournament_id': None,
    'torneo_completato': False,
    'classifica_finale': None,
    'sidebar_state_reset': False,
    'show_load_menu': False
}

def reset_app_state():
    for key in list(st.session_state.keys()):
        if key not in ['df_torneo', 'players_collection', 'tournaments_collection']:
            st.session_state.pop(key)
    st.session_state.update(DEFAULT_STATE)
    st.session_state['df_torneo'] = pd.DataFrame()

# -------------------------
# FUNZIONI CONNESSIONE MONGO (SENZA SUCCESS VERDI)
# -------------------------
@st.cache_resource
def init_mongo_connection(uri, db_name, collection_name, show_ok: bool = False):
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

def safe_str(val):
    return "" if val is None else str(val)

# -------------------------

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
def carica_tornei_da_db(tournaments_collection):
    if tournaments_collection is None:
        st.error("❌ Impossibile connettersi alla collezione dei tornei.")
        return {}
    
    tornei_disponibili = {}
    try:
        for torneo in tournaments_collection.find({}, {"nome_torneo": 1}):
            tornei_disponibili[torneo['nome_torneo']] = str(torneo['_id'])
    except Exception as e:
        st.error(f"❌ Errore durante il caricamento della lista dei tornei: {e}")
        return {}

    return tornei_disponibili

def carica_torneo_da_db(tournaments_collection, tournament_id):
    if tournaments_collection is None:
        st.error("❌ La collezione dei tornei non è disponibile.")
        return None
    try:
        torneo_data = tournaments_collection.find_one({"_id": ObjectId(tournament_id)})
        
        if torneo_data and 'calendario' in torneo_data:
            df_torneo = pd.DataFrame(torneo_data['calendario'])
            df_torneo['Valida'] = df_torneo['Valida'].astype(bool)
            
            df_torneo['GolCasa'] = pd.to_numeric(df_torneo['GolCasa'], errors='coerce')
            df_torneo['GolOspite'] = pd.to_numeric(df_torneo['GolOspite'], errors='coerce')
            
            df_torneo = df_torneo.fillna(0)
            
            df_torneo['GolCasa'] = df_torneo['GolCasa'].astype('Int64')
            df_torneo['GolOspite'] = df_torneo['GolOspite'].astype('Int64')

            st.session_state['df_torneo'] = df_torneo
            return torneo_data
    except Exception as e:
        st.error(f"❌ Errore caricamento torneo: {e}")
        return None

def carica_giocatori_da_db(collection):
    if collection is None:
        st.error("❌ La collezione dei giocatori non è disponibile. Ritorno un DataFrame vuoto.")
        return pd.DataFrame(columns=['Giocatore', 'Squadra', 'Potenziale'])

    try:
        data = list(collection.find({}, {'_id': 0, 'Giocatore': 1, 'Squadra': 1, 'Potenziale': 1}))
        
        if not data:
            return pd.DataFrame(columns=['Giocatore', 'Squadra', 'Potenziale'])
        
        df = pd.DataFrame(data)

        if 'Giocatore' not in df.columns or 'Squadra' not in df.columns:
            st.warning("⚠️ I documenti del database non contengono le colonne 'Giocatore' o 'Squadra'.")
            return pd.DataFrame(columns=['Giocatore', 'Squadra', 'Potenziale'])
        
        df = df.dropna(subset=['Giocatore'])
            
        return df

    except Exception as e:
        st.error(f"❌ Errore durante il caricamento dei giocatori: {e}")
        st.info("Ritorno un DataFrame vuoto per prevenire ulteriori errori.")
        return pd.DataFrame(columns=['Giocatore', 'Squadra', 'Potenziale'])

def salva_torneo_su_db(tournaments_collection, df_torneo, nome_torneo):
    if tournaments_collection is None:
        return None
    try:
        # ➡️ CORREZIONE: Pulisci il dataframe prima di convertirlo, evitando i None
        df_torneo_pulito = df_torneo.fillna(0)
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
        # ➡️ CORREZIONE: Pulisci il dataframe prima di aggiornarlo, evitando i None
        df_torneo_pulito = df_torneo.fillna(0)
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
                        "Casa": casa, "Ospite": ospite, "GolCasa": 0, "GolOspite": 0, "Valida": False
                    })
                    if tipo == "Andata e ritorno":
                        partite.append({
                            "Girone": gname, "Giornata": giornata + 1 + n - 1,
                            "Casa": ospite, "Ospite": casa, "GolCasa": 0, "GolOspite": 0, "Valida": False
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
        return pd.DataFrame()
    df_classifica = pd.concat(classifiche, ignore_index=True)
    df_classifica = df_classifica.sort_values(by=['Girone', 'Punti', 'DR'], ascending=[True, False, False])
    return df_classifica

# -------------------------
# FUNZIONI DI VISUALIZZAZIONE & EVENTI
# -------------------------
def mostra_calendario_giornata(df, girone_sel, giornata_sel, tournaments_collection):
    df_giornata = df[(df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel)].copy()
    if df_giornata.empty:
        return
    
    with st.expander("⚽ Inserisci i risultati della giornata"):
        for index, row in df_giornata.iterrows():
            col1, col2, col3, col4, col5 = st.columns([1, 0.4, 0.1, 0.4, 1])

            with col1:
                #st.write(f"**{row['Casa']}**")
                st.write(f"**{safe_str(row['Casa'])}**")


            
            with col2:
                gol_casa_val = int(row['GolCasa']) if pd.notna(row['GolCasa']) else 0
                st.number_input(
                    "Gol",
                    min_value=0,
                    step=1,
                    #key=f"golcasa_{index}",
                    key=f"golcasa_{girone_sel}_{giornata_sel}_{index}",
                    label_visibility="hidden",
                    value=gol_casa_val
                )
            
            with col3:
                st.write("**:**")
            
            with col4:
                gol_ospite_val = int(row['GolOspite']) if pd.notna(row['GolOspite']) else 0
                st.number_input(
                    "Gol",
                    min_value=0,
                    step=1,
                    #key=f"golospite_{index}",
                    key=f"golospite_{girone_sel}_{giornata_sel}_{index}",

                    label_visibility="hidden",
                    value=gol_ospite_val
                )
            
            with col5:
                #st.write(f"**{row['Ospite']}**")
                st.write(f"**{safe_str(row['Ospite'])}**")
            
            st.checkbox(
                "Partita Conclusa",
                value=bool(row['Valida']),
                #key=f"valida_{index}"
                key=f"valida_{girone_sel}_{giornata_sel}_{index}"
            )
            st.write("---")

    #if st.button("💾 Salva Risultati Giornata", key="salva_giornata_button"):
    if st.button("💾 Salva Risultati Giornata", key="salva_giornata_button"):
        with st.spinner('Salvataggio in corso...'):
            # 🔎 DEBUG: Mostro DataFrame PRIMA del salvataggio
            st.subheader("📊 DEBUG: DataFrame prima del salvataggio")
            st.dataframe(st.session_state['df_torneo'], use_container_width=True)
            st.text("Tipi di colonna:")
            st.write(st.session_state['df_torneo'].dtypes)
    
            df_to_save = st.session_state['df_torneo'].copy()

        with st.spinner('Salvataggio in corso...'):
            df_to_save = st.session_state['df_torneo'].copy()

            for index, row in df_giornata.iterrows():
                gol_casa = st.session_state.get(f"golcasa_{index}", 0)
                gol_ospite = st.session_state.get(f"golospite_{index}", 0)
                valida = st.session_state.get(f"valida_{index}", False)
                
                df_to_save.loc[index, 'GolCasa'] = int(gol_casa)
                df_to_save.loc[index, 'GolOspite'] = int(gol_ospite)
                df_to_save.loc[index, 'Valida'] = bool(valida)

                # 🔎 DEBUG: Mostro DataFrame DOPO aggiornamento ma prima di salvare
                st.subheader("📊 DEBUG: DataFrame dopo aggiornamento ma prima di scrivere su MongoDB")
                st.dataframe(df_to_save, use_container_width=True)
                st.text("Tipi di colonna:")
                st.write(df_to_save.dtypes)


            if 'tournament_id' in st.session_state:
                try:
                    aggiorna_torneo_su_db(tournaments_collection, st.session_state['tournament_id'], df_to_save)
                    st.session_state['df_torneo'] = df_to_save
                    st.toast("Risultati salvati su MongoDB ✅")

                    # 🔎 DEBUG 3: DataFrame DOPO salvataggio su MongoDB
                    st.subheader("📊 DEBUG: DataFrame dopo salvataggio su MongoDB")
                    st.dataframe(st.session_state['df_torneo'], use_container_width=True)
                    st.text("Tipi di colonna:")
                    st.write(st.session_state['df_torneo'].dtypes)

                    st.toast("Risultati salvati su MongoDB ✅")

                    if df_to_save['Valida'].all():
                        nome_completato = f"completato_{st.session_state['nome_torneo']}"
                        classifica_finale = aggiorna_classifica(df_to_save)
                        salva_torneo_su_db(tournaments_collection, df_to_save, nome_completato)
                        st.session_state['torneo_completato'] = True
                        st.session_state['classifica_finale'] = classifica_finale
                        st.toast(f"Torneo completato e salvato come {nome_completato} ✅")
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"❌ Errore durante il salvataggio: {e}")
            else:
                st.error("❌ Errore: ID del torneo non trovato. Impossibile salvare.")
    

def mostra_classifica_stilizzata(df_classifica, girone_sel):    
    if df_classifica is None or df_classifica.empty:
        st.info("⚽ Nessuna partita validata")
        return
    df_girone = df_classifica[df_classifica['Girone'] == girone_sel].reset_index(drop=True)
    st.dataframe(df_girone, use_container_width=True)


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

def mostra_schermata_torneo(players_collection, tournaments_collection):
    st.sidebar.header("⚙️ Opzioni Torneo")
    # ➡️ CORREZIONE: Assicurati che il dataframe non contenga None prima di visualizzarlo
    df = st.session_state['df_torneo'].fillna(0)
    classifica = aggiorna_classifica(df)

    if classifica is not None and not classifica.empty:
        st.sidebar.download_button(
            label="📄 Esporta in PDF",
            data=esporta_pdf(df, classifica, st.session_state['nome_torneo']),
            file_name=f"torneo_{st.session_state['nome_torneo']}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    else:
        st.sidebar.info("Nessuna partita valida. Per generare la classifica completa, compila e valida i risultati.")
        
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Visualizza Classifica")
    gironi_sidebar = sorted(df['Girone'].dropna().unique().tolist())
    
    gironi_sidebar.insert(0, 'Nessuno')  
    
    girone_class_sel = st.sidebar.selectbox(
        "Seleziona Girone", gironi_sidebar, key="sidebar_classifica_girone"
    )
    
    if st.sidebar.button("Visualizza Classifica", key="btn_classifica_sidebar"):
        if girone_class_sel != 'Nessuno':
            st.subheader(f"Classifica {girone_class_sel}")
            classifica = aggiorna_classifica(df)
            if classifica is not None and not classifica.empty:
                mostra_classifica_stilizzata(classifica, girone_class_sel)
            else:
                st.info("⚽ Nessuna partita validata per questo girone.")
        else:
            st.info("Seleziona un girone per visualizzare la classifica.")

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
        st.sidebar.markdown("#### Filtra per Giocatore")
        giocatori = sorted(list(set(df['Casa'].unique().tolist() + df['Ospite'].unique().tolist())))
        giocatore_scelto = st.sidebar.selectbox("Seleziona un giocatore", [''] + giocatori, key='filtro_giocatore_sel')
        tipo_andata_ritorno = st.sidebar.radio("Andata/Ritorno", ["Entrambe", "Andata", "Ritorno"], key='tipo_giocatore')
        if giocatore_scelto:
            st.subheader(f"Partite da giocare per {giocatore_scelto}")
            df_filtrato = df[(df['Valida'] == False) & ((df['Casa'] == giocatore_scelto) | (df['Ospite'] == giocatore_scelto))]
            if tipo_andata_ritorno == "Andata":
                n_squadre_girone = len(df.groupby('Girone').first().index)
                df_filtrato = df_filtrato[df_filtrato['Giornata'] <= n_squadre_girone - 1]
            elif tipo_andata_ritorno == "Ritorno":
                n_squadre_girone = len(df.groupby('Girone').first().index)
                df_filtrato = df_filtrato[df_filtrato['Giornata'] > n_squadre_girone - 1]

            if not df_filtrato.empty:
                df_filtrato_show = df_filtrato[['Girone', 'Giornata', 'Casa', 'Ospite']].rename(
                    columns={'Girone': 'Girone', 'Giornata': 'Giornata', 'Casa': 'Casa', 'Ospite': 'Ospite'}
                )
                st.dataframe(df_filtrato_show.reset_index(drop=True), use_container_width=True)
            else:
                st.info("🎉 Nessuna partita da giocare trovata per questo giocatore.")
            
    elif st.session_state['filtro_attivo'] == 'Girone':
        st.sidebar.markdown("#### Filtra per Girone")
        gironi_disponibili = sorted(df['Girone'].unique().tolist())
        girone_scelto = st.sidebar.selectbox("Seleziona un girone", gironi_disponibili, key='filtro_girone_sel')
        tipo_andata_ritorno = st.sidebar.radio("Andata/Ritorno", ["Entrambe", "Andata", "Ritorno"], key='tipo_girone')
        st.subheader(f"Partite da giocare nel {girone_scelto}")
        df_filtrato = df[(df['Valida'] == False) & (df['Girone'] == girone_scelto)]

        if tipo_andata_ritorno == "Andata":
            n_squadre_girone = len(df[df['Girone'] == girone_scelto]['Casa'].unique())
            df_filtrato = df_filtrato[df_filtrato['Giornata'] <= n_squadre_girone - 1]
        elif tipo_andata_ritorno == "Ritorno":
            n_squadre_girone = len(df[df['Girone'] == girone_scelto]['Casa'].unique())
            df_filtrato = df_filtrato[df_filtrato['Giornata'] > n_squadre_girone - 1]

        if not df_filtrato.empty:
            df_filtrato_show = df_filtrato[['Giornata', 'Casa', 'Ospite']].rename(
                columns={'Giornata': 'Giornata', 'Casa': 'Casa', 'Ospite': 'Ospite'}
            )
            st.dataframe(df_filtrato_show.reset_index(drop=True), use_container_width=True)
        else:
            st.info("🎉 Tutte le partite di questo girone sono state giocate.")

    st.markdown("---")
    if st.session_state['filtro_attivo'] == 'Nessuno':
        st.subheader("Navigazione Calendario")
        gironi = sorted(df['Girone'].dropna().unique().tolist())
        giornate_correnti = sorted(
            df[df['Girone'] == st.session_state['girone_sel']]['Giornata'].dropna().unique().tolist()
        )
        
        nuovo_girone = st.selectbox("Seleziona Girone", gironi, index=gironi.index(st.session_state['girone_sel']))
        #if nuovo_girone != st.session_state['girone_sel']:
        if nuovo_girone != st.session_state['girone_sel']:
            st.session_state['girone_sel'] = nuovo_girone
            st.session_state['giornata_sel'] = 1
            
            # 🔎 Pulizia widget orfani
            keys_to_remove = [k for k in st.session_state.keys() if k.startswith("golcasa_") or k.startswith("golospite_") or k.startswith("valida_")]
            for k in keys_to_remove:
                st.session_state.pop(k, None)
            
            st.rerun()


        
        modalita_nav = st.radio(        
            "Modalità navigazione giornata",
            ["Menu a tendina", "Bottoni"],
            index=0,
            key="modalita_navigazione"
        )
        
        if modalita_nav == "Bottoni":
            navigation_buttons("Giornata", 'giornata_sel', 1, len(giornate_correnti))
        else:
            try:
                current_index = giornate_correnti.index(st.session_state['giornata_sel'])
            except ValueError:
                current_index = 0
                st.session_state['giornata_sel'] = giornate_correnti[0]
        
            nuova_giornata = st.selectbox("Seleziona Giornata", giornate_correnti, index=current_index)
            #if nuova_giornata != st.session_state['giornata_sel']:
            if nuova_giornata != st.session_state['giornata_sel']:
                st.session_state['giornata_sel'] = nuova_giornata
                
                # 🔎 Pulizia widget orfani
                keys_to_remove = [k for k in st.session_state.keys() if k.startswith("golcasa_") or k.startswith("golospite_") or k.startswith("valida_")]
                for k in keys_to_remove:
                    st.session_state.pop(k, None)
                
                st.rerun()


        st.markdown("---")
        st.subheader("Navigazione Calendario")
        mostra_calendario_giornata(df, st.session_state['girone_sel'], st.session_state['giornata_sel'], tournaments_collection)
    
def main():
    for key, value in DEFAULT_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if st.session_state.get('sidebar_state_reset', False):
        reset_app_state()
        st.session_state['sidebar_state_reset'] = False
        st.rerun()

    players_collection = init_mongo_connection(st.secrets["MONGO_URI"], "giocatori_subbuteo", "superba_players", show_ok=False)
    tournaments_collection = init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"], "TorneiSubbuteo", "Superba", show_ok=False)

    if players_collection is None and tournaments_collection is None:
        st.error("❌ Impossibile avviare l'applicazione. La connessione a MongoDB non è disponibile.")
        return

    if st.session_state.get('calendario_generato', False) and 'nome_torneo' in st.session_state:
        st.markdown(f"<div class='big-title'>🏆 {safe_str(st.session_state.get('nome_torneo'))}</div>", unsafe_allow_html=True)
        if st.session_state.get('torneo_completato', False) and st.session_state.get('classifica_finale') is not None:
            vincitori = []
            df_classifica = st.session_state['classifica_finale']
            for girone in df_classifica['Girone'].unique():
                primo = df_classifica[df_classifica['Girone'] == girone].iloc[0]['Squadra']
                vincitori.append(f"🏅 {girone}: {primo}")
            st.success("🎉 Torneo Completato! Vincitori → " + ", ".join(vincitori))
        mostra_schermata_torneo(players_collection, tournaments_collection)
        return

    st.markdown("""
        <style>
        .big-title { text-align: center; font-size: clamp(18px, 4vw, 38px); font-weight: bold; margin: 15px 0; color: #e63946; }
        .sub-title { font-size: 20px; font-weight: 600; margin-top: 15px; color: d3557; }
        .stButton>button { background-color: #457b9d; color: white; border-radius: 8px; padding: 0.5em 1em; font-weight: bold; }
        .stButton>button:hover { background-color: d3557; color: white; }
        .stDownloadButton>button { background-color: #2a9d8f; color: white; border-radius: 8px; font-weight: bold; }
        .stDownloadButton>button:hover { background-color: #21867a; }
        .stDataFrame { border: 2px solid #f4a261; border-radius: 10px; }
        </style>
    """, unsafe_allow_html=True)

    try:
        df_master = carica_giocatori_da_db(players_collection)
        giocatori_esistenti = df_master['Giocatore'].unique().tolist()
    except KeyError:
        st.error("❌ Errore: La colonna 'Giocatore' non è stata trovata nei dati del database. Potrebbe essere vuoto o avere una struttura diversa. Verrà caricata una lista vuota di giocatori.")
        giocatori_esistenti = []

    st.info("Benvenuto! Seleziona una delle opzioni qui sotto per iniziare.")

    col_iniziali = st.columns(2)
    with col_iniziali[0]:
        if st.button("➕ Crea Nuovo Torneo", use_container_width=True, key="crea_nuovo_button"):
            st.session_state['mostra_form_creazione'] = True
            st.session_state['show_load_menu'] = False
            st.rerun()

    with col_iniziali[1]:
        st.session_state['tornei_disponibili'] = carica_tornei_da_db(tournaments_collection)
        opzioni_tornei = st.session_state['tornei_disponibili']
        
        if not opzioni_tornei:
            st.warning("Non ci sono tornei salvati. Crea un nuovo torneo per iniziare.")
        else:
            if st.button("📂 Carica Torneo Esistente", use_container_width=True, key="carica_esistente_button"):
                st.session_state['mostra_form_creazione'] = False
                st.session_state['show_load_menu'] = True
                st.rerun()

    if st.session_state.get('mostra_form_creazione', False):
        st.markdown("---")
        st.subheader("Nuovo Torneo")
        st.session_state['nome_torneo'] = st.text_input("Nome del Torneo")
        num_partecipanti = st.number_input("Numero di partecipanti (4-12)", min_value=4, max_value=12, step=1)
        tipo_torneo = st.selectbox("Tipo di Torneo", ["Solo andata", "Andata e ritorno"])
        giocatori_scelti = st.multiselect(
        "Seleziona i partecipanti dal DB",
        giocatori_esistenti,
        max_selections=num_partecipanti
    )

        mancanti = num_partecipanti - len(giocatori_scelti)
        nuovi_giocatori = []
        if mancanti > 0:
            st.warning(f"⚠️ Mancano {mancanti} giocatori: inseriscili manualmente")
            for i in range(mancanti):
                nuovo_nome = st.text_input(f"Nome giocatore {i+1}", key=f"nuovo_giocatore_{i}")
                if nuovo_nome:
                    nuovi_giocatori.append(nuovo_nome)

        giocatori_finali = giocatori_scelti + nuovi_giocatori

        if len(giocatori_finali) == num_partecipanti:
            st.session_state['giocatori_selezionati_definitivi'] = giocatori_finali
            st.session_state['mostra_assegnazione_squadre'] = True
            st.session_state['tipo_torneo'] = tipo_torneo

        if st.session_state.get('mostra_assegnazione_squadre', False) and len(st.session_state['giocatori_selezionati_definitivi']) == num_partecipanti:
            st.markdown("---")
            if st.button("Avanti e Assegna Squadre"):
                st.session_state['mostra_gironi'] = True
                st.rerun()

    if st.session_state.get('mostra_gironi', False):
        st.markdown("---")
        st.subheader("Assegnazione Squadre ai Gironi")
        col_gironi_manuali = st.columns(2)
        with col_gironi_manuali[0]:
            st.write("Configurazione Gironi")
        
        with col_gironi_manuali[1]:
            if st.button("Torna indietro", key="indietro_assegnazione"):
                st.session_state['mostra_gironi'] = False
                st.rerun()
        
        gironi_players = {}
        num_gironi = st.number_input("Numero di gironi", min_value=1, max_value=3, step=1)
        players_per_girone = len(st.session_state['giocatori_selezionati_definitivi']) // num_gironi
        
        giocatori_shuffled = st.session_state['giocatori_selezionati_definitivi'][:]
        random.shuffle(giocatori_shuffled)

        st.markdown("---")
        for i in range(num_gironi):
            girone_name = f"Girone {i+1}"
            gironi_players[girone_name] = st.multiselect(
                f"Giocatori del {girone_name}",
                giocatori_shuffled,
                default=giocatori_shuffled[i*players_per_girone: (i+1)*players_per_girone],
                key=f"manual_girone_{i}"
            )
        
        gironi_completi = all(len(gironi_players[f"Girone {i+1}"]) == players_per_girone for i in range(num_gironi))
        st.session_state['gironi_manuali_completi'] = gironi_completi and all(p in sum(gironi_players.values(), []) for p in st.session_state['giocatori_selezionati_definitivi'])

        if st.session_state['gironi_manuali_completi']:
            if st.button("Conferma Gironi e Genera Calendario"):
                df_torneo = genera_calendario_from_list(list(gironi_players.values()), tipo=st.session_state['tipo_torneo'])
                st.session_state['df_torneo'] = df_torneo
                
                tid = salva_torneo_su_db(tournaments_collection, df_torneo, st.session_state['nome_torneo'])

                if tid:
                    st.session_state['df_torneo'] = df_torneo
                    st.session_state['tournament_id'] = str(tid)
                    st.session_state['calendario_generato'] = True
                    st.toast("Calendario generato e salvato su MongoDB ✅")
                    st.rerun()
                else:
                    st.error("❌ Errore: Il salvataggio su MongoDB è fallito. Controlla la connessione al database.")
        else:
            st.warning("Per continuare, devi assegnare tutti i giocatori ai gironi senza duplicazioni.")
    
    if st.session_state.get('show_load_menu', False):
        st.markdown("---")
        st.subheader("Carica Torneo Esistente")
        torneo_selezionato_nome = st.selectbox(
            "Seleziona un torneo da caricare",
            list(opzioni_tornei.keys()),
            key="selezione_torneo_carica"
        )
        
        if st.button("Carica Torneo"):
            if torneo_selezionato_nome:
                tournament_id_selezionato = opzioni_tornei[torneo_selezionato_nome]
                dati_caricati = carica_torneo_da_db(tournaments_collection, tournament_id_selezionato)
                
                if dati_caricati and 'calendario' in dati_caricati:
                    st.session_state['nome_torneo'] = dati_caricati['nome_torneo']
                    st.session_state['tournament_id'] = str(dati_caricati['_id'])
                    st.session_state['calendario_generato'] = True
                    st.toast(f"Torneo '{st.session_state['nome_torneo']}' caricato con successo ✅")
                    st.rerun()
                else:
                    st.error("❌ Errore durante il caricamento del torneo. Il file potrebbe essere corrotto.")
if __name__ == "__main__":
    main()
