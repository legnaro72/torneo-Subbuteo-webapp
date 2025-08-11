import streamlit as st
import pandas as pd
import requests
from io import StringIO
import random
from fpdf import FPDF
import io

st.set_page_config(page_title="📅 Gestione Torneo a Gironi by Legnaro72", layout="wide")

# URL CSV giocatori
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
        return pd.DataFrame()  # nessuna partita valida

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
                valida = st.checkbox("✔️ Valida", key=f"{key_prefix}_valida_{i}", value=r['Valida'])
            df_giornata.at[i, 'GolCasa'] = gol_casa
            df_giornata.at[i, 'GolOspite'] = gol_ospite
            df_giornata.at[i, 'Valida'] = valida
    return df_giornata

def esporta_pdf(df_torneo, df_classifica):
    pdf = FPDF(format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)

    gironi = sorted(df_torneo['Girone'].unique())
    for girone in gironi:
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, f"Calendario {girone}", ln=True, align='C')
        pdf.ln(5)

        giornate = sorted(df_torneo[df_torneo['Girone'] == girone]['Giornata'].dropna().unique())
        for g in giornate:
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 10, f"Giornata {int(g)}", ln=True)
            pdf.set_font("Arial", '', 12)

            partite = df_torneo[(df_torneo['Girone'] == girone) & (df_torneo['Giornata'] == g)]
            # Header tabella
            pdf.set_fill_color(200, 200, 200)
            pdf.cell(50, 8, "Casa", border=1, fill=True)
            pdf.cell(50, 8, "Ospite", border=1, fill=True)
            pdf.cell(20, 8, "Gol Casa", border=1, fill=True, align='C')
            pdf.cell(20, 8, "Gol Ospite", border=1, fill=True, align='C')
            pdf.cell(20, 8, "Validata", border=1, fill=True, align='C')
            pdf.ln()

            for _, row in partite.iterrows():
                # Evidenzia partite non validate in rosso
                if not row['Valida']:
                    pdf.set_text_color(255, 0, 0)
                else:
                    pdf.set_text_color(0, 0, 0)

                pdf.cell(50, 8, str(row['Casa']), border=1)
                pdf.cell(50, 8, str(row['Ospite']), border=1)
                pdf.cell(20, 8, str(row['GolCasa']) if pd.notna(row['GolCasa']) else "-", border=1, align='C')
                pdf.cell(20, 8, str(row['GolOspite']) if pd.notna(row['GolOspite']) else "-", border=1, align='C')
                pdf.cell(20, 8, "Sì" if row['Valida'] else "No", border=1, align='C')
                pdf.ln()

            pdf.ln(5)

        # Classifica girone
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, f"Classifica {girone}", ln=True)
        pdf.set_font("Arial", 'B', 12)

        class_girone = df_classifica[df_classifica['Girone'] == girone].sort_values(['Punti','DR'], ascending=[False,False])
        headers = ['Squadra','Punti','V','P','S','GF','GS','DR']
        col_widths = [60, 15, 15, 15, 15, 15, 15, 15]

        for h, w in zip(headers, col_widths):
            pdf.cell(w, 8, h, border=1, align='C')
        pdf.ln()

        pdf.set_font("Arial", '', 12)
        for _, r in class_girone.iterrows():
            pdf.cell(col_widths[0], 8, str(r['Squadra']), border=1)
            pdf.cell(col_widths[1], 8, str(r['Punti']), border=1, align='C')
            pdf.cell(col_widths[2], 8, str(r['V']), border=1, align='C')
            pdf.cell(col_widths[3], 8, str(r['P']), border=1, align='C')
            pdf.cell(col_widths[4], 8, str(r['S']), border=1, align='C')
            pdf.cell(col_widths[5], 8, str(r['GF']), border=1, align='C')
            pdf.cell(col_widths[6], 8, str(r['GS']), border=1, align='C')
            pdf.cell(col_widths[7], 8, str(r['DR']), border=1, align='C')
            pdf.ln()

    pdf_output = io.BytesIO()
    pdf.output(pdf_output)
    pdf_output.seek(0)
    return pdf_output

def main():
    st.title("📅 Gestione Torneo a Gironi by Legnaro72")

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

        if st.button("🎲 Assegna Squadre"):
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
                row = df_master[df_master['Giocatore'] == gioc].iloc[0]
                squadra_default = row['Squadra']
                potenziale_default = row['Potenziale']
            else:
                squadra_default = ""
                potenziale_default = 4
            squadra_nuova = st.text_input(f"Squadra per {gioc}", value=squadra_default, key=f"squadra_{gioc}")
            potenziale_nuovo = st.slider(f"Potenziale per {gioc}", 1, 10, potenziale_default, key=f"potenziale_{gioc}")
            gioc_info[gioc] = {"Squadra": squadra_nuova, "Potenziale": potenziale_nuovo}

        if st.button("✅ Conferma e genera calendario"):
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
        giornate = sorted(df[df['Girone'] == girone_sel]['Giornata'].dropna().unique())
        giornata_sel = st.selectbox("Seleziona giornata", giornate)
        df_giornata = df[(df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel)].copy()
        if 'Valida' not in df_giornata.columns:
            df_giornata['Valida'] = False

        df_mod = modifica_risultati_compatti(df_giornata, key_prefix=f"{girone_sel}_{giornata_sel}")
        for i, row in df_mod.iterrows():
            idx = row.name
            st.session_state['df_torneo'].at[idx, 'GolCasa'] = row['GolCasa']
            st.session_state['df_torneo'].at[idx, 'GolOspite'] = row['GolOspite']
            st.session_state['df_torneo'].at[idx, 'Valida'] = row['Valida']

        classifica = aggiorna_classifica(st.session_state['df_torneo'])

        if classifica.empty or 'Girone' not in classifica.columns:
            st.warning("Classifica non disponibile: nessuna partita valida o dati insufficienti.")
        else:
            st.subheader(f"🏆 Classifica {girone_sel}")
            st.dataframe(classifica[classifica['Girone'] == girone_sel], use_container_width=True)

        csv = st.session_state['df_torneo'].to_csv(index=False)
        st.download_button("📥 Scarica CSV Torneo", csv, "torneo.csv", "text/csv")

        if st.button("📄 Mostra tutte le giornate per girone"):
            with st.expander(f"Tutte le giornate - {girone_sel}"):
                giornate = sorted(df[df['Girone'] == girone_sel]['Giornata'].dropna().unique())
                for g in giornate:
                    st.markdown(f"### Giornata {g}")
                    df_giornata = df[(df['Girone'] == girone_sel) & (df['Giornata'] == g)]
                    st.dataframe(df_giornata[['Casa','Ospite','GolCasa','GolOspite','Valida']], use_container_width=True)

        st.subheader("🔎 Filtra partite da validare per squadra")
        squadre = pd.unique(df[['Casa', 'Ospite']].values.ravel())
        squadra_scelta = st.selectbox("Seleziona squadra", squadre, key="filter_squadra")

        partite_da_validare = df[
            (df['Valida'] == False) &
            ((df['Casa'] == squadra_scelta) | (df['Ospite'] == squadra_scelta))
        ]

        st.dataframe(partite_da_validare[['Girone','Giornata','Casa','Ospite','GolCasa','GolOspite']], use_container_width=True)

        # --- NUOVO: bottone esporta PDF ---
        if st.button("📄 Esporta PDF Calendario + Classifiche"):
            classifica = aggiorna_classifica(st.session_state['df_torneo'])
            if classifica.empty:
                st.warning("Non ci sono partite valide per generare la classifica.")
            else:
                pdf_data = esporta_pdf(st.session_state['df_torneo'], classifica)
                st.download_button("⬇️ Scarica PDF", data=pdf_data, file_name="calendario_classifiche.pdf", mime="application/pdf")

    elif scelta == "Carica torneo da CSV":
        file = st.file_uploader("📂 Carica file CSV", type="csv")
        if file:
            try:
                df_torneo = pd.read_csv(file, encoding='latin1')
                st.session_state['df_torneo'] = df_torneo
                st.success("Torneo caricato!")
            except Exception as e:
                st.error(f"Errore caricamento CSV: {e}")

if __name__ == '__main__':
    main()
