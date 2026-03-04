import streamlit as st

# Configurazione pagina (deve essere il primo comando)
st.set_page_config(
    page_title="Super Suite | Hub Tornei",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CSS centralizzato ---
from common.styles import inject_hub_styles
inject_hub_styles()

# --- HERO SECTION ---
st.markdown("""
<div style="text-align: center; padding: 3rem 1rem 1rem 1rem; animation: fadeInUp 0.8s ease-out;">
    <img src="https://raw.githubusercontent.com/legnaro72/torneo-Subbuteo-webapp/main/logo_tigullio.jpg" 
         style="width: 120px; border-radius: 50%; box-shadow: 0 10px 30px rgba(0,0,0,0.3); margin-bottom: 1.5rem;">
    <h1 class="main-title" style="margin-bottom: 0.5rem; font-size: clamp(36px, 6vw, 64px);">⚽ SUPER SUITE SUBBUTEO 🏆</h1>
    <p style="font-size: 1.2rem; color: var(--text-muted); max-width: 600px; margin: 0 auto; line-height: 1.6;">
        Benvenuto nel centro di controllo definitivo per i tornei di Subbuteo. <br>
        Scegli una modalità per iniziare.
    </p>
</div>
<hr style="margin: 3rem 0; opacity: 0.3;">
""", unsafe_allow_html=True)

# --- CARDS GRID ---
# Utilizziamo le colonne per creare una griglia responsiva ma strutturata
col1, space, col2 = st.columns([1, 0.05, 1])

with col1:
    st.markdown('''
        <div class="card" style="height: 100%;">
            <div style="font-size: 3rem; margin-bottom: 15px;">🏁</div>
            <div class="card-title">Campionato / Preliminari</div>
            <div class="card-desc">
                Gestisci la fase a girone unico, campionati o le <b>qualificazioni</b> per i tornei maggiori. Classifiche automatiche e generazione giornate.
            </div>
            <br>
            <a class="card-link" href="https://torneo-subbuteo-tigullio-ita-all-db.streamlit.app/" target="_blank">
                <span style="margin-right:8px;">▶</span> Avvia Modalità
            </a>
        </div>
    ''', unsafe_allow_html=True)

with col2:
    st.markdown('''
        <div class="card" style="height: 100%;">
            <div style="font-size: 3rem; margin-bottom: 15px;">🏆</div>
            <div class="card-title">Fase Finale Eliminatoria</div>
            <div class="card-desc">
                Ideale per le fasi calienti del torneo. Gestisce i <b>Gironi</b> o l'<b>Eliminazione Diretta</b> (Quarti, Semifinali, Finali) con tabelloni automatici.
            </div>
            <br>
            <a class="card-link" href="https://torneo-subbuteo-FF-tigullio-ita-all-db.streamlit.app/" target="_blank">
                <span style="margin-right:8px;">▶</span> Avvia Modalità
            </a>
        </div>
    ''', unsafe_allow_html=True)

st.write("") # Spacer spaziatura
st.write("")
st.write("")

col3, space2, col4 = st.columns([1, 0.05, 1])

with col3:
    st.markdown('''
        <div class="card" style="height: 100%;">
            <div style="font-size: 3rem; margin-bottom: 15px;">🇨🇭</div>
            <div class="card-title">Torneo Svizzero x Club</div>
            <div class="card-desc">
                L'algoritmo svizzero accoppia giocatori dello stesso livello turno dopo turno, evitando sfide tra membri dello stesso club.
            </div>
            <br>
            <div style="display: flex; justify-content: center; gap: 15px; flex-wrap: wrap;">
                <a class="card-link" href="https://torneo-subbuteo-tigullio-svizzero-alldb.streamlit.app/" target="_blank">
                    Versione Stabile
                </a>
                <a class="card-link card-link-beta" href="https://torneo-subbuteo-tigullio-new-version-svizzero-alldb.streamlit.app/" target="_blank">
                    <span style="margin-right:5px;">⭐</span> Beta Premium
                </a>
            </div>
        </div>
    ''', unsafe_allow_html=True)

with col4:
    st.markdown('''
        <div class="card" style="height: 100%; border: 1px solid rgba(230,57,70,0.3);">
            <div style="font-size: 3rem; margin-bottom: 15px;">⚙️</div>
            <div class="card-title">Pannello Gestione Club</div>
            <div class="card-desc">
                Il database centrale. Inserisci giocatori, modifica le loro schede, o <b>cancella tornei</b> dal database del cloud in totale sicurezza.
            </div>
            <br>
            <a class="card-link card-link-red" href="https://edit-tigullio-club-all-db.streamlit.app/" target="_blank" style="width: 80%;">
                <span style="margin-right:8px;">🔓</span> Gestisci Database
            </a>
        </div>
    ''', unsafe_allow_html=True)

st.markdown("<hr style='margin: 3rem 0; opacity: 0.3;'>", unsafe_allow_html=True)

# --- INFO & MANUAL BOX ---
col_manual, col_empty = st.columns([2, 1])
with col_manual:
    st.markdown('''
        <div class="manual-box" style="display: flex; align-items: center; text-align: left;">
            <div style="font-size: 4rem; margin-right: 25px;">📖</div>
            <div>
                <h3 style="margin-top:0; border: none; padding: 0; background: none; box-shadow: none; color: var(--color-primary-light);">Manuale Operativo dell'App</h3>
                <p style="margin-bottom: 10px; color: var(--text-muted);">
                    Hai dubbi o vuoi scoprire trucchetti per gestire al meglio le leghe? 
                    Il manuale della Super Suite contiene screenshot, spiegazioni per i log e regole sulle formule di torneo.
                </p>
            </div>
        </div>
    ''', unsafe_allow_html=True)
    
    # Download Button Integrato
    pdf_url = "https://raw.githubusercontent.com/legnaro72/torneo-Subbuteo-webapp/main/%F0%9F%93%96%20Manuale%20Utente_%20Hub%20tornei%20Subbuteo.pdf"
    
    try:
        import requests, io
        r = requests.get(pdf_url)
        r.raise_for_status()
        pdf_bytes = io.BytesIO(r.content)
        st.download_button(
            label="⬇️ SCARICA IL MANUALE IN PDF",
            data=pdf_bytes,
            file_name="Manuale_Utente_Super_Suite_Subbuteo.pdf",
            mime="application/pdf",
            type="primary",
            width="stretch"
        )
    except Exception as e:
        st.error(f"⚠️ Impossibile caricare il PDF in questo momento. ({e})")

# Footer
st.markdown("""
<div style="text-align: center; margin-top: 4rem; padding-bottom: 2rem; color: var(--text-muted); font-size: 0.9rem;">
    <b>Subbuteo Tournament Manager • Super Suite Edition</b><br>
    Sviluppato con dedizione da <b>Legnaro72</b>
</div>
""", unsafe_allow_html=True)
