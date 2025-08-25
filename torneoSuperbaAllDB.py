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
# CONFIG PAGINA
# -------------------------------------------------
st.set_page_config(page_title="🏆 Torneo Subbuteo Superba", layout="wide")


# -------------------------
# STATO APP
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


# -------------------------
# UTILITY
# -------------------------
def reset_app_state():
for key in list(st.session_state.keys()):
if key not in ['df_torneo', 'sidebar_state_reset']:
st.session_state.pop(key)
st.session_state.update(DEFAULT_STATE)
st.session_state['df_torneo'] = pd.DataFrame()


def notify(msg, tipo="info"):
icons = {"success": "✅", "error": "❌", "warning": "⚠️", "info": "ℹ️"}
st.toast(f"{icons.get(tipo,'ℹ️')} {msg}")


def df_hide_none(df):
return df.fillna("").replace("None", "")


# -------------------------
# MONGO DB
# -------------------------
@st.cache_resource
def init_mongo_connection(uri, db_name, collection_name):
try:
st.title("⚽ Torneo Superba - Gestione Gironi")

    st.markdown("""
        <style>
        ul, li { list-style-type: none !important; padding-left: 0 !important; margin-left: 0 !important; }
        .big-title { text-align: center; font-size: clamp(16px, 4vw, 36px); font-weight: bold; margin-top: 10px; margin-bottom: 20px; color: red; word-wrap: break-word; white-space: normal; }
        </style>
    """, unsafe_allow_html=True)

    df_master = carica_giocatori_da_db(players_collection)

    if players_collection is None and tournements_collection is None:
        st.error("❌ Impossibile avviare l'applicazione. La connessione a MongoDB non è disponibile.")
        return

    if st.session_state.get('calendario_generato', False):
        st.sidebar.subheader("Opzioni Torneo")
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
                    df_clean = df_filtrato_show.reset_index(drop=True).fillna("").replace("None", "")
                    st.dataframe(df_clean, use_container_width=True)
                   
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

                df_clean = df_hide_none(df_filtrato_show.reset_index(drop=True).fillna("").replace("None", ""))
                st.dataframe(df_clean, use_container_width=True)

                #st.dataframe(df_hide_none(df_filtrato_show.reset_index(drop=True)), use_container_width=True)
            else:
                st.info("🎉 Tutte le partite di questo girone sono state giocate.")

        st.markdown("---")
        if st.session_state['filtro_attivo'] == 'Nessuno':
            st.subheader("Navigazione Calendario")
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
            if st.button("💾 Salva Risultati Giornata"):
                salva_risultati_giornata(tournements_collection, st.session_state['girone_sel'], st.session_state['giornata_sel'])
                st.rerun()   # 👈 qui funziona perché sei fuori dal callback
            if st.button("🔢 Mostra Classifica Aggiornata"):
                st.markdown("---")
                st.subheader(f"Classifica {st.session_state['girone_sel']}")
                classifica = aggiorna_classifica(df)
                mostra_classifica_stilizzata(classifica, st.session_state['girone_sel'])

    else:
        st.subheader("📁 Carica un torneo o crea uno nuovo")
        col1, col2 = st.columns(2)
        with col1:
            tornei_disponibili = carica_tornei_da_db(tournements_collection)
            if tornei_disponibili:
                tornei_map = {t['nome_torneo']: str(t['_id']) for t in tornei_disponibili}
                nome_sel = st.selectbox("Seleziona torneo esistente:", list(tornei_map.keys()))
                if st.button("Carica Torneo Selezionato"):
                    st.session_state['tournement_id'] = tornei_map[nome_sel]
                    st.session_state['nome_torneo'] = nome_sel
                    torneo_data = carica_torneo_da_db(tournements_collection, st.session_state['tournement_id'])
                    if torneo_data and 'calendario' in torneo_data:
                        st.session_state['calendario_generato'] = True
                        st.toast("Torneo caricato con successo ✅")
                        st.rerun()
                    else:
                        st.error("❌ Errore durante il caricamento del torneo. Riprova.")
            else:
                st.info("Nessun torneo salvato trovato su MongoDB.")

        with col2:
            st.markdown("---")
            if st.button("➕ Crea Nuovo Torneo"):
                st.session_state['mostra_form_creazione'] = True
                st.rerun()

        if st.session_state.get('mostra_form_creazione', False):
            st.markdown("---")
            st.header("Dettagli Nuovo Torneo")
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
                st.warning(f"⚠️ Hai selezionato più giocatori ({len(amici_selezionati)}) del numero partecipanti ({st.session_state['n_giocatori']}). Riduci la selezione.")
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

            if st.button("Conferma Giocatori"):
                giocatori_scelti = amici_selezionati + [g for g in giocatori_supplementari if g]
                if len(set(giocatori_scelti)) < 4:
                    st.warning("⚠️ Inserisci almeno 4 giocatori diversi.")
                    return

                st.session_state['giocatori_selezionati_definitivi'] = list(set(giocatori_scelti))
                st.session_state['mostra_assegnazione_squadre'] = True
                st.session_state['mostra_gironi'] = False
                st.session_state['gironi_manuali_completi'] = False
                
                # Inizializzazione definitiva del dizionario gioc_info
                st.session_state['gioc_info'] = {}
                for gioc in st.session_state['giocatori_selezionati_definitivi']:
                    row = df_master[df_master['Giocatore'] == gioc].iloc[0] if gioc in df_master['Giocatore'].values else None
                    squadra_default = row['Squadra'] if row is not None and not pd.isna(row['Squadra']) else ""
                    potenziale_default = int(row['Potenziale']) if row is not None and not pd.isna(row['Potenziale']) else 4
                    st.session_state['gioc_info'][gioc] = {"Squadra": squadra_default, "Potenziale": potenziale_default}
                
                st.toast("Giocatori confermati ✅")
                st.rerun()

            if st.session_state.get('mostra_assegnazione_squadre', False):
                st.markdown("---")
                st.markdown("### ⚽ Modifica Squadra e Potenziale")
                
                for gioc in st.session_state['giocatori_selezionati_definitivi']:
                    squadra_nuova = st.text_input(f"Squadra per {gioc}", value=st.session_state['gioc_info'].get(gioc, {}).get('Squadra', ""), key=f"squadra_{gioc}")
                    potenziale_nuovo = st.slider(f"Potenziale per {gioc}", 1, 10, int(st.session_state['gioc_info'].get(gioc, {}).get('Potenziale', 4)), key=f"potenziale_{gioc}")

                    if gioc not in st.session_state['gioc_info']:
                        st.session_state['gioc_info'][gioc] = {}
                    st.session_state['gioc_info'][gioc]["Squadra"] = squadra_nuova
                    st.session_state['gioc_info'][gioc]["Potenziale"] = potenziale_nuovo

                if st.button("Conferma Squadre e Potenziali"):
                    st.session_state['mostra_gironi'] = True
                    st.toast("Squadre e potenziali confermati ✅")
                    st.rerun()

            if st.session_state.get('mostra_gironi', False):
                st.markdown("---")
                st.markdown("### ➡️ Modalità di creazione dei gironi")
                modalita_gironi = st.radio("Scegli come popolare i gironi", ["Popola Gironi Automaticamente", "Popola Gironi Manualmente"], key="modo_gironi_radio")

                if modalita_gironi == "Popola Gironi Manualmente":
                    st.warning("⚠️ ATTENZIONE: se hai modificato il numero di giocatori, assicurati che i gironi manuali siano coerenti prima di generare il calendario.")
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

                    if st.button("Valida e Assegna Gironi Manuali"):
                        tutti_i_giocatori_assegnati = sum(gironi_manuali.values(), [])
                        if sorted(tutti_i_giocatori_assegnati) == sorted(st.session_state['giocatori_selezionati_definitivi']):
                            st.session_state['gironi_manuali'] = gironi_manuali
                            st.session_state['gironi_manuali_completi'] = True
                            st.toast("Gironi manuali assegnati ✅")
                            st.rerun()
                        else:
                            st.error("❌ Assicurati di assegnare tutti i giocatori e che ogni giocatore sia in un solo girone.")

                if st.button("Genera Calendario"):
                    if modalita_gironi == "Popola Gironi Manualmente" and not st.session_state.get('gironi_manuali_completi', False):
                        st.error("❌ Per generare il calendario manualmente, clicca prima su 'Valida e Assegna Gironi Manuali'.")
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
                    tid = salva_torneo_su_db(tournements_collection, df_torneo, st.session_state['nome_torneo'])
                    if tid:
                        st.session_state['df_torneo'] = df_torneo
                        st.session_state['tournement_id'] = str(tid)
                        st.session_state['calendario_generato'] = True
                        st.toast("Calendario generato e salvato su MongoDB ✅")
                        st.rerun()

if __name__ == "__main__":
    main()
