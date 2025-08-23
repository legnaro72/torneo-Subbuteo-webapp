import streamlit as st
import pandas as pd
import random
from fpdf import FPDF
from datetime import datetime
import time
from pymongo import MongoClient
from pymongo.server_api import ServerApi

st.set_page_config(page_title="⚽ Torneo Subbuteo - Sistema Svizzero", layout="wide")

# ------------------------- Connessione a MongoDB -------------------------
players_collection = None
try:
    MONGO_URI = st.secrets["MONGO_URI"]
    server_api = ServerApi('1')
    client = MongoClient(MONGO_URI, server_api=server_api)
    db = client.get_database("giocatori_subbuteo")
    players_collection = db.get_collection("superba_players")
    _ = players_collection.find_one()
    st.success("✅ Connessione a MongoDB riuscita")
except Exception as e:
    st.warning("⚠️ Connessione MongoDB non disponibile: dati da file CSV")

# ------------------------- Funzioni utilità -------------------------
def carica_giocatori_da_db():
    if players_collection is not None:
        df = pd.DataFrame(list(players_collection.find()))
        if '_id' in df.columns: 
            df = df.drop(columns=['_id'])
        return df
    return pd.DataFrame()

def genera_calendario(gironi, tipo="Solo andata"):
    partite = []
    for idx, girone in enumerate(gironi, 1):
        g = f"Girone {idx}"
        teams = girone[:]
        if len(teams) % 2 == 1: teams.append("Riposo")
        n = len(teams)
        half = n // 2
        for giornata in range(n - 1):
            for i in range(half):
                casa, ospite = teams[i], teams[-(i+1)]
                if casa != "Riposo" and ospite != "Riposo":
                    partite.append({"Girone": g, "Giornata": giornata+1,
                                     "Casa": casa, "Ospite": ospite, "GolCasa": None, "GolOspite": None, "Valida": False})
                    if tipo=="Andata e ritorno":
                        partite.append({"Girone": g, "Giornata": giornata+1 + (n-1),
                                         "Casa": ospite, "Ospite": casa, "GolCasa": None, "GolOspite": None, "Valida": False})
            teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    return pd.DataFrame(partite)

def aggiorna_classifica(df):
    gironi = df['Girone'].dropna().unique()
    classifiche = []
    for girone in gironi:
        partite = df[(df['Girone']==girone) & (df['Valida']==True)]
        if partite.empty: continue
        squadre = pd.unique(partite[['Casa','Ospite']].values.ravel())
        stats = {s:{'Punti':0,'V':0,'P':0,'S':0,'GF':0,'GS':0,'DR':0} for s in squadre}
        for _, r in partite.iterrows():
            try: gc, go = int(r['GolCasa']), int(r['GolOspite'])
            except: gc, go = 0,0
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
    if len(classifiche)==0: return pd.DataFrame()
    df_classifica = pd.concat(classifiche, ignore_index=True)
    df_classifica = df_classifica.sort_values(by=['Girone','Punti','DR'], ascending=[True,False,False])
    return df_classifica

def salva_giornata(df, girone_sel, giornata_sel):
    df_giornata = df[(df['Girone']==girone_sel) & (df['Giornata']==giornata_sel)]
    for idx,_ in df_giornata.iterrows():
        df.at[idx,'GolCasa'] = st.session_state.get(f"golcasa_{idx}", df.at[idx,'GolCasa'])
        df.at[idx,'GolOspite'] = st.session_state.get(f"golospite_{idx}", df.at[idx,'GolOspite'])
        df.at[idx,'Valida'] = st.session_state.get(f"valida_{idx}", df.at[idx,'Valida'])
    st.session_state['df_torneo'] = df
    st.success("💾 Risultati salvati!")

def esporta_pdf(df_torneo, df_classifica):
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial",'B',16)
    pdf.cell(0,10,"Calendario e Classifiche Torneo",ln=True,align='C')
    for girone in df_torneo['Girone'].dropna().unique():
        pdf.set_font("Arial",'B',14); pdf.ln(3); pdf.cell(0,8,f"{girone}",ln=True)
        for g in sorted(df_torneo[df_torneo['Girone']==girone]['Giornata'].unique()):
            pdf.set_font("Arial",'B',12); pdf.cell(0,7,f"Giornata {g}",ln=True)
            pdf.set_font("Arial",'B',11); pdf.cell(60,6,"Casa",1); pdf.cell(20,6,"Gol",1); pdf.cell(20,6,"Gol",1); pdf.cell(60,6,"Ospite",1); pdf.ln()
            pdf.set_font("Arial",'',11)
            for _, r in df_torneo[(df_torneo['Girone']==girone)&(df_torneo['Giornata']==g)].iterrows():
                pdf.cell(60,6,str(r['Casa']),1); pdf.cell(20,6,str(r['GolCasa'] or ""),1); pdf.cell(20,6,str(r['GolOspite'] or ""),1); pdf.cell(60,6,str(r['Ospite']),1); pdf.ln()
    return pdf

# ------------------------- Interfaccia Streamlit -------------------------
st.title("⚽ Torneo Subbuteo - Sistema Svizzero")

# Caricamento giocatori
modo = st.radio("Caricamento giocatori", ["Da DB Mongo", "Da CSV"])
if modo=="Da DB Mongo":
    df_giocatori = carica_giocatori_da_db()
else:
    uploaded_file = st.file_uploader("Carica CSV giocatori", type=["csv"])
    if uploaded_file:
        df_giocatori = pd.read_csv(uploaded_file)
    else:
        df_giocatori = pd.DataFrame()

st.write(f"Totale giocatori: {len(df_giocatori)}")
st.dataframe(df_giocatori)

# Creazione gironi
num_gironi = st.number_input("Numero gironi", min_value=1, max_value=10, value=2)
btn_crea_gironi = st.button("Crea gironi casuali")
if btn_crea_gironi and not df_giocatori.empty:
    giocatori = df_giocatori['Nome'].tolist() if 'Nome' in df_giocatori.columns else df_giocatori.iloc[:,0].tolist()
    random.shuffle(giocatori)
    gironi = [giocatori[i::num_gironi] for i in range(num_gironi)]
    st.session_state['gironi'] = gironi
    st.success("✅ Gironi creati")
    for i,g in enumerate(gironi,1): st.write(f"Girone {i}: {g}")

# Genera calendario
tipo_giornate = st.selectbox("Tipo calendario", ["Solo andata","Andata e ritorno"])
if st.button("Genera calendario"):
    if 'gironi' in st.session_state:
        df_torneo = genera_calendario(st.session_state['gironi'], tipo_giornate)
        st.session_state['df_torneo'] = df_torneo
        st.success("📅 Calendario generato")
        st.dataframe(df_torneo)
    else: st.warning("Crea prima i gironi")

# Seleziona girone e giornata per inserimento risultati
if 'df_torneo' in st.session_state:
    girone_sel = st.selectbox("Seleziona girone", st.session_state['df_torneo']['Girone'].unique())
    giornate_sel = sorted(st.session_state['df_torneo'][st.session_state['df_torneo']['Girone']==girone_sel]['Giornata'].unique())
    giornata_sel = st.selectbox("Seleziona giornata", giornate_sel)
    df_giornata = st.session_state['df_torneo'][(st.session_state['df_torneo']['Girone']==girone_sel) & (st.session_state['df_torneo']['Giornata']==giornata_sel)]
    st.subheader(f"Giornata {giornata_sel} - {girone_sel}")
    for idx, row in df_giornata.iterrows():
        col1,col2,col3,col4,col5 = st.columns([5,1.5,1,1.5,1])
        with col1: st.markdown(f"**{row['Casa']}** vs **{row['Ospite']}**")
        with col2: st.session_state[f"golcasa_{idx}"] = col2.number_input("",0,20,value=row['GolCasa'] or 0,key=f"golcasa_{idx}",label_visibility="hidden")
        with col3: st.markdown("-")
        with col4: st.session_state[f"golospite_{idx}"] = col4.number_input("",0,20,value=row['GolOspite'] or 0,key=f"golospite_{idx}",label_visibility="hidden")
        with col5: st.session_state[f"valida_{idx}"] = col5.checkbox("Valida",value=row['Valida'],key=f"valida_{idx}")
    st.button("💾 Salva Risultati", on_click=salva_giornata, args=(st.session_state['df_torneo'], girone_sel, giornata_sel))

# Mostra classifica aggiornata
if 'df_torneo' in st.session_state:
    df_classifica = aggiorna_classifica(st.session_state['df_torneo'])
    st.subheader("🏆 Classifica Generale")
    st.dataframe(df_classifica)

# Esporta PDF
if st.button("📄 Esporta PDF"):
    if 'df_torneo' in st.session_state:
        pdf = esporta_pdf(st.session_state['df_torneo'], df_classifica)
        pdf_file = f"Torneo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf.output(pdf_file)
        st.success(f"PDF generato: {pdf_file}")
