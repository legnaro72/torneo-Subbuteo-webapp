import streamlit as st
import pandas as pd
import requests
from io import StringIO
import random
from fpdf import FPDF

st.set_page_config(page_title="Gestione Torneo Superba a Gironi by Legnaro72", layout="wide")

st.markdown("""
    <style>
    /* Rimuove i puntini neri */
    ul, li {
        list-style-type: none !important;
        padding-left: 0 !important;
        margin-left: 0 !important;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* Rimuove l'asterisco dai campi con etichetta nascosta */
div[data-testid="stNumberInput"] label::before {
    content: none;
}
</style>
""", unsafe_allow_html=True)


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
        return None  # <-- qui cambiato da DataFrame vuoto a None

    df_classifica = pd.concat(classifiche, ignore_index=True)
    df_classifica = df_classifica.sort_values(by=['Girone','Punti','DR'], ascending=[True,False,False])
    return df_classifica


def esporta_pdf(df_torneo, df_classifica):
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=False)  # controllo manuale
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Calendario e Classifiche Torneo", ln=True, align='C')

    line_height = 6
    margin_bottom = 15
    page_height = 297  # A4 height in mm

    gironi = df_torneo['Girone'].dropna().unique()

    for girone in gironi:
        pdf.set_font("Arial", 'B', 14)

        # Controllo spazio per titolo girone
        if pdf.get_y() + 8 + margin_bottom > page_height:
            pdf.add_page()
        pdf.cell(0, 8, f"{girone}", ln=True)

        giornate = sorted(df_torneo[df_torneo['Girone'] == girone]['Giornata'].dropna().unique())

        for g in giornate:
            # Spazio necessario: titolo giornata + intestazione tabella + almeno 1 riga + margine
            needed_space = 7 + line_height + line_height + margin_bottom
            if pdf.get_y() + needed_space > page_height:
                pdf.add_page()

            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 7, f"Giornata {g}", ln=True)

            # Intestazione tabella
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(60, 6, "Casa", border=1)
            pdf.cell(20, 6, "Gol", border=1, align='C')
            pdf.cell(20, 6, "Gol", border=1, align='C')
            pdf.cell(60, 6, "Ospite", border=1)
            pdf.ln()

            pdf.set_font("Arial", '', 11)
            partite = df_torneo[(df_torneo['Girone'] == girone) & (df_torneo['Giornata'] == g)]

            for _, row in partite.iterrows():
                # Controllo spazio per ogni riga
                if pdf.get_y() + line_height + margin_bottom > page_height:
                    pdf.add_page()
                    # Ripeto intestazione tabella in pagina nuova
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

        # Controllo spazio per classifica girone (circa 40mm + margine)
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
            # Controllo spazio per riga classifica
            if pdf.get_y() + line_height + margin_bottom > page_height:
                pdf.add_page()
                # Ripeto intestazione classifica
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
    #st.subheader(f"Calendario  {girone_sel} - Giornata {giornata_sel}")

    df_giornata = df[(df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel)].copy()
    if 'Valida' not in df_giornata.columns:
        df_giornata['Valida'] = False

    for idx, row in df_giornata.iterrows():
        casa = row['Casa']
        ospite = row['Ospite']
        val = row['Valida']

        col1, col2, col3, col4, col5 = st.columns([5, 1.5, 1, 1.5, 1])

        # Usa st.session_state solo per inizializzare
        if f"golcasa_{idx}" not in st.session_state:
            st.session_state[f"golcasa_{idx}"] = int(row['GolCasa']) if pd.notna(row['GolCasa']) else 0
        if f"golospite_{idx}" not in st.session_state:
            st.session_state[f"golospite_{idx}"] = int(row['GolOspite']) if pd.notna(row['GolOspite']) else 0
        if f"valida_{idx}" not in st.session_state:
            st.session_state[f"valida_{idx}"] = val

        with col1:
            st.markdown(f"**{casa}** vs **{ospite}**")

        with col2:
            st.number_input(
                "", min_value=0, max_value=20,
                key=f"golcasa_{idx}", 
                value=st.session_state[f"golcasa_{idx}"],
                label_visibility="hidden"
            )

        with col3:
            st.markdown("-")

        with col4:
            st.number_input(
                "", min_value=0, max_value=20,
                key=f"golospite_{idx}",
                value=st.session_state[f"golospite_{idx}"],
                label_visibility="hidden"
            )

        with col5:
            st.checkbox(
                "Valida",
                key=f"valida_{idx}",
                value=st.session_state[f"valida_{idx}"]
            )

        # Aggiorna il DataFrame direttamente dai valori dei widget
        df.at[idx, 'GolCasa'] = st.session_state[f"golcasa_{idx}"]
        df.at[idx, 'GolOspite'] = st.session_state[f"golospite_{idx}"]
        df.at[idx, 'Valida'] = st.session_state[f"valida_{idx}"]

        # Messaggi
        if not st.session_state[f"valida_{idx}"]:
            st.markdown('<div style="color:red; margin-bottom: 15px;">Partita non ancora validata</div>', unsafe_allow_html=True)
        else:
            st.markdown("<hr>", unsafe_allow_html=True)

    st.session_state['df_torneo'] = df


def mostra_classifica_stilizzata(df_classifica, girone_sel):
    st.subheader(f"Classifica Girone {girone_sel}")

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

def main():
    if "calendario_generato" not in st.session_state:
        st.session_state.calendario_generato = False
    
    # Mostra titolo solo se non ancora generato
    if not st.session_state.calendario_generato:
        st.title("🏆⚽Gestione Torneo Superba a Gironi by Legnaro72🥇🥈🥉")

    # Visualizza sempre il nome torneo se esiste in session_state
    if "nome_torneo" in st.session_state:
        st.markdown(
            f"""
            <style>
            .big-title {{
                text-align: center;
                font-size: clamp(16px, 4vw, 36px);
                font-weight: bold;
                margin-top: 10px;
                margin-bottom: 20px;
                color: red;
                word-wrap: break-word;   /* forza il wrapping */
                white-space: normal;     /* permette a Streamlit di andare a capo */
            }}
            </style>
            <div class="big-title">🏆{st.session_state["nome_torneo"]}🏆</div>
            """,
            unsafe_allow_html=True
        )


    # Visualizza sempre il nome torneo se esiste in session_state
    # if "nome_torneo" in st.session_state:
    #     st.markdown(
    #         f'<h2 style="color: red; text-align: center;">🏆{st.session_state["nome_torneo"]}🏆</h2>', 
    #         unsafe_allow_html=True
    #     )
        
    df_master = carica_giocatori_master()

    # Inizializza stato per mostra/nascondi form
    if 'mostra_form' not in st.session_state:
        st.session_state['mostra_form'] = True

    scelta = st.sidebar.radio("Azione:", ["Nuovo torneo", "Carica torneo da CSV"])

    if st.session_state['mostra_form']:
        # TUTTO il blocco NUOVO TORNEO + selezione giocatori + modifica squadra/potenziale
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
                    giocatori_supplementari.append(nome.strip())

            giocatori_scelti = amici_selezionati + giocatori_supplementari

            st.markdown(f"**Giocatori selezionati:** {', '.join(giocatori_scelti)}")

            if st.button("Assegna Squadre"):
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

            if st.button("Conferma e genera calendario"):
                giocatori_formattati = []
                for gioc in st.session_state['giocatori_scelti']:
                    squadra = gioc_info[gioc]['Squadra'].strip()
                    if squadra == "":
                        st.warning(f"Scegli un nome squadra valido per il giocatore {gioc}")
                        return
                    giocatori_formattati.append(f"{squadra} ({gioc})")

                df_torneo = genera_calendario(giocatori_formattati, st.session_state['num_gironi'], st.session_state['tipo_calendario'])
                st.session_state['df_torneo'] = df_torneo
                st.success("Calendario generato e salvato!")
                st.session_state.calendario_generato = True
                st.session_state['mostra_form'] = False
                st.rerun() 

    elif scelta == "Carica torneo da CSV":
        uploaded_file = st.file_uploader("Carica CSV torneo", type=["csv"])
        if uploaded_file is not None:
            try:
                df_caricato = pd.read_csv(uploaded_file)
                expected_cols = ['Girone', 'Giornata', 'Casa', 'Ospite', 'GolCasa', 'GolOspite', 'Valida']
                if all(col in df_caricato.columns for col in expected_cols):
                    df_caricato['Valida'] = df_caricato['Valida'].astype(bool)
                    st.session_state['df_torneo'] = df_caricato
                    st.success("Torneo caricato correttamente!")
                    # Nascondi form se carico torneo
                    st.session_state['mostra_form'] = False
                else:
                    st.error(f"Il CSV non contiene tutte le colonne richieste: {expected_cols}")
            except Exception as e:
                st.error(f"Errore nel caricamento CSV: {e}")

    # Se calendario generato o caricato E form nascosta, mostro calendario + classifica
    if 'df_torneo' in st.session_state and not st.session_state['mostra_form']:
        df = st.session_state['df_torneo']

        # --- Selettori inline nel corpo pagina (sotto il titolo torneo) ---
        gironi = sorted(df['Girone'].dropna().unique().tolist())
        
        # Persistenza selezioni
        if 'girone_sel' not in st.session_state:
            st.session_state['girone_sel'] = gironi[0]
        
        giornate_correnti = sorted(
            df[df['Girone'] == st.session_state['girone_sel']]['Giornata'].dropna().unique().tolist()
        )
        if 'giornata_sel' not in st.session_state:
            st.session_state['giornata_sel'] = giornate_correnti[0]
        
        # Titolo della sezione corrente
        st.subheader(f"Calendario {st.session_state['girone_sel']} - Giornata {st.session_state['giornata_sel']}")
        
        # --- Selettori Girone + Giornata con pulsanti + e - ---
        gironi = sorted(df['Girone'].dropna().unique().tolist())
        
        # Inizializza selezioni se non esistono
        if 'girone_sel' not in st.session_state:
            st.session_state['girone_sel'] = gironi[0]
        
        giornate_correnti = sorted(
            df[df['Girone'] == st.session_state['girone_sel']]['Giornata'].dropna().unique().tolist()
        )
        if 'giornata_sel' not in st.session_state or st.session_state['giornata_sel'] not in giornate_correnti:
            st.session_state['giornata_sel'] = giornate_correnti[0]
            
        # --- Stile compatto per mobile Seleziona Girone---
        
        # --- Stile compatto per mobile ---
        st.markdown("""
        <style>
        /* Riduce larghezza selectbox */
        div[data-baseweb="select"] {
            min-width: 60px !important;
            max-width: 90px !important;
            margin-top: 0px !important;
            margin-bottom: 0px !important;
        }
        
        /* Riduce padding dei bottoni */
        button[kind="secondary"] {
            padding: 0.2rem 0.4rem !important;
            min-width: 30px !important;
        }
        
        /* Riduce gap tra colonne */
        .css-1adrfps {
            gap: 0.2rem !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # --- Inizializza gironi e giornate ---
        gironi = sorted(df['Girone'].dropna().unique().tolist())
        if 'girone_sel' not in st.session_state:
            st.session_state['girone_sel'] = gironi[0]
        
        giornate_correnti = sorted(df[df['Girone'] == st.session_state['girone_sel']]['Giornata'].dropna().unique().tolist())
        if 'giornata_sel' not in st.session_state or st.session_state['giornata_sel'] not in giornate_correnti:
            st.session_state['giornata_sel'] = giornate_correnti[0]
        
        # --- Contenitore principale: Girone + Giornata sulla stessa riga ---
        col_gm, col_gsel, col_gp, col_jm, col_jsel, col_jp = st.columns([0.5, 1, 0.5, 0.5, 1, 0.5])
        
        # Freccia Girone -
        with col_gm:
            if st.button("◀️", key="girone_meno"):
                idx = gironi.index(st.session_state['girone_sel'])
                if idx > 0:
                    st.session_state['girone_sel'] = gironi[idx-1]
                    st.session_state['giornata_sel'] = None
                    st.rerun()
        
        # Selectbox Girone
        with col_gsel:
            nuovo_girone = st.selectbox(
                "Gir",
                gironi,
                index=gironi.index(st.session_state['girone_sel']),
                key="sel_girone_inline",
                label_visibility="collapsed"
            )
        
        # Freccia Girone +
        with col_gp:
            if st.button("▶️", key="girone_piu"):
                idx = gironi.index(st.session_state['girone_sel'])
                if idx < len(gironi)-1:
                    st.session_state['girone_sel'] = gironi[idx+1]
                    st.session_state['giornata_sel'] = None
                    st.rerun()
        
        # Aggiorna girone se cambiato tramite selectbox
        if nuovo_girone != st.session_state['girone_sel']:
            st.session_state['girone_sel'] = nuovo_girone
            st.session_state['giornata_sel'] = None
        
        # Aggiorna giornate correnti dopo cambio girone
        giornate_correnti = sorted(df[df['Girone'] == st.session_state['girone_sel']]['Giornata'].dropna().unique().tolist())
        if st.session_state['giornata_sel'] not in giornate_correnti:
            st.session_state['giornata_sel'] = giornate_correnti[0]
        
        # Freccia Giornata -
        with col_jm:
            if st.button("◀️", key="giornata_meno"):
                idx = giornate_correnti.index(st.session_state['giornata_sel'])
                if idx > 0:
                    st.session_state['giornata_sel'] = giornate_correnti[idx-1]
                    st.rerun()
        
        # Selectbox Giornata
        with col_jsel:
            nuova_giornata = st.selectbox(
                "Gio",
                giornate_correnti,
                index=giornate_correnti.index(st.session_state['giornata_sel']),
                key="sel_giornata_inline",
                label_visibility="collapsed"
            )
        
        # Freccia Giornata +
        with col_jp:
            if st.button("▶️", key="giornata_piu"):
                idx = giornate_correnti.index(st.session_state['giornata_sel'])
                if idx < len(giornate_correnti)-1:
                    st.session_state['giornata_sel'] = giornate_correnti[idx+1]
                    st.rerun()
        
        # Aggiorna giornata se cambiata tramite selectbox
        if nuova_giornata != st.session_state['giornata_sel']:
            st.session_state['giornata_sel'] = nuova_giornata

        
        # --- Titolo sezione corrente ---
        st.subheader(f"Calendario {st.session_state['girone_sel']} - Giornata {st.session_state['giornata_sel']}")
        
                
        girone_sel = st.session_state['girone_sel']
        giornata_sel = st.session_state['giornata_sel']


        mostra_calendario_giornata(df, girone_sel, giornata_sel)

        classifica = aggiorna_classifica(st.session_state['df_torneo'])
        mostra_classifica_stilizzata(classifica, girone_sel)

        # Pulsante per tornare indietro e modificare la selezione
        if st.button("🔙 Torna indietro e modifica giocatori"):
            st.session_state['mostra_form'] = True

        # --- FILTRI ---
        st.sidebar.markdown("---")
        st.sidebar.markdown("### Filtri partite da giocare")

        if st.sidebar.button("🎯 Filtra Giocatore"):
            st.session_state["filtra_giocatore"] = True
        if st.sidebar.button("🏆 Filtra Girone"):
            st.session_state["filtra_girone"] = True

        if st.session_state.get("filtra_giocatore", False):
            giocatori = sorted(pd.unique(pd.concat([df['Casa'], df['Ospite']])))
            gioc_sel = st.sidebar.selectbox("Seleziona giocatore", giocatori, key="sel_giocatore")
        
            filtro_tipo = "Entrambe"
            if st.session_state.get("tipo_calendario") == "Andata e ritorno":
                filtro_tipo = st.sidebar.radio("Mostra partite", ["Andata", "Ritorno", "Entrambe"], index=2, key="tipo_giocatore")
        
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
        
            # --- SOLO INFO MINIMALI ---
            if not df_filtrato.empty:
                df_min = pd.DataFrame({
                    "Giornata": df_filtrato["Giornata"],
                    "Partita": df_filtrato["Casa"] + " vs " + df_filtrato["Ospite"]
                }).sort_values("Giornata").reset_index(drop=True)  # <-- elimina colonna indice
                st.sidebar.dataframe(df_min, use_container_width=True, hide_index=True)


            else:
                st.sidebar.info("Nessuna partita da giocare.")
        
            if st.sidebar.button("Chiudi filtro giocatore"):
                st.session_state["filtra_giocatore"] = False


        if st.session_state.get("filtra_girone", False):
            gironi = sorted(df['Girone'].unique())
            gir_sel = st.sidebar.selectbox("Seleziona girone", gironi, key="sel_girone")
        
            filtro_tipo_g = "Entrambe"
            if st.session_state.get("tipo_calendario") == "Andata e ritorno":
                filtro_tipo_g = st.sidebar.radio("Mostra partite", ["Andata", "Ritorno", "Entrambe"], index=2, key="tipo_girone")
        
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
        
            # --- SOLO INFO MINIMALI ---
            if not df_girone.empty:
                df_min_g = pd.DataFrame({
                    "Giornata": df_girone["Giornata"],
                    "Partita": df_girone["Casa"] + " vs " + df_girone["Ospite"]
                }).sort_values("Giornata").reset_index(drop=True)  # <-- elimina colonna indice
                st.sidebar.dataframe(df_min_g, use_container_width=True, hide_index=True)

            else:
                st.sidebar.info("Nessuna partita da giocare.")
        
            if st.sidebar.button("Chiudi filtro girone"):
                st.session_state["filtra_girone"] = False

        # --- ESPORTA CSV ---
        st.sidebar.markdown("---")
        nome_torneo = st.session_state.get("nome_torneo", "torneo.csv")
        csv_bytes = df.to_csv(index=False).encode('utf-8')
        st.sidebar.download_button("⬇️ Scarica CSV Torneo", data=csv_bytes, file_name=nome_torneo, mime="text/csv")

        # --- ESPORTA PDF ---
        st.sidebar.markdown("---")
        if st.sidebar.button("📄 Esporta PDF Calendario + Classifica"):
            pdf_bytes = esporta_pdf(df, classifica)
            st.sidebar.download_button("Download PDF calendario + classifica", data=pdf_bytes, file_name=nome_torneo, mime="application/pdf")


if __name__ == "__main__":
    main()
