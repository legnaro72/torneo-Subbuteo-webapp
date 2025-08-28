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
st.markdown('''
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
    .card-link-red {
        background-color: #f44336;
    }
    .card-link-red:hover {
        background-color: #d32f2f;
    }
    </style>
''', unsafe_allow_html=True)

# --- Layout in due righe e due colonne per le 4 carte principali ---

# Prima riga di carte
col1, col2 = st.columns(2)

with col1:
    st.markdown('''
        <div class="card">
            <div class="card-title">🏁 Campionato / Fase Preliminare</div>
            <div class="card-desc">
                Da usare per disputare un campionato o la <b>prima parte</b> di un torneo 
                articolato che prevede una successiva fase finale.
            </div>
            <a class="card-link" href="https://torneo-subbuteo-superba-ita-all-db.streamlit.app/" target="_blank">Apri App</a>
        </div>
    ''', unsafe_allow_html=True)

with col2:
    st.markdown('''
        <div class="card">
            <div class="card-title">🏆 Fase Finale</div>
            <div class="card-desc">
                Da selezionare per disputare la <b>fase finale</b> del torneo, 
                che può essere organizzata a <b>Gironi</b> o ad <b>Eliminazione Diretta</b>.
            </div>
            <a class="card-link" href="https://torneo-subbuteo-FF-superba-ita-all-db.streamlit.app/" target="_blank">Apri App</a>
        </div>
    ''', unsafe_allow_html=True)

st.markdown("<br><br>", unsafe_allow_html=True) # Aggiunta per distanziare le righe

# Seconda riga di carte
col3, col4 = st.columns(2)

with col3:
    st.markdown('''
        <div class="card">
            <div class="card-title">🇨🇭 Torneo Svizzero x Club</div>
            <div class="card-desc">
                Torneo sviluppato con il <b>criterio svizzero</b>, perfetto per gestire 
                competizioni equilibrate tra più squadre/club.
            </div>
            <a class="card-link" href="https://torneo-subbuteo-superba-svizzero-alldb.streamlit.app/" target="_blank">Apri App</a>
        </div>
    ''', unsafe_allow_html=True)

with col4:
    st.markdown('''
        <div class="card">
            <div class="card-title">🧑‍💻 Gestione Database Giocatori e Tornei Club</div>
            <div class="card-desc">
                Permette di inserire, modificare e cancellare i giocatori affiliati al club. Cancellare Tornei.
            </div>
            <a class="card-link card-link-red" https://edit-superba-club-all-db.streamlit.app/" target="_blank">Apri App</a>
        </div>
    ''', unsafe_allow_html=True)

st.markdown("---")

# Container separato per il Manuale Utente
with st.container():
    st.markdown('''
        <div class="card" style="background-color:#0B5FFF;">
            <div class="card-title">📖 Manuale Utente</div>
            <div class="card-desc">
                Consulta il manuale completo per usare al meglio tutte le funzionalità dell'Hub Tornei Subbuteo.
            </div>
        </div>
    ''', unsafe_allow_html=True)

    pdf_url = "https://raw.githubusercontent.com/legnaro72/torneo-Subbuteo-webapp/main/%F0%9F%93%96%20Manuale%20Utente_%20Hub%20tornei%20Subbuteo.pdf"
    
    try:
        import requests, io
        r = requests.get(pdf_url)
        r.raise_for_status()
        pdf_bytes = io.BytesIO(r.content)
        st.download_button(
            label="⬇️ Scarica Manuale PDF",
            data=pdf_bytes,
            file_name="Manuale_Utente_Hub_Tornei_Subbuteo.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.warning("Errore nel caricamento del PDF. Controlla la connessione o l'URL.")
