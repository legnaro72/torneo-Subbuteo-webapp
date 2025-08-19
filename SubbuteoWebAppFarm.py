import streamlit as st

# Configurazione pagina
st.set_page_config(
    page_title="Hub Tornei Subbuteo",
    page_icon="🏆",
    layout="wide"
)

st.title("🎯 Hub Tornei Subbuteo")
st.write("Benvenuto! Seleziona la modalità di torneo che vuoi gestire:")

# --- CSS per cards ---
st.markdown("""
    <style>
    .card {
        background-color: #262730;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.3);
        text-align: center;
        color: white;
        transition: transform 0.2s;
    }
    .card:hover {
        transform: scale(1.05);
    }
    .card-title {
        font-size: 22px;
        font-weight: bold;
        margin-bottom: 10px;
    }
    .card-desc {
        font-size: 16px;
        margin-bottom: 20px;
        color: #ddd;
    }
    .card-link {
        display: inline-block;
        padding: 10px 18px;
        font-size: 16px;
        font-weight: bold;
        color: white;
        background-color: #4CAF50;
        border-radius: 10px;
        text-decoration: none;
    }
    .card-link:hover {
        background-color: #45a049;
    }
    </style>
""", unsafe_allow_html=True)

# --- Layout in 3 colonne ---
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
        <div class="card">
            <div class="card-title">🏁 Campionato / Fase Preliminare</div>
            <div class="card-desc">
                Da usare per disputare un campionato o la <b>prima parte</b> di un torneo 
                articolato che prevede una successiva fase finale.
            </div>
            <a class="card-link" href="h
