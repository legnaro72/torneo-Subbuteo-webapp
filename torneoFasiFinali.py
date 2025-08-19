import streamlit as st
import pandas as pd
import random

# ======================
# FUNZIONI DI SUPPORTO
# ======================

def classifica_complessiva(df):
    """Calcola la classifica generale dal CSV importato."""
    squadre = set(df['Squadra1']).union(set(df['Squadra2']))
    data = {s: {"Punti": 0, "GF": 0, "GS": 0, "DR": 0} for s in squadre}

    for _, row in df.iterrows():
        if pd.isna(row["Gol1"]) or pd.isna(row["Gol2"]):
            continue
        g1, g2 = int(row["Gol1"]), int(row["Gol2"])
        s1, s2 = row["Squadra1"], row["Squadra2"]

        data[s1]["GF"] += g1
        data[s1]["GS"] += g2
        data[s1]["DR"] = data[s1]["GF"] - data[s1]["GS"]

        data[s2]["GF"] += g2
        data[s2]["GS"] += g1
        data[s2]["DR"] = data[s2]["GF"] - data[s2]["GS"]

        if g1 > g2:
            data[s1]["Punti"] += 3
        elif g2 > g1:
            data[s2]["Punti"] += 3
        else:
            data[s1]["Punti"] += 1
            data[s2]["Punti"] += 1

    df_class = pd.DataFrame.from_dict(data, orient="index").reset_index()
    df_class = df_class.rename(columns={"index": "Squadra"})
    df_class = df_class.sort_values(by=["Punti", "DR", "GF"], ascending=[False, False, False]).reset_index(drop=True)
    return df_class

def reset_fase_finale():
    """Reset variabili di sessione per rigenerare la fase finale."""
    st.session_state['fase_generata'] = None
    st.session_state['gironi_fase'] = None
    st.session_state['tabellone_ko'] = None


# ======================
# APP STREAMLIT
# ======================

st.set_page_config(page_title="Fasi Finali Torneo", layout="wide")

st.title("🏆 Fasi Finali Torneo Subbuteo")

# Upload CSV
uploaded_file = st.file_uploader("📂 Carica il file CSV del torneo", type=["csv"])

if uploaded_file:
    df_in = pd.read_csv(uploaded_file)

    # Mostra CLASSIFICA GENERALE solo se non ho generato la fase finale
    if 'fase_generata' not in st.session_state:
        st.session_state['fase_generata'] = None

    if st.session_state['fase_generata'] is None:
        df_class = classifica_complessiva(df_in)
        st.success("✅ Torneo completo e valido! Classifica calcolata qui sotto.")
        st.dataframe(df_class, use_container_width=True)
        st.divider()

        # Scelta formula fase finale
        colA, colB = st.columns([1,1])
        with colA:
            fase = st.radio("Formula fase finale", ["Gironi", "Eliminazione diretta"], key="fase_scelta", horizontal=True)

        if fase == "Gironi":
            if st.button("🎲 Genera Gironi (serpentina)"):
                reset_fase_finale()
                st.session_state['fase_generata'] = "gironi"
                squadre = classifica_complessiva(df_in)["Squadra"].tolist()
                random.shuffle(squadre)
                n_gironi = 2
                gironi = {f"Girone {i+1}": [] for i in range(n_gironi)}
                for i, squadra in enumerate(squadre):
                    gironi[f"Girone {(i % n_gironi)+1}"].append(squadra)
                st.session_state['gironi_fase'] = gironi

        elif fase == "Eliminazione diretta":
            if st.button("🧩 Genera Tabellone KO"):
                reset_fase_finale()
                st.session_state['fase_generata'] = "ko"
                squadre = classifica_complessiva(df_in)["Squadra"].tolist()
                random.shuffle(squadre)
                tabellone = []
                for i in range(0, len(squadre), 2):
                    if i+1 < len(squadre):
                        tabellone.append((squadre[i], squadre[i+1]))
                st.session_state['tabellone_ko'] = tabellone

    # Mostra FASE FINALE
    if st.session_state['fase_generata'] == "gironi":
        st.subheader("📊 Gironi Fase Finale")
        gironi = st.session_state['gironi_fase']
        for g, squadre in gironi.items():
            st.markdown(f"**{g}**")
            for s in squadre:
                st.write(f"▫️ {s}")
            st.divider()

    elif st.session_state['fase_generata'] == "ko":
        st.subheader("⚔️ Tabellone Eliminazione Diretta")
        for i, match in enumerate(st.session_state['tabellone_ko'], 1):
            st.write(f"Match {i}: **{match[0]}** vs **{match[1]}**")
        st.divider()
