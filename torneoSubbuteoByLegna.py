import streamlit as st
import pandas as pd
import math
import random

st.set_page_config(page_title="Gestione Torneo a Gironi by Legnaro72", layout="wide")

# Funzione per generare calendario gironi
def genera_calendario(giocatori, num_gironi):
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
            teams = [teams[0]] + [teams[-1]] + teams[1:-1]

    return pd.DataFrame(partite)

# Calcolo classifica da partite validate
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
    return pd.concat(classifiche, ignore_index=True)



def interfaccia_partite_finali(df_fasi):
    st.subheader("Fasi Finali")
    for i, row in df_fasi.iterrows():
        col1, col2, col3 = st.columns([4,1,4])
        with col1:
            st.markdown(f"**{row['Squadra1']}**")
        with col2:
            gol1 = st.number_input("", 0, 20, key=f"g1_{i}", value=int(row['Gol1']) if pd.notna(row['Gol1']) else 0)
        with col3:
            st.markdown(f"**{row['Squadra2']}**")
            gol2 = st.number_input("", 0, 20, key=f"g2_{i}", value=int(row['Gol2']) if pd.notna(row['Gol2']) else 0)
        valida = st.checkbox("Valida", key=f"valida_{i}", value=row['Valida'])
        df_fasi.at[i, 'Gol1'] = gol1
        df_fasi.at[i, 'Gol2'] = gol2
        df_fasi.at[i, 'Valida'] = valida

    semi = df_fasi[df_fasi['Fase'] == 'Semifinale']
    if len(semi) == 2 and semi['Valida'].all():
        vincente1 = semi.iloc[0]['Squadra1'] if semi.iloc[0]['Gol1'] > semi.iloc[0]['Gol2'] else semi.iloc[0]['Squadra2']
        vincente2 = semi.iloc[1]['Squadra1'] if semi.iloc[1]['Gol1'] > semi.iloc[1]['Gol2'] else semi.iloc[1]['Squadra2']
        perdente1 = semi.iloc[0]['Squadra2'] if vincente1 == semi.iloc[0]['Squadra1'] else semi.iloc[0]['Squadra1']
        perdente2 = semi.iloc[1]['Squadra2'] if vincente2 == semi.iloc[1]['Squadra1'] else semi.iloc[1]['Squadra1']
        df_fasi.loc[df_fasi['Fase'] == 'Finale', ['Squadra1','Squadra2']] = [vincente1, vincente2]
        df_fasi.loc[df_fasi['Fase'] == 'Finale 3° Posto', ['Squadra1','Squadra2']] = [perdente1, perdente2]
    return df_fasi

# Inserimento compatto risultati girone
def modifica_risultati_compatti(df_giornata, key_prefix):
    for i, r in df_giornata.iterrows():
        col1, col2, col3, col4, col5, col6 = st.columns([3,1,1,1,3,2])
        with col1: st.markdown(f"**{r['Casa']}**")
        with col2:
            gol_casa = st.number_input("", 0, 20, key=f"{key_prefix}_casa_{i}", value=int(r['GolCasa']) if pd.notna(r['GolCasa']) else 0)
        with col3: st.markdown(" - ")
        with col4:
            gol_ospite = st.number_input("", 0, 20, key=f"{key_prefix}_ospite_{i}", value=int(r['GolOspite']) if pd.notna(r['GolOspite']) else 0)
        with col5: st.markdown(f"**{r['Ospite']}**")
        with col6:
            valida = st.checkbox("✔", key=f"{key_prefix}_valida_{i}", value=r['Valida'])
        df_giornata.at[i, 'GolCasa'] = gol_casa
        df_giornata.at[i, 'GolOspite'] = gol_ospite
        df_giornata.at[i, 'Valida'] = valida
    return df_giornata

def seleziona_qualificate(classifica):
    # Prendi le prime classificate di ogni girone
    prime = classifica.groupby('Girone').apply(lambda df: df.nlargest(1, 'Punti')).reset_index(drop=True)

    semifinalisti_tot = 4
    num_prime = len(prime)

    if num_prime < semifinalisti_tot:
        escluse_prime = classifica[~classifica['Squadra'].isin(prime['Squadra'])]
        migliori_seconde = escluse_prime.nlargest(semifinalisti_tot - num_prime, 'Punti')
        qualificate = pd.concat([prime, migliori_seconde])
    else:
        qualificate = prime.head(semifinalisti_tot)

    qualificate = qualificate.sort_values(by='Punti', ascending=False).reset_index(drop=True)
    return qualificate


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

    df_fasi_finali = pd.DataFrame(partite)
    return df_fasi_finali



def main():
    st.title("Gestione Torneo a Gironi by Legnaro72")
    scelta = st.sidebar.radio("Scegli azione:", ["Nuovo torneo", "Carica torneo da CSV"])

    if scelta == "Nuovo torneo":
        num_gironi = st.number_input("Numero di gironi", 1, 8, value=2)
        nomi = st.text_area("Inserisci nomi giocatori (separati da virgola)")
        if st.button("Genera torneo"):
            giocatori = [n.strip() for n in nomi.split(",") if n.strip()]
            if len(giocatori) < 4:
                st.warning("Inserisci almeno 4 giocatori")
            else:
                df = genera_calendario(giocatori, num_gironi)
                st.session_state['df_torneo'] = df

    elif scelta == "Carica torneo da CSV":
        file = st.file_uploader("Carica file CSV", type="csv")
        if file:
            df = pd.read_csv(file)
            st.session_state['df_torneo'] = df


    if 'df_torneo' in st.session_state:
        df = st.session_state['df_torneo']
        gironi = df['Girone'].dropna().unique()
        girone_sel = st.sidebar.selectbox("Seleziona girone", gironi)
        giornate = sorted(df[df['Girone']==girone_sel]['Giornata'].dropna().unique())
        giornata_sel = st.sidebar.selectbox("Giornata", giornate)

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
        st.subheader(f"Classifica {girone_sel}")
        st.dataframe(classifica[classifica['Girone'] == girone_sel])

        # Bottone per mostrare tutte le classifiche dei gironi
        if st.button("Mostra tutte le classifiche dei gironi"):
            st.subheader("Classifiche complete")
            gironi_unici = classifica['Girone'].unique()
            colonne = st.columns(len(gironi_unici))
            for idx, girone in enumerate(gironi_unici):
                with colonne[idx]:
                    st.markdown(f"**{girone}**")
                    st.dataframe(classifica[classifica['Girone'] == girone].reset_index(drop=True))

        csv = st.session_state['df_torneo'].to_csv(index=False)
        st.download_button("Scarica CSV Torneo", csv, "torneo.csv", "text/csv")

if __name__ == '__main__':
    main()
