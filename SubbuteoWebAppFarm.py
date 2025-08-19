import streamlit as st

# Configurazione pagina
st.set_page_config(
    page_title="Hub Tornei Subbuteo",
    page_icon="🏆",
    layout="centered"
)

st.title("🎯 Hub Tornei Subbuteo")
st.write("Seleziona la web app da aprire:")

# CSS per rendere i link come bottoni
st.markdown("""
    <style>
    .hub-button {
        display: inline-block;
        padding: 15px 25px;
        margin: 10px;
        font-size: 18px;
        font-weight: bold;
        color: white;
        background-color: #4CAF50;
        border-radius: 12px;
        text-decoration: none;
        transition: 0.3s;
    }
    .hub-button:hover {
        background-color: #45a049;
    }
    </style>
""", unsafe_allow_html=True)

# Bottoni (in realtà link stilizzati)
st.markdown('<a class="hub-button" href="https://torneo-subbuteo-superba.streamlit.app/" target="_blank">🏁 Campionato / Fase Preliminare</a>', unsafe_allow_html=True)
st.markdown('<a class="hub-button" href="https://torneo-subbuteo-finali.streamlit.app/" target="_blank">🏆 Fase Finale</a>', unsafe_allow_html=True)
st.markdown('<a class="hub-button" href="https://torneosvizzerobylegnaxclub.streamlit.app/" target="_blank">🇨🇭 Torneo Svizzero x Club</a>', unsafe_allow_html=True)
