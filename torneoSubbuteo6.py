import streamlit as st
import pandas as pd
import requests
from io import StringIO
import random
from fpdf import FPDF
from datetime import datetime

st.set_page_config(page_title="Gestione Torneo Superba a Gironi by Legnaro72", layout="wide")

st.markdown("""
    <style>
    ul, li {
        list-style-type: none !important;
        padding-left: 0 !important;
        margin-left: 0 !important;
    }
    div[data-testid="stNumberInput"] label::before {
        content: none;
    }
    .big-title {
        text-align: center;
        font-size: clamp(16px, 4vw, 36px);
        font-weight: bold;
        margin-top: 10px;
        margin-bottom: 20px;
        color: red;
        word-wrap: break-word;
        white-space: normal;
    }
    </style>
""", unsafe_allow_html=True)


URL_GIOCATORI = "https://raw.githubusercontent.com/legnaro72/torneoSvizzerobyLegna/refs/heads/main/giocatoriSuperba.csv"

def carica_giocatori_master(url=URL_GIOCATORI):
    try:
        r = requests.get(url)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.content.decode('latin1')))
        df["Potenziale"] = pd.to_numeric(df["Potenziale"], errors='coerce').fillna(4).astype(int)
        return df[["Giocatore","Squadra","Potenziale"]]
    except Exception as e:
        st.warning(f"Impossibile caricare lista giocatori: {e}")
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
    if df.empty or 'Girone' not in df.columns:
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

    if not classifiche:
        return pd.DataFrame()

    df_classifica = pd.concat(classifiche, ignore_index=True)
    df_classifica = df_classifica.sort_values(by=['Girone','Punti','DR'], ascending=[True,False,False])
    return df_classifica

def esporta_pdf(df_torneo, df_classifica):
    if df_torneo.empty:
        return None
    
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
            partite = df_torneo[(df_torneo['Girone'] == girone) & (df['Giornata'] == g)]

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

        if not df_classifica.empty:
            if pdf.get_y() + 40 + margin_bottom > page_height:
                pdf.add_page()

            pdf.set_font("Arial", 'B', 13)
            pdf.cell(0, 8, f"Classifica {girone}", ln=True)
            df_c = df_classifica[df_classifica['Girone'] == girone]
            if not df_c.empty:
                pdf.set_font("Arial", 'B', 11)
                headers = ["Squadra", "Punti", "V", "P", "S", "GF", "GS", "DR"]
                col_widths = [60, 15, 15, 15, 15, 15, 15, 15]
                for i, h in enumerate(headers): pdf.cell(col_widths[i], 6, h, border=1, align='C')
                pdf.ln()
                pdf.set_font("Arial", '', 11)
                for _, r in df_c.iterrows():
                    if pdf.get_y() + line_height + margin_bottom > page_height: pdf.add_page()
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
    st.subheader(f"Calendario  {girone_sel} - Giornata {giornata_sel}")
    
    df_giornata = df[(df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel)].copy()
    
    if df_giornata.empty:
        st.info("Nessuna partita da mostrare per questa giornata.")
        return

    for idx, row in df_giornata.iterrows():
        casa = row['Casa']
        ospite = row['Ospite']
        val = row['Valida']
        col1, col2, col3, col4, col5 = st.columns([5, 1.5, 1, 1.5, 1])
        with col1: st.markdown(f"**{casa}** vs **{ospite}**")
        with col2: st.number_input("", min_value=0, max_value=20, key=f"golcasa_{idx}", value=int(row['GolCasa']) if pd.notna(row['GolCasa']) else 0, label_visibility="hidden")
        with col3: st.markdown("-")
        with col4: st.number_input("", min_value=0, max_value=20, key=f"golospite_{idx}", value=int(row['GolOspite']) if pd.notna(row['GolOspite']) else 0, label_visibility="hidden")
        with col5: st.checkbox("Valida", key=f"valida_{idx}", value=val)
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
        st.rerun()
    st.button("Salva Risultati Giornata", on_click=salva_risultati_giornata)

def mostra_classifica_stilizzata(df_classifica, girone_sel):
    st.subheader(f"Classifica Girone {girone_sel}")
    if df_classifica.empty:
        st.info("Nessuna partita validata.")
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
    if "initialized" not in st.session_state:
        st.session_state.clear()
        st.session_state.initialized = True
        st.session_state.calendario_generato = False
        st.session_state.mostra_form = False
        st.session_state.filtra_giocatore = False
        st.session_state.filtra_girone = False
        st.session_state.squadre_assegnate = False

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
                        st.success("✅ Torneo caricato correttamente!")
                        st.rerun()
                    else:
                        st.error(f"❌ Il CSV non contiene le colonne richieste: {expected_cols}")
                except Exception as e:
                    st.error(f"❌ Errore nel caricamento: {e}")

        with col2:
            st.markdown("<h4 style='text-align: center;'>⚽ Crea Nuovo Torneo</h4>", unsafe_allow_html=True)
            if st.button("➕ Crea Nuovo Torneo"):
                st.session_state['mostra_form'] = True
                st.session_state['calendario_generato'] = False
                st.session_state['squadre_assegnate'] = False
                st.rerun()

        st.write("---")
        
        if st.session_state.get('mostra_form', False):
            oggi = datetime.now()
            nome_default = f"TorneoSubbuteo_{oggi.day:02d}{oggi.month:02d}{oggi.year}"
            
            st.header("Dettagli Nuovo Torneo")
            nome_torneo = st.text_input("Nome del torneo:", value=nome_default, key="nome_torneo_nuovo")
            st.session_state["nome_torneo"] = nome_torneo
            num_gironi = st.number_input("Numero di gironi", 1, 8, value=2, key="num_gironi")
            tipo_calendario = st.selectbox("Tipo calendario", ["Solo andata", "Andata e ritorno"], key="tipo_cal")
            n_giocatori = st.number_input("Numero giocatori", 4, 32, value=8, key="n_giocatori")

            st.markdown("### 👥 Seleziona Giocatori")
            amici = df_master['Giocatore'].tolist()
            all_seleziona = st.checkbox("Seleziona tutti gli amici", key="all_amici")
            amici_selezionati = st.multiselect("Seleziona amici", amici, default=amici if all_seleziona else [])
            
            num_supplementari = n_giocatori - len(amici_selezionati)
            if num_supplementari < 0:
                st.warning(f"Hai selezionato troppi amici. Riduci la selezione o aumenta il numero di giocatori.")
                st.stop()

            st.markdown(f"Giocatori supplementari da inserire: **{num_supplementari}**")
            giocatori_supplementari = [st.text_input(f"Nome giocatore suppl. {i+1}", key=f"supp_nome_{i}") for i in range(num_supplementari)]
            giocatori_supplementari_puliti = [n for n in giocatori_supplementari if n.strip() != ""]
            
            if len(giocatori_supplementari_puliti) < num_supplementari:
                st.warning("Inserisci i nomi per tutti i giocatori supplementari.")
                st.stop()

            giocatori_scelti = amici_selezionati + giocatori_supplementari_puliti
            if len(set(giocatori_scelti)) < n_giocatori:
                st.warning("Ci sono nomi duplicati tra i giocatori. Rimuovi i duplicati.")
                st.stop()
                
            st.markdown(f"**Giocatori selezionati:** {', '.join(giocatori_scelti)}")
            
            if st.button("Assegna Squadre"):
                st.session_state['giocatori_scelti'] = giocatori_scelti
                st.session_state['num_gironi'] = num_gironi
                st.session_state['tipo_calendario'] = tipo_calendario
                st.session_state.squadre_assegnate = True
                st.rerun()
            
            if st.session_state.get('squadre_assegnate', False):
                st.markdown("### Modifica Squadra e Potenziale")
                gioc_info = {}
                for gioc in st.session_state['giocatori_scelti']:
                    row = df_master[df_master['Giocatore']==gioc].iloc[0] if gioc in df_master['Giocatore'].values else None
                    squadra_default = row['Squadra'] if row is not None else ""
                    potenziale_default = int(row['Potenziale']) if row is not None else 4
                    squadra_nuova = st.text_input(f"Squadra per {gioc}", value=squadra_default, key=f"squadra_{gioc}")
                    potenziale_nuovo = st.slider(f"Potenziale per {gioc}", 1, 10, potenziale_default, key=f"potenziale_{gioc}")
                    gioc_info[gioc] = {"Squadra": squadra_nuova, "Potenziale": potenziale_nuovo}
                
                if st.button("Conferma e genera calendario"):
                    giocatori_formattati = []
                    for gioc in st.session_state['giocatori_scelti']:
                        squadra = gioc_info[gioc]['Squadra'].strip()
                        if not squadra:
                            st.warning(f"Scegli un nome squadra per {gioc}.")
                            st.stop()
                        giocatori_formattati.append(f"{squadra} ({gioc})")
                    
                    df_torneo = genera_calendario(giocatori_formattati, st.session_state['num_gironi'], st.session_state['tipo_calendario'])
                    st.session_state['df_torneo'] = df_torneo
                    st.success("Calendario generato e salvato!")
                    st.session_state.calendario_generato = True
                    st.session_state['mostra_form'] = False
                    st.session_state.squadre_assegnate = False
                    st.rerun()
    
    if st.session_state.get("calendario_generato", False):
        if 'df_torneo' not in st.session_state or st.session_state['df_torneo'].empty:
            st.error("Errore: DataFrame del torneo non trovato o vuoto. Torna alla schermata iniziale.")
            if st.button("Ritorna alla schermata iniziale"):
                st.session_state.clear()
                st.rerun()
            return
            
        df = st.session_state['df_torneo']
        gironi = sorted(df['Girone'].dropna().unique().tolist())
        if 'girone_sel' not in st.session_state or st.session_state['girone_sel'] not in gironi:
            st.session_state['girone_sel'] = gironi[0] if gironi else None
        
        if st.session_state['girone_sel']:
            giornate_correnti = sorted(df[df['Girone'] == st.session_state['girone_sel']]['Giornata'].dropna().unique().tolist())
            if 'giornata_sel' not in st.session_state or st.session_state['giornata_sel'] not in giornate_correnti:
                st.session_state['giornata_sel'] = giornate_correnti[0] if giornate_correnti else None
        else:
            giornate_correnti = []
            st.session_state['giornata_sel'] = None
        
        if gironi and giornate_correnti:
            sel_col1, sel_col2 = st.columns(2)
            with sel_col1:
                nuovo_girone = st.selectbox("Seleziona Girone", gironi, index=gironi.index(st.session_state['girone_sel']), key="sel_girone_main")
            with sel_col2:
                giornata_index = giornate_correnti.index(st.session_state['giornata_sel']) if st.session_state['giornata_sel'] in giornate_correnti else 0
                nuova_giornata = st.selectbox("Seleziona Giornata", giornate_correnti, index=giornata_index, key="sel_giornata_main")
                
            if (nuovo_girone != st.session_state['girone_sel']) or (nuova_giornata != st.session_state['giornata_sel']):
                st.session_state['girone_sel'] = nuovo_girone
                st.session_state['giornata_sel'] = nuova_giornata
                st.rerun()
                
            girone_sel = st.session_state['girone_sel']
            giornata_sel = st.session_state['giornata_sel']
            
            mostra_calendario_giornata(df, girone_sel, giornata_sel)
            classifica = aggiorna_classifica(st.session_state['df_torneo'])
            mostra_classifica_stilizzata(classifica, girone_sel)

        if st.button("🔙 Torna indietro e modifica giocatori"):
            st.session_state.clear()
            st.session_state.mostra_form = True
            st.rerun()

        st.sidebar.markdown("---")
        st.sidebar.markdown("### Filtri partite da giocare")
        if st.sidebar.button("🎯 Filtra Giocatore"):
            st.session_state["filtra_giocatore"] = True
            st.session_state["filtra_girone"] = False
        if st.sidebar.button("🏆 Filtra Girone"):
            st.session_state["filtra_girone"] = True
            st.session_state["filtra_giocatore"] = False
        
        if st.session_state.get("filtra_giocatore", False):
            giocatori = sorted(pd.unique(pd.concat([df['Casa'], df['Ospite']])))
            gioc_sel = st.sidebar.selectbox("Seleziona giocatore", giocatori, key="sel_giocatore")
            filtro_tipo = st.sidebar.radio("Mostra partite", ["Andata", "Ritorno", "Entrambe"], index=2, key="tipo_giocatore") if st.session_state.get("tipo_calendario") == "Andata e ritorno" else "Entrambe"
            df_filtrato = df[((df['Casa'] == gioc_sel) | (df['Ospite'] == gioc_sel)) & (df['Valida'] == False)]
            if filtro_tipo != "Entrambe":
                n_giornate = df['Giornata'].max()
                df_filtrato = df_filtrato[df_filtrato['Giornata'] <= n_giornate / 2] if filtro_tipo == "Andata" else df_filtrato[df_filtrato['Giornata'] > n_giornate / 2]
            st.sidebar.dataframe(pd.DataFrame({"Giorno": df_filtrato["Giornata"], "Partita": df_filtrato["Casa"] + " vs " + df_filtrato["Ospite"]}).sort_values("Giorno").reset_index(drop=True), use_container_width=True, hide_index=True)
            if st.sidebar.button("Chiudi filtro giocatore"):
                st.session_state["filtra_giocatore"] = False
                st.rerun()

        if st.session_state.get("filtra_girone", False):
            gironi_filtrabili = sorted(df['Girone'].unique())
            gir_sel = st.sidebar.selectbox("Seleziona girone", gironi_filtrabili, key="sel_girone_filt")
            filtro_tipo_g = st.sidebar.radio("Mostra partite", ["Andata", "Ritorno", "Entrambe"], index=2, key="tipo_girone") if st.session_state.get("tipo_calendario") == "Andata e ritorno" else "Entrambe"
            df_girone = df[(df['Girone'] == gir_sel) & (df['Valida'] == False)]
            if filtro_tipo_g != "Entrambe":
                n_giornate = df['Giornata'].max()
                df_girone = df_girone[df_girone['Giornata'] <= n_giornate / 2] if filtro_tipo_g == "Andata" else df_girone[df_girone['Giornata'] > n_giornate / 2]
            st.sidebar.dataframe(pd.DataFrame({"Giorno": df_girone["Giornata"], "Partita": df_girone["Casa"] + " vs " + df_girone["Ospite"]}).sort_values("Giorno").reset_index(drop=True), use_container_width=True, hide_index=True)
            if st.sidebar.button("Chiudi filtro girone"):
                st.session_state["filtra_girone"] = False
                st.rerun()

        st.sidebar.markdown("---")
        nome_torneo = st.session_state.get("nome_torneo", "torneo")
        df_calendario = st.session_state['df_torneo']
        df_classifica = aggiorna_classifica(df_calendario)
        
        if not df_classifica.empty:
            df_classifica['Tipo'] = 'Classifica'
            df_calendario['Tipo'] = 'Calendario'
            for col in df_classifica.columns:
                if col not in df_calendario.columns: df_calendario[col] = ''
            for col in df_calendario.columns:
                if col not in df_classifica.columns: df_classifica[col] = ''
            df_combinato = pd.concat([df_calendario, df_classifica], ignore_index=True)
            csv_bytes = df_combinato.to_csv(index=False).encode('utf-8')
            st.sidebar.download_button("⬇️ Scarica CSV Torneo + Classifica", data=csv_bytes, file_name=f"{nome_torneo}.csv", mime="text/csv")
            st.sidebar.markdown("---")
            pdf_bytes = esporta_pdf(df_calendario, df_classifica)
            if pdf_bytes:
                st.sidebar.download_button("📄 Esporta PDF Calendario + Classifica", data=pdf_bytes, file_name=f"{nome_torneo}.pdf", mime="application/pdf")
            else:
                st.sidebar.info("Nessun dato di classifica da esportare in PDF.")
        else:
            st.sidebar.info("La classifica non è ancora disponibile per l'esportazione.")
            st.sidebar.download_button("⬇️ Scarica CSV Torneo (solo calendario)", data=df_calendario.to_csv(index=False).encode('utf-8'), file_name=f"{nome_torneo}.csv", mime="text/csv")

        if st.button("🔄 Carica un nuovo torneo o creane un altro"):
            st.session_state.clear()
            st.session_state.mostra_form = True
            st.rerun()

if __name__ == "__main__":
    main()
