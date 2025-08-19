import streamlit as st
import pandas as pd
import random

st.set_page_config(page_title="Fase Finale Torneo", layout="wide")

# --- Funzione per calcolare classifica finale dal CSV caricato ---
def calcola_classifica(df):
    partite = df[df['Valida'] == True]
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
    df_stat = df_stat.sort_values(by=['Punti','DR'], ascending=[False,False]).reset_index(drop=True)
    return df_stat


# --- Interfaccia ---
st.title("🏆 Fase Finale Torneo")

uploaded = st.file_uploader("📁 Carica il CSV del torneo concluso", type=["csv"])

if uploaded:
    df = pd.read_csv(uploaded)

    # Controllo che tutte le partite siano giocate e validate
    if not all(df['Valida'] == True):
        st.error("❌ Non tutte le partite sono state validate. Carica un torneo COMPLETO.")
    else:
        st.success("✅ Torneo completo caricato!")

        classifica = calcola_classifica(df)
        st.subheader("Classifica finale")
        st.dataframe(classifica, use_container_width=True)

        st.write("---")
        st.subheader("Scegli formula fase finale:")

        formula = st.radio("Formula", ["Gironi", "Eliminazione diretta"])

        if formula == "Gironi":
            num_gironi = st.number_input("Numero di gironi", 1, 8, 2)
            if st.button("Genera Gironi"):
                squadre = classifica['Squadra'].tolist()
                gironi = [[] for _ in range(num_gironi)]
                for i, squadra in enumerate(squadre):
                    gironi[i % num_gironi].append(squadra)

                st.success("✅ Gironi generati!")
                for i, g in enumerate(gironi, 1):
                    st.write(f"**Girone {i}**: {', '.join(g)}")

        elif formula == "Eliminazione diretta":
            turno = st.selectbox("Parti da", ["Ottavi", "Quarti", "Semifinali"])
            mapping = {"Ottavi":16, "Quarti":8, "Semifinali":4}
            n = mapping[turno]

            if len(classifica) < n:
                st.warning(f"⚠️ Servono almeno {n} squadre per partire dagli {turno.lower()}.")
            else:
                if st.button("Genera Tabellone"):
                    squadre = classifica['Squadra'].tolist()[:n]
                    abbinamenti = []
                    for i in range(n//2):
                        abbinamenti.append((squadre[i], squadre[-(i+1)]))

                    st.success(f"✅ Tabellone {
