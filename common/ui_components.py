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
    # Stili CSS iniettati usando la logica advanced :has per non influenzare altre colonne.
    # Questo compatta la navigazione tutto in un'unica riga anche per smartphone
    st.markdown("""
        <style>
        /* Forza la riga su mobile, impedendo l'accatastamento verticale standard di Streamlit */
        div[data-testid="stHorizontalBlock"]:has(.nav-btn-marker) {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 15px !important;
        }
        
        /* I due bottoni ai lati prendono TUTTO lo spazio possibile disponibile in parti uguali */
        div[data-testid="stHorizontalBlock"]:has(.nav-btn-marker) > div[data-testid="column"]:first-child,
        div[data-testid="stHorizontalBlock"]:has(.nav-btn-marker) > div[data-testid="column"]:last-child {
            width: auto !important;
            flex: 1 1 0% !important;
            min-width: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
        }

        /* La colonna centrale con il numero occupa solo lo spazio stretto necessario per il numero stesso */
        div[data-testid="stHorizontalBlock"]:has(.nav-btn-marker) > div[data-testid="column"]:nth-child(2) {
            width: fit-content !important;
            flex: 0 0 auto !important;
            min-width: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
        }
        
        /* I bottoni si allargano alla massima ampiezza del proprio genitore (che ora prenderà quasi mezzo schermo) */
        div[data-testid="stHorizontalBlock"]:has(.nav-btn-marker) button {
            width: 100% !important;
            min-width: 0 !important;
            padding: 0.2rem 0 !important;
            margin: 0 !important;
        }
        
        /* Sistema l'allineamento del testo numerico per essere centrato perfettamente */
        .nav-btn-marker {
            text-align: center;
            font-weight: 900;
            font-size: 1.5rem;
            line-height: 1.5rem;
        }
        p {
          margin-bottom: 0px;  
        }
        </style>
    """, unsafe_allow_html=True)

    current = st.session_state.get(value_key, min_val)
    
    # Rimuoviamo il testo "Gio" / "Turno" come richiesto, lasciando solo il NUEMRO (es. "1", "2") per attaccare i bottoni
    display_label = str(current)
        
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("◀️", key=f"{key_prefix}nav_prev_{value_key}", use_container_width=True):
            if current > min_val:
                st.session_state[value_key] = current - 1
                st.rerun()
    with col2:
        # Il testo al centro conterrà solo il numero
        st.markdown(f"<div class='nav-btn-marker'>{display_label}</div>", unsafe_allow_html=True)
    with col3:
        if st.button("▶️", key=f"{key_prefix}nav_next_{value_key}", use_container_width=True):
            if current < max_val:
                st.session_state[value_key] = current + 1
                st.rerun()


# ==============================================================================
# 🔄 KEEP-ALIVE — Sistema di mantenimento attivo della sessione Streamlit
# ==============================================================================
#
# Garantisce che l'applicazione Streamlit rimanga connessa e utilizzabile
# senza richiedere una nuova autenticazione anche in assenza di interazioni
# utente per almeno 30 minuti (es. durante una partita di Subbuteo).
#
# Meccanismo a doppio heartbeat (ogni 3 minuti):
#   1. Simulazione evento mousemove → mantiene attiva la WebSocket
#   2. Fetch HTTP verso l'URL dell'app → mantiene attiva la sessione server
#
# Compatibile con: Streamlit Cloud, VPS, Docker, PaaS.
# ==============================================================================

def enable_session_keepalive(interval_ms: int = 180000):
    """
    Inietta un heartbeat JavaScript invisibile per mantenere la sessione attiva.

    Il sistema si attiva una sola volta per sessione e genera attività periodica
    invisibile che impedisce:
      - timeout della WebSocket Streamlit
      - inattività della sessione
      - disconnessione dell'utente

    Args:
        interval_ms: Intervallo in millisecondi fra gli heartbeat (default: 180000 = 3 minuti).
                     Con 3 minuti di intervallo si ottengono ~7 heartbeat in 20 minuti,
                     garantendo margine rispetto al timeout tipico di Streamlit (10-15 min).
    """
    # Guard: si attiva una sola volta per sessione
    if "keepalive_initialized" in st.session_state:
        return

    st.session_state.keepalive_initialized = True

    import streamlit.components.v1 as components
    components.html(
        f"""
        <script>

        function streamlitHeartbeat() {{

            // 1. Simula un evento utente per mantenere attiva la WebSocket
            window.parent.dispatchEvent(new Event("mousemove"));

            // 2. Effettua una richiesta HTTP per mantenere attiva la sessione server
            fetch(window.parent.location.href, {{
                method: "GET",
                cache: "no-store",
                mode: "no-cors"
            }}).catch(function() {{}});

        }}

        // Esecuzione heartbeat ogni {interval_ms} ms (default: 3 minuti)
        setInterval(streamlitHeartbeat, {interval_ms});

        </script>
        """,
        height=0, width=0
    )


def add_keep_alive(interval_ms: int = 180000):
    """
    Wrapper retrocompatibile per enable_session_keepalive().
    Mantiene compatibilità con il codice esistente che importa add_keep_alive.

    Args:
        interval_ms: Intervallo in millisecondi fra gli heartbeat (default: 3 minuti).
    """
    enable_session_keepalive(interval_ms)

