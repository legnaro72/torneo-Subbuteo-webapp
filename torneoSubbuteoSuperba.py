import streamlit as st
import pandas as pd
import requests
from io import StringIO
import random
from fpdf import FPDF

st.set_page_config(page_title="🎲 Gestione Torneo a Gironi by Legnaro72", layout="wide")

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
        st.warning(f"Impossibile caricare lista giocatori dal CSV: {e}")
        return pd.DataFrame(columns=["Giocatore","Squadra","Potenziale"])

def genera_calendario(giocatori, num_gironi, tipo="Solo andata"):
    random.shuffle(giocatori)
    gironi = [[] for _ in range(num_gironi)]
    for i, nome in enumerate(giocatori):
        gironi[i % num_gironi].append(nome)

    partite = []
    for idx, girone in enumerate(gironi, 1):
        g = f"Girone {idx}"
        if len(girone) % 2 == 1:
            girone.append("Riposo")
        n = len(girone)
        half = n // 2
        teams = girone[:]
        for giornata in range(n - 1):
            for i in range(half):
                casa, ospite = teams[i], teams[-(i+1)]
                if casa != "Riposo" and ospite != "Riposo":
                    partite.append({"Tipo": "Partita", "Girone": g, "Giornata": giornata+1,
                                     "Casa": casa, "Ospite": ospite, "GolCasa": None, "GolOspite": None, "Valida": False})
                    if tipo == "Andata e ritorno":
                        partite.append({"Tipo": "Partita", "Girone": g, "Giornata": giornata+1 + (n - 1),
                                        "Casa": ospite, "Ospite": casa, "GolCasa": None, "GolOspite": None, "Valida": False})
            teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    return pd.DataFrame(partite)

def aggiorna_classifica(df):
    gironi = df['Girone'].dropna().unique() if 'Girone' in df.columns else []
    classifiche = []

    for girone in gironi:
        partite = df[(df['Girone'] == girone) & (df['Valida'] == True)]
        if partite.empty:
            continue
        squadre = pd.unique(partite[['Casa','Ospite']].values.ravel())
        stats = {s: {'Punti':0,'V':0,'P':0,'S':0,'GF':0,'GS':0,'DR':0} for s in squadre}

        for _, r in partite.iterrows():
            try:
                gc, go = int(r['GolCasa']), int(r['GolOspite'])
            except Exception:
                gc, go = 0,0
            casa, ospite = r['Casa'], r['Ospite']
            stats[casa]['GF'] += gc
            stats[casa]['GS'] += go
            stats[ospite]['GF'] += go
            stats[ospite]['GS'] += gc

            if gc > go:
                stats[casa]['Punti'] += 3; stats[casa]['V'] +=1; stats[ospite]['S'] +=1
            elif gc < go:
                stats[ospite]['Punti'] += 3; stats[ospite]['V'] +=1; stats[casa]['S'] +=1
            else:
                stats[casa]['Punti'] +=1; stats[ospite]['Punti'] +=1; stats[casa]['P'] +=1; stats[ospite]['P'] +=1

        for s in squadre:
            stats[s]['DR'] = stats[s]['GF'] - stats[s]['GS']

        df_stat = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index': 'Squadra'})
        df_stat['Girone'] = girone
        classifiche.append(df_stat)

    if not classifiche:
        colonne = ['Girone','Squadra','Punti','V','P','S','GF','GS','DR']
        return pd.DataFrame(columns=colonne)

    df_classifica = pd.concat(classifiche, ignore_index=True)

    for col in ['Girone','Punti','DR']:
        if col not in df_classifica.columns:
            df_classifica[col] = 0

    df_classifica = df_classifica.sort_values(by=['Girone','Punti','DR'], ascending=[True,False,False])
    return df_classifica

def modifica_risultati_compatti(df_giornata, key_prefix):
    for i, r in df_giornata.iterrows():
        with st.container():
            st.markdown(f"**{r['Casa']}** vs **{r['Ospite']}**")
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                gol_casa = st.number_input("Gol Casa", 0, 20, key=f"{key_prefix}_casa_{i}", value=int(r['GolCasa']) if pd.notna(r['GolCasa']) else 0)
            with col2:
                gol_ospite = st.number_input("Gol Ospite", 0, 20, key=f"{key_prefix}_ospite_{i}", value=int(r['GolOspite']) if pd.notna(r['GolOspite']) else 0)
            with col3:
                valida = st.checkbox("? Valida", key=f"{key_prefix}_valida_{i}", value=r['Valida'])
            df_giornata.at[i, 'GolCasa'] = gol_casa
            df_giornata.at[i, 'GolOspite'] = gol_ospite
            df_giornata.at[i, 'Valida'] = valida
    return df_giornata

def esporta_pdf(df_torneo, df_classifica):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Calendario e Classifiche Torneo", ln=True, align="C")

    gironi = df_torneo['Girone'].dropna().unique()

    for g in gironi:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, f"{g}", ln=True)

        giornate = sorted(df_torneo[df_torneo['Girone']==g]['Giornata'].dropna().unique())
        for giornata in giornate:
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(0, 7, f"Giornata {giornata}", ln=True)
            partite = df_torneo[(df_torneo['Girone']==g) & (df_torneo['Giornata']==giornata)]

            # Tabella partite
            pdf.set_font("Arial", '', 10)
            pdf.cell(60, 6, "Casa", 1)
            pdf.cell(60, 6, "Ospite", 1)
            pdf.cell(20, 6, "Gol Casa", 1)
            pdf.cell(20, 6, "Gol Ospite", 1)
            pdf.ln()
            for _, row in partite.iterrows():
                bgcolor = 255 if row['Valida'] else 220  # grigio chiaro se non valida
                pdf.set_fill_color(bgcolor, bgcolor, bgcolor)
                pdf.cell(60, 6, str(row['Casa']), 1, fill=True)
                pdf.cell(60, 6, str(row['Ospite']), 1, fill=True)
                pdf.cell(20, 6, str(row['GolCasa']) if pd.notna(row['GolCasa']) else "", 1, fill=True)
                pdf.cell(20, 6, str(row['GolOspite']) if pd.notna(row['GolOspite']) else "", 1, fill=True)
                pdf.ln()
            pdf.ln(4)

        # Classifica girone
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, f"Classifica {g}", ln=True)
        class_girone = df_classifica[df_classifica['Girone']==g].copy()
        if class_girone.empty:
            pdf.set_font("Arial", 'I', 10)
            pdf.cell(0, 6, "Nessuna partita valida", ln=True)
        else:
            pdf.set_font("Arial", '', 10)
            pdf.cell(50, 6, "Squadra", 1)
            pdf.cell(15, 6, "Punti", 1)
            pdf.cell(15, 6, "V", 1)
            pdf.cell(15, 6, "P", 1)
            pdf.cell(15, 6, "S", 1)
            pdf.cell(15, 6, "GF", 1)
            pdf.cell(15, 6, "GS", 1)
            pdf.cell(15, 6, "DR", 1)
            pdf.ln()
            for _, row in class_girone.iterrows():
                pdf.cell(50, 6, str(row['Squadra']), 1)
                pdf.cell(15, 6, str(row['Punti']), 1)
                pdf.cell(15, 6, str(row['V']), 1)
                pdf.cell(15, 6, str(row['P']), 1)
                pdf.cell(15, 6, str(row['S']), 1)
                pdf.cell(15, 6, str(row['GF']), 1)
                pdf.cell(15, 6, str(row['GS']), 1)
                pdf.cell(15, 6, str(row['DR']), 1)
                pdf.ln()
        pdf.ln(10)

    return pdf.output(dest='S').encode('latin1')  # PDF in bytes

def main():
    st.title("🎲 Gestione Torneo a Gironi by Legnaro72")

    df_master = carica_giocatori_master()

    scelta = st.sidebar.radio("⚙️ Azione:", ["Nuovo torneo", "Carica torneo da CSV"])

    if scelta == "Nuovo torneo":
        num_gironi = st.number_input("Numero di gironi", 1, 8, value=2)
        tipo_calendario = st.selectbox("Tipo calendario", ["Solo andata", "Andata e ritorno"])
        n_giocatori = st.number_input("Numero giocatori", 4, 32, value=8)

        st.markdown("### Amici del Club")
        amici = df_master['Giocatore'].tolist()
        all_seleziona = st.checkbox("Seleziona tutti gli amici", key="all_amici")

        if all_seleziona:
            amici_selezionati = st.multiselect("Seleziona amici", amici, default=amici)
        else:
            amici_selezionati = st.multiselect("Seleziona amici", amici)

        num_supplementari = n_giocatori - len(amici_selezionati)
        if num_supplementari < 0:
            st.warning(f"Hai selezionato più amici ({len(amici_selezionati)}) del numero partecipanti ({n_giocatori}). Riduci la selezione.")
            return

        st.markdown(f"Giocatori supplementari da inserire: **{num_supplementari}**")

        giocatori_supplementari = []
        for i in range(num_supplementari):
            use = st.checkbox(f"Aggiungi giocatore supplementare G{i+1}", key=f"supp_{i}_check")
            if use:
                nome = st.text_input(f"Nome giocatore supplementare G{i+1}", key=f"supp_{i}_nome")
                if nome.strip() == "":
                    st.warning(f"Inserisci un nome valido per G{i+1}")
                    return
                giocatori_supplementari.append(nome.strip())

        giocatori_scelti = amici_selezionati + giocatori_supplementari

        st.markdown(f"**Giocatori selezionati:** {', '.join(giocatori_scelti)}")

        if st.button("⚽ Assegna Squadre"):
            if len(set(giocatori_scelti)) < 4:
                st.warning("Inserisci almeno 4 giocatori diversi")
            else:
                st.session_state['giocatori_scelti'] = giocatori_scelti
                st.session_state['num_gironi'] = num_gironi
                st.session_state['tipo_calendario'] = tipo_calendario
                st.success("Giocatori selezionati, passa alla fase successiva.")

    if 'giocatori_scelti' in st.session_state and scelta == "Nuovo torneo":
        st.markdown("### Modifica Squadra e Potenziale per i giocatori")
        gioc_info = {}
        for gioc in st.session_state['giocatori_scelti']:
            if gioc in df_master['Giocatore'].values:
                row = df_master[df_master['Giocatore']==gioc].iloc[0]
                squadra_default = row['Squadra']
                potenziale_default = row['Potenziale']
            else:
                squadra_default = ""
                potenziale_default = 4
            squadra_nuova = st.text_input(f"Squadra per {gioc}", value=squadra_default, key=f"squadra_{gioc}")
            potenziale_nuovo = st.slider(f"Potenziale per {gioc}", 1, 10, potenziale_default, key=f"potenziale_{gioc}")
            gioc_info[gioc] = {"Squadra": squadra_nuova, "Potenziale": potenziale_nuovo}

        if st.button("📅 Conferma e genera calendario"):
            giocatori_formattati = []
            for gioc in st.session_state['giocatori_scelti']:
                squadra = gioc_info[gioc]['Squadra'].strip()
                if squadra == "":
                    st.warning(f"Scegli un nome squadra valido per il giocatore {gioc}")
                    return
                giocatori_formattati.append(f"{squadra} ({gioc})")

            df_torneo = genera_calendario(giocatori_formattati, st.session_state['num_gironi'], st.session_state['tipo_calendario'])
            st.session_state['df_torneo'] = df_torneo
            st.success("Calendario generato!")

    if 'df_torneo' in st.session_state:
        df = st.session_state['df_torneo']

        gironi = df['Girone'].dropna().unique() if 'Girone' in df.columns else []
        if len(gironi) == 0:
            st.warning("Non ci sono gironi nel torneo. Genera un calendario valido.")
            return

        girone_sel = st.selectbox("Seleziona girone", gironi)
        giornate = sorted(df[df['Girone']==girone_sel]['Giornata'].dropna().unique())
        giornata_sel = st.selectbox("Seleziona giornata", giornate)
        df_giornata = df[(df['Girone']==girone_sel) & (df['Giornata']==giornata_sel)].copy()
        if 'Valida' not in df_giornata.columns:
            df_giornata['Valida'] = False

        # Nuova UI con st.data_editor per modifica diretta in tabella
        df_edit = df_giornata[['Casa', 'Ospite', 'GolCasa', 'GolOspite', 'Valida']].copy()
        edited = st.data_editor(df_edit, num_rows="dynamic")

        # Aggiorna session_state con modifiche da tabella
        for idx, row in edited.iterrows():
            mask = (df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel) & (df['Casa'] == row['Casa']) & (df['Ospite'] == row['Ospite'])
            ind = df[mask].index
            if not ind.empty:
                i = ind[0]
                st.session_state['df_torneo'].at[i, 'GolCasa'] = row['GolCasa']
                st.session_state['df_torneo'].at[i, 'GolOspite'] = row['GolOspite']
                st.session_state['df_torneo'].at[i, 'Valida'] = row['Valida']

        classifica = aggiorna_classifica(st.session_state['df_torneo'])

        if classifica.empty or 'Girone' not in classifica.columns:
            st.warning("Classifica non disponibile: nessuna partita valida o dati insufficienti.")
        else:
            st.subheader(f"🏆 Classifica {girone_sel}")
            st.dataframe(classifica[classifica['Girone'] == girone_sel], use_container_width=True)

        csv = st.session_state['df_torneo'].to_csv(index=False)
        st.download_button("📥 Scarica CSV Torneo", csv, "torneo.csv", "text/csv")

        if st.button("📄 Esporta PDF calendario e classifiche"):
            pdf_data = esporta_pdf(st.session_state['df_torneo'], classifica)
            st.download_button("⬇️ Scarica PDF", data=pdf_data, file_name="calendario_classifiche.pdf", mime="application/pdf")

        # Mostra tutte le giornate per girone
        if st.button("📅 Mostra tutte le giornate per girone"):
            with st.expander(f"Tutte le giornate - {girone_sel}"):
                giornate = sorted(df[df['Girone'] == girone_sel]['Giornata'].dropna().unique())
                for g in giornate:
                    st.write(f"### Giornata {g}")
                    partite_g = df[(df['Girone']==girone_sel) & (df['Giornata']==g)][['Casa','Ospite','GolCasa','GolOspite','Valida']]
                    st.table(partite_g)

    if scelta == "Carica torneo da CSV":
        uploaded_file = st.file_uploader("Carica file CSV torneo", type=['csv'])
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
                st.session_state['df_torneo'] = df
                st.success("Torneo caricato correttamente!")
            except Exception as e:
                st.error(f"Errore nel caricamento CSV: {e}")

if __name__ == "__main__":
    main()
