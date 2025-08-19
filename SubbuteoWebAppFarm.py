import streamlit as st

# Configurazione pagina
st.set_page_config(
    page_title="Hub Tornei Subbuteo",
    page_icon="🏆",
    layout="centered"
)

st.title("🎯 Hub Tornei Subbuteo")
st.write("Seleziona la web app da aprire:")

# Creazione dei bottoni per le altre web app
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🏁 Campionato / Fase Preliminare"):
        st.markdown(
            '[Apri qui](https://torneo-subbuteo-superba.streamlit.app/)',
            unsafe_allow_html=True
        )

with col2:
    if st.button("🏆 Fase Finale"):
        st.markdown(
            '[Apri qui](https://torneo-subbuteo-finali.streamlit.app/)',
            unsafe_allow_html=True
        )

with col3:
    if st.button("🇨🇭 Torneo Svizzero x Club"):
        st.markdown(
            '[Apri qui](https://torneosvizzerobylegnaxclub.streamlit.app/)',
            unsafe_allow_html=True
        )

st.info("Cliccando sul link, la web app si aprirà in una nuova scheda del browser.")
