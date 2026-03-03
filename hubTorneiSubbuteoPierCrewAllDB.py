import streamlit as st

# Configurazione pagina (deve essere il primo comando)
st.set_page_config(
    page_title="PierCrew Suite | Hub Tornei",
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
    <img src="https://raw.githubusercontent.com/legnaro72/torneo-Subbuteo-webapp/main/logo_piercrew.jpg" 
         style="width: 120px; border-radius: 50%; box-shadow: 0 10px 30px rgba(0,0,0,0.3); margin-bottom: 1.5rem;"
         onerror="this.src='https://raw.githubusercontent.com/legnaro72/torneo-Subbuteo-webapp/main/logo_superba.jpg'">
    <h1 class="main-title" style="margin-bottom: 0.5rem; font-size: clamp(36px, 6vw, 64px);">⚽ PIERCREW SUITE SUBBUTEO 🏆</h1>
    <p style="font-size: 1.2rem; color: var(--text-muted); max-width: 600px; margin: 0 auto; line-height: 1.6;">
        Centro di controllo tornei per il club PierCrew. <br>
        Scegli una modalità per iniziare.
    </p>
</div>
<hr style="margin: 3rem 0; opacity: 0.3;">
""", unsafe_allow_html=True)

# --- CARDS GRID ---
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
            <a class="card-link" href="https://torneo-subbuteo-piercrew-ita-all-db.streamlit.app/" target="_blank">
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
            <a class="card-link" href="https://torneo-subbuteo-ff-piercrew-ita-all-db.streamlit.app/" target="_blank">
                <span style="margin-right:8px;">▶</span> Avvia Modalità
            </a>
        </div>
    ''', unsafe_allow_html=True)

st.write("") 
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
                <a class="card-link" href="https://torneo-subbuteo-piercrew-svizzero-alldb.streamlit.app/" target="_blank">
                    Vai al Torneo
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
                Il database centrale. Inserisci giocatori, modifica le loro schede, o <b>cancella tornei</b> dal database in totale sicurezza.
            </div>
            <br>
            <a class="card-link card-link-red" href="https://edit-piercrew-club-all-db.streamlit.app/" target="_blank" style="width: 80%;">
                <span style="margin-right:8px;">🔓</span> Gestisci Database
            </a>
        </div>
    ''', unsafe_allow_html=True)

st.markdown("<hr style='margin: 3rem 0; opacity: 0.3;'>", unsafe_allow_html=True)

# Footer
st.markdown("""
<div style="text-align: center; margin-top: 4rem; padding-bottom: 2rem; color: var(--text-muted); font-size: 0.9rem;">
    <b>Subbuteo Tournament Manager • PierCrew Edition</b><br>
    Sviluppato con dedizione da <b>Legnaro72</b>
</div>
""", unsafe_allow_html=True)
