import streamlit as st
import pandas as pd
import random

# ======================================================
# Funzioni di utilità
# ======================================================

def classifica_complessiva(df):
    """Calcola la classifica complessiva dal dataframe delle partite."""
    squadre = pd.concat([df['Squadra A'], df['Squadra B']]).unique()
    data = []
    for squadra in squadre:
        giocate = vinte = pareggiate = perse = gol_fatti = gol_subiti = punti = 0
        for _, r in df.iterrows():
            if pd.isna(r['Gol A']) or pd.isna(r['Gol B']):
                continue
            if r['Squadra A'] == squadra or r['Squadra B'] == squadra:
                giocate += 1
                if r['Squadra A'] == squadra:
                    gf, gs = r['Gol A'], r['Gol B']
                else:
                    gf, gs = r['Gol B'], r['Gol A']
                gol_fatti += gf
                gol_subiti += gs
                if gf > gs:
                    vinte += 1
                    punti += 3
                elif gf == gs:
                    pareggiate += 1
                    punti += 1
                else:
                    perse += 1
        data.append([squadra, giocate, vinte, pareggiate, perse, gol_fatti, gol_subiti, punti])

    df_class = pd.DataFrame(data, columns=["Squadra","G","V","N","P","GF","GS","Pt"])
    df_class['DR'] = df_class['GF'] - df_class['GS']
    df_class = df_class.sort_values(by=["Pt","DR","GF"], ascending=[False,False,False]).reset_index(drop=True)
    return df_class


def reset_fase_finale():
    """Resetta lo stato della fase finale."""
    keys = ['fase_generata', 'gironi', 'giorni_gironi', 'calendario', 'tabellone']
    for k in keys:
        if k in st.session_state:
            del st.session_state[k]


def genera_gironi_serpentina(df_class, num_gironi=2):
    """Genera i gironi con metodo serpentina a partire dalla classifica."""
    squadre = df_class['Squadra'].tolist()
    gironi = {f"Girone {i+1}": [] for i in range(num_gironi)}
    direction = 1
    idx_girone = 0
    for squadra in squadre:
        gironi[f"Girone {idx_girone+1}"].append(squadra)
        if direction == 1:
            if idx_girone == num_gironi-1:
                direction = -1
                idx_girone -= 1
            else:
                idx_girone += 1
        else:
            if idx_girone == 0:
                direction = 1
                idx_girone += 1
            else:
                idx_girone -= 1
    return gironi


def genera_calendario_girone(squadre):
    """Genera il calendario di un girone con round robin."""
    if len(squadre) % 2:
        squadre.append("Riposo")
    n = len(squadre)
    calendario = []
    for i in range(n-1):
        giornata = []
        for j in range(n//2):
            a, b = squadre[j], squadre[n-1-j]
            if a != "Riposo" and b != "Riposo":
                giornata.append((a, b))
        squadre.insert(1, squadre.pop())
        calendario.append(giornata)
    return calendario


def mostra_calendario_gironi(gironi, calendario):
    """Mostra in Streamlit il calendario dei gironi."""
    for g, giornate in calendario.items():
        st.subheader(f"📅 {g}")
        for i, partite in enumerate(giornate, 1):
            st.markdown(f"**Giornata {i}**")
            for a, b in partite:
                st.write(f"{a} 🆚 {b}")


def genera_tabellone(df_class, n=8):
    """Genera il tabellone KO prendendo le prime n squadre."""
    qualificate = df_class.head(n)['Squadra'].tolist()
    random.shuffle(qualificate)
    tabellone = []
    for i in range(0, len(qualificate), 2):
        tabellone.append((qualificate[i], qualificate[i+1]))
    return tabellone


def mostra_tabellone(tabellone):
    """Mostra in Streamlit il tabellone KO."""
    st.subheader("🏆 Tabellone Eliminazione Diretta")
    for a, b in tabellone:
        st.write(f"{a} ⚔️ {b}")


# ======================================================
# App Streamlit
# ======================================================

st.set_page_config(page_title="Torneo - Fasi Finali", layout="wide")

st.title("🏆 Gestione Fasi Finali Torneo")

# Dati di esempio (partite giocate nei gironi)
data = {
    "Squadra A": ["Milan","Inter","Juve","Roma","Lazio","Napoli"],
    "Squadra B": ["Inter","Juve","Roma","Lazio","Napoli","Milan"],
    "Gol A": [1,2,2,1,3,0],
    "Gol B": [0,2,1,1,1,2],
}
df_in = pd.DataFrame(data)

# Inizializza flag
if 'fase_generata' not in st.session_state:
    st.session_state['fase_generata'] = None

# Se non ho ancora generato nulla → Mostro classifica + scelta fase finale
if st.session_state['fase_generata'] is None:
    st.success("✅ Torneo completo e valido! Classifica calcolata qui sotto.")
    df_class = classifica_complessiva(df_in)
    st.dataframe(df_class, use_container_width=True)

    st.divider()

    colA, colB = st.columns([1,1])
    with colA:
        fase = st.radio("Formula fase finale", ["Gironi", "Eliminazione diretta"], key="fase_scelta", horizontal=True)

    st.markdown("<span class='small-muted'>Le squadre vengono **estratte dal CSV** ...</span>", unsafe_allow_html=True)
    st.write("")

    # --- Bottone Gironi
    if fase == "Gironi":
        num_gironi = st.number_input("Numero di gironi", min_value=2, max_value=4, value=2, step=1)
        if st.button("🎲 Genera Gironi (serpentina)"):
            reset_fase_finale()
            st.session_state['fase_generata'] = "gironi"
            st.session_state['gironi'] = genera_gironi_serpentina(df_class, num_gironi)
            st.session_state['calendario'] = {g: genera_calendario_girone(list(sq)) for g, sq in st.session_state['gironi'].items()}

    # --- Bottone Eliminazione diretta
    elif fase == "Eliminazione diretta":
        n = st.number_input("Numero squadre per KO", min_value=2, max_value=16, value=8, step=2)
        if st.button("🧩 Genera tabellone iniziale"):
            reset_fase_finale()
            st.session_state['fase_generata'] = "ko"
            st.session_state['tabellone'] = genera_tabellone(df_class, n)

else:
    # Classifica serve comunque per i calcoli
    df_class = classifica_complessiva(df_in)

# ======================================================
# Mostra solo la parte scelta
# ======================================================

if st.session_state['fase_generata'] == "gironi":
    st.header("📊 Assegnazione Gironi")
    for g, sq in st.session_state['gironi'].items():
        st.write(f"**{g}**: {', '.join(sq)}")

    st.divider()
    mostra_calendario_gironi(st.session_state['gironi'], st.session_state['calendario'])

elif st.session_state['fase_generata'] == "ko":
    mostra_tabellone(st.session_state['tabellone'])
