import streamlit as st
import pandas as pd
import random
from fpdf import FPDF
from datetime import datetime
import json
import time
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId

# Aggiungi questo blocco subito dopo gli import
# Questo garantisce che 'df_torneo' esista sempre in session_state
if 'df_torneo' not in st.session_state:
    st.session_state['df_torneo'] = pd.DataFrame() 

def init_db_connection():
    try:
        uri = st.secrets["MONGO_URI"]
        client = MongoClient(uri)
        db = client['tornei_db']
        tournaments_collection = db['tornei_collection']
        players_collection = db['players_collection']
        return players_collection, tournaments_collection, db
    except KeyError:
        st.error("❌ Errore di connessione a MongoDB: 'st.secrets has no key \"MONGO_URI\". Did you forget to add it to secrets.toml, mount it to secret directory, or the app settings on Streamlit Cloud? More info: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management'. Non sarà possibile caricare i dati.")
        return None, None, None
    except Exception as e:
        st.error(f"❌ Errore di connessione a MongoDB: {e}. Non sarà possibile caricare i dati.")
        return None, None, None

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

def carica_giocatori_da_db():
    if players_collection is not None:
        try:
            count = players_collection.count_documents({})
            if count == 0:
                st.warning("⚠️ La collection 'superba_players' è vuota o non esiste. Non è stato caricato alcun giocatore.")
                return pd.DataFrame()
            else:
                st.info(f"✅ Trovati {count} giocatori nel database. Caricamento in corso...")
            
            df = pd.DataFrame(list(players_collection.find()))
            
            if '_id' in df.columns:
                df = df.drop(columns=['_id'])
            
            if 'Giocatore' not in df.columns:
                st.error("❌ Errore: la colonna 'Giocatore' non è presente nel database dei giocatori.")
                return pd.DataFrame()
                
            return df
        except Exception as e:
            st.error(f"❌ Errore durante la lettura dalla collection dei giocatori: {e}")
            return pd.DataFrame()
    else:
        st.warning("⚠️ La connessione a MongoDB non è attiva.")
        return pd.DataFrame()

def carica_tornei_da_db():
    if tournaments_collection is not None:
        try:
            return list(tournaments_collection.find({}, {"nome_torneo": 1}))
        except Exception as e:
            st.error(f"❌ Errore durante il caricamento dei tornei dal database: {e}")
            return []
    return []

def carica_torneo_da_db(tournament_id):
    if tournaments_collection is not None:
        try:
            torneo_data = tournaments_collection.find_one({"_id": ObjectId(tournament_id)})
            if torneo_data:
                df_torneo = pd.DataFrame(torneo_data['calendario'])
                if 'Valida' not in df_torneo.columns:
                    df_torneo['Valida'] = False
                df_torneo['Valida'] = df_torneo['Valida'].astype(bool)
                df_torneo['GolCasa'] = df_torneo['GolCasa'].astype('Int64')
                df_torneo['GolOspite'] = df_torneo['GolOspite'].astype('Int64')
                # Aggiungi questa riga per salvare il DataFrame nello stato della sessione
                st.session_state['df_torneo'] = df_torneo
            return torneo_data
        except Exception as e:
            st.error(f"❌ Errore durante il caricamento del torneo dal database: {e}")
            return None
    return None
    
def salva_torneo_su_db(df_torneo, nome_torneo):
    if tournaments_collection is not None:
        try:
            # Converte il DataFrame in un formato che può essere salvato su MongoDB
            torneo_data = {
                "nome_torneo": nome_torneo,
                "calendario": df_torneo.to_dict('records')
            }
            result = tournaments_collection.insert_one(torneo_data)
            return result.inserted_id
        except Exception as e:
            st.error(f"❌ Errore durante il salvataggio del torneo su MongoDB: {e}")
            return None

def aggiorna_torneo_su_db(tournament_id, df_torneo):
    if tournaments_collection is not None:
        try:
            # Aggiorna solo il campo 'calendario'
            tournaments_collection.update_one(
                {"_id": ObjectId(tournament_id)},
                {"$set": {"calendario": df_torneo.to_dict('records')}}
            )
            return True
        except Exception as e:
            st.error(f"❌ Errore durante l'aggiornamento del torneo su MongoDB: {e}")
            return False

# --- NAVIGAZIONE COMPATTA ---
def navigation_controls(label, value, min_val, max_val, key_prefix=""):
    col1, col2, col3 = st.columns([1, 3, 1])
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
    st.session_state.girone = 1
if "giornata" not in st.session_state:
    st.session_state.giornata = 1
if "calendario_generato" not in st.session_state:
    st.session_state.calendario_generato = False

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
                    partite.append({"Girone": g, "Giornata": giornata + 1,
                                     "Casa": casa, "Ospite": ospite, "GolCasa": None, "GolOspite": None, "Valida": False})
                    if tipo == "Andata e ritorno":
                        partite.append({"Girone": g, "Giornata": giornata + 1 + (n - 1),
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
    df_giornata = df[(df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel)].copy()
    if 'Valida' not in df_giornata.columns:
        df_giornata['Valida'] = False

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
                value=int(row['GolCasa']) if pd.notna(row['GolCasa']) else 0,
                label_visibility="hidden",
                disabled=val
            )
                
        with col3:
            st.markdown("-")

        with col4:
            st.number_input(
                "", min_value=0, max_value=20,
                key=f"golospite_{idx}",
                value=int(row['GolOspite']) if pd.notna(row['GolOspite']) else 0,
                label_visibility="hidden",
                disabled=val
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
            st.markdown('<div style="color:red; margin-bottom: 15px;">Partita non ancora validata ❌</div>', unsafe_allow_html=True)

def salva_risultati_giornata(girone_sel, giornata_sel):
    df = st.session_state['df_torneo']
    df_giornata_copia = df[(df['Girone'] == girone_sel) & (df['Giornata'] == giornata_sel)].copy()
    
    for idx, row in df_giornata_copia.iterrows():
        # Aggiorna solo se la partita non è ancora stata validata
        if not row['Valida']:
            df.at[idx, 'GolCasa'] = st.session_state.get(f"golcasa_{idx}", 0)
            df.at[idx, 'GolOspite'] = st.session_state.get(f"golospite_{idx}", 0)
            df.at[idx, 'Valida'] = st.session_state.get(f"valida_{idx}", False)
            
    df['GolCasa'] = df['GolCasa'].astype('Int64')
    df['GolOspite'] = df['GolOspite'].astype('Int64')
    st.session_state['df_torneo'] = df
    
    if 'tournament_id' in st.session_state:
        success = aggiorna_torneo_su_db(st.session_state['tournament_id'], df)
        if success:
            st.info("✅ Risultati salvati su MongoDB!")
        else:
            st.warning("⚠️ Errore nel salvataggio dei risultati su MongoDB.")
    else:
        st.info("✅ Risultati aggiornati in memoria.")

def mostra_classifica_stilizzata(df_classifica, girone_sel):
    st.subheader(f"Classifica Girone {girone_sel}")
    if df_classifica is None or df_classifica.empty:
        st.info("⚽ Nessuna partita validata: la classifica sarà disponibile dopo l'inserimento e validazione dei risultati.")
        return
    df_girone = df_classifica[df_classifica['Girone'] == girone_sel].reset_index(drop=True)
    styled = combined_style(df_girone)
    st.dataframe(styled, use_container_width=True)

def main():
    if not st.session_state.get('calendario_generato', False):
        st.title("🏆⚽Gestione Torneo Superba a Gironi by Legnaro72🥇🥈🥉")
    else:
        nome_torneo = st.session_state.get("nome_torneo", "Torneo")
        st.markdown(f"<div class='big-title'>🏆⚽{nome_torneo}🥇🥈🥉</div>", unsafe_allow_html=True)

    players_collection, tournaments_collection, db = init_db_connection()

    st.markdown("""
        <style>
        ul, li { list-style-type: none !important; padding-left: 0 !important; margin-left: 0 !important; }
        .big-title { text-align: center; font-size: clamp(16px, 4vw, 36px); font-weight: bold; margin-top: 10px; margin-bottom: 20px; color: red; word-wrap: break-word; white-space: normal; }
        div[data-testid="stNumberInput"] label::before { content: none; }
        </style>
    """, unsafe_allow_html=True)
    
    if players_collection is None or tournaments_collection is None:
        return

    df_master = carica_giocatori_da_db()
    if df_master.empty:
        st.error("❌ Impossibile procedere: non è stato possibile caricare la lista giocatori.")
        return

    if not st.session_state.calendario_generato:
        st.write("---")
        st.subheader("Scegli un'azione per iniziare: 👇")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("<h4 style='text-align: center;'>📁 Carica Torneo Esistente</h4>", unsafe_allow_html=True)
            st.info("Seleziona un torneo salvato su MongoDB per continuare a giocare. 🎮")
            tornei = carica_tornei_da_db()
            tornei_map = {t['nome_torneo']: str(t['_id']) for t in tornei}
            if tornei_map:
                nome_torneo_sel = st.selectbox("Seleziona un torneo:", options=list(tornei_map.keys()))
                if st.button("Carica Torneo Selezionato"):
                    tournament_id = tornei_map[nome_torneo_sel]
                    torneo_data = carica_torneo_da_db(tournament_id)
                    if torneo_data:
                        df_torneo = pd.DataFrame(torneo_data['calendario'])
                        df_torneo['Valida'] = df_torneo['Valida'].astype(bool)
                        st.session_state['df_torneo'] = df_torneo
                        st.session_state['nome_torneo'] = torneo_data['nome_torneo']
                        st.session_state['tournament_id'] = tournament_id
                        st.session_state.calendario_generato = True
                        st.success("✅ Torneo caricato correttamente da MongoDB!")
                        st.rerun()
            else:
                st.warning("⚠️ Nessun torneo trovato nel database.")

        with col2:
            st.markdown("<h4 style='text-align: center;'>⚽ Crea Nuovo Torneo</h4>", unsafe_allow_html=True)
            st.info("Inizia una nuova competizione configurando giocatori, gironi e tipo di calendario. ✍️")
            if st.button("➕ Crea Nuovo Torneo"):
                st.session_state['mostra_form'] = True
                
        st.write("---")
        
        if st.session_state.get('mostra_form', False):
            oggi = datetime.now()
            mesi = {1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile", 5: "Maggio", 6: "Giugno", 7: "Luglio", 8: "Agosto", 9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre"}
            nome_default = f"TorneoSubbuteo_{oggi.day}{mesi[oggi.month]}{oggi.year}"
            
            st.header("Dettagli Nuovo Torneo")
            nome_torneo = st.text_input("📝 Nome del torneo:", value=nome_default)
            st.session_state["nome_torneo"] = nome_torneo
            num_gironi = st.number_input("🔢 Numero di gironi", 1, 8, value=2)
            tipo_calendario = st.selectbox("📅 Tipo calendario", ["Solo andata", "Andata e ritorno"])
            n_giocatori = st.number_input("👥 Numero giocatori", 4, 32, value=8)
            st.markdown("### 👥 Seleziona Giocatori")
            amici = df_master['Giocatore'].tolist()
            all_seleziona = st.checkbox("Seleziona tutti i giocatori", key="all_amici")
            if all_seleziona:
                amici_selezionati = st.multiselect("Seleziona giocatori", amici, default=amici)
            else:
                amici_selezionati = st.multiselect("Seleziona giocatori", amici)
            
            num_supplementari = n_giocatori - len(amici_selezionati)
            if num_supplementari < 0:
                st.warning(f"⚠️ Hai selezionato più amici ({len(amici_selezionati)}) del numero partecipanti ({n_giocatori}). Riduci la selezione.")
                return
            
            st.markdown(f"Giocatori supplementari da inserire: **{num_supplementari}**")
            giocatori_supplementari = []
            for i in range(num_supplementari):
                use = st.checkbox(f"Aggiungi giocatore supplementare G{i+1}", key=f"supp_{i}_check")
                if use:
                    nome = st.text_input(f"Nome giocatore supplementare G{i+1}", key=f"supp_{i}_nome")
                    if nome.strip() == "":
                        st.warning(f"⚠️ Inserisci un nome valido per G{i+1}")
                        return
                    giocatori_supplementari.append(nome.strip())
            giocatori_scelti = amici_selezionati + giocatori_supplementari
            
            if st.button("Genera Calendario"):
                if len(set(giocatori_scelti)) < 4:
                    st.warning("⚠️ Inserisci almeno 4 giocatori diversi.")
                else:
                    gironi_finali = [[] for _ in range(num_gironi)]
                    giocatori_formattati = [
                        f"{df_master[df_master['Giocatore']==g].iloc[0]['Squadra']} ({g})" if g in df_master['Giocatore'].values else f"Squadra_default ({g})"
                        for g in giocatori_scelti
                    ]
                    random.shuffle(giocatori_formattati)
                    for i, g in enumerate(giocatori_formattati):
                        gironi_finali[i % num_gironi].append(g)
                    
                    df_torneo = genera_calendario_from_list(
                        gironi_finali, tipo_calendario
                    )
                    
                    tournament_id = salva_torneo_su_db(df_torneo, nome_torneo)
                    if tournament_id:
                        st.session_state['df_torneo'] = df_torneo
                        st.session_state['tournament_id'] = str(tournament_id)
                        st.success("✅ Calendario generato e salvato su MongoDB!")
                        st.session_state.calendario_generato = True
                        st.session_state['mostra_form'] = False
                        st.rerun()
                    else:
                        st.error("❌ Errore nel salvataggio del nuovo torneo.")

    if st.session_state.get('calendario_generato', False):
        df = st.session_state['df_torneo']
        gironi = sorted(df['Girone'].dropna().unique().tolist())
        if 'girone_sel' not in st.session_state:
            st.session_state['girone_sel'] = gironi[0]
        
        giornate_correnti = sorted(df[df['Girone'] == st.session_state['girone_sel']]['Giornata'].dropna().unique().tolist())
        if 'giornata_sel' not in st.session_state or st.session_state['giornata_sel'] not in giornate_correnti:
            st.session_state['giornata_sel'] = giornate_correnti[0]
        
        st.subheader("Girone")
        gironi_numeri = [g.replace("Girone ", "") for g in gironi]
        nuovo_girone = st.selectbox(
            "",
            gironi_numeri,
            index=gironi_numeri.index(str(int(st.session_state['girone_sel'].replace("Girone ","")))),
            key="girone_nav_sb"
        )
        girone_selezionato = f"Girone {nuovo_girone}"
        if girone_selezionato != st.session_state['girone_sel']:
            st.session_state['girone_sel'] = girone_selezionato
            giornate_correnti = sorted(
                df[df['Girone'] == girone_selezionato]['Giornata'].dropna().unique().tolist()
            )
            giornate_correnti = [int(g) for g in giornate_correnti]
            st.session_state['giornata_sel'] = giornate_correnti[0]
            st.rerun()

        st.subheader("Giornate")
        modo_giornate = st.radio(
            "",
            ["Menu a tendina", "Bottoni"],
            index=0,
            horizontal=True,
            key="modo_giornate"
        )
        
        giornate_correnti = sorted(
            df[df['Girone'] == st.session_state['girone_sel']]['Giornata'].dropna().unique().tolist()
        )
        giornate_correnti = [int(g) for g in giornate_correnti]
        
        if modo_giornate == "Menu a tendina":
            nuova_giornata = st.selectbox(
                "",
                giornate_correnti,
                index=giornate_correnti.index(int(st.session_state['giornata_sel'])),
                key="giornata_nav_sb"
            )
            if nuova_giornata != st.session_state['giornata_sel']:
                st.session_state['giornata_sel'] = nuova_giornata
                st.rerun()
        else:
            st.markdown("""
                <style>
                div[data-testid="stButton"] > button[selected="true"] {
                    background-color: mediumseagreen !important;
                    color: white !important;
                    font-weight: bold !important;
                    border: 2px solid #2e8b57 !important;
                }
                </style>
            """, unsafe_allow_html=True)
            cols = st.columns(5)
            for i, g in enumerate(giornate_correnti):
                selected = (g == int(st.session_state['giornata_sel']))
                if cols[i % 5].button(str(g), key=f"giornata_{g}"):
                    st.session_state['giornata_sel'] = g
                    st.rerun()

        girone_sel = st.session_state['girone_sel']
        giornata_sel = st.session_state['giornata_sel']
        mostra_calendario_giornata(df, girone_sel, giornata_sel)
        classifica = aggiorna_classifica(st.session_state['df_torneo'])
        mostra_classifica_stilizzata(classifica, girone_sel)

        if 'df_torneo' in st.session_state and not st.session_state['df_torneo'].empty:
            # Qui devi assicurarti che 'girone_sel' e 'giornata_sel' siano già definiti
            girone_sel = st.session_state.get('girone_sel', 'A')
            giornata_sel = st.session_state.get('giornata_sel', 1)
        
            mostra_calendario_giornata(st.session_state['df_torneo'], girone_sel, giornata_sel)
            
            # Questo è il pulsante. Deve essere al LORO STESSO LIVELLO DI INDENTAZIONE.
            st.button("💾 Salva Risultati Giornata", on_click=salva_risultati_giornata, args=(girone_sel, giornata_sel))
        else:
            st.info("⚠️ Carica un torneo o creane uno nuovo per visualizzare il calendario.")


        if st.button("?"):
            st.markdown("---")
            st.subheader("Esporta PDF")
            if 'df_torneo' in st.session_state and not st.session_state['df_torneo'].empty:
                df_calendario = st.session_state['df_torneo']
                df_classifica = aggiorna_classifica(df_calendario)
                if df_classifica is not None:
                    pdf_bytes = esporta_pdf(df_calendario, df_classifica)
                    st.download_button(
                        label="⬇️ Scarica PDF",
                        data=pdf_bytes,
                        file_name=f"{st.session_state.get('nome_torneo', 'torneo')}_report.pdf",
                        mime="application/pdf"
                    )
                else:
                    st.warning("⚠️ Non è possibile generare il PDF senza risultati validati.")
            else:
                st.warning("⚠️ Non è stato generato o caricato alcun calendario del torneo.")

if __name__ == "__main__":
    main()
