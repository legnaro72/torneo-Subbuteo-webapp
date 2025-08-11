import streamlit as st
import pandas as pd
import requests
from io import StringIO
import random
from fpdf import FPDF

st.set_page_config(page_title="Gestione Torneo Superba a Gironi by Legnaro72", layout="wide")

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
        gr = girone[:]
        if len(gr) % 2 == 1:
            gr.append("Riposo")
        n = len(gr)
        half = n // 2

        teams = gr[:]
        for giornata in range(n - 1):
            for i in range(half):
                casa, ospite = teams[i], teams[-(i+1)]
                if casa != "Riposo" and ospite != "Riposo":
                    partite.append({"Girone": g, "Giornata": giornata+1,
                                    "Casa": casa, "Ospite": ospite, "GolCasa": None, "GolOspite": None, "Valida": False})
                    if tipo == "Andata e ritorno":
                        partite.append({"Girone": g, "Giornata": giornata+1 + (n - 1),
                                        "Casa": ospite, "Ospite": casa, "GolCasa": None, "GolOspite": None, "Valida": False})
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
        squadre = pd.unique(partite[['Casa','Ospite']].values.ravel())
        stats = {s: {'Punti':0,'V':0,'P':0,'S':0,'GF':0,'GS':0,'DR':0} for s in squadre}

        for _, r in partite.iterrows():
            try:
                gc, go = int(r['GolCasa']), int(r['GolOspite'])
            except:
                gc, go = 0, 0
            casa, ospite = r['Casa'], r['Ospite']
            stats[casa]['GF'] += gc
            stats[casa]['GS'] += go
            stats[ospite]['GF'] += go
            stats[ospite]['GS'] += gc

            if gc > go:
                stats[casa]['Punti'] += 3
                stats[casa]['V'] += 1
                stats[ospite]['S'] += 1
            elif gc < go:
                stats[ospite]['Punti'] += 3
                stats[ospite]['V'] += 1
                stats[casa]['S'] += 1
            else:
                stats[casa]['Punti'] += 1
                stats[ospite]['Punti'] += 1
                stats[casa]['P'] += 1
                stats[ospite]['P'] += 1

        for s in squadre:
            stats[s]['DR'] = stats[s]['GF'] - stats[s]['GS']

        df_stat = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index':'Squadra'})
        df_stat['Girone'] = girone
        classifiche.append(df_stat)

    if len(classifiche) == 0:
        return None

    df_classifica = pd.concat(classifiche, ignore_index=True)
    df_classifica = df_classifica.sort_values(by=['Girone','Punti','DR'], ascending=[True,False,False])
    return df_classifica

def esporta_pdf(df_torneo, df_classifica):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Calendario e Classifiche Torneo", ln=True, align='C')

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
            pdf.cell(60, 6, "Casa", border=1)
            pdf.cell(20, 6, "Gol", border=1, align='C')
            pdf.cell(20, 6, "Gol", border=1, align='C')
            pdf.cell(60, 6, "Ospite", border=1)
            pdf.ln()

            pdf.set_font("Arial", '', 11)
            partite = df_torneo[(df_torneo['Girone'] == girone) & (df_torneo['Giornata'] == g)]

            for _, row in partite.iterrows():
                if pdf.get_y() + line_height + margin_bottom > page_height:
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 7, f"Giornata {g} (continua)", ln=True)
                    pdf.set_font("Arial", 'B', 11)
                    pdf.cell(60, 6, "Casa", border=1)
                    pdf.cell(20, 6, "Gol", border=1, align='C')
                    pdf.cell(20, 6, "Gol", border=1, align='C')
                    pdf.cell(60, 6, "Ospite", border=1)
                    pdf.ln()
                    pdf.set_font("Arial", '', 11)

                pdf.set_text_color(255, 0, 0) if not row['Valida'] else pdf.set_text_color(0, 0, 0)

                pdf.cell(60, 6, str(row['Casa']), border=1)
                pdf.cell(20, 6, str(row['GolCasa']) if pd.notna(row['GolCasa']) else "-", border=1, align='C')
                pdf.cell(20, 6, str(row['GolOspite']) if pd.notna(row['GolOspite']) else "-", border=1, align='C')
                pdf.cell(60, 6, str(row['Ospite']), border=1)
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

def main():
    st.title("⚽ Gestione Torneo Superba a Gironi by Legnaro72")

    # Carica master giocatori
    df_master = carica_giocatori_master()

    scelta = st.sidebar.radio("Azione:", ["🆕 Nuovo torneo", "📂 Carica torneo da CSV"])

    if scelta == "🆕 Nuovo torneo":
        num_gironi = st.number_input("Numero di gironi", 1, 8, value=2)
        tipo_calendario = st.selectbox("Tipo calendario", ["Solo andata", "Andata e ritorno"])
        n_giocatori = st.number_input("Numero giocatori", 4, 32, value=8)

        st.markdown("### 👥 Amici del Club")
        amici = df_master['Giocatore'].tolist()
        all_seleziona = st.checkbox("Seleziona tutti gli amici", key="all_amici")

        if all_seleziona:
            amici_selezionati = st.multiselect("Seleziona amici", amici, default=amici)
        else:
            amici_selezionati = st.multiselect("Seleziona amici", amici)

        num_supplementari = n_giocatori - len(amici_selezionati)
        if num_supplementari < 0:
            st.warning(f"Hai selezionato più amici ({len(amici_selezionati)}) del numero partecipanti ({n_giocatori}).")
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

        if st.button("Genera calendario"):
            if len(set(giocatori_scelti)) < 4:
                st.warning("Inserisci almeno 4 giocatori diversi")
                return
            df_torneo = genera_calendario(giocatori_scelti, num_gironi, tipo=tipo_calendario)
            st.session_state['df_torneo'] = df_torneo
            st.session_state['num_gironi'] = num_gironi
            st.session_state['tipo_calendario'] = tipo_calendario
            st.success("Calendario generato!")

    if scelta == "📂 Carica torneo da CSV":
        uploaded_file = st.file_uploader("Carica CSV torneo", type=["csv"])
        if uploaded_file is not None:
            try:
                df_caricato = pd.read_csv(uploaded_file)
                expected_cols = ['Girone', 'Giornata', 'Casa', 'Ospite', 'GolCasa', 'GolOspite', 'Valida']
                if all(col in df_caricato.columns for col in expected_cols):
                    df_caricato['Valida'] = df_caricato['Valida'].astype(bool)
                    st.session_state['df_torneo'] = df_caricato
                    st.success("Torneo caricato correttamente!")
                else:
                    st.error(f"Il CSV non contiene tutte le colonne richieste: {expected_cols}")
            except Exception as e:
                st.error(f"Errore nel caricamento CSV: {e}")

    if 'df_torneo' in st.session_state:
        df_torneo = st.session_state['df_torneo']

        gironi = df_torneo['Girone'].dropna().unique()
        girone_sel = st.selectbox("Seleziona Girone", gironi)
        giornate = sorted(df_torneo[df_torneo['Girone'] == girone_sel]['Giornata'].dropna().unique())
        giornata_sel = st.selectbox("Seleziona Giornata", giornate)

        st.header(f"📅 Calendario - {girone_sel} - Giornata {giornata_sel}")
        df_giornata = df_torneo[(df_torneo['Girone'] == girone_sel) & (df_torneo['Giornata'] == giornata_sel)].copy()

        for idx, row in df_giornata.iterrows():
            cols = st.columns([4, 1, 1, 1])
            cols[0].write(f"**{row['Casa']}** vs **{row['Ospite']}**")
            gol_casa = cols[1].number_input(f"Gol {row['Casa']}", min_value=0, max_value=20, value=int(row['GolCasa']) if pd.notna(row['GolCasa']) else 0, key=f"golcasa_{idx}")
            gol_ospite = cols[2].number_input(f"Gol {row['Ospite']}", min_value=0, max_value=20, value=int(row['GolOspite']) if pd.notna(row['GolOspite']) else 0, key=f"golospite_{idx}")
            valida = cols[3].checkbox("Valida", value=row['Valida'], key=f"valida_{idx}")

            # Aggiorna session state
            st.session_state['df_torneo'].at[idx, 'GolCasa'] = gol_casa
            st.session_state['df_torneo'].at[idx, 'GolOspite'] = gol_ospite
            st.session_state['df_torneo'].at[idx, 'Valida'] = valida

        st.header(f"📊 Classifica - {girone_sel}")
        df_classifica = aggiorna_classifica(st.session_state['df_torneo'])
        if df_classifica is not None:
            df_girone = df_classifica[df_classifica['Girone'] == girone_sel].reset_index(drop=True)
            st.dataframe(df_girone.style.background_gradient(cmap='Blues', subset=['Punti']), use_container_width=True)
        else:
            st.info("Inserisci e valida i risultati per visualizzare la classifica.")

        if st.button("Esporta calendario e classifiche in PDF"):
            pdf_bytes = esporta_pdf(st.session_state['df_torneo'], df_classifica)
            st.download_button("Scarica PDF ⚽", data=pdf_bytes, file_name="calendario_classifica.pdf", mime="application/pdf")

if __name__ == "__main__":
    main()
