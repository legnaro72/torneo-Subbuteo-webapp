import streamlit as st

def check_password(password: str) -> bool:
    """Verifica se la password è corretta"""
    return password == "Sup3rb4"

def show_auth_screen():
    """Mostra la schermata di autenticazione"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.read_only = True
        st.session_state.show_password_field = False

    if not st.session_state.authenticated:
        st.title("🔐 Accesso Torneo Subbuteo")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔓 Accesso in sola lettura", use_container_width=True, type="primary"):
                st.session_state.authenticated = True
                st.session_state.read_only = True
                st.rerun()
                
        with col2:
            if st.button("✏️ Accesso in scrittura", use_container_width=True, type="secondary"):
                st.session_state.show_password_field = True
                
            if st.session_state.get('show_password_field', False):
                with st.form("login_form"):
                    password = st.text_input("Inserisci la password", type="password")
                    if st.form_submit_button("Accedi"):
                        if check_password(password):
                            st.session_state.authenticated = True
                            st.session_state.read_only = False
                            st.session_state.show_password_field = False
                            st.success("Accesso in scrittura consentito!")
                            st.rerun()
                        else:
                            st.error("Password non valida. Riprova o accedi in sola lettura.")
        
        st.markdown("---")
        st.info("💡 Seleziona 'Accesso in sola lettura' per visualizzare i tornei o 'Accesso in scrittura' per effettuare modifiche.")
        
        st.stop()  # Ferma l'esecuzione del resto dell'app finché non si è autenticati

def verify_write_access() -> bool:
    """Verifica se l'utente ha i permessi di scrittura"""
    if 'read_only' not in st.session_state:
        return False
    return not st.session_state.read_only
