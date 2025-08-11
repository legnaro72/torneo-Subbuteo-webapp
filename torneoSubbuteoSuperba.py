import streamlit as st
import pandas as pd
import requests
from io import StringIO
import random
from fpdf import FPDF

st.set_page_config(page_title="🎲 Gestione Torneo Superba a Gironi by Legnaro72", layout="wide")

URL_GIOCATORI = "https://raw.githubusercontent.com/legnaro72/torneoSvizzerobyLegna/refs/heads/main/giocatoriSuperba.csv"

def carica_giocatori_master(url=URL_GIOCATORI):
    try:
        r = requests.get(url)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.content.decode('latin1')))
        for c in ["Giocatore","Squadra","Potenziale"]:
            if c not in df.columns:
                df[c] = ""
        df["Potenziale"] = pd.to_numeric(df["Potenziale"], errors='coerce').fillna(4).astype(int)
        return df[["Giocatore","Squadra","Potenziale"]]
    except Exception as e:
        st.warning(f"⚠️ Impossibile caricare lista giocatori dal CSV: {e}")
        return pd.DataFrame(columns=["Giocatore","Squadra","Potenziale"])

# ... (tutto invariato fino a main)

def main():
    st.title("🎲 Gestione Torneo Superba a Gironi by Legnaro72")

    df_master = carica_giocatori_master()

    scelta = st.sidebar.radio("🔧 Azione:", ["Nuovo torneo", "Carica torneo da CSV"])

    if scelta == "Nuovo torneo":
        num_gironi = st.number_input("Numero di gironi", 1, 8, value=2)
        tipo_calendario = st.selectbox("Tipo calendario", ["Solo andata", "Andata e ritorno"])
        n_giocatori = st.number_input("Numero giocatori", 4, 32, value=8)

        st.markdown("### 👥 Amici del Club")
        amici = df_master['Giocatore'].tolist()
        all_seleziona = st.checkbox("✅ Seleziona tutti gli amici", key="all_amici")

        if all_seleziona:
            amici_selezionati = st.multiselect("Seleziona amici", amici, default=amici)
        else:
            amici_selezionati = st.multiselect("Seleziona amici", amici)

        num_supplementari = n_giocatori - len(amici_selezionati)
        if num_supplementari < 0:
            st.warning(f"⚠️ Hai selezionato più amici ({len(amici_selezionati)}) del numero partecipanti ({n_giocatori}). Riduci la selezione.")
            return

        st.markdown(f"Giocatori supplementari da inserire: **{num_supplementari}**")

        giocatori_supplementari = []
        for i in range(num_supplementari):
            use = st.checkbox(f"➕ Aggiungi giocatore supplementare G{i+1}", key=f"supp_{i}_check")
            if use:
                nome = st.text_input(f"📝 Nome giocatore supplementare G{i+1}", key=f"supp_{i}_nome")
                if nome.strip() == "":
                    st.warning(f"⚠️ Inserisci un nome valido per G{i+1}")
                    return
                giocatori_supplementari.append(nome.strip())

        giocatori_scelti = amici_selezionati + giocatori_supplementari

        st.markdown(f"**🧑‍🤝‍🧑 Giocatori selezionati:** {', '.join(giocatori_scelti)}")

        if st.button("⚽️ Assegna Squadre"):
            if len(set(giocatori_scelti)) < 4:
                st.warning("⚠️ Inserisci almeno 4 giocatori diversi")
            else:
                st.session_state['giocatori_scelti'] = giocatori_scelti
                st.session_state['num_gironi'] = num_gironi
                st.session_state['tipo_calendario'] = tipo_calendario
                st.success("✅ Giocatori selezionati, passa alla fase successiva.")

    if scelta == "Carica torneo da CSV":
        uploaded_file = st.file_uploader("📂 Carica CSV torneo", type=["csv"])
        if uploaded_file is not None:
            try:
                df_caricato = pd.read_csv(uploaded_file)
                expected_cols = ['Girone', 'Giornata', 'Casa', 'Ospite', 'GolCasa', 'GolOspite', 'Valida']
                if all(col in df_caricato.columns for col in expected_cols):
                    df_caricato['Valida'] = df_caricato['Valida'].astype(bool)
                    st.session_state['df_torneo'] = df_caricato
                    st.success("🎉 Torneo caricato correttamente!")
                else:
                    st.error(f"❌ Il CSV non contiene tutte le colonne richieste: {expected_cols}")
            except Exception as e:
                st.error(f"❌ Errore nel caricamento CSV: {e}")

    if 'giocatori_scelti' in st.session_state and scelta == "Nuovo torneo":
        st.markdown("### ✏️ Modifica Squadra e Potenziale per i giocatori")
        gioc_info = {}
        for gioc in st.session_state['giocatori_scelti']:
            if gioc in df_master['Giocatore'].values:
                row = df_master[df_master['Giocatore']==gioc].iloc[0]
                squadra_default = row['Squadra']
                potenziale_default = row['Potenziale']
            else:
                squadra_default = ""
                potenziale_default = 4
            squadra_nuova = st.text_input(f"🏷️ Squadra per {gioc}", value=squadra_default, key=f"squadra_{gioc}")
            potenziale_nuovo = st.slider(f"⚡ Potenziale per {gioc}", 1, 10, potenziale_default, key=f"potenziale_{gioc}")
            gioc_info[gioc] = {"Squadra": squadra_nuova, "Potenziale": potenziale_nuovo}

        if st.button("🎲 Conferma e genera calendario"):
            giocatori_formattati = []
            for gioc in st.session_state['giocatori_scelti']:
                squadra = gioc_info[gioc]['Squadra'].strip()
                if squadra == "":
                    st.warning(f"⚠️ Scegli un nome squadra valido per il giocatore {gioc}")
                    return
                giocatori_formattati.append(f"{squadra} ({gioc})")

            df_torneo = genera_calendario(giocatori_formattati, st.session_state['num_gironi'], st.session_state['tipo_calendario'])
            st.session_state['df_torneo'] = df_torneo
            st.success("✅ Calendario generato e salvato!")

    if 'df_torneo' in st.session_state:
        df = st.session_state['df_torneo']

        st.sidebar.markdown("---")
        gironi = sorted(df['Girone'].dropna().unique())
        girone_sel = st.sidebar.selectbox("🏅 Seleziona Girone", gironi)
        giornate = sorted(df[df['Girone'] == girone_sel]['Giornata'].dropna().unique())
        giornata_sel = st.sidebar.selectbox("📅 Seleziona Giornata", giornate)

        mostra_calendario_giornata(df, girone_sel, giornata_sel)

        classifica = aggiorna_classifica(st.session_state['df_torneo'])
        mostra_classifica_stilizzata(classifica, girone_sel)

        # --- FILTRI ---
        st.sidebar.markdown("---")
        st.sidebar.markdown("🔍 Filtri partite da giocare")

        if st.sidebar.button("🎯 Filtra Giocatore"):
            st.session_state["filtra_giocatore"] = True
        if st.sidebar.button("🏆 Filtra Girone"):
            st.session_state["filtra_girone"] = True

        if st.session_state.get("filtra_giocatore", False):
            giocatori = sorted(pd.unique(pd.concat([df['Casa'], df['Ospite']])))
            gioc_sel = st.sidebar.selectbox("👤 Seleziona giocatore", giocatori, key="sel_giocatore")

            filtro_tipo = "Entrambe"
            if st.session_state.get("tipo_calendario") == "Andata e ritorno":
                filtro_tipo = st.sidebar.radio("🛤️ Mostra partite", ["Andata", "Ritorno", "Entrambe"], index=2, key="tipo_giocatore")

            df_filtrato = df[
                ((df['Casa'] == gioc_sel) | (df['Ospite'] == gioc_sel)) &
                (df['Valida'] == False)
            ]

            if filtro_tipo != "Entrambe":
                n_giornate = df['Giornata'].max()
                if filtro_tipo == "Andata":
                    df_filtrato = df_filtrato[df_filtrato['Giornata'] <= n_giornate / 2]
                else:
                    df_filtrato = df_filtrato[df_filtrato['Giornata'] > n_giornate / 2]

            st.sidebar.dataframe(df_filtrato)

            if st.sidebar.button("❌ Chiudi filtro giocatore"):
                st.session_state["filtra_giocatore"] = False

        if st.session_state.get("filtra_girone", False):
            gironi = sorted(df['Girone'].unique())
            gir_sel = st.sidebar.selectbox("🏅 Seleziona girone", gironi, key="sel_girone")

            filtro_tipo_g = "Entrambe"
            if st.session_state.get("tipo_calendario") == "Andata e ritorno":
                filtro_tipo_g = st.sidebar.radio("🛤️ Mostra partite", ["Andata", "Ritorno", "Entrambe"], index=2, key="tipo_girone")

            df_girone = df[
                (df['Girone'] == gir_sel) &
                (df['Valida'] == False)
            ]

            if filtro_tipo_g != "Entrambe":
                n_giornate = df['Giornata'].max()
                if filtro_tipo_g == "Andata":
                    df_girone = df_girone[df_girone['Giornata'] <= n_giornate / 2]
                else:
                    df_girone = df_girone[df_girone['Giornata'] > n_giornate / 2]

            st.sidebar.dataframe(df_girone)

            if st.sidebar.button("❌ Chiudi filtro girone"):
                st.session_state["filtra_girone"] = False

        # --- ESPORTA CSV ---
        st.sidebar.markdown("---")
        csv_bytes = df.to_csv(index=False).encode('utf-8')
        st.sidebar.download_button("⬇️ Scarica CSV Torneo", data=csv_bytes, file_name="torneo_superba.csv", mime="text/csv")

        # --- ESPORTA PDF ---
        st.sidebar.markdown("---")
        if st.sidebar.button("📄 Esporta PDF Calendario + Classifica"):
            pdf_bytes = esporta_pdf(df, classifica)
            st.sidebar.download_button("📥 Download PDF calendario + classifica", data=pdf_bytes, file_name="torneo_superba.pdf", mime="application/pdf")

if __name__ == "__main__":
    main()
