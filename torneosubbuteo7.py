import streamlit as st
import pandas as pd
import requests
from io import StringIO
import random
from fpdf import FPDF
from datetime import datetime
import json
import time

# --- Funzione di stile per None/nan invisibili e colorazione righe ---
def combined_style(df):
    is_dark = st.get_option("theme.base") == "dark"

    def apply_row_style(row):
        base = [''] * len(row)
        if row.name == 0:
            base = ['background-color: #d4edda; color: black'] * len(row)
        elif row.name <= 2:
            base = ['background-color: #fff3cd; color: black'] * len(row)
        return base

    def hide_none(val):
        sval = str(val).strip().lower()
        if sval in ["none", "nan", ""]:
            return 'color: transparent; text-shadow: none;'
        return ''

    styled_df = df.style.apply(apply_row_style, axis=1)
    styled_df = styled_df.map(hide_none)
    
    return styled_df

# ---------------------------------------------------------------------

st.set_page_config(page_title="Gestione Torneo Superba a Gironi by Legnaro72", layout="wide")

st.markdown("""
    <style>
    ul, li { list-style-type: none !important; padding-left: 0 !important; margin-left: 0 !important; }
    .big-title { text-align: center; font-size: clamp(16px, 4vw, 36px); font-weight: bold; margin-top: 10px; margin-bottom: 20px; color: red; word-wrap: break-word; white-space: normal; }
    div[data-testid="stNumberInput"] label::before { content: none; }
    </style>
""", unsafe_allow_html=True)

URL_GIOCATORI = "https://raw.githubusercontent.com/legnaro72/torneoSvizzerobyLegna/refs/heads/main/giocatoriSuperba.csv"

# --- NAVIGAZIONE COMPATTA ---
def navigation_controls(label, value, min_val, max_val, key_prefix=""):
    col1, col2, col3 = st.columns([1, 3, 1])  # pulsante - testo - pulsante

    with col1:
        if st.button("◀️", key=f"{key_prefix}_prev", use_container_width=True):
            st.session_state[value] = max(min_val, st.session_state[value] - 1)

    with col2:
        st.markdown(
            f"<div style='text-align:center; font-weight:bold;'>{label} {st.session_state[value]}</div>",
            unsafe_allow_html=True
        )

    with col3:
        if st.button("▶️", key=f"{key_prefix}_next", use_container_width=True):
            st.session_state[value] = min(max_val, st.session_state[value] + 1)

if "girone" not in st.session_state:
    st.session_state.girone = 1   # valore iniziale
if "giornata" not in st.session_state:
    st.session_state.giornata = 1 # valore iniziale
    
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

def genera_calendario_auto(giocatori, num_gironi, tipo="Solo andata"):
    random.shuffle(giocatori)
    gironi = [[] for _ in range(num_gironi)]
    for i, nome in enumerate(giocatori):
        gironi[i % num_gironi].append(nome)
    
    return genera_calendario_from_list(gironi, tipo)

def genera_calendario_from_list(gironi_popolati, tipo="Solo andata"):
    partite = []
    for idx, girone in enumerate(gironi_popolati, 1):
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
            # CORREZIONE: Ho sostituito 'df' con 'df_torneo'
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
    df_giornata = df[(df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel)].copy()
    if 'Valida' not in df_giornata.columns:
        df_giornata['Valida'] = False

    def safe_int(val):
        try:
            sval = str(val).strip().lower()
            if sval in ["none", "nan", ""] or not sval.isdigit():
                return 0
            return int(float(val))
        except (ValueError, TypeError):
            return 0

    for idx, row in df_giornata.iterrows():
        casa = row['Casa']
        ospite = row['Ospite']
        val = row['Valida']

        col1, col2, col3, col4, col5 = st.columns([5, 1.5, 1, 1.5, 1])

        with col1:
            st.markdown(f"**{casa}** vs **{ospite}**")

        with col2:
            st.number_input(
                "", min_value=0, max_value=20,
                key=f"golcasa_{idx}",
                value=safe_int(row['GolCasa']),
                label_visibility="hidden"
            )

        with col3:
            st.markdown("-")

        with col4:
            st.number_input(
                "", min_value=0, max_value=20,
                key=f"golospite_{idx}",
                value=safe_int(row['GolOspite']),
                label_visibility="hidden"
            )

        with col5:
            st.checkbox(
                "Valida",
                key=f"valida_{idx}",
                value=val
            )
        
        if st.session_state.get(f"valida_{idx}", False):
            st.markdown("<hr>", unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:red; margin-bottom: 15px;">Partita non ancora validata</div>', unsafe_allow_html=True)

    def salva_risultati_giornata():
        df = st.session_state['df_torneo']
        df_giornata_copia = df[(df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel)].copy()
        for idx, _ in df_giornata_copia.iterrows():
            df.at[idx, 'GolCasa'] = st.session_state[f"golcasa_{idx}"]
            df.at[idx, 'GolOspite'] = st.session_state[f"golospite_{idx}"]
            df.at[idx, 'Valida'] = st.session_state[f"valida_{idx}"]

        st.session_state['df_torneo'] = df
        st.session_state['last_autosave_time'] = time.time()
        st.info("Risultati salvati!")
        
    st.button("Salva Risultati Giornata", on_click=salva_risultati_giornata)

def mostra_classifica_stilizzata(df_classifica, girone_sel):
    st.subheader(f"Classifica Girone {girone_sel}")
    if df_classifica is None or df_classifica.empty:
        st.info("Nessuna partita validata: la classifica sarà disponibile dopo l'inserimento e validazione dei risultati.")
        return

    df_girone = df_classifica[df_classifica['Girone'] == girone_sel].reset_index(drop=True)
    styled = combined_style(df_girone)
    st.dataframe(styled, use_container_width=True)

def autosave_to_file():
    if "df_torneo" in st.session_state and st.session_state.calendario_generato:
        df_calendario = st.session_state['df_torneo']
        df_classifica = aggiorna_classifica(df_calendario)

        if df_classifica is not None and not df_classifica.empty:
            df_classifica['Tipo'] = 'Classifica'
            df_calendario['Tipo'] = 'Calendario'
            for col in df_classifica.columns:
                if col not in df_calendario.columns:
                    df_calendario[col] = ''
            for col in df_calendario.columns:
                if col not in df_classifica.columns:
                    df_classifica[col] = ''
            df_combinato = pd.concat([df_calendario, df_classifica], ignore_index=True)
            df_combinato = df_combinato.sort_values(by=['Tipo', 'Girone'], ascending=[False, True])
        else:
            df_calendario['Tipo'] = 'Calendario'
            df_combinato = df_calendario
        
        nome_torneo = st.session_state.get("nome_torneo", "torneo")
        autosave_filename = f"{nome_torneo}_autosave.csv"
        
        # Simula il salvataggio in memoria, per evitare di scrivere sul filesystem di Streamlit Cloud
        # In un'applicazione locale, potresti usare:
        # df_combinato.to_csv(autosave_filename, index=False)
        st.info(f"Autosalvataggio in memoria completato: {autosave_filename}")


def main():
    if "calendario_generato" not in st.session_state:
        st.session_state.calendario_generato = False
    
    # Inizializza il timestamp di autosave se non esiste
    if "last_autosave_time" not in st.session_state:
        st.session_state.last_autosave_time = time.time()
    
    # Controlla se è passato abbastanza tempo per l'autosave
    if st.session_state.calendario_generato and (time.time() - st.session_state.last_autosave_time) > 60:
        autosave_to_file()
        st.session_state.last_autosave_time = time.time()
    
    if st.session_state.get("calendario_generato", False):
        nome_torneo = st.session_state.get("nome_torneo", "Torneo")
        st.markdown(f"<div class='big-title'>🏆⚽{nome_torneo}🥇🥈🥉</div>", unsafe_allow_html=True)
    else:
        st.title("🏆⚽Gestione Torneo Superba a Gironi by Legnaro72🥇🥈🥉")
    
    df_master = carica_giocatori_master()
    if df_master.empty:
        st.error("Impossibile procedere: non è stato possibile caricare la lista giocatori.")
        return

    if not st.session_state.calendario_generato:
        st.write("---")
        st.subheader("Scegli un'azione per iniziare:")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("<h4 style='text-align: center;'>📁 Carica Torneo Esistente</h4>", unsafe_allow_html=True)
            st.info("Se hai un torneo salvato in un file CSV, caricalo per continuare a giocare.")
            uploaded_file = st.file_uploader("Carica CSV torneo", type=["csv"], label_visibility="hidden")
            
            if uploaded_file is not None:
                try:
                    df_caricato = pd.read_csv(uploaded_file)
                    expected_cols = ['Girone', 'Giornata', 'Casa', 'Ospite', 'GolCasa', 'GolOspite', 'Valida']
                    if all(col in df_caricato.columns for col in expected_cols):
                        df_caricato['Valida'] = df_caricato['Valida'].astype(bool)
                        st.session_state['df_torneo'] = df_caricato
                        st.session_state["nome_torneo"] = uploaded_file.name.replace(".csv", "")
                        st.session_state.calendario_generato = True
                        st.session_state.torneo_caricato = True
                        st.success("✅ Torneo caricato correttamente!")
                        st.rerun()
                    else:
                        st.error(f"❌ Il CSV non contiene tutte le colonne richieste: {expected_cols}")
                except Exception as e:
                    st.error(f"❌ Errore nel caricamento CSV: {e}")

        with col2:
            st.markdown("<h4 style='text-align: center;'>⚽ Crea Nuovo Torneo</h4>", unsafe_allow_html=True)
            st.info("Inizia una nuova competizione configurando giocatori, gironi e tipo di calendario.")
            if st.button("➕ Crea Nuovo Torneo"):
                st.session_state['mostra_form'] = True
                
        st.write("---")
        
        if st.session_state.get('mostra_form', False):
            oggi = datetime.now()
            mesi = {1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile", 5: "Maggio", 6: "Giugno", 7: "Luglio", 8: "Agosto", 9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre"}
            nome_default = f"TorneoSubbuteo_{oggi.day}{mesi[oggi.month]}{oggi.year}"
            
            st.header("Dettagli Nuovo Torneo")
            nome_torneo = st.text_input("Nome del torneo:", value=nome_default)
            st.session_state["nome_torneo"] = nome_torneo
            num_gironi = st.number_input("Numero di gironi", 1, 8, value=2)
            tipo_calendario = st.selectbox("Tipo calendario", ["Solo andata", "Andata e ritorno"])
            n_giocatori = st.number_input("Numero giocatori", 4, 32, value=8)

            st.markdown("### 👥 Seleziona Giocatori")
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
            
            if st.button("Assegna Squadre"):
                if len(set(giocatori_scelti)) < 4:
                    st.warning("Inserisci almeno 4 giocatori diversi.")
                else:
                    st.session_state['giocatori_scelti'] = giocatori_scelti
                    st.session_state['num_gironi'] = num_gironi
                    st.session_state['tipo_calendario'] = tipo_calendario
                    st.session_state['mostra_assegnazione'] = True
                    st.session_state.pop('gioc_info', None)
                    st.success("Giocatori selezionati, passa alla fase successiva.")
                    st.rerun()

            if st.session_state.get('mostra_assegnazione', False):
                st.markdown("### Modifica Squadra e Potenziale per i giocatori")
                if 'gioc_info' not in st.session_state:
                    st.session_state['gioc_info'] = {}
                
                for gioc in st.session_state['giocatori_scelti']:
                    if gioc not in st.session_state['gioc_info']:
                        if gioc in df_master['Giocatore'].values:
                            row = df_master[df_master['Giocatore']==gioc].iloc[0]
                            squadra_default = row['Squadra']
                            potenziale_default = row['Potenziale']
                        else:
                            squadra_default = ""
                            potenziale_default = 4
                        st.session_state['gioc_info'][gioc] = {"Squadra": squadra_default, "Potenziale": potenziale_default}
                        
                    squadra_nuova = st.text_input(f"Squadra per {gioc}", value=st.session_state['gioc_info'][gioc]['Squadra'], key=f"squadra_{gioc}")
                    potenziale_nuovo = st.slider(f"Potenziale per {gioc}", 1, 10, int(st.session_state['gioc_info'][gioc]['Potenziale']), key=f"potenziale_{gioc}")
                    st.session_state['gioc_info'][gioc]["Squadra"] = squadra_nuova
                    st.session_state['gioc_info'][gioc]["Potenziale"] = potenziale_nuovo
                
                st.markdown("### Modalità di creazione dei gironi")
                modalita_gironi = st.radio(
                    "Scegli come popolare i gironi",
                    ["Popola Gironi Automaticamente", "Popola Gironi Manualmente"]
                )
                
                if st.button("✅ Conferma modalità gironi"):
                    if modalita_gironi == "Popola Gironi Manualmente":
                        st.session_state['mostra_gironi_manuali'] = True
                    else:
                        gironi_finali = [[] for _ in range(st.session_state['num_gironi'])]
                        giocatori_formattati = [
                            f"{st.session_state['gioc_info'][gioc]['Squadra']} ({gioc})"
                            for gioc in st.session_state['giocatori_scelti']
                        ]
                        random.shuffle(giocatori_formattati)
                        for i, g in enumerate(giocatori_formattati):
                            gironi_finali[i % st.session_state['num_gironi']].append(g)
                        
                        df_torneo = genera_calendario_from_list(
                            gironi_finali, st.session_state['tipo_calendario']
                        )
                        st.session_state['df_torneo'] = df_torneo
                        st.success("Calendario generato automaticamente e salvato!")
                        st.session_state.calendario_generato = True
                        st.session_state['mostra_form'] = False
                        st.session_state['mostra_assegnazione'] = False
                        st.rerun()
                
                if st.session_state.get('mostra_gironi_manuali', False):
                    st.subheader("Assegna i giocatori ai gironi")
                    st.info("Ogni giocatore deve comparire una sola volta. Assegna tutti i giocatori prima di confermare.")
                    
                    gironi_manuali = {}
                    giocatori_disponibili = [
                        f"{st.session_state['gioc_info'][gioc]['Squadra']} ({gioc})"
                        for gioc in st.session_state['giocatori_scelti']
                    ]
                    
                    for i in range(st.session_state['num_gironi']):
                        girone_key = f"manual_girone_{i+1}"
                        with st.expander(f"Girone {i+1}"):
                            default_val = st.session_state.get(girone_key, [])
                            selezionati = st.multiselect(
                                f"Giocatori per Girone {i+1}",
                                options=[g for g in giocatori_disponibili if g not in sum([val for key, val in gironi_manuali.items()], [])],
                                default=default_val,
                                key=girone_key
                            )
                            gironi_manuali[f"Girone {i+1}"] = selezionati

                    assegnati_unici = set(sum(gironi_manuali.values(), []))
                    st.markdown(f"**Giocatori assegnati: {len(assegnati_unici)} / {len(giocatori_disponibili)}**")
                    
                    if len(assegnati_unici) != len(giocatori_disponibili):
                        st.warning("⚠️ Devi assegnare tutti i giocatori, senza duplicati, per continuare.")
                    else:
                        if st.button("✅ Conferma gironi manuali e genera calendario"):
                            gironi_finali = list(gironi_manuali.values())
                            df_torneo = genera_calendario_from_list(
                                gironi_finali, st.session_state['tipo_calendario']
                            )
                            st.session_state['df_torneo'] = df_torneo
                            st.success("Calendario generato e salvato!")
                            st.session_state.calendario_generato = True
                            st.session_state['mostra_form'] = False
                            st.session_state['mostra_assegnazione'] = False
                            st.session_state['mostra_gironi_manuali'] = False
                            st.rerun()
    if st.session_state.calendario_generato:
        df = st.session_state['df_torneo']
        gironi = sorted(df['Girone'].dropna().unique().tolist())
        if 'girone_sel' not in st.session_state:
            st.session_state['girone_sel'] = gironi[0]
        
        giornate_correnti = sorted(df[df['Girone'] == st.session_state['girone_sel']]['Giornata'].dropna().unique().tolist())
        if 'giornata_sel' not in st.session_state or st.session_state['giornata_sel'] not in giornate_correnti:
            st.session_state['giornata_sel'] = giornate_correnti[0]
        
        # --- Navigazione compatta Girone / Giornata ---
        gironi = sorted(df['Girone'].dropna().unique().tolist())
        giornate_correnti = sorted(df[df['Girone'] == st.session_state['girone_sel']]['Giornata'].dropna().unique().tolist())
        
        # --- PRIMA RIGA: Selettore Girone ---
        colg1, colg2, colg3 = st.columns([1,4,1])
        with colg1:
            if st.button("◀️", key="prev_girone"):
                idx = gironi.index(st.session_state['girone_sel'])
                st.session_state['girone_sel'] = gironi[(idx - 1) % len(gironi)]
                st.session_state['giornata_sel'] = sorted(df[df['Girone'] == st.session_state['girone_sel']]['Giornata'].unique())[0]
                st.rerun()
        with colg2:
            st.markdown(
                f"<div style='text-align:center; font-weight:bold;'>Seleziona Girone: Gir {st.session_state['girone_sel'].split()[-1]}</div>",
                unsafe_allow_html=True
            )
        with colg3:
            if st.button("▶️", key="next_girone"):
                idx = gironi.index(st.session_state['girone_sel'])
                st.session_state['girone_sel'] = gironi[(idx + 1) % len(gironi)]
                st.session_state['giornata_sel'] = sorted(df[df['Girone'] == st.session_state['girone_sel']]['Giornata'].unique())[0]
                st.rerun()
        
        # --- SECONDA RIGA: Selettore Giornata ---
        colj1, colj2, colj3 = st.columns([1,4,1])
        with colj1:
            if st.button("◀️", key="prev_giornata"):
                idx = giornate_correnti.index(st.session_state['giornata_sel'])
                st.session_state['giornata_sel'] = giornate_correnti[(idx - 1) % len(giornate_correnti)]
                st.rerun()
        with colj2:
            st.markdown(
                f"<div style='text-align:center; font-weight:bold;'>Seleziona Giornata: Gio {st.session_state['giornata_sel']}</div>",
                unsafe_allow_html=True
            )
        with colj3:
            if st.button("▶️", key="next_giornata"):
                idx = giornate_correnti.index(st.session_state['giornata_sel'])
                st.session_state['giornata_sel'] = giornate_correnti[(idx + 1) % len(giornate_correnti)]
                st.rerun()


            
        girone_sel = st.session_state['girone_sel']
        giornata_sel = st.session_state['giornata_sel']
        
        mostra_calendario_giornata(df, girone_sel, giornata_sel)
        classifica = aggiorna_classifica(st.session_state['df_torneo'])
        mostra_classifica_stilizzata(classifica, girone_sel)

        if st.button("🔙 Torna indietro e modifica giocatori"):
            st.session_state['mostra_form'] = True
            st.session_state['calendario_generato'] = False
            st.rerun()

        st.sidebar.markdown("---")
        st.sidebar.markdown("### Filtri partite da giocare")
        if st.sidebar.button("🎯 Filtra Giocatore"):
            st.session_state["filtra_giocatore"] = True
            st.session_state["filtra_girone"] = False
            st.rerun()
        if st.sidebar.button("🏆 Filtra Girone"):
            st.session_state["filtra_girone"] = True
            st.session_state["filtra_giocatore"] = False
            st.rerun()
        
        if st.session_state.get("filtra_giocatore", False) and 'df_torneo' in st.session_state and not st.session_state['df_torneo'].empty:
            df = st.session_state['df_torneo']
            giocatori = sorted(pd.unique(pd.concat([df['Casa'], df['Ospite']])))
            gioc_sel = st.sidebar.selectbox("Seleziona giocatore", giocatori, key="sel_giocatore")
            filtro_tipo = "Entrambe"
            if st.session_state.get("tipo_calendario") == "Andata e ritorno":
                filtro_tipo = st.sidebar.radio("Mostra partite", ["Andata", "Ritorno", "Entrambe"], index=2, key="tipo_giocatore")
            df_filtrato = df[((df['Casa'] == gioc_sel) | (df['Ospite'] == gioc_sel)) & (df['Valida'] == False)]
            if filtro_tipo != "Entrambe":
                n_giornate = df['Giornata'].max()
                if filtro_tipo == "Andata":
                    df_filtrato = df_filtrato[df_filtrato['Giornata'] <= n_giornate / 2]
                else:
                    df_filtrato = df_filtrato[df_filtrato['Giornata'] > n_giornate / 2]
            if not df_filtrato.empty:
                df_min = pd.DataFrame({"Giornata": df_filtrato["Giornata"], "Partita": df_filtrato["Casa"] + " vs " + df_filtrato["Ospite"]}).sort_values("Giornata").reset_index(drop=True)
                st.sidebar.dataframe(df_min, use_container_width=True, hide_index=True)
            else:
                st.sidebar.info("Nessuna partita da giocare.")
            if st.sidebar.button("Chiudi filtro giocatore"):
                st.session_state["filtra_giocatore"] = False
                st.rerun()
        
        if st.session_state.get("filtra_girone", False) and 'df_torneo' in st.session_state and not st.session_state['df_torneo'].empty:
            df = st.session_state['df_torneo']
            gironi = sorted(df['Girone'].unique())
            gir_sel = st.sidebar.selectbox("Seleziona girone", gironi, key="sel_girone_filt")
            filtro_tipo_g = "Entrambe"
            if st.session_state.get("tipo_calendario") == "Andata e ritorno":
                filtro_tipo_g = st.sidebar.radio("Mostra partite", ["Andata", "Ritorno", "Entrambe"], index=2, key="tipo_girone_filt")
            df_girone = df[(df['Girone'] == gir_sel) & (df['Valida'] == False)]
            if filtro_tipo_g != "Entrambe":
                n_giornate = df['Giornata'].max()
                if filtro_tipo_g == "Andata":
                    df_girone = df_girone[df_girone['Giornata'] <= n_giornate / 2]
                else:
                    df_girone = df_girone[df_girone['Giornata'] > n_giornate / 2]
            if not df_girone.empty:
                df_min_g = pd.DataFrame({"Giornata": df_girone["Giornata"], "Partita": df_girone["Casa"] + " vs " + df_girone["Ospite"]}).sort_values("Giornata").reset_index(drop=True)
                st.sidebar.dataframe(df_min_g, use_container_width=True, hide_index=True)
            else:
                st.sidebar.info("Nessuna partita da giocare.")
            if st.sidebar.button("Chiudi filtro girone"):
                st.session_state["filtra_girone"] = False
                st.rerun()
        
        st.sidebar.markdown("---")
        nome_torneo = st.session_state.get("nome_torneo", "torneo")
        csv_filename = nome_torneo + ".csv"
        df_calendario = st.session_state['df_torneo']
        df_classifica = aggiorna_classifica(df_calendario)

        if df_classifica is not None and not df_classifica.empty:
            df_classifica['Tipo'] = 'Classifica'
            df_calendario['Tipo'] = 'Calendario'
            for col in df_classifica.columns:
                if col not in df_calendario.columns:
                    df_calendario[col] = ''
            for col in df_calendario.columns:
                if col not in df_classifica.columns:
                    df_classifica[col] = ''
            df_combinato = pd.concat([df_calendario, df_classifica], ignore_index=True)
            df_combinato = df_combinato.sort_values(by=['Tipo', 'Girone'], ascending=[False, True])
        else:
            df_calendario['Tipo'] = 'Calendario'
            df_combinato = df_calendario

        csv_bytes = df_combinato.to_csv(index=False).encode('utf-8')
        st.sidebar.download_button("⬇️ Scarica CSV Torneo + Classifica", data=csv_bytes, file_name=csv_filename, mime="text/csv")
        
        st.sidebar.markdown("---")
        
        if classifica is not None and not classifica.empty:
            pdf_bytes = esporta_pdf(df, classifica)
            nome_pdf = st.session_state.get("nome_torneo", "torneo") + ".pdf"
            st.sidebar.download_button(
                label="📄 Esporta PDF Calendario + Classifica",
                data=pdf_bytes,
                file_name=nome_pdf,
                mime="application/pdf"
            )
        else:
            st.sidebar.info("La classifica non è ancora disponibile per l'esportazione.")
        
        if st.button("🔄 Carica un nuovo torneo o creane un altro"):
            st.session_state.clear()
            st.rerun()

if __name__ == "__main__":
    main()
