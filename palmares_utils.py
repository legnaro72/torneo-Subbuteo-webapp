import streamlit as st

def normalize_tournament_name(name: str) -> str:
    if not name:
        return ""
    # Rimuove SOLO i suffissi/prefissi tecnici di stato (NON quelli che identificano il tipo di torneo)
    suffixes_to_remove = ["_completed", "_incomplete"]
    prefixes_to_remove = ["completato_", "finito_"]
    for s in suffixes_to_remove:
        name = name.replace(s, "")
    for p in prefixes_to_remove:
        name = name.replace(p, "")
    return name.strip()

def lower_normalize(name: str) -> str:
    return normalize_tournament_name(name).lower()

def already_registered(lista, tournament_name: str) -> bool:
    if not lista:
        return False
    normalized = lower_normalize(tournament_name)
    for t in lista:
        if lower_normalize(t) == normalized:
            return True
    return False

def register_win(db_players_col, winner_name: str, tournament_name: str, tournament_type: str, num_gironi: int = 1, mode_fasi_finali: str = None):
    """
    Registra la vittoria nel palmarès del giocatore (solo per Superba_players).
    
    :param db_players_col: La collection MongoDB (es. Superba_players)
    :param winner_name: Il nome del giocatore o stringa "Squadra - Giocatore"
    :param tournament_name: Il nome del torneo originale
    :param tournament_type: 'italiana', 'svizzero', 'fasi_finali'
    :param num_gironi: numero di gironi totali (se type == 'italiana', aggiorna campionati solo se == 1)
    :param mode_fasi_finali: 'eliminazione_diretta' o 'gironi' (se type == 'fasi_finali')
    """
    try:
        # Estrazione pulita del nome giocatore se nel formato "Squadra - Giocatore"
        real_winner = winner_name
        if " - " in winner_name:
            real_winner = winner_name.split(" - ")[-1].strip()
        
        # Ricerca robusta: prova per nome giocatore OPPURE per squadra
        player = db_players_col.find_one({
            "$or": [
                {"Giocatore": real_winner},
                {"Squadra": real_winner}
            ]
        })
        
        # Se il giocatore non esiste nel DB, SKIP
        if not player:
            print(f"[PALMARES] Vincitore '{real_winner}' non trovato nel DB (Ospite?). Skip.")
            return

        name_to_save = normalize_tournament_name(tournament_name)
        updates = {}
        
        # Helper interno per gestire liste e contatori senza duplicati
        def add_to_list(list_field, count_field):
            current_list = player.get(list_field, [])
            if not isinstance(current_list, list):
                current_list = []
            
            if not already_registered(current_list, name_to_save):
                current_list.append(name_to_save)
                current_count = int(player.get(count_field, 0)) + 1
                updates[list_field] = current_list
                updates[count_field] = current_count
                return True
            return False

        # LOGICA DI ASSEGNAZIONE
        t_name_lower = tournament_name.lower()
        
        if "eliminazionediretta" in t_name_lower or mode_fasi_finali == "eliminazione_diretta":
            add_to_list("listaFFElimDirettaVinte", "NFFElimDirettaVinte")
        
        elif "fasefinaleagironi" in t_name_lower or mode_fasi_finali == "gironi":
            add_to_list("listaGironiFFVinti", "NGironiFFVinti")
            
        elif tournament_type == "svizzero":
            # Lo svizzero viene considerato CAMPIONATO come da richiesta esplicita
            add_to_list("listaCampionatiVinti", "NCampionatiVinti")
            
        elif tournament_type == "italiana":
            # Per l'italiana, si vince il campionato solo se è un girone unico (Campionato)
            # Se ci sono più gironi, è una fase preliminare (Fase a Gironi)
            if num_gironi == 1:
                add_to_list("listaCampionatiVinti", "NCampionatiVinti")
            else:
                add_to_list("listaGironiFFVinti", "NGironiFFVinti")
        
        else:
            # Fallback
            if tournament_type == "fasi_finali":
                add_to_list("listaGironiFFVinti", "NGironiFFVinti")

        # Se c'è stato un aggiornamento, salva nel DB
        if updates:
            db_players_col.update_one(
                {"_id": player["_id"]},
                {"$set": updates}
            )
            print(f"[PALMARES] Aggiornato {real_winner} con: {updates}")
            return True
        return False
        
    except Exception as e:
        print(f"[PALMARES ERROR] {e}")
        return False
