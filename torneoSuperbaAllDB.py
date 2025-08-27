
import streamlit as st
import pandas as pd
import random
from fpdf import FPDF
from datetime import datetime
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId

# =================================================
# CONFIGURAZIONE PAGINA
# =================================================
st.set_page_config(page_title="⚽ Campionato Subbuteo", layout="wide")

# =================================================
# STATO DI DEFAULT
# =================================================
DEFAULT_STATE = {
    'df_torneo': pd.DataFrame(),
    'calendario_generato': False,
    'mostra_form_creazione': False,
    'girone_sel': "Girone 1",
    'giornata_sel': 1,
    'mostra_assegnazione_squadre': False,
    'mostra_gironi': False,
    'gironi_manuali_completi': False,
    'giocatori_selezionati_definitivi': [],
    'gioc_info': {},
    'filtro_attivo': 'Nessuno',
    'torneo_completato': False,
    'classifica_finale': None
}

for k, v in DEFAULT_STATE.items():
    if k not in st.session_state:
        st.session_state[k] = v

def reset_app_state():
    st.session_state.clear()
    st.session_state.update(DEFAULT_STATE)

# =================================================
# UTILITY UI
# =================================================
def load_custom_css():
    st.markdown("""
        <style>
        .big-title {
            text-align: center;
            font-size: clamp(22px, 4vw, 40px);
            font-weight: bold;
            margin: 15px 0;
            color: #e63946;
        }
        .stButton>button {
            background-color: #457b9d; color: white;
            border-radius: 8px; padding: 0.5em 1em;
            font-weight: bold;
        }
        .stButton>button:hover { background-color: #1d3557; }
        .stDownloadButton>button {
            background-color: #2a9d8f; color: white; border-radius: 8px;
        }
        .stDownloadButton>button:hover { background-color: #21867a; }
        .stDataFrame { border: 2px solid #f4a261; border-radius: 10px; }
        </style>
    """, unsafe_allow_html=True)

def navigation_buttons(label, value_key, min_val, max_val):
    c1, c2, c3 = st.columns([1,3,1])
    with c1:
        if st.button("◀️", key=f"{value_key}_prev", use_container_width=True):
            st.session_state[value_key] = max(min_val, st.session_state[value_key]-1)
            st.rerun()
    with c2:
        st.markdown(f"<div style='text-align:center; font-weight:bold;'>{label} {st.session_state[value_key]}</div>", unsafe_allow_html=True)
    with c3:
        if st.button("▶️", key=f"{value_key}_next", use_container_width=True):
            st.session_state[value_key] = min(max_val, st.session_state[value_key]+1)
            st.rerun()

# =================================================
# MONGO DB
# =================================================
@st.cache_resource
def init_mongo_connection(uri, db_name, collection_name):
    try:
        client = MongoClient(uri, server_api=ServerApi('1'))
        db = client[db_name]
        return db[collection_name]
    except Exception as e:
        st.error(f"❌ Errore di connessione: {e}")
        return None

def carica_giocatori_da_db(col):
    if not col: return pd.DataFrame()
    try:
        return pd.DataFrame(list(col.find({}, {"_id":0})))
    except: return pd.DataFrame()

def carica_tornei_da_db(col):
    if not col: return []
    try:
        return list(col.find({}, {"nome_torneo":1}))
    except: return []

def carica_torneo_da_db(col, tid):
    try:
        t = col.find_one({"_id": ObjectId(tid)})
        if t and 'calendario' in t:
            df = pd.DataFrame(t['calendario'])
            df['Valida'] = df['Valida'].astype(bool)
            st.session_state['df_torneo'] = df
        return t
    except: return None

def salva_torneo_su_db(col, df, nome):
    try:
        clean = df.where(pd.notna(df), None)
        return col.insert_one({"nome_torneo": nome, "calendario": clean.to_dict('records')}).inserted_id
    except: return None

def aggiorna_torneo_su_db(col, tid, df):
    try:
        clean = df.where(pd.notna(df), None)
        col.update_one({"_id":ObjectId(tid)}, {"$set":{"calendario": clean.to_dict('records')}})
        return True
    except: return False

# =================================================
# LOGICA TORNEO
# =================================================
def genera_calendario(gironi, tipo="Solo andata"):
    partite = []
    for idx,gir in enumerate(gironi,1):
        gname=f"Girone {idx}"
        g=gir[:]
        if len(g)%2: g.append("Riposo")
        n=len(g); half=n//2; teams=g[:]
        for giornata in range(n-1):
            for i in range(half):
                c,o=teams[i],teams[-(i+1)]
                if c!="Riposo" and o!="Riposo":
                    partite.append({"Girone":gname,"Giornata":giornata+1,"Casa":c,"Ospite":o,"GolCasa":None,"GolOspite":None,"Valida":False})
                    if tipo=="Andata e ritorno":
                        partite.append({"Girone":gname,"Giornata":giornata+1+n-1,"Casa":o,"Ospite":c,"GolCasa":None,"GolOspite":None,"Valida":False})
            teams=[teams[0]]+[teams[-1]]+teams[1:-1]
    return pd.DataFrame(partite)

def aggiorna_classifica(df):
    if 'Girone' not in df: return pd.DataFrame()
    out=[]
    for g in df['Girone'].dropna().unique():
        p=df[(df['Girone']==g)&(df['Valida']==True)]
        if p.empty: continue
        teams=pd.unique(p[['Casa','Ospite']].values.ravel())
        stats={t:{'Punti':0,'V':0,'P':0,'S':0,'GF':0,'GS':0,'DR':0} for t in teams}
        for _,r in p.iterrows():
            gc,go=int(r['GolCasa'] or 0),int(r['GolOspite'] or 0)
            c,o=r['Casa'],r['Ospite']
            stats[c]['GF']+=gc; stats[c]['GS']+=go
            stats[o]['GF']+=go; stats[o]['GS']+=gc
            if gc>go: stats[c]['Punti']+=2; stats[c]['V']+=1; stats[o]['S']+=1
            elif gc<go: stats[o]['Punti']+=2; stats[o]['V']+=1; stats[c]['S']+=1
            else: stats[c]['Punti']+=1; stats[o]['Punti']+=1; stats[c]['P']+=1; stats[o]['P']+=1
        for t in teams: stats[t]['DR']=stats[t]['GF']-stats[t]['GS']
        d=pd.DataFrame.from_dict(stats,orient='index').reset_index().rename(columns={'index':'Squadra'}); d['Girone']=g
        out.append(d)
    if not out: return None
    return pd.concat(out).sort_values(by=['Girone','Punti','DR'],ascending=[True,False,False])

# =================================================
# UI FUNZIONI
# =================================================
def mostra_calendario(df,girone,giornata):
    f=df[(df['Girone']==girone)&(df['Giornata']==giornata)]
    if f.empty: return
    for idx,r in f.iterrows():
        c1,c2,c3,c4,c5=st.columns([5,1.5,1,1.5,1])
        with c1: st.markdown(f"**{r['Casa']}** vs **{r['Ospite']}**")
        with c2: st.number_input("",0,20,key=f"gc_{idx}",value=int(r['GolCasa'] or 0),disabled=r['Valida'],label_visibility="hidden")
        with c3: st.markdown("-")
        with c4: st.number_input("",0,20,key=f"go_{idx}",value=int(r['GolOspite'] or 0),disabled=r['Valida'],label_visibility="hidden")
        with c5: st.checkbox("Valida",key=f"valida_{idx}",value=r['Valida'])
        st.markdown("<hr>",unsafe_allow_html=True) if st.session_state[f"valida_{idx}"] else st.markdown("<div style='color:red'>❌ Non validata</div>",unsafe_allow_html=True)

def salva_risultati(col,girone,giornata):
    df=st.session_state['df_torneo']
    f=df[(df['Girone']==girone)&(df['Giornata']==giornata)]
    for idx,_ in f.iterrows():
        df.at[idx,'GolCasa']=st.session_state[f"gc_{idx}"]
        df.at[idx,'GolOspite']=st.session_state[f"go_{idx}"]
        df.at[idx,'Valida']=st.session_state[f"valida_{idx}"]
    st.session_state['df_torneo']=df
    if 'tournament_id' in st.session_state: aggiorna_torneo_su_db(col,st.session_state['tournament_id'],df)
    if df['Valida'].all():
        nome=f"completato_{st.session_state['nome_torneo']}"
        st.session_state['classifica_finale']=aggiorna_classifica(df)
        salva_torneo_su_db(col,df,nome); st.session_state['torneo_completato']=True
    st.rerun()

# =================================================
# MAIN APP
# =================================================
def main():
    load_custom_css()

    players_col=init_mongo_connection(st.secrets["MONGO_URI"],"giocatori_subbuteo","superba_players")
    tourn_col=init_mongo_connection(st.secrets["MONGO_URI_TOURNEMENTS"],"TorneiSubbuteo","Superba")
    df_master=carica_giocatori_da_db(players_col)

    titolo=st.session_state['nome_torneo'] if st.session_state.get('calendario_generato') else "Torneo Superba"
    st.markdown(f"<div class='big-title'>🏆 {titolo}</div>",unsafe_allow_html=True)

    if st.session_state['torneo_completato'] and st.session_state['classifica_finale'] is not None:
        vinc=[f"🏅 {g}: {st.session_state['classifica_finale'][st.session_state['classifica_finale']['Girone']==g].iloc[0]['Squadra']}" for g in st.session_state['classifica_finale']['Girone'].unique()]
        st.success("🎉 Torneo completato! " + ", ".join(vinc)); st.balloons()

    if st.session_state['calendario_generato']:
        st.sidebar.header("⚙️ Opzioni")
        df=st.session_state['df_torneo']
        classifica=aggiorna_classifica(df)
        if classifica is not None:
            st.sidebar.download_button("📄 Esporta PDF", data=b"PDF", file_name="torneo.pdf", mime="application/pdf")
        gironi=sorted(df['Girone'].unique()); giornate=sorted(df[df['Girone']==st.session_state['girone_sel']]['Giornata'].unique())
        nuovo_g=st.selectbox("Seleziona Girone",gironi,index=gironi.index(st.session_state['girone_sel']))
        if nuovo_g!=st.session_state['girone_sel']: st.session_state['girone_sel']=nuovo_g; st.session_state['giornata_sel']=1; st.rerun()
        navigation_buttons("Giornata",'giornata_sel',1,len(giornate))
        mostra_calendario(df,st.session_state['girone_sel'],st.session_state['giornata_sel'])
        st.button("💾 Salva giornata",on_click=salva_risultati,args=(tourn_col,st.session_state['girone_sel'],st.session_state['giornata_sel']))

    else:
        st.subheader("📁 Carica o crea torneo")
        tornei=carica_tornei_da_db(tourn_col)
        if tornei:
            mapping={t['nome_torneo']:str(t['_id']) for t in tornei}
            scelta=st.selectbox("Tornei disponibili",list(mapping.keys()))
            if st.button("Carica"):
                st.session_state['tournament_id']=mapping[scelta]; st.session_state['nome_torneo']=scelta
                t=carica_torneo_da_db(tourn_col,st.session_state['tournament_id'])
                if t: st.session_state['calendario_generato']=True; st.rerun()
        if st.button("➕ Nuovo Torneo"):
            nome=f"Torneo_{datetime.now().strftime('%d%m%Y')}"
            giocatori=df_master['Giocatore'].tolist() if not df_master.empty else []
            if len(giocatori)<4: st.error("Servono almeno 4 giocatori")
            else:
                random.shuffle(giocatori)
                gironi=[giocatori[i::2] for i in range(2)]
                df=genera_calendario(gironi,"Solo andata")
                tid=salva_torneo_su_db(tourn_col,df,nome)
                st.session_state.update({'df_torneo':df,'tournament_id':str(tid),'nome_torneo':nome,'calendario_generato':True})
                st.rerun()

if __name__=="__main__":
    main()
