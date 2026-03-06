"""
ui_components.py — Componenti UI riutilizzabili per le app Subbuteo.

Fornisce:
  - Header/titolo tornei con stile gradiente
  - Barra laterale comune (sidebar standard)
  - Navigazione giornate/turni
  - Keep-alive script
"""
import streamlit as st
import streamlit.components.v1 as components

# Moduli interni rimossi gli import di COLORS perché ora usiamo CSS vars native


# ==============================================================================
# 🏆 HEADER / TITOLO
# ==============================================================================

def render_tournament_header(title: str, emoji_left: str = "⚽", emoji_right: str = "🏆"):
    """
    Renderizza il titolo del torneo con lo stile gradiente.
    
    Args:
        title: Titolo da visualizzare.
        emoji_left: Emoji a sinistra del titolo.
        emoji_right: Emoji a destra del titolo.
    """
    st.markdown(f"""
    <div style='text-align:center; padding:20px; border-radius:10px;
         background: linear-gradient(90deg, var(--color-primary-mid, #457b9d), var(--color-primary-dark, #1d3557));
         box-shadow: 0 4px 14px rgba(0,0,0,0.15);'>
        <h1 style='color:white; margin:0; font-weight:700;'>
            {emoji_left} {title} {emoji_right}
        </h1>
    </div>
    """, unsafe_allow_html=True)


def render_section_header(title: str):
    """Renderizza un subtitle h3 nel contenuto principale."""
    st.markdown(f"### {title}")


# ==============================================================================
# 🧭 SIDEBAR COMUNE
# ==============================================================================

# Default Hub URL (will be used if no custom hub_url is provided)
DEFAULT_HUB_URL = "https://farm-tornei-subbuteo-superba-all-db.streamlit.app/"

def setup_common_sidebar(show_user_info: bool = True, show_hub_link: bool = True, hub_url: str = DEFAULT_HUB_URL):
    """
    Configura la sidebar con elementi comuni a tutte le app.
    
    Args:
        show_user_info: Se True, mostra le info dell'utente autenticato.
        show_hub_link: Se True, mostra il link all'Hub.
        hub_url: URL dell'Hub di destinazione.
    """
    # Info utente
    if show_user_info and st.session_state.get("authenticated"):
        user = st.session_state.get("user", {})
        st.sidebar.markdown(f"**👤 Utente:** {user.get('username', '??')}")
        st.sidebar.markdown(f"**🔑 Ruolo:** {user.get('role', '??')}")

    if show_hub_link:
        st.sidebar.markdown("---")
        st.sidebar.subheader("🕹️ Gestione Rapida")
        st.sidebar.link_button(
            "➡️ Vai a Hub Tornei",
            hub_url,
            use_container_width=True
        )



def setup_player_selection_mode():
    """
    Aggiunge la sezione di selezione modalità partecipanti nella sidebar.
    Gestisce Multiselect vs Checkbox individuali.
    """
    st.sidebar.markdown("---")
    st.sidebar.subheader("👤 Mod Selezione Partecipanti")
    st.session_state.usa_multiselect_giocatori = st.sidebar.checkbox(
        "Utilizza 'Multiselect'",
        value=st.session_state.get('usa_multiselect_giocatori', False),
        key='sidebar_usa_multiselect_giocatori',
        help="Disabilitato per usare la modalità 'Checkbox Individuali' (raccomandata)"
    )


# ==============================================================================
# 🎛️ NAVIGAZIONE GIORNATE CON BOTTONI
# ==============================================================================

def navigation_buttons(label: str, value_key: str, min_val: int, max_val: int, key_prefix: str = ""):
    """
    Aggiunge bottoni ← e → per navigare fra valori numerici (giornate, turni, ecc.).
    
    Args:
        label: Etichetta del valore corrente.
        value_key: Chiave nel session_state da modificare.
        min_val: Valore minimo.
        max_val: Valore massimo.
        key_prefix: Prefisso per le chiavi dei bottoni (per evitare conflitti).
    """
    col1, col2, col3 = st.columns([1, 3, 1])
    current = st.session_state.get(value_key, min_val)
    with col1:
        if st.button("⬅️", key=f"{key_prefix}nav_prev_{value_key}"):
            if current > min_val:
                st.session_state[value_key] = current - 1
                st.rerun()
    with col2:
        st.markdown(f"**{label}: {current}**")
    with col3:
        if st.button("➡️", key=f"{key_prefix}nav_next_{value_key}"):
            if current < max_val:
                st.session_state[value_key] = current + 1
                st.rerun()


# ==============================================================================
# 🔄 KEEP-ALIVE (anti sleep per Streamlit Cloud)
# ==============================================================================

def add_keep_alive(interval_ms: int = 240000):
    """
    Inietta un keep-alive JavaScript per evitare che la sessione Streamlit vada in sleep.
    
    Args:
        interval_ms: Intervallo in millisecondi fra i ping (default: 4 minuti).
    """
    js = f"""
    <script>
    const target = document.referrer || window.location.origin;
    setInterval(function() {{
        fetch(target, {{
            method: 'HEAD',
            cache: 'no-store',
            credentials: 'same-origin',
            mode: 'no-cors'
        }}).then(() => {{
            console.log("Keep-alive sent:", new Date().toLocaleTimeString());
        }}).catch((err) => console.log("Keep-alive error", err));
    }}, {interval_ms});
    </script>
    """
    components.html(js, height=0, width=0)
