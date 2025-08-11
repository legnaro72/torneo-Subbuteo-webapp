import streamlit as st
import pandas as pd
import requests
from io import StringIO, BytesIO
import random
from fpdf import FPDF

st.set_page_config(page_title="⚽️ Gestione Torneo a Gironi by Legnaro72", layout="wide")

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

def esporta_pdf(df_torneo, df_classifica):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "📅 Calendario e 🏆 Classifiche Torneo", ln=True, align='C')

    gironi = df_torneo['Girone'].dropna().unique()

    for girone in gironi:
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 8, f"⚽ Girone {girone}", ln=True)
        giornate = sorted(df_torneo[df_torneo['Girone']==girone]['Giornata'].dropna().unique())

        for g in giornate:
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 7, f"🗓 Giornata {g}", ln=True)
            partite = df_torneo[(df_torneo['Girone']==girone) & (df_torneo['Giornata']==g)]

            # Header tabella partite
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(65, 7, "🏠 Casa", border=1, align='C')
            pdf.cell(20, 7, "⚽ Gol", border=1, align='C')
            pdf.cell(20, 7, "⚽ Gol", border=1, align='C')
            pdf.cell(65, 7, "🏟 Ospite", border=1, align='C')
            pdf.ln()

            pdf.set_font("Arial", '', 11)
            for _, row in partite.iterrows():
                if not row['Valida']:
                    pdf.set_text_color(200, 50, 50)  # rosso per partite non validate
                else:
                    pdf.set_text_color(0, 0, 0)

                pdf.cell(65, 7, str(row['Casa']), border=1)
                pdf.cell(20, 7, str(row['GolCasa']) if pd.notna(row['GolCasa']) else "-", border=1, align='C')
                pdf.cell(20, 7, str(row['GolOspite']) if pd.notna(row['GolOspite']) else "-", border=1, align='C')
                pdf.cell(65, 7, str(row['Ospite']), border=1)
                pdf.ln()
            pdf.ln(5)

        # Classifica girone
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, f"🏅 Classifica Girone {girone}", ln=True)

        df_c = df_classifica[df_classifica['Girone'] == girone]

        # Header classifica
        pdf.set_font("Arial", 'B', 11)
        headers = ["Squadra", "Punti", "V", "P", "S", "GF", "GS", "DR"]
        col_widths = [65, 18, 15, 15, 15, 15, 15, 15]
        for i, h in enumerate(headers):
            pdf.cell(col_widths[i], 7, h, border=1, align='C')
        pdf.ln()

        pdf.set_font("Arial", '', 11)
        for _, r in df_c.iterrows():
            pdf.cell(col_widths[0], 7, str(r['Squadra']), border=1)
            pdf.cell(col_widths[1], 7, str(r['Punti']), border=1, align='C')
            pdf.cell(col_widths[2], 7, str(r['V']), border=1, align='C')
            pdf.cell(col_widths[3], 7, str(r['P']), border=1, align='C')
            pdf.cell(col_widths[4], 7, str(r['S']), border=1, align='C')
            pdf.cell(col_widths[5], 7, str(r['GF']), border=1, align='C')
            pdf.cell(col_widths[6], 7, str(r['GS']), border=1, align='C')
            pdf.cell(col_widths[7], 7, str(r['DR']), border=1, align='C')
            pdf.ln()
        pdf.ln(12)

    pdf_output = BytesIO()
    pdf.output(pdf_output)
    pdf_output.seek(0)
    return pdf_output.read()

def mostra_calendario_giornata(df, girone_sel, giornata_sel):
    st.subheader(f"⚽ Calendario Girone {girone_sel} - Giornata {giornata_sel}")

    df_giornata = df[(df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel)].copy()
    if 'Valida' not in df_giornata.columns:
        df_giornata['Valida'] = False

    edited_rows = []
    for idx, row in df_giornata.iterrows():
        casa = row['Casa']
        ospite = row['Ospite']
        val = row['Valida']
        col1, col2, col3, col4 = st.columns([4,1,1,1])

        with col1:
            st.markdown(f"**{casa}**  vs  **{ospite}**")

        with col2:
            gol_casa = st.number_input(f"Gol {casa}", min_value=0, max_value=20, value=int(row['GolCasa']) if pd.notna(row['GolCasa']) else 0, key=f"golcasa_{idx}")

        with col3:
            gol_ospite = st.number_input(f"Gol {ospite}", min_value=0, max_value=20, value=int(row['GolOspite']) if pd.notna(row['GolOspite']) else 0, key=f"golospite_{idx}")

        with col4:
            valida = st.checkbox("Valida", value=val, key=f"valida_{idx}")

        if not valida:
            st.markdown(f'<div style="color:red; margin-bottom: 15px;">Partita non ancora validata</div>', unsafe_allow_html=True)
        else:
            st.markdown("<hr>", unsafe_allow_html=True)

        edited_rows.append({
            "idx": idx,
            "GolCasa": gol_casa,
            "GolOspite": gol_ospite,
            "Valida": valida
        })

    for er in edited_rows:
        st.session_state['df_torneo'].at[er['idx'], 'GolCasa'] = er['GolCasa']
        st.session_state['df_torneo'].at[er['idx'], 'GolOspite'] = er['GolOspite']
        st.session_state['df_torneo'].at[er['idx'], 'Valida'] = er['Valida']

def mostra_classifica_stilizzata(df_classifica, girone_sel):
    st.subheader(f"🏅 Classifica Girone {girone_sel}")

    def color_rows(row):
        if row.name == 0:
            return ['background-color: #d4edda'] * len(row)  # verde chiaro per primo
        elif row.name <= 2:
            return ['background-color: #fff3cd'] * len(row)  # giallo chiaro per secondi e terzi
        else:
            return [''] * len(row)

    df_girone = df_classifica[df_classifica['Girone'] == girone_sel].reset_index(drop=True)

    st.dataframe(df_girone.style.apply(color_rows, axis=1), use_container_width=True)

def main():
    st.title("⚽️ Gestione Torneo a Gironi by Legnaro72")

    df_master = carica_giocatori_master()

    scelta = st.sidebar.radio("🎯 Azione:", ["Nuovo torneo", "Carica torneo da CSV"])

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
                row = df_master[df_master['Giocatore']==gioc].iloc[0]
                squadra_default = row['Squadra']
                potenziale_default = row['Potenziale']
            else:
                squadra_default = ""
                potenziale_default = 4
            squadra_nuova = st.text_input(f"Squadra per {gioc}", value=squadra_default, key=f"squadra_{gioc}")
            potenziale_nuovo = st.slider(f"Potenziale per {gioc}", 1, 10, potenziale_default, key=f"potenziale_{gioc}")
            gioc_info[gioc] = {"Squadra": squadra_nuova, "Potenziale": potenziale_nuovo}

        if st.button("⚽ Conferma e genera calendario"):
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

        mostra_calendario_giornata(df, girone_sel, giornata_sel)

        classifica = aggiorna_classifica(st.session_state['df_torneo'])
        if classifica.empty or 'Girone' not in classifica.columns:
            st.warning("Classifica non disponibile: nessuna partita valida o dati insufficienti.")
        else:
            mostra_classifica_stilizzata(classifica, girone_sel)

        csv = st.session_state['df_torneo'].to_csv(index=False)
        st.download_button("⬇️ Scarica calendario CSV", csv, file_name="calendario_torneo.csv", mime="text/csv")

        if st.button("📄 Esporta PDF calendario e classifiche"):
            pdf_bytes = esporta_pdf(st.session_state['df_torneo'], classifica)
            st.download_button("⬇️ Scarica PDF calendario", pdf_bytes, file_name="calendario_classifiche.pdf", mime="application/pdf")

    if scelta == "Carica torneo da CSV":
        uploaded_file = st.file_uploader("Carica il file CSV del torneo", type=["csv"])
        if uploaded_file:
            df_caricato = pd.read_csv(uploaded_file)
            st.session_state['df_torneo'] = df_caricato
            st.success("Torneo caricato! Ora puoi gestire i risultati.")

if __name__ == "__main__":
    if 'df_torneo' not in st.session_state:
        st.session_state['df_torneo'] = pd.DataFrame()
    main()
