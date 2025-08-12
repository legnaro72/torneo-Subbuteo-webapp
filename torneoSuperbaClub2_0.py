
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


def mostra_calendario_giornata(df, girone_sel, giornata_sel):
    st.subheader(f"Calendario {girone_sel} - Giornata {giornata_sel}")

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
    st.subheader(f"Classifica {girone_sel}")

    if df_classifica is None or df_classifica.empty:
        st.info("Nessuna partita validata: la classifica sarà disponibile dopo l'inserimento e validazione dei risultati.")
        return

    is_dark = st.get_option("theme.base") == "dark"

    def color_rows(row):
        if row.name == 0:
            return ['background-color: #155724; color: white'] * len(row) if is_dark else ['background-color: #d4edda; color: black'] * len(row)
        elif row.name <= 2:
            return ['background-color: #856404; color: white'] * len(row) if is_dark else ['background-color: #fff3cd; color: black'] * len(row)
        else:
            return ['color: white'] * len(row) if is_dark else [''] * len(row)

    df_girone = df_classifica[df_classifica['Girone'] == girone_sel].reset_index(drop=True)

    st.dataframe(df_girone.style.apply(color_rows, axis=1), use_container_width=True)


def distribuisci_giocatori_bilanciato(giocatori_info, num_gironi):
    sorted_gioc = sorted(giocatori_info, key=lambda x: x['potenziale'], reverse=True)
    gironi = [[] for _ in range(num_gironi)]
    idx = 0
    direzione = 1

    for gioc in sorted_gioc:
        if idx < 0 or idx >= num_gironi:
            raise IndexError(f"Indice girone fuori limite: {idx}, num_gironi={num_gironi}")
        gironi[idx].append(gioc)
        idx += direzione
        if idx >= num_gironi:
            idx = num_gironi - 2
            direzione = -1
        elif idx < 0:
            idx = 1
            direzione = 1
    return gironi





def main():
    # Inizializza session_state se non presente
    if "comp_gironi_confermata" not in st.session_state:
        st.session_state["comp_gironi_confermata"] = False
    if "calendario_generato" not in st.session_state:
        st.session_state["calendario_generato"] = False

    st.title("🏆⚽Gestione Torneo Superba a Gironi by Legnaro72🥇🥈🥉")

    df_master = carica_giocatori_master()

    scelta = st.sidebar.radio("Azione:", ["Nuovo torneo", "Carica torneo da CSV"])

    if scelta == "Nuovo torneo":
        from datetime import datetime

        mesi = {
            1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile",
            5: "Maggio", 6: "Giugno", 7: "Luglio", 8: "Agosto",
            9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre"
        }
        
        oggi = datetime.now()
        nome_default = f"TorneoSubbuteo_{oggi.day}{mesi[oggi.month]}{oggi.year}"
        nome_torneo = st.text_input("Nome del torneo:", value=nome_default)
        st.session_state["nome_torneo"] = nome_torneo

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
                giocatori_supplementari.append(nome)

        # Lista completa giocatori scelti
        giocatori_scelti = amici_selezionati + giocatori_supplementari
        st.session_state['giocatori_scelti'] = giocatori_scelti
        st.session_state['num_gironi'] = num_gironi
        st.session_state['tipo_calendario'] = tipo_calendario

        if len(giocatori_scelti) < num_gironi:
            st.warning("Il numero di giocatori è inferiore al numero di gironi.")
            return

        # Modifica squadra e potenziale per giocatori scelti
        st.markdown("### Modifica squadra e potenziale per ogni giocatore")
        gioc_info = []
        for gioc in giocatori_scelti:
            if gioc in df_master['Giocatore'].values:
                row = df_master[df_master['Giocatore'] == gioc].iloc[0]
                squadra_default = row['Squadra']
                potenziale_default = row['Potenziale']
            else:
                squadra_default = ""
                potenziale_default = 4
            squadra_nuova = st.text_input(f"Squadra per {gioc}", value=squadra_default, key=f"squadra_{gioc}")
            potenziale_nuovo = st.slider(f"Potenziale per {gioc}", 1, 10, potenziale_default, key=f"potenziale_{gioc}")
            gioc_info.append({"nome": gioc, "squadra": squadra_nuova, "potenziale": potenziale_nuovo})

        # Se la composizione non è ancora confermata, mostra proposta e modifica gironi
        if not st.session_state["comp_gironi_confermata"]:
            st.markdown("### Composizione automatica bilanciata dei gironi")

            if num_gironi > 1:
                gironi = distribuisci_giocatori_bilanciato(gioc_info, num_gironi)
            else:
                # se un solo girone, metto tutti i giocatori in un unico girone
                gironi = [gioc_info]

            composizione_modificata = {}
            for i, girone in enumerate(gironi, 1):
                st.markdown(f"**Girone {i}**")
                lista_girone = [f"{g['squadra']} ({g['nome']}) [Pot: {g['potenziale']}]" for g in girone]
                testo_modificabile = st.text_area(f"Modifica giocatori girone {i} (separa con virgola)", 
                                                 value=", ".join(lista_girone),
                                                 key=f"mod_girone_{i}")
                composizione_modificata[i] = [x.strip() for x in testo_modificabile.split(",") if x.strip() != ""]

            if st.button("Conferma composizione gironi"):
                st.session_state['gironi_composizione'] = composizione_modificata
                st.session_state["comp_gironi_confermata"] = True
                st.success("Composizione gironi confermata. Ora puoi generare il calendario.")

        else:
            if st.button("Genera Calendario"):
                giocatori_finali = []
                for i in range(1, num_gironi+1):
                    for g_str in st.session_state['gironi_composizione'][i]:
                        try:
                            squadra = g_str.split("(")[0].strip()
                            nome = g_str.split("(")[1].split(")")[0].strip()
                            if squadra == "" or nome == "":
                                st.warning(f"Errore nella composizione: verifica la stringa '{g_str}' nel girone {i}")
                                return
                            giocatori_finali.append(f"{squadra} ({nome})")
                        except Exception as e:
                            st.warning(f"Errore nel parsing della stringa '{g_str}': {e}")
                            return

                df_torneo = genera_calendario(giocatori_finali, num_gironi, tipo_calendario)
                st.session_state['df_torneo'] = df_torneo
                st.session_state["calendario_generato"] = True
                st.success("Calendario generato e salvato!")

    elif scelta == "Carica torneo da CSV":
        st.info("Funzione caricamento CSV da implementare")

    # Se calendario generato, mostra schermata torneo e classifica
    if st.session_state["calendario_generato"]:
        st.title(f"🏆⚽Gestione Torneo Superba a Gironi by Legnaro72🥇🥈🥉 - {st.session_state.get('nome_torneo','')}")

        df = st.session_state['df_torneo']
        gironi = sorted(df['Girone'].dropna().unique())
        girone_sel = st.selectbox("Seleziona Girone", gironi, index=0)
        giornate = sorted(df[df['Girone'] == girone_sel]['Giornata'].dropna().unique())
        giornata_sel = st.selectbox("Seleziona Giornata", giornate, index=0)

        mostra_calendario_giornata(df, girone_sel, giornata_sel)
        classifica = aggiorna_classifica(df)
        mostra_classifica_stilizzata(classifica, girone_sel)

        if st.button("Esporta calendario e classifica in PDF"):
            pdf_bytes = esporta_pdf(df, classifica)
            st.download_button("Scarica PDF", pdf_bytes, file_name="Calendario_Classifica.pdf", mime="application/pdf")

if __name__ == "__main__":
    main()
