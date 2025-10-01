import os
from pymongo import MongoClient
from bson import ObjectId
import streamlit as st
import pandas as pd
from logging_utils import log_action # Assumendo che esista
from datetime import datetime

# DELTA 1: Aggiungi importazione di auth_utils e configurazione della pagina
# --------------------------------------------------------------------------
# Importa il modulo di autenticazione centralizzato
import auth_utils as auth
from auth_utils import verify_write_access, get_current_user # Import utili

# Configurazione della pagina di Streamlit
st.set_page_config(
    page_title="MongoDB CRUD Manager",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)
# --------------------------------------------------------------------------

# Lista dei tuoi database (puoi adattare se aggiungi nuovi DB)
DATABASES = ["Log", "Password", "TorneiSubbuteo", "giocatori_subbuteo"]

# Dizionario delle Emoji Tematiche
EMOJI_MAP = {
    "Log": "📄",
    "Password": "🔑",
    "TorneiSubbuteo": "🏆",
    "giocatori_subbuteo": "🧑‍🤝‍🧑",
    "title": "⚙️ MongoDB CRUD Manager",
    "sidebar_title": "🔎 Selezione DB & Collection",
    "crud_title_prefix": "Gestione",
    "filters": "🔍 Filtri per la ricerca",
    "records_header": "🗃️ Tutti i record (Editabile)", # Etichetta modificata
    "edit_delete_header": "✏️ Modifica o elimina record (Singolo)",
    "new_record_header": "➕ Aggiungi nuovo record",
    "save_changes": "💾 Salva modifiche",
    "delete_record": "🗑️ Elimina record",
    "save_new": "✅ Salva nuovo record",
    "bulk_delete_header": "✂️ Cancellazione Bulk per Tornei",
    "log_cleanup_header": "🧹 Cancellazione Tutti i Record in Log",
    "bulk_delete_warning": "⚠️ Cancella tutti i tornei tranne quelli con 'CAMPIONATO' nel nome.",
    "log_cleanup_warning": "⚠️ Cancella tutti i record nelle collection del DB Log.",
    "no_records": "🚫 Nessun record trovato con i filtri applicati.",
    "error": "❌",
    "success": "✅",
    "info": "💡",
    "warning": "🚨",
    "save_table": "⬆️ Salva modifiche tabella" 
}

# --- Connessione a MongoDB ---
def get_mongo_client():
    MONGO_URI = os.getenv(
        "MONGO_URI",
        "mongodb+srv://massimilianoferrando:Legnaro21!$@cluster0.t3750lc.mongodb.net/"
    )
    return MongoClient(MONGO_URI)
    
# NUOVO DELTA: Simula il logout resettando lo stato di autenticazione

# DELTA: Definizione della funzione handle_logout() all'interno o prima del blocco principale

# DELTA: Definizione della funzione handle_logout() all'interno o prima del blocco principale

def handle_logout():
    """Resetta lo stato per forzare la riapparizione della schermata di login con campi vuoti."""
    
    # 1. Pulisce lo stato principale di autenticazione
    if 'authenticated' in st.session_state:
        st.session_state['authenticated'] = False
        
    # 2. Pulisce la chiave specifica che memorizza lo username di Streamlit Authenticator
    #    (Questa è la chiave che probabilmente mantiene il campo username pre-compilato)
    if 'username' in st.session_state:
        del st.session_state['username']
        
    # 3. Pulisce i dati utente completi
    if 'user' in st.session_state:
        del st.session_state['user']
        
    # 4. Pulisce il flag read-only
    if 'read_only' in st.session_state:
        st.session_state['read_only'] = True 
        
    # Forza il riavvio
    st.rerun()

# --------------------------------------------------------------------------
# ... (Il tuo blocco if __name__ == "__main__": inizierà qui)
# --------------------------------------------------------------------------



def get_databases_and_collections():
    client = get_mongo_client()
    databases = {}
    for db_name in DATABASES:
        db = client[db_name]
        collections = db.list_collection_names()
        databases[db_name] = collections
    return databases

# --- Interfaccia CRUD ---
def crud_interface(selected_db, collection_name):
    db_emoji = EMOJI_MAP.get(selected_db, "")
    st.title(f"{db_emoji} {EMOJI_MAP['crud_title_prefix']} {collection_name} in {selected_db}")
    client = get_mongo_client()
    db = client[selected_db]
    collection = db[collection_name]

    # Filtri per Login/Actions nel DB Log
    query = {}
    # DELTA: Sostituisci l'intero blocco di Filtri per il DB Log
# Inizia attorno alla riga 112 nel tuo script

    # Filtri per Login/Actions nel DB Log
    query = {}
    if selected_db == "Log" and collection_name in ["Login", "Actions"]:
        st.header(EMOJI_MAP['filters'])
        
        # Uso di st.form per attuare i filtri solo al click del pulsante
        with st.form(key=f"log_filters_{collection_name}"):
            
            # --- Filtro Username ---
            col_user, col_field = st.columns([1, 1])
            with col_field:
                username_field = st.text_input("Campo username", value="username", key=f"user_field_{collection_name}")
            with col_user:
                username_value = st.text_input("Valore username", key=f"user_value_{collection_name}")
            
            if username_value:
                query[username_field] = username_value
                
            st.markdown("---") # Separatore
                
            # --- Filtro Temporale (Data + Ora) ---
            date_field = st.text_input("Campo data/ora (es. timestamp)", value="timestamp", key=f"date_field_{collection_name}")
            
            # Colonne per Data Inizio / Ora Inizio
            col_start_date, col_start_time = st.columns(2)
            with col_start_date:
                start_date = st.date_input("Data inizio", key=f"start_date_{collection_name}", value=datetime.today().date())
            with col_start_time:
                # NUOVO: Aggiungi input per l'ora di inizio (di default mezzanotte)
                start_time = st.time_input("Ora inizio", key=f"start_time_{collection_name}", value=datetime.min.time())

            # Colonne per Data Fine / Ora Fine
            col_end_date, col_end_time = st.columns(2)
            with col_end_date:
                end_date = st.date_input("Data fine", key=f"end_date_{collection_name}", value=datetime.today().date())
            with col_end_time:
                # NUOVO: Aggiungi input per l'ora di fine (di default l'ora corrente)
                end_time = st.time_input("Ora fine", key=f"end_time_{collection_name}", value=datetime.now().time())

            # Pulsante per applicare i filtri
            submitted = st.form_submit_button("🔎 Applica Filtri Log")
        
        # Logica di applicazione dei filtri temporali (eseguita solo se il form è stato inviato)
        if submitted or not st.session_state.get('log_filters_applied', False):
            
            st.session_state['log_filters_applied'] = True # Segna che i filtri sono stati applicati almeno una volta
            
            if start_date and end_date:
                if start_date <= end_date:
                    
                    # COMBINA DATA E ORA
                    start_datetime = datetime.combine(start_date, start_time)
                    end_datetime = datetime.combine(end_date, end_time)
                    
                    # Aggiungi il filtro solo se le date sono valide
                    query[date_field] = {
                        "$gte": start_datetime,
                        "$lte": end_datetime
                    }
                else:
                    st.error(f"{EMOJI_MAP['error']} La data di inizio deve essere precedente o uguale alla data di fine.")
                    # Se c'è un errore, forziamo una query vuota per non mostrare dati non filtrati
                    query = {"error": True} 

    # Recupera documenti con filtri (il resto dello script continua da qui)
    docs = list(collection.find(query))


    # Elenco record
    st.header(EMOJI_MAP['records_header'])
    
    if not docs:
        st.info(f"{EMOJI_MAP['info']} Nessun record trovato con i filtri applicati.")
        log_action(
            username=st.session_state.get('user', 'unknown'),
            action='no_records_found',
            torneo=f"{selected_db}.{collection_name}",
            details={'message': 'Nessun record con filtri'}
        )
    else:
        df = pd.DataFrame(docs)
        
        # --- LOGICA DI VISUALIZZAZIONE E EDITABILITÀ ---
        
        if selected_db == "giocatori_subbuteo":
            
            # Preparazione del DataFrame per l'editing
            df['_id_orig'] = df['_id'].apply(str) 
            df = df.drop(columns=['_id'])
            
            # Utilizza st.data_editor per rendere la tabella editabile
            edited_df = st.data_editor(
                df,
                key=f"data_editor_{collection_name}",
                # L'ID originale è visualizzato ma non editabile
                disabled=['_id_orig'] 
            )

            # Logica di salvataggio
            if st.button(EMOJI_MAP['save_table'], key=f"save_table_changes_{collection_name}"):
                
                updates_count = 0
                for index, row in edited_df.iterrows():
                    original_doc_id_str = row['_id_orig']
                    # Recupera la riga originale dal DF iniziale (più efficiente che query su mongo)
                    original_row = df[df['_id_orig'] == original_doc_id_str].iloc[0]
                    
                    changes = {}
                    for col in edited_df.columns:
                        if col != '_id_orig':
                            new_value = row[col]
                            original_value = original_row[col]
                            
                            # Confronta i valori (converte a stringa per confronto robusto)
                            if str(new_value) != str(original_value):
                                changes[col] = new_value

                    if changes:
                        object_id = ObjectId(original_doc_id_str)
                        collection.update_one(
                            {"_id": object_id},
                            {"$set": changes}
                        )
                        updates_count += 1
                        
                        log_action(
                            username=st.session_state.get('user', 'unknown'),
                            action='table_record_updated',
                            torneo=f"{selected_db}.{collection_name}",
                            details={'record_id': original_doc_id_str, 'updates': changes}
                        )
                
                if updates_count > 0:
                    st.success(f"{EMOJI_MAP['success']} Aggiornati {updates_count} record con successo!")
                else:
                    st.info(f"{EMOJI_MAP['info']} Nessuna modifica rilevata da salvare.")
                
                st.rerun() # Ricarica l'interfaccia per mostrare i dati aggiornati
                
        else:
            # Per tutti gli altri DB, usa il normale st.dataframe non editabile
            if "_id" in df.columns: # Ri-controllo per sicurezza, anche se rimosso per Subbuteo
                df = df.drop(columns=["_id"])
            st.dataframe(df)
        # --- FINE LOGICA DI VISUALIZZAZIONE ---


    # Modifica/elimina record (Singolo record)
    st.header(EMOJI_MAP['edit_delete_header'])
    if docs:
        doc_options = {str(doc["_id"]): doc for doc in docs}

        # --- FUNZIONE PER FORMATTARE IL SELETTORE IN MODO INTUITIVO ---
        def format_record_display(doc_id):
            doc = doc_options[doc_id]
            
            # CASO 1: giocatori_subbuteo
            if selected_db == "giocatori_subbuteo":
                giocatore = doc.get('Giocatore', 'N/D')
                squadra = doc.get('Squadra', 'N/D')
                return f"🧑 {giocatore} - Squadra: {squadra} (ID: {doc_id[-4:]})"
            
            # CASO 2: TorneiSubbuteo
            if selected_db == "TorneiSubbuteo":
                nome_torneo = doc.get('nome_torneo', 'N/D')
                if doc.get('turno_attivo') is not None:
                    data = doc.get('data_salvataggio')
                    # Gestione del campo data_salvataggio se è un oggetto datetime
                    data_str = data.strftime("%Y-%m-%d") if isinstance(data, datetime) else 'N/D'
                    turno = doc.get('turno_attivo', 'N/D')
                    return f"🇨🇭 {nome_torneo} - Turno {turno} - Salvato: {data_str} (ID: {doc_id[-4:]})"
                else:
                    return f"🇮🇹 {nome_torneo} (ID: {doc_id[-4:]})"
            
            # CASO 3: Log
            if selected_db == "Log":
                if collection_name == "Actions":
                    action = doc.get('action', 'N/D')
                    username = doc.get('username', 'N/D')
                    torneo = doc.get('torneo', '')
                    return f"⚡ Azione: {action} da {username} sul Torneo '{torneo}' (ID: {doc_id[-4:]})"
                elif collection_name == "Login":
                    username = doc.get('username', 'N/D')
                    esito = doc.get('esito', 'N/D')
                    return f"🔑 Accesso: {username} - Esito: {esito} (ID: {doc_id[-4:]})"

            # Default
            return f"Record ID: {doc_id}"
        # -----------------------------------------------------------------------

        selected_id = st.selectbox(
            "Seleziona un record da modificare/eliminare (modalità singola)",
            options=list(doc_options.keys()),
            format_func=format_record_display, 
            key=f"record_selector_{selected_db}_{collection_name}"
        )

        if selected_id:
            selected_doc = doc_options[selected_id]
            with st.form(key=f"edit_form_{selected_db}_{collection_name}"):
                updated_data = {}
                for field, value in selected_doc.items():
                    if field != "_id":
                        display_value = str(value)
                        if isinstance(value, datetime):
                            display_value = value.strftime("%Y-%m-%d %H:%M:%S")

                        updated_data[field] = st.text_input(
                            field,
                            value=display_value,
                            key=f"edit_{field}_{selected_id}"
                        )

                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button(f"{EMOJI_MAP['save_changes']}"):
                        updated_data.pop("_id", None)
                        updated_data = {k: v for k, v in updated_data.items() if v}
                        collection.update_one(
                            {"_id": ObjectId(selected_id)},
                            {"$set": updated_data}
                        )
                        log_action(
                            username=st.session_state.get('user', 'unknown'),
                            action='record_updated',
                            torneo=f"{selected_db}.{collection_name}",
                            details={'record_id': selected_id, 'updates': updated_data}
                        )
                        st.success(f"{EMOJI_MAP['success']} Record aggiornato con successo!")
                        st.rerun()

                with col2:
                    if st.form_submit_button(f"{EMOJI_MAP['delete_record']}"):
                        collection.delete_one({"_id": ObjectId(selected_id)})
                        log_action(
                            username=st.session_state.get('user', 'unknown'),
                            action='record_deleted',
                            torneo=f"{selected_db}.{collection_name}",
                            details={'record_id': selected_id}
                        )
                        st.success(f"{EMOJI_MAP['success']} Record eliminato con successo!")
                        st.rerun()

    # Inserimento nuovo record (solo per giocatori_subbuteo)
    if selected_db == "giocatori_subbuteo":
        st.header(EMOJI_MAP['new_record_header'])
        sample_doc = collection.find_one()
        if sample_doc:
            new_data = {}
            for field in sample_doc:
                if field != "_id":
                    new_data[field] = st.text_input(field, key=f"new_{field}_{collection_name}")

            if st.button(f"{EMOJI_MAP['save_new']}", key=f"save_new_{collection_name}"):
                new_data = {k: v for k, v in new_data.items() if v}
                if new_data:
                    collection.insert_one(new_data)
                    log_action(
                        username=st.session_state.get('user', 'unknown'),
                        action='record_inserted',
                        torneo=f"{selected_db}.{collection_name}",
                        details={'record': new_data}
                    )
                    st.success(f"{EMOJI_MAP['success']} Record aggiunto con successo!")
                    st.rerun()
                else:
                    st.warning(f"{EMOJI_MAP['warning']} Nessun dato valido da inserire.")
        else:
            st.info(f"{EMOJI_MAP['info']} Collection vuota, inserisci campi manualmente.")
            field_name = st.text_input("Nome campo", key="new_field_name")
            field_value = st.text_input("Valore campo", key="new_field_value")
            if st.button("Aggiungi campo ➕", key="add_field_btn") and field_name and field_value:
                collection.insert_one({field_name: field_value})
                st.success(f"{EMOJI_MAP['success']} Campo aggiunto con successo!")
                st.rerun()

    # Logging apertura CRUD
    log_action(
        username=st.session_state.get('user', 'unknown'),
        action='crud_interface_opened',
        torneo=f"{selected_db}.{collection_name}",
        details={'message': 'Interfaccia CRUD aperta'}
    )
# --- App principale ---
# DELTA 2: Sostituisci l'intero blocco if __name__ == "__main__":
# --------------------------------------------------------------------------
# --- App principale (con autenticazione e vincolo utente) ---
# DELTA CORRETTO E DEFINITIVO: Sostituisci l'intero blocco if __name__ == "__main__":
# --------------------------------------------------------------------------
# --- App principale (con autenticazione e vincolo utente) ---
if __name__ == "__main__":
    
    # 1. Mostra la schermata di autenticazione se non si è già autenticati
    if not st.session_state.get('authenticated', False):
        # Chiama la funzione corretta per mostrare la schermata di login
        # Ho rimosso 'club="Superba"' perché non ha senso per un manager CRUD generico, 
        # ma se è obbligatorio nel tuo auth_utils, ripristinalo.
        auth.show_auth_screen() 
        st.stop()  # blocca tutto finché non sei loggato

    # 2. Debug: mostra utente autenticato e ruolo (come nel tuo snippet)
    user_info = auth.get_current_user()
    current_username = user_info.get('username')
    
    st.sidebar.markdown(f"**👤 Utente:** {current_username}")
    st.sidebar.markdown(f"**🔑 Ruolo:** {user_info.get('role', '??')}")
    
    # 3. VERIFICA DELL'ACCESSO: Utente deve essere Legnaro72 E avere permessi di scrittura
    if current_username == "Legnaro72" and auth.verify_write_access():
        
        st.title(EMOJI_MAP['title'])
        st.sidebar.success(f"Accesso Autorizzato: {current_username} (CRUD Manager)")
        
        st.sidebar.title(EMOJI_MAP['sidebar_title'])
        databases = get_databases_and_collections()

        selected_db = st.sidebar.selectbox(
            "Seleziona un database",
            options=list(databases.keys()),
            format_func=lambda x: f"{EMOJI_MAP.get(x, '📁')} {x}",
            key="db_selector"
        )
        collection_name = st.sidebar.selectbox(
            "Seleziona una collection",
            options=databases[selected_db],
            key="collection_selector"
        )
        
        # Logout button
        if st.sidebar.button("Logout 🚪", key="logout_btn"):
            handle_logout()

        # --- Qui continua il resto della logica dell'interfaccia CRUD ---
        
        # Bulk delete tornei (mantieni campionati)
        st.sidebar.header(EMOJI_MAP['bulk_delete_header'])
        st.sidebar.warning(EMOJI_MAP['bulk_delete_warning'])
        tournament_field = st.sidebar.text_input("Campo nome torneo", value="nome_torneo", key="tournament_field")
        if st.sidebar.button("Esegui cancellazione bulk 🗑️", key="bulk_delete_btn"):
            client = get_mongo_client()
            db = client[selected_db]
            collection = db[collection_name]
            query = {tournament_field: {"$not": {"$regex": "CAMPIONATO", "$options": "i"}}}
            deleted_count = collection.delete_many(query).deleted_count
            log_action(
                username=st.session_state.get('user', 'unknown'),
                action='bulk_delete_tournaments',
                torneo=f"{selected_db}.{collection_name}",
                details={'deleted_count': deleted_count, 'kept_with': 'CAMPIONATO'}
            )
            st.sidebar.success(f"{EMOJI_MAP['success']} Cancellati {deleted_count} record.")
            st.rerun()

        # Pulizia Log
        st.sidebar.header(EMOJI_MAP['log_cleanup_header'])
        st.sidebar.warning(EMOJI_MAP['log_cleanup_warning'])
        log_collection = st.sidebar.selectbox(
            "Seleziona collection da svuotare",
            ["Login", "Actions"],
            key="log_collection_selector"
        )
        if st.sidebar.button("Svuota collection selezionata 💥", key="empty_log_btn"):
            client = get_mongo_client()
            db = client["Log"]
            collection = db[log_collection]
            deleted_count = collection.delete_many({}).deleted_count
            log_action(
                username=st.session_state.get('user', 'unknown'),
                action='all_records_delete',
                torneo=f"Log.{log_collection}",
                details={'deleted_count': deleted_count}
            )
            st.sidebar.success(f"{EMOJI_MAP['success']} Cancellati {deleted_count} record da {log_collection}.")
            st.rerun()

        # Mostra l'interfaccia CRUD
        crud_interface(selected_db, collection_name)
        
    else:
        # Utente autenticato ma non Legnaro72 o non ha permessi di scrittura
        st.error(f"❌ Accesso Negato. L'utente '{current_username}' non è autorizzato ad usare il MongoDB CRUD Manager o non ha permessi di scrittura.")
        if st.sidebar.button("Logout 🚪", key="logout_btn_denied"):
            handle_logout()
# --------------------------------------------------------------------------