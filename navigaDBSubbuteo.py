import os
from pymongo import MongoClient
from bson import ObjectId
import streamlit as st
import pandas as pd
from logging_utils import log_action # Assumendo che esista
from datetime import datetime

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
    if selected_db == "Log" and collection_name in ["Login", "Actions"]:
        st.header(EMOJI_MAP['filters'])

        username_field = st.text_input("Campo username (es. username)", value="username", key=f"user_field_{collection_name}")
        username_value = st.text_input("Valore username", key=f"user_value_{collection_name}")
        if username_value:
            query[username_field] = username_value

        date_field = st.text_input("Campo data/ora (es. timestamp)", value="timestamp", key=f"date_field_{collection_name}")
        start_date = st.date_input("Data inizio", key=f"start_date_{collection_name}")
        end_date = st.date_input("Data fine", key=f"end_date_{collection_name}")
        if start_date and end_date:
            if start_date <= end_date:
                query[date_field] = {
                    "$gte": datetime.combine(start_date, datetime.min.time()),
                    "$lte": datetime.combine(end_date, datetime.max.time())
                }
            else:
                st.error(f"{EMOJI_MAP['error']} La data di inizio deve essere precedente alla data di fine.")

    # Recupera documenti con filtri
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
if __name__ == "__main__":
    st.title(EMOJI_MAP['title'])
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

    crud_interface(selected_db, collection_name)