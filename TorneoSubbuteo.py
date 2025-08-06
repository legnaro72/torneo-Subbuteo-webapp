import streamlit as st
import pandas as pd
import math
import random

st.set_page_config(page_title="Gestione Torneo a Gironi by Legnaro72", layout="wide")

# 🌐 Stile responsive
st.markdown("""
    <style>
        .block-container {
            padding: 1rem 1rem 2rem 1rem;
        }
        h1, h2, h3 {
            text-align: center;
        }
        .stDownloadButton {
            margin-top: 1em;
        }
        .stCheckbox > label {
            font-size: 0.9rem;
        }
    </style>
""", unsafe_allow_html=True)

# ================= FUNZIONI ===================

# ⏱ Generazione calendario
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

# 🧮 Calcolo classifica
def aggiorna_classifica(df):
    gironi = df['Girone'].dropna().unique()
    classifiche = []

    for girone in gironi:
        partite = df[(df['Girone'] == girone) & (df['Valida'] == True)]
        squadre = pd.unique(partite[['Casa','Ospite']].values.ravel())
        stats = {s: {'Punti':0,'V':0,'P':0,'S':0,'GF':0,'GS':0,'DR':0} for s in squadre}

        for _, r in partite.iterrows():
            gc, go = int(r['GolCasa']), int(r['GolOspite'])
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

    # Controllo se ci sono dati prima di ordinare
    if not classifiche:
        return pd.DataFrame()  # nessuna partita valida

    df_classifica = pd.concat(classifiche, ignore_index=True)

    # Controllo colonne prima del sort
    colonne_necessarie = ['Girone','Punti','DR']
    for col in colonne_necessarie:
        if col not in df_classifica.columns:
            df_classifica[col] = 0  # assegna zero se manca

    # Ordina in sicurezza
    df_classifica = df_classifica.sort_values(by=['Girone','Punti','DR'], ascending=[True,False,False])
    return df_classifica



# ✅ Inserimento risultati compatto e mobile-friendly
def modifica_risultati_compatti(df_giornata, key_prefix):
    for i, r in df_giornata.iterrows():
        with st.container():
            st.markdown(f"**{r['Casa']}** vs **{r['Ospite']}**")
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                gol_casa = st.number_input("Gol Casa", 0, 20, key=f"{key_prefix}_casa_{i}", value=int(r['GolCasa']) if pd.notna(r['GolCasa']) else 0)
            with col2:
                gol_ospite = st.number_input("Gol Ospite", 0, 20, key=f"{key_prefix}_ospite_{i}", value=int(r['GolOspite']) if pd.notna(r['GolOspite']) else 0)
            with col3:
                valida = st.checkbox("✔ Valida", key=f"{key_prefix}_valida_{i}", value=r['Valida'])
            df_giornata.at[i, 'GolCasa'] = gol_casa
            df_giornata.at[i, 'GolOspite'] = gol_ospite
            df_giornata.at[i, 'Valida'] = valida
    return df_giornata

# 🏆 Fasi finali
def seleziona_qualificate(classifica):
    prime = classifica.groupby('Girone').apply(lambda df: df.nlargest(1, 'Punti')).reset_index(drop=True)
    semifinalisti_tot = 4
    num_prime = len(prime)
    if num_prime < semifinalisti_tot:
        escluse_prime = classifica[~classifica['Squadra'].isin(prime['Squadra'])]
        migliori_seconde = escluse_prime.nlargest(semifinalisti_tot - num_prime, 'Punti')
        qualificate = pd.concat([prime, migliori_seconde])
    else:
        qualificate = prime.head(semifinalisti_tot)
    return qualificate.sort_values(by='Punti', ascending=False).reset_index(drop=True)

def genera_fasi_finali(classifica):
    qualificate = seleziona_qualificate(classifica)
    if len(qualificate) < 4:
        return pd.DataFrame(columns=["Fase", "Match", "Squadra1", "Squadra2", "Gol1", "Gol2"])
    partite = [
        {"Fase": "Semifinale", "Match": 1, "Squadra1": qualificate.iloc[0]['Squadra'], "Squadra2": qualificate.iloc[3]['Squadra'], "Gol1": None, "Gol2": None},
        {"Fase": "Semifinale", "Match": 2, "Squadra1": qualificate.iloc[1]['Squadra'], "Squadra2": qualificate.iloc[2]['Squadra'], "Gol1": None, "Gol2": None},
        {"Fase": "Finale 3° Posto", "Match": 3, "Squadra1": None, "Squadra2": None, "Gol1": None, "Gol2": None},
        {"Fase": "Finale", "Match": 4, "Squadra1": None, "Squadra2": None, "Gol1": None, "Gol2": None},
    ]
    return pd.DataFrame(partite)

# ========== MAIN ==========
def main():
    st.title("🏆 Gestione Torneo a Gironi by Legnaro72")
    scelta = st.sidebar.radio("⚙️ Azione:", ["Nuovo torneo", "Carica torneo da CSV"])

    if scelta == "Nuovo torneo":
        num_gironi = st.number_input("Numero di gironi", 1, 8, value=2)
        tipo_calendario = st.selectbox("Tipo calendario", ["Solo andata", "Andata e ritorno"])
        nomi = st.text_area("Inserisci nomi giocatori (separati da virgola)")
        if st.button("🎲 Genera torneo"):
            giocatori = [n.strip() for n in nomi.split(",") if n.strip()]
            if len(giocatori) < 4:
                st.warning("Inserisci almeno 4 giocatori")
            else:
                df = genera_calendario(giocatori, num_gironi, tipo_calendario)
                st.session_state['df_torneo'] = df

    elif scelta == "Carica torneo da CSV":
        file = st.file_uploader("📂 Carica file CSV", type="csv")
        if file:
            df = pd.read_csv(file)
            st.session_state['df_torneo'] = df

    if 'df_torneo' in st.session_state:
        df = st.session_state['df_torneo']
        gironi = df['Girone'].dropna().unique()
        girone_sel = st.sidebar.selectbox("🌀 Seleziona girone", gironi)
        giornate = sorted(df[df['Girone']==girone_sel]['Giornata'].dropna().unique())
        giornata_sel = st.sidebar.selectbox("📅 Giornata", giornate)

        df_giornata = df[(df['Girone']==girone_sel) & (df['Giornata']==giornata_sel)].copy()
        if 'Valida' not in df_giornata.columns:
            df_giornata['Valida'] = False

        st.subheader(f"{girone_sel} - Giornata {giornata_sel}")
        df_mod = modifica_risultati_compatti(df_giornata, key_prefix=f"{girone_sel}_{giornata_sel}")
        for i, row in df_mod.iterrows():
            idx = row.name
            st.session_state['df_torneo'].at[idx, 'GolCasa'] = row['GolCasa']
            st.session_state['df_torneo'].at[idx, 'GolOspite'] = row['GolOspite']
            st.session_state['df_torneo'].at[idx, 'Valida'] = row['Valida']

        classifica = aggiorna_classifica(st.session_state['df_torneo'])
        st.subheader(f"📊 Classifica {girone_sel}")
        st.dataframe(classifica[classifica['Girone'] == girone_sel], use_container_width=True)

        if st.button("🔍 Mostra tutte le classifiche"):
            st.subheader("📋 Classifiche complete")
            gironi_unici = classifica['Girone'].unique()
            for girone in gironi_unici:
                with st.expander(f"🔸 {girone}"):
                    st.dataframe(classifica[classifica['Girone'] == girone].reset_index(drop=True), use_container_width=True)

        with st.expander("🎯 Filtra partite ancora da giocare per squadra"):
            squadre = pd.unique(df[['Casa', 'Ospite']].values.ravel())
            squadra_scelta = st.selectbox("Seleziona squadra", squadre)
            partite_da_giocare = df[
                (df['Valida'] == False) & 
                ((df['Casa'] == squadra_scelta) | (df['Ospite'] == squadra_scelta))
            ]
            st.dataframe(partite_da_giocare, use_container_width=True)

        csv = st.session_state['df_torneo'].to_csv(index=False)
        st.markdown('<div style="text-align: center;">', unsafe_allow_html=True)
        st.download_button("📥 Scarica CSV Torneo", csv, "torneo.csv", "text/csv")
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == '__main__':
    main()
