import streamlit as st
import pandas as pd
import random
from fpdf import FPDF
from datetime import datetime
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId

st.set_page_config(page_title="⚽ Torneo Subbuteo", layout="wide")

# -------------------------
# SESSION_STATE DEFAULT
# -------------------------
if 'df_torneo' not in st.session_state:
    st.session_state['df_torneo'] = pd.DataFrame()
if 'calendario_generato' not in st.session_state:
    st.session_state['calendario_generato'] = False
if 'girone_sel' not in st.session_state:
    st.session_state['girone_sel'] = 1
if 'giornata_sel' not in st.session_state:
    st.session_state['giornata_sel'] = 1
if 'risultati' not in st.session_state:
    st.session_state['risultati'] = {}
if 'mostra_form' not in st.session_state:
    st.session_state['mostra_form'] = False

# -------------------------
# FUNZIONI CONNESSIONE MONGO
# -------------------------
def connetti_mongo(uri, db_name, collection_name):
    try:
        client = MongoClient(uri, server_api=ServerApi('1'))
        db = client.get_database(db_name)
        col = db.get_collection(collection_name)
        _ = col.find_one()
        st.success(f"✅ Connessione a {db_name}.{collection_name} riuscita")
        return col
    except Exception as e:
        st.error(f"❌ Errore connessione a {db_name}.{collection_name}: {e}")
        return None

# Connessioni
players_collection = connetti_mongo(st.secrets["MONGO_URI"], "giocatori_subbuteo", "superba_players")
tournaments_collection = connetti_mongo(st.secrets["MONGO_URI_TOURNEMENTS"], "subbuteo_tournament", "tournament")

# -------------------------
# UTILITY
# -------------------------
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

def navigation_controls(label, value, min_val, max_val, key_prefix=""):
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        if st.button("◀️", key=f"{key_prefix}_prev", use_container_width=True):
            st.session_state[value] = max(min_val, st.session_state[value] - 1)
            st.rerun()
    with col2:
        st.markdown(f"<div style='text-align:center; font-weight:bold;'>{label} {st.session_state[value]}</div>", unsafe_allow_html=True)
    with col3:
        if st.button("▶️", key=f"{key_prefix}_next", use_container_width=True):
            st.session_state[value] = min(max_val, st.session_state[value] + 1)
            st.rerun()

# -------------------------
# CARICAMENTO DATI
# -------------------------
def carica_giocatori_da_db():
    if players_collection is None:
        st.warning("⚠️ Connessione al database giocatori non attiva")
        return pd.DataFrame()
    try:
        df = pd.DataFrame(list(players_collection.find({}, {"_id":0})))
        if df.empty:
            st.warning("⚠️ Nessun giocatore trovato")
        return df
    except Exception as e:
        st.error(f"❌ Errore lettura giocatori: {e}")
        return pd.DataFrame()

def carica_tornei_da_db():
    if tournaments_collection is None:
        return []
    try:
        return list(tournaments_collection.find({}, {"nome_torneo":1}))
    except Exception as e:
        st.error(f"❌ Errore caricamento tornei: {e}")
        return []

def carica_torneo_da_db(tournament_id):
    if tournaments_collection is None:
        return None
    try:
        torneo_data = tournaments_collection.find_one({"_id": ObjectId(tournament_id)})
        if torneo_data:
            df_torneo = pd.DataFrame(torneo_data['calendario'])
            if 'Valida' not in df_torneo.columns:
                df_torneo['Valida'] = False
            df_torneo['Valida'] = df_torneo['Valida'].astype(bool)
            df_torneo['GolCasa'] = df_torneo['GolCasa'].astype('Int64')
            df_torneo['GolOspite'] = df_torneo['GolOspite'].astype('Int64')
            st.session_state['df_torneo'] = df_torneo
        return torneo_data
    except Exception as e:
        st.error(f"❌ Errore caricamento torneo: {e}")
        return None

def salva_torneo_su_db(df_torneo, nome_torneo):
    if tournaments_collection is None:
        return None
    try:
        data = {"nome_torneo": nome_torneo, "calendario": df_torneo.to_dict('records')}
        result = tournaments_collection.insert_one(data)
        return result.inserted_id
    except Exception as e:
        st.error(f"❌ Errore salvataggio torneo: {e}")
        return None

def aggiorna_torneo_su_db(tournament_id, df_torneo):
    if tournaments_collection is None:
        return False
    try:
        tournaments_collection.update_one(
            {"_id": ObjectId(tournament_id)},
            {"$set": {"calendario": df_torneo.to_dict('records')}}
        )
        return True
    except Exception as e:
        st.error(f"❌ Errore aggiornamento torneo: {e}")
        return False

# -------------------------
# CALENDARIO & CLASSIFICA
# -------------------------
def genera_calendario_from_list(gironi, tipo="Solo andata"):
    partite = []
    for idx, girone in enumerate(gironi,1):
        gname = f"Girone {idx}"
        gr = girone[:]
        if len(gr)%2==1:
            gr.append("Riposo")
        n = len(gr)
        half = n//2
        teams = gr[:]
        for giornata in range(n-1):
            for i in range(half):
                casa, ospite = teams[i], teams[-(i+1)]
                if casa != "Riposo" and ospite != "Riposo":
                    partite.append({"Girone":gname, "Giornata":giornata+1,
                                     "Casa":casa, "Ospite":ospite, "GolCasa":None, "GolOspite":None, "Valida":False})
                    if tipo=="Andata e ritorno":
                        partite.append({"Girone":gname, "Giornata":giornata+1+n-1,
                                         "Casa":ospite, "Ospite":casa, "GolCasa":None, "GolOspite":None, "Valida":False})
            teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    return pd.DataFrame(partite)

def aggiorna_classifica(df):
    if 'Girone' not in df.columns:
        return pd.DataFrame()
    gironi = df['Girone'].dropna().unique()
    classifiche = []
    for girone in gironi:
        partite = df[(df['Girone']==girone) & (df['Valida']==True)]
        if partite.empty: continue
        squadre = pd.unique(partite[['Casa','Ospite']].values.ravel())
        stats = {s:{'Punti':0,'V':0,'P':0,'S':0,'GF':0,'GS':0,'DR':0} for s in squadre}
        for _, r in partite.iterrows():
            gc, go = int(r['GolCasa'] or 0), int(r['GolOspite'] or 0)
            casa, ospite = r['Casa'], r['Ospite']
            stats[casa]['GF'] += gc; stats[casa]['GS'] += go
            stats[ospite]['GF'] += go; stats[ospite]['GS'] += gc
            if gc>go: stats[casa]['Punti']+=2; stats[casa]['V']+=1; stats[ospite]['S']+=1
            elif gc<go: stats[ospite]['Punti']+=2; stats[ospite]['V']+=1; stats[casa]['S']+=1
            else: stats[casa]['Punti']+=1; stats[ospite]['Punti']+=1; stats[casa]['P']+=1; stats[ospite]['P']+=1
        for s in squadre: stats[s]['DR']=stats[s]['GF']-stats[s]['GS']
        df_stat = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index':'Squadra'})
        df_stat['Girone'] = girone
        classifiche.append(df_stat)
    if not classifiche: return None
    df_classifica = pd.concat(classifiche, ignore_index=True)
    df_classifica = df_classifica.sort_values(by=['Girone','Punti','DR'], ascending=[True,False,False])
    return df_classifica

# -------------------------
# FUNZIONI VISUALIZZAZIONE
# -------------------------
def mostra_calendario_giornata(df, girone_sel, giornata_sel):
    df_giornata = df[(df['Girone']==girone_sel) & (df['Giornata']==giornata_sel)].copy()
    for idx, row in df_giornata.iterrows():
        col1, col2, col3, col4, col5 = st.columns([5,1.5,1,1.5,1])
        with col1: st.markdown(f"**{row['Casa']}** vs **{row['Ospite']}**")
        with col2: st.number_input("", min_value=0, max_value=20,
                                     key=f"golcasa_{idx}", value=int(row['GolCasa'] or 0),
                                     disabled=row['Valida'], label_visibility="hidden")
        with col3: st.markdown("-")
        with col4: st.number_input("", min_value=0, max_value=20,
                                     key=f"golospite_{idx}", value=int(row['GolOspite'] or 0),
                                     disabled=row['Valida'], label_visibility="hidden")
        with col5: st.checkbox("Valida", key=f"valida_{idx}", value=row['Valida'])
        if st.session_state.get(f"valida_{idx}", False):
            st.markdown("<hr>", unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:red">Partita non validata ❌</div>', unsafe_allow_html=True)

def salva_risultati_giornata(girone_sel, giornata_sel):
    df = st.session_state['df_torneo']
    df_giornata = df[(df['Girone']==girone_sel) & (df['Giornata']==giornata_sel)].copy()
    for idx, row in df_giornata.iterrows():
        df.at[idx,'GolCasa'] = st.session_state.get(f"golcasa_{idx}",0)
        df.at[idx,'GolOspite'] = st.session_state.get(f"golospite_{idx}",0)
        df.at[idx,'Valida'] = st.session_state.get(f"valida_{idx}", False)
    df['GolCasa'] = df['GolCasa'].astype('Int64')
    df['GolOspite'] = df['GolOspite'].astype('Int64')
    st.session_state['df_torneo'] = df
    if 'tournament_id' in st.session_state:
        aggiorna_torneo_su_db(st.session_state['tournament_id'], df)
        st.success("✅ Risultati salvati su MongoDB")
    else:
        st.info("✅ Risultati aggiornati in memoria")

def mostra_classifica_stilizzata(df_classifica, girone_sel):
    st.subheader(f"Classifica {girone_sel}")
    if df_classifica is None or df_classifica.empty:
        st.info("⚽ Nessuna partita validata")
        return
    df_girone = df_classifica[df_classifica['Girone']==girone_sel].reset_index(drop=True)
    st.dataframe(combined_style(df_girone), use_container_width=True)

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
            headers = ["Casa", "Gol", "Gol", "Ospite"]
            col_widths = [60, 20, 20, 60]
            for i, h in enumerate(headers):
                pdf.cell(col_widths[i], 6, h, border=1, align='C')
            pdf.ln()
            pdf.set_font("Arial", '', 11)
            partite = df_torneo[(df_torneo['Girone'] == girone) & (df_torneo['Giornata'] == g)]
            for _, row in partite.iterrows():
                if pdf.get_y() + line_height + margin_bottom > page_height:
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 7, f"Giornata {g} (continua)", ln=True)
                    pdf.set_font("Arial", 'B', 11)
                    for i, h in enumerate(headers):
                        pdf.cell(col_widths[i], 6, h, border=1, align='C')
                    pdf.ln()
                    pdf.set_font("Arial", '', 11)
                pdf.set_text_color(255, 0, 0) if not row['Valida'] else pdf.set_text_color(0, 0, 0)
                pdf.cell(col_widths[0], 6, str(row['Casa']), border=1)
                pdf.cell(col_widths[1], 6, str(row['GolCasa']) if pd.notna(row['GolCasa']) else "-", border=1, align='C')
                pdf.cell(col_widths[2], 6, str(row['GolOspite']) if pd.notna(row['GolOspite']) else "-", border=1, align='C')
                pdf.cell(col_widths[3], 6, str(row['Ospite']), border=1)
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

# -------------------------
# MAIN
# -------------------------
def main():
    st.title("🏆 Torneo Superba - Gestione Gironi")
    df_master = carica_giocatori_da_db()
    if df_master.empty: return
    
    if not st.session_state['calendario_generato']:
        st.subheader("📁 Carica torneo o crea nuovo torneo")
        col1, col2 = st.columns(2)
        with col1:
            tornei = carica_tornei_da_db()
            if tornei:
                tornei_map = {t['nome_torneo']: str(t['_id']) for t in tornei}
                nome_sel = st.selectbox("Seleziona torneo:", list(tornei_map.keys()))
                if st.button("Carica torneo"):
                    torneo_data = carica_torneo_da_db(tornei_map[nome_sel])
                    if torneo_data:
                        st.session_state['tournament_id'] = tornei_map[nome_sel]
                        st.session_state['nome_torneo'] = nome_sel
                        st.session_state['calendario_generato'] = True
                        st.success("Torneo caricato con successo.")
                        st.rerun()
            else:
                st.info("Nessun torneo trovato su MongoDB.")
        with col2:
            if st.button("➕ Crea nuovo torneo"):
                st.session_state['mostra_form'] = True
                
        if st.session_state.get('mostra_form', False):
            st.subheader("Dettagli nuovo torneo")
            nome_default = f"TorneoSubbuteo_{datetime.now().strftime('%d%m%Y')}"
            nome_torneo = st.text_input("Nome torneo", value=nome_default)
            num_gironi = st.number_input("Numero gironi", 1, 8, value=2)
            tipo_calendario = st.selectbox("Tipo calendario", ["Solo andata","Andata e ritorno"])
            n_giocatori = st.number_input("Numero giocatori", 4, 32, value=8)
            amici = df_master['Giocatore'].tolist()
            amici_sel = st.multiselect("Seleziona giocatori", amici)
            giocatori_scelti = amici_sel
            if st.button("Genera calendario"):
                if len(set(giocatori_scelti))<4: st.warning("Inserisci almeno 4 giocatori"); return
                gironi_finali = [[] for _ in range(num_gironi)]
                random.shuffle(giocatori_scelti)
                for i, g in enumerate(giocatori_scelti):
                    gironi_finali[i % num_gironi].append(g)
                df_torneo = genera_calendario_from_list(gironi_finali, tipo_calendario)
                tid = salva_torneo_su_db(df_torneo, nome_torneo)
                if tid:
                    st.session_state['df_torneo'] = df_torneo
                    st.session_state['tournament_id'] = str(tid)
                    st.session_state['nome_torneo'] = nome_torneo
                    st.session_state['calendario_generato'] = True
                    st.success("Calendario generato e salvato")
                    st.rerun()
    else:
        st.subheader(f"Torneo: {st.session_state.get('nome_torneo', 'Corrente')}")
        df = st.session_state['df_torneo']
        gironi = sorted(df['Girone'].dropna().unique())
        giornate = sorted(df[df['Girone']==st.session_state['girone_sel']]['Giornata'].unique())
        
        col_nav1, col_nav2 = st.columns(2)
        with col_nav1:
            navigation_controls("Girone", "girone_sel", 1, len(gironi), "girone")
        with col_nav2:
            navigation_controls("Giornata", "giornata_sel", 1, len(giornate), "giornata")

        mostra_calendario_giornata(df, st.session_state['girone_sel'], st.session_state['giornata_sel'])
        st.button("💾 Salva Risultati", on_click=salva_risultati_giornata, args=(st.session_state['girone_sel'],st.session_state['giornata_sel']))
        
        st.markdown("---")
        classifica = aggiorna_classifica(df)
        if classifica is not None:
            st.download_button(
                label="📄 Esporta in PDF",
                data=esporta_pdf(df, classifica),
                file_name=f"torneo_{st.session_state.get('nome_torneo', 'Corrente')}.pdf",
                mime="application/pdf"
            )
        mostra_classifica_stilizzata(classifica, st.session_state['girone_sel'])

if __name__ == "__main__":
    main()
