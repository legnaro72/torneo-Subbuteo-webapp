import streamlit as st

from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

from .session_manager import restore_session_from_cookie, restore_session_from_handoff, set_cookie, sign_out
from .token_manager import create_handoff_token, create_persistent_session
from .users import (
    find_user,
    log_event,
    update_user_password,
    user_payload,
    validate_system_password,
    validate_user_password,
)


def _init_state(club: str):
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("read_only", False)
    st.session_state.setdefault("auth_phase", "username")
    st.session_state.setdefault("player", None)
    st.session_state.setdefault("club", club)


def _complete_login(user: dict, remember: bool, device_name: str = ""):
    st.session_state.authenticated = True
    st.session_state.read_only = user.get("role") in ["R", "G", "ospite", "lettura"]
    st.session_state.user = user
    token, expires_at = create_persistent_session(user, remember=remember, device_name=device_name)
    set_cookie(token, expires_at)
    st.success("Accesso completato.")
    if st.button("Continua"):
        st.rerun()
    st.stop()


def show_auth_screen(club: str = "Superba"):
    _init_state(club)
    if restore_session_from_handoff() or restore_session_from_cookie():
        return True
    if st.session_state.authenticated:
        return True

    st.markdown("## Accesso Super Suite Subbuteo")
    st.caption("Login unico per launcher, campionato, fasi finali, svizzero e gestione club.")
    if st.session_state.get("auth_restore_error"):
        st.warning(st.session_state.auth_restore_error)
        if st.button("Ignora sessione salvata su questo browser"):
            from .session_manager import clear_cookie

            st.session_state.auth_cookie_restore_disabled = True
            st.session_state.auth_handoff_restore_disabled = True
            st.session_state.auth_restore_error = None
            clear_cookie(reload_page=False)
            st.rerun()

    if st.session_state.auth_phase == "username":
        with st.form(key="auth_form_username"):
            username = st.text_input("Username", key="auth_username", autocomplete="username")
            remember = st.checkbox("Ricordami su questo dispositivo", value=True, key="auth_remember")
            device_name = st.text_input(
                "Nome dispositivo",
                value="Telefono",
                key="auth_device_name",
                help="Serve solo per riconoscere questa sessione in futuro.",
            )
            col1, col2 = st.columns([1, 1])
            with col1:
                submitted = st.form_submit_button("Accedi")
            with col2:
                guest_submitted = st.form_submit_button("Accedi come ospite")

        if guest_submitted:
            user = {"username": "Ospite", "role": "G", "collection": "guests", "id": "guest"}
            log_event("Ospite", "Accesso riuscito", {"ruolo": "Guest", "club": club})
            _complete_login(user, remember=False, device_name="Ospite")

        if submitted:
            if not username:
                st.error("Inserisci lo username")
                return False

            log_event(username, "Inserimento username", {"azione": "Tentativo Log", "club": club})
            player = find_user(username, club)
            if not player:
                st.error(f"Utente non trovato nel club {club}")
                log_event(username, "Utente non trovato", {"motivo": "Username inesistente", "club": club})
                return False

            st.session_state.player = player
            ruolo = player.get("Ruolo", "R")
            if ruolo == "R":
                user = user_payload(player, role=ruolo)
                log_event(player.get("Giocatore"), "Accesso riuscito", {"club": player["_collection"], "ruolo": ruolo})
                _complete_login(user, remember=remember, device_name=device_name)

            st.session_state.auth_phase = "password" if int(player.get("SetPwd", 0)) == 1 else "set_password"
            st.rerun()

    elif st.session_state.auth_phase == "password":
        st.markdown("### Inserisci la tua password")
        with st.form(key="auth_form_password"):
            pwd = st.text_input("Password", type="password", key="auth_pwd_input", autocomplete="current-password")
            remember = st.checkbox("Ricordami su questo dispositivo", value=True, key="auth_remember_pwd")
            device_name = st.text_input("Nome dispositivo", value="Telefono", key="auth_device_name_pwd")
            submit_pwd = st.form_submit_button("Invia Password")
        if submit_pwd:
            player = st.session_state.player
            if validate_user_password(player, pwd):
                user = user_payload(player)
                log_event(player.get("Giocatore"), "Accesso riuscito", {"club": player["_collection"], "ruolo": user["role"]})
                _complete_login(user, remember=remember, device_name=device_name)
            else:
                st.error("Password errata")
                log_event(player.get("Giocatore", "Sconosciuto"), "Password errata", {"motivo": "Password non corrispondente"})

    elif st.session_state.auth_phase == "set_password":
        st.markdown("### Imposta la tua password")
        with st.form(key="auth_form_setpwd"):
            sys_pwd = st.text_input("System Password", type="password", key="auth_sys_pwd")
            new_pwd = st.text_input("New Password", type="password", key="auth_new_pwd", autocomplete="new-password")
            confirm_pwd = st.text_input("Confermare New Password", type="password", key="auth_confirm_pwd")
            remember = st.checkbox("Ricordami su questo dispositivo", value=True, key="auth_remember_set")
            device_name = st.text_input("Nome dispositivo", value="Telefono", key="auth_device_name_set")
            submit_set = st.form_submit_button("Imposta Password")
        if submit_set:
            if not validate_system_password(sys_pwd):
                st.error("System Password non valida")
                log_event(st.session_state.player.get("Giocatore", "Sconosciuto"), "Password non impostata", {"motivo": "System password errata"})
                return False
            if not new_pwd or not confirm_pwd:
                st.error("Inserisci entrambe le password")
                return False
            if new_pwd != confirm_pwd:
                st.error("Le password non coincidono")
                return False

            player = st.session_state.player
            player["Password"] = update_user_password(player, new_pwd)
            player["SetPwd"] = 1
            user = user_payload(player)
            log_event(player.get("Giocatore"), "Impostazione nuova password", {"club": player["_collection"], "ruolo": user["role"]})
            _complete_login(user, remember=remember, device_name=device_name)

    return st.session_state.authenticated


def require_auth(club: str = "Superba"):
    if restore_session_from_handoff() or restore_session_from_cookie():
        return True
    if not st.session_state.get("authenticated", False):
        show_auth_screen(club=club)
        st.stop()
    return True


def logout_button(label: str = "Logout"):
    if st.sidebar.button(label, use_container_width=True):
        sign_out()
        st.stop()


def verify_write_access():
    return st.session_state.get("authenticated", False) and not st.session_state.get("read_only", False)


def get_current_user():
    return st.session_state.get("user")


def make_authenticated_url(url: str):
    user = get_current_user()
    if not user or user.get("id") in [None, "guest"]:
        return url
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["auth_handoff"] = create_handoff_token(user)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
