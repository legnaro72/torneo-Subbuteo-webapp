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
    Versione ultra-persistente per Streamlit. Mantiene in vita l'audio fra un reload e l'altro.
    
    Args:
        audio_url: URL raw dell'mp3 da riprodurre.
    
    Returns:
        True se l'audio è stato iniettato correttamente, False altrimenti.
    """
    if st.session_state.get('bg_audio_disabled', False):
        return False
        
    js = f"""
    <div style="display:none;" id="persistent_audio_container">
        <!-- Audio Player nascosto -->
        <audio id="subbuteo_audio_player" loop>
            <source src="{audio_url}" type="audio/mpeg">
        </audio>
    </div>
    <script>
        // Sfruttiamo window.parent per garantire sopravvivenza al component reload
        var parentWin = window.parent;
        
        // Se l'audio non esiste ancora nel DOM del parent, lo creiamo
        if (!parentWin.document.getElementById('persistent_audio_player')) {{
            var audioEl = document.createElement('audio');
            audioEl.id = 'persistent_audio_player';
            audioEl.src = '{audio_url}';
            audioEl.loop = true;
            audioEl.volume = 0.5;
            audioEl.style.display = 'none';
            parentWin.document.body.appendChild(audioEl);
            
            // Tentativo play immediato
            var playPromise = audioEl.play();
            if (playPromise !== undefined) {{
                playPromise.catch(function(error) {{
                    console.log("Autoplay bloccato. Attesa del primo interaction utente.");
                    // Autoplay bloccato da policy browser: attende un click
                    document.addEventListener('click', function() {{
                        audioEl.play().catch(e=>console.log(e));
                    }}, {{ once: true }});
                }});
            }}
        }} else {{
            // L'audio esiste già, verifichiamo che sia in esecuzione (se non è in pausa per volere dell'utente)
            var currentAudio = parentWin.document.getElementById('persistent_audio_player');
            if(currentAudio.paused && !currentAudio.hasAttribute('user-muted')) {{
                currentAudio.play().catch(e=>console.log(e));
            }}
        }}
    </script>
    """
    st.components.v1.html(js, height=0, width=0)
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
    L'atto di chiamarla garantisce che st.session_state.bg_audio_disabled sia aggiornato.
    Sincronizza immediatamente il player native nel window.parent
    """
    disabled = st.session_state.get('bg_audio_disabled', False)
    
    js_sync = f"""<script>
    var parentWin = window.parent;
    if (parentWin && parentWin.document) {{
        var audioEl = parentWin.document.getElementById('persistent_audio_player');
        if (audioEl) {{
            if ({str(disabled).lower()}) {{
                audioEl.pause();
                audioEl.setAttribute('user-muted', 'true');
            }} else {{
                audioEl.removeAttribute('user-muted');
                audioEl.play().catch(e=>console.log(e));
            }}
        }}
    }}
    </script>"""
    st.components.v1.html(js_sync, height=0, width=0)


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
