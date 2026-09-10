"""Persistence and result drafts, used only by the three Superba tournaments."""

from copy import deepcopy
from datetime import datetime


class ConcurrentTournamentUpdate(Exception):
    pass


def compare_and_save(collection, original, changes):
    """Compare the loaded values atomically, including writes by legacy clients."""
    fields = set(changes) | {"data_modifica", "_superba_revision"}
    conditions = []
    for field in sorted(fields):
        expected = {"$eq": original[field], "$exists": True} if field in original else {"$exists": False}
        conditions.append({field: expected})
    updated = deepcopy(changes)
    # BSON dates have millisecond precision; retain the exact value we send.
    now = datetime.now()
    updated["data_modifica"] = now.replace(microsecond=(now.microsecond // 1000) * 1000)
    updated["_superba_revision"] = int(original.get("_superba_revision", 0)) + 1
    result = collection.update_one({"_id": original["_id"], "$and": conditions}, {"$set": updated})
    if result.matched_count != 1:
        raise ConcurrentTournamentUpdate("Il torneo e' cambiato su un altro dispositivo oppure non esiste piu'. Ricaricalo prima di salvare. Le modifiche locali sono ancora disponibili.")
    return {**deepcopy(original), **updated}


def _snapshots():
    import streamlit as st
    return st.session_state.setdefault("_superba_snapshots", {})


def remember_document(collection, document):
    def bson_dates(value):
        if isinstance(value, datetime):
            return value.replace(microsecond=(value.microsecond // 1000) * 1000)
        if isinstance(value, dict):
            return {key: bson_dates(item) for key, item in value.items()}
        if isinstance(value, list):
            return [bson_dates(item) for item in value]
        return value
    _snapshots()[(collection.full_name, str(document["_id"]))] = bson_dates(deepcopy(document))


def save_document(collection, tournament_id, changes):
    import streamlit as st
    from shared.auth import verify_write_access
    if not verify_write_access():
        st.error("Accesso in sola lettura: salvataggio non consentito.")
        return False
    key = (collection.full_name, str(tournament_id))
    original = _snapshots().get(key)
    if original is None:
        st.error("Ricarica il torneo prima di salvare: manca la versione di partenza.")
        return False
    try:
        _snapshots()[key] = compare_and_save(collection, original, changes)
    except Exception as exc:
        st.session_state["_superba_save_error"] = str(exc)
        st.error(f"Salvataggio non riuscito: {exc}")
        return False
    st.session_state.pop("_superba_save_error", None)
    return True


def _drafts():
    import streamlit as st
    tournament_id = str(st.session_state.get("tournament_id", "new"))
    return st.session_state.setdefault("_superba_drafts", {}).setdefault(tournament_id, {})


def _canonical(key):
    for prefix in ("comp_", "prem_", "pc_"):
        if key.startswith(prefix):
            return key[len(prefix):]
    return key


def draft_value(key, default=None):
    entry = _drafts().get(_canonical(key))
    return entry["value"] if entry is not None else default


def mark_saved(key, value):
    entry = _drafts().setdefault(_canonical(key), {})
    entry.update(value=value, saved=value, changed=False)


def consume_change(key):
    entry = _drafts().get(_canonical(key), {})
    changed = entry.get("changed", False)
    entry["changed"] = False
    return changed


def reset_result_drafts(tournament_id):
    import streamlit as st
    st.session_state.setdefault("_superba_drafts", {}).pop(str(tournament_id), None)
    st.session_state.pop("_superba_save_error", None)
    for key in st.session_state.pop("_superba_result_widgets", []):
        st.session_state.pop(key, None)


def _result_widget(widget, label, *args, key, value=None, **kwargs):
    import streamlit as st
    canonical = _canonical(key)
    if value is None:
        value = st.session_state.get(key, False if widget == "checkbox" else 0)
    entry = _drafts().setdefault(canonical, {"value": value, "saved": value, "changed": False})
    st.session_state.setdefault("_superba_result_widgets", set()).add(key)
    st.session_state[key] = entry["value"]

    def capture():
        entry["value"] = st.session_state[key]
        entry["changed"] = True

    return getattr(st, widget)(label, *args, key=key, on_change=capture, **kwargs)


def result_number_input(label, *args, **kwargs):
    return _result_widget("number_input", label, *args, **kwargs)


def result_checkbox(label, *args, **kwargs):
    return _result_widget("checkbox", label, *args, **kwargs)


def has_unsaved_results():
    return any(entry['value'] != entry['saved'] for entry in _drafts().values())


def show_save_status():
    import streamlit as st
    import streamlit.components.v1 as components
    dirty = {key: entry["value"] for key, entry in _drafts().items() if entry["value"] != entry["saved"]}
    components.html("""
        <script>
        const host = window.parent;
        host.__superbaUnsavedResults = DIRTY;
        if (!host.__superbaUnsavedGuard) {
            host.__superbaUnsavedGuard = true;
            host.addEventListener('beforeunload', function(event) {
                if (host.__superbaUnsavedResults) {
                    event.preventDefault();
                    event.returnValue = '';
                }
            });
        }
        </script>
        """.replace("DIRTY", "true" if dirty else "false"), height=0, width=0)
    if dirty:
        st.caption("Modifiche non salvate")
        if st.session_state.get("_superba_save_error"):
            import json
            st.warning(st.session_state["_superba_save_error"])
            st.download_button("Scarica modifiche in sospeso", json.dumps(dirty, ensure_ascii=False, indent=2, default=str),
                               file_name="risultati_in_sospeso.json", mime="application/json", key="superba_draft_export")
    return bool(dirty)


def render_sidebar_startup():
    import streamlit.components.v1 as components
    components.html("""
    <div id="subbuteo-sidebar-tools">
      <button id="subbuteo-collapse-sidebar" type="button">Chiudi sidebar</button>
    </div>
    <style>
      html, body { margin: 0; padding: 0; background: transparent; overflow: hidden; }
      #subbuteo-sidebar-tools { display: none; justify-content: flex-end; width: 100%; }
      #subbuteo-collapse-sidebar { width: auto; border: 0; border-radius: 7px; padding: .42rem .72rem; background: #1d3557; color: white; font-size: .78rem; font-weight: 700; cursor: pointer; box-shadow: 0 2px 8px rgba(29, 53, 87, .24); }
      #subbuteo-collapse-sidebar:hover { background: #457b9d; }
    </style>
    <script>
    (function() {
      let host, d;
      try { host = window.parent; d = host.document; } catch (e) { return; }
      const box = document.getElementById("subbuteo-sidebar-tools");
      const btn = document.getElementById("subbuteo-collapse-sidebar");
      // Persist across Streamlit reruns, but reset when the page is reopened.
      const state = host.__superbaSidebarStartup ||
        (host.__superbaSidebarStartup = {done: false});
      function sidebarOpen(sidebar) {
        const aria = sidebar.getAttribute("aria-expanded");
        if (aria === "true") return true;
        if (aria === "false") return false;
        const rect = sidebar.getBoundingClientRect();
        return rect.width > 80 && rect.right > 0;
      }
      function closeSidebar(sidebar) {
        const nativeButton = sidebar.querySelector(
          '[data-testid="stSidebarCollapseButton"] button, ' +
          'button[data-testid="stSidebarCollapseButton"], ' +
          '[data-testid="stSidebarHeader"] button, ' +
          'button[aria-label="Close sidebar"], button[aria-label="Collapse sidebar"], ' +
          'button[title="Close sidebar"], button[title="Collapse sidebar"]'
        );
        if (!nativeButton) return false;
        state.done = true;
        nativeButton.click();
        return true;
      }
      function update() {
        const sidebar = d.querySelector('section[data-testid="stSidebar"]');
        const expanded = sidebar && sidebarOpen(sidebar);
        box.style.display = expanded ? "flex" : "none";
        if (state.done) return;
        if (!sidebar) return;
        const content = sidebar.querySelector('[data-testid="stSidebarUserContent"]') ||
                        sidebar.querySelector('[data-testid="stSidebarContent"]');
        if (!content || !content.textContent.trim()) return;
        if (expanded) closeSidebar(sidebar);
        else state.done = true;
      }
      function respectUserChoice(event) {
        if (!event.isTrusted || !event.target.closest) return;
        if (event.target.closest(
          '[data-testid="stSidebarCollapseButton"], [data-testid="stSidebarHeader"], ' +
          '[data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"], ' +
          'button[aria-label="Open sidebar"], button[aria-label="Expand sidebar"]'
        )) state.done = true;
      }
      d.addEventListener("click", respectUserChoice, true);
      btn.addEventListener("click", function() {
        state.done = true;
        const sidebar = d.querySelector('section[data-testid="stSidebar"]');
        if (sidebar && sidebarOpen(sidebar)) closeSidebar(sidebar);
      });
      update();
      const observer = new MutationObserver(update);
      observer.observe(d.body, {childList: true, subtree: true, attributes: true,
                               attributeFilter: ['aria-expanded']});
      window.addEventListener("unload", function() {
        observer.disconnect();
        d.removeEventListener("click", respectUserChoice, true);
      });
    })();
    </script>
    """, height=44, width=150)
