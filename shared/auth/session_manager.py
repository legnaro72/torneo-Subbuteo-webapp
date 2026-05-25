import html
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
from pymongo.errors import PyMongoError

from .token_manager import consume_handoff_token, create_persistent_session, rotate_token, revoke_token
from .users import find_user_by_id, user_payload

try:
    import extra_streamlit_components as stx
except Exception:
    stx = None


COOKIE_NAME = "subbuteo_superba_auth"
LOCAL_TOKEN_QUERY_PARAM = "auth_local_token"


def get_cookie_manager():
    if stx is None:
        return None
    try:
        return stx.CookieManager(key="subbuteo_superba_cookie_manager")
    except Exception:
        return None


def get_cookie(name: str = COOKIE_NAME):
    manager = get_cookie_manager()
    if manager is not None:
        try:
            value = manager.get(name)
            if value:
                return value
        except Exception:
            pass
    try:
        cookies = getattr(st.context, "cookies", {}) or {}
        return cookies.get(name)
    except Exception:
        return None


def set_cookie(token: str, expires_at: datetime):
    manager = get_cookie_manager()
    if manager is not None:
        try:
            manager.set(COOKIE_NAME, token, expires_at=expires_at, key="set_subbuteo_superba_auth")
        except Exception as exc:
            print(f"CookieManager set fallito, uso fallback JS: {exc}")

    expires = expires_at.strftime("%a, %d %b %Y %H:%M:%S GMT")
    token_js = html.escape(token, quote=True)
    cookie_js = (
        f"{COOKIE_NAME}={token_js}; expires={expires}; path=/; "
        "SameSite=Lax"
    )
    components.html(
        f"""
        <script>
        const secureAttr = window.parent.location.protocol === "https:" ? "; Secure" : "";
        const cookieValue = {cookie_js!r} + secureAttr;
        try {{
          window.parent.document.cookie = cookieValue;
          window.parent.localStorage.setItem({COOKIE_NAME!r}, {token!r});
        }} catch (e) {{
          document.cookie = cookieValue;
          localStorage.setItem({COOKIE_NAME!r}, {token!r});
        }}
        </script>
        """,
        height=0,
        width=0,
    )


def clear_cookie(reload_page: bool = False):
    manager = get_cookie_manager()
    if manager is not None:
        try:
            manager.delete(COOKIE_NAME, key="delete_subbuteo_superba_auth")
        except Exception as exc:
            print(f"CookieManager delete fallito, uso fallback JS: {exc}")

    cookie_js = f"{COOKIE_NAME}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax"
    reload_js = "window.parent.location.reload();" if reload_page else ""
    fallback_reload_js = "window.location.reload();" if reload_page else ""
    components.html(
        f"""
        <script>
        const cookieValue = {cookie_js!r};
        const secureCookieValue = cookieValue + "; Secure";
        try {{
          window.parent.document.cookie = cookieValue;
          window.parent.document.cookie = secureCookieValue;
          window.parent.localStorage.removeItem({COOKIE_NAME!r});
          {reload_js}
        }} catch (e) {{
          document.cookie = cookieValue;
          document.cookie = secureCookieValue;
          localStorage.removeItem({COOKIE_NAME!r});
          {fallback_reload_js}
        }}
        </script>
        """,
        height=0,
        width=0,
    )


def restore_session_from_cookie():
    if st.session_state.get("authenticated"):
        return True
    if st.session_state.get("auth_cookie_restore_disabled"):
        return False
    token = get_cookie()
    if not token:
        return False

    try:
        session, new_token = rotate_token(token)
    except (PyMongoError, TimeoutError) as exc:
        st.session_state.auth_cookie_restore_disabled = True
        st.session_state.auth_restore_error = (
            "Connessione a MongoDB non disponibile: impossibile verificare la sessione salvata. "
            "Riprova quando la rete/Atlas risponde, oppure elimina i cookie locali se vuoi forzare un nuovo login."
        )
        if not st.session_state.get("auth_restore_error_logged"):
            print(f"Errore ripristino cookie persistente: {exc}")
            st.session_state.auth_restore_error_logged = True
        return False
    if not session:
        st.session_state.auth_cookie_restore_disabled = True
        clear_cookie(reload_page=False)
        return False

    try:
        player = find_user_by_id(session.get("user_id"), session.get("collection", "superba_players"))
    except (PyMongoError, TimeoutError) as exc:
        st.session_state.auth_cookie_restore_disabled = True
        st.session_state.auth_restore_error = "Connessione a MongoDB non disponibile: impossibile caricare l'utente."
        if not st.session_state.get("auth_restore_error_logged"):
            print(f"Errore caricamento utente da sessione persistente: {exc}")
            st.session_state.auth_restore_error_logged = True
        return False
    if not player:
        try:
            revoke_token(new_token)
        except (PyMongoError, TimeoutError) as exc:
            print(f"Errore revoca token senza utente: {exc}")
        st.session_state.auth_cookie_restore_disabled = True
        clear_cookie(reload_page=False)
        return False

    st.session_state.authenticated = True
    st.session_state.read_only = player.get("Ruolo") in ["R", "G"]
    st.session_state.user = user_payload(player)
    st.session_state.player = player
    set_cookie(new_token, session["expires_at"])
    return True


def restore_session_from_local_query():
    if st.session_state.get("authenticated"):
        return True if st.session_state.get("authenticated") else False
    if st.session_state.get("auth_local_restore_disabled"):
        return False
    try:
        token = st.query_params.get(LOCAL_TOKEN_QUERY_PARAM)
    except Exception:
        token = None
    if not token:
        return False

    try:
        session, new_token = rotate_token(token)
    except (PyMongoError, TimeoutError) as exc:
        st.session_state.auth_local_restore_disabled = True
        st.session_state.auth_restore_error = "Connessione a MongoDB non disponibile: impossibile verificare la sessione locale salvata."
        if not st.session_state.get("auth_restore_error_logged"):
            print(f"Errore ripristino localStorage persistente: {exc}")
            st.session_state.auth_restore_error_logged = True
        return False
    if not session:
        st.session_state.auth_local_restore_disabled = True
        clear_cookie(reload_page=False)
        return False

    try:
        player = find_user_by_id(session.get("user_id"), session.get("collection", "superba_players"))
    except (PyMongoError, TimeoutError) as exc:
        st.session_state.auth_local_restore_disabled = True
        st.session_state.auth_restore_error = "Connessione a MongoDB non disponibile: impossibile caricare l'utente locale salvato."
        if not st.session_state.get("auth_restore_error_logged"):
            print(f"Errore caricamento utente da localStorage persistente: {exc}")
            st.session_state.auth_restore_error_logged = True
        return False
    if not player:
        st.session_state.auth_local_restore_disabled = True
        clear_cookie(reload_page=False)
        return False

    st.session_state.authenticated = True
    st.session_state.read_only = player.get("Ruolo") in ["R", "G"]
    st.session_state.user = user_payload(player)
    st.session_state.player = player
    set_cookie(new_token, session["expires_at"])
    try:
        del st.query_params[LOCAL_TOKEN_QUERY_PARAM]
    except Exception:
        pass
    return True


def inject_local_storage_bridge():
    components.html(
        f"""
        <script>
        try {{
          const parentWindow = window.parent;
          const token = parentWindow.localStorage.getItem({COOKIE_NAME!r});
          const url = new URL(parentWindow.location.href);
          if (token && !url.searchParams.has({LOCAL_TOKEN_QUERY_PARAM!r})) {{
            url.searchParams.set({LOCAL_TOKEN_QUERY_PARAM!r}, token);
            parentWindow.location.replace(url.toString());
          }}
        }} catch (e) {{}}
        </script>
        """,
        height=0,
        width=0,
    )


def restore_session_from_handoff():
    if st.session_state.get("authenticated"):
        return True
    if st.session_state.get("auth_handoff_restore_disabled"):
        return False
    try:
        handoff_token = st.query_params.get("auth_handoff")
    except Exception:
        handoff_token = None
    if not handoff_token:
        return False

    try:
        handoff = consume_handoff_token(handoff_token)
    except (PyMongoError, TimeoutError) as exc:
        st.session_state.auth_handoff_restore_disabled = True
        st.session_state.auth_restore_error = "Connessione a MongoDB non disponibile: impossibile verificare il passaggio dal launcher."
        if not st.session_state.get("auth_restore_error_logged"):
            print(f"Errore handoff auth: {exc}")
            st.session_state.auth_restore_error_logged = True
        return False
    if not handoff:
        return False

    try:
        player = find_user_by_id(handoff.get("user_id"), handoff.get("collection", "superba_players"))
    except (PyMongoError, TimeoutError) as exc:
        st.session_state.auth_handoff_restore_disabled = True
        st.session_state.auth_restore_error = "Connessione a MongoDB non disponibile: impossibile caricare l'utente."
        if not st.session_state.get("auth_restore_error_logged"):
            print(f"Errore caricamento utente da handoff: {exc}")
            st.session_state.auth_restore_error_logged = True
        return False
    if not player:
        return False

    user = user_payload(player)
    st.session_state.authenticated = True
    st.session_state.read_only = player.get("Ruolo") in ["R", "G"]
    st.session_state.user = user
    st.session_state.player = player
    token, expires_at = create_persistent_session(user, remember=True, device_name="Handoff")
    set_cookie(token, expires_at)
    try:
        del st.query_params["auth_handoff"]
    except Exception:
        pass
    return True


def sign_out():
    token = get_cookie()
    if token:
        try:
            revoke_token(token)
        except (PyMongoError, TimeoutError) as exc:
            print(f"Errore revoca token persistente: {exc}")
    for key in ["authenticated", "read_only", "user", "player", "auth_phase", "club"]:
        st.session_state.pop(key, None)
    clear_cookie(reload_page=True)
