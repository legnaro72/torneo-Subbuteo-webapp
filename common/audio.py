"""
audio.py — Gestione audio di sottofondo per le app Subbuteo.

Funzionalità:
  - autoplay_background_audio(): Audio persistente con loop (per sottofondo)
  - autoplay_audio(): Audio one-shot (per eventi come vittoria)
  - toggle_audio_callback(): Callback per checkbox mute/unmute
  - setup_audio_sidebar(): Widget sidebar per gestire audio on/off
"""
import streamlit as st
import base64
import requests


def autoplay_background_audio(audio_url: str) -> bool:
    """
    Inietta un elemento <audio> persistente nel DOM con autoplay e loop.
    Utilizza direttamente l'URL per evitare MemoryError dovuti a stringhe base64 giganti.
    
    Args:
        audio_url: URL raw dell'mp3 da riprodurre.
    
    Returns:
        True se l'audio è stato iniettato correttamente, False altrimenti.
    """
    # Iniezione JS nel corpo principale (non in un iframe) per persistenza reale
    html_code = f"""
    <div id="audio-container" style="display:none;"></div>
    <script>
        // Funzione per avviare l'audio se non già presente nel window superiore
        (function() {{
            const AUDIO_ID = "subbuteo_bg_audio";
            const AUDIO_URL = "{audio_url}";
            
            // Proviamo a usare window.top o window.parent per massima persistenza
            const targetWindow = window.parent || window;
            
            if (!targetWindow.subbuteoAudioInstance) {{
                console.log("🎵 Inizializzazione nuova istanza audio...");
                const audio = new Audio(AUDIO_URL);
                audio.id = AUDIO_ID;
                audio.loop = true;
                audio.volume = 0.5;
                
                // Salva l'istanza nel window per i prossimi rerun
                targetWindow.subbuteoAudioInstance = audio;
                
                audio.play().catch(err => {{
                    console.log("⚠️ Autoplay bloccato dal browser. Partirà al primo click.");
                    const playOnClick = () => {{
                        audio.play();
                        document.removeEventListener('click', playOnClick);
                    }};
                    document.addEventListener('click', playOnClick);
                }});
            }} else {{
                // Se l'URL è cambiato, aggiorna la sorgente
                if (targetWindow.subbuteoAudioInstance.src !== AUDIO_URL && AUDIO_URL.startsWith("http")) {{
                     targetWindow.subbuteoAudioInstance.src = AUDIO_URL;
                     targetWindow.subbuteoAudioInstance.load();
                     if (!targetWindow.subbuteoAudioInstance.userPaused) {{
                         targetWindow.subbuteoAudioInstance.play().catch(() => {{}});
                     }}
                }}

                // Assicuriamoci che stia suonando (se non mutato)
                if (targetWindow.subbuteoAudioInstance.paused && !targetWindow.subbuteoAudioInstance.userPaused) {{
                    targetWindow.subbuteoAudioInstance.play().catch(() => {{}});
                }}
            }}
            
            // Gestione muting sincronizzata con Streamlit
            window.syncAudio = function(disabled) {{
                if (targetWindow.subbuteoAudioInstance) {{
                    if (disabled) {{
                        targetWindow.subbuteoAudioInstance.pause();
                        targetWindow.subbuteoAudioInstance.userPaused = true;
                    }} else {{
                        targetWindow.subbuteoAudioInstance.play();
                        targetWindow.subbuteoAudioInstance.userPaused = false;
                    }}
                }}
            }};
        }})();
    </script>
    """
    # Usiamo st.components.v1.html ma con il targetWindow hack
    st.components.v1.html(html_code, height=0, width=0)
    
    # Iniziamo la sincronizzazione dello stato (muto/non muto)
    disabled_js = "true" if st.session_state.get('bg_audio_disabled', False) else "false"
    st.components.v1.html(f"<script>if(window.parent.syncAudio) window.parent.syncAudio({disabled_js});</script>", height=0, width=0)
    
    return True


def autoplay_audio(audio_data: bytes):
    """
    Riproduce un audio una sola volta (es. effetto sonoro vittoria).
    
    Args:
        audio_data: Bytes dell'audio da riprodurre.
    """
    b64 = base64.b64encode(audio_data).decode("utf-8")
    md = f"""
        <audio autoplay="true">
        <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        """
    st.markdown(md, unsafe_allow_html=True)


def toggle_audio_callback():
    """
    Callback per la checkbox dell'audio.
    L'atto di chiamarla garantisce che st.session_state.bg_audio_disabled
    sia aggiornato prima del rerun.
    """
    pass


def init_audio_state():
    """Inizializza lo stato dell'audio nel session_state."""
    if "bg_audio_disabled" not in st.session_state:
        st.session_state.bg_audio_disabled = False


def start_background_audio(audio_url: str):
    """
    Inizializza e avvia l'audio di sottofondo se non è disabilitato.
    Da chiamare nel corpo principale dell'app.
    
    Args:
        audio_url: URL raw dell'mp3 da usare come sottofondo.
    """
    init_audio_state()
    if not st.session_state.bg_audio_disabled:
        autoplay_background_audio(audio_url)


def setup_audio_sidebar():
    """
    Aggiunge la sezione di gestione audio nella sidebar.
    Include la checkbox per abilitare/disabilitare l'audio di sottofondo.
    """
    st.sidebar.markdown("---")
    st.sidebar.subheader("🎵️ Gestione Audio Sottofondo")
    st.sidebar.checkbox(
        "Disabilita audio di sottofondo🔊",
        key="bg_audio_disabled",
        on_change=toggle_audio_callback
    )
