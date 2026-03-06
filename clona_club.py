import os

# CONFIGURAZIONE: Assicurati che i nomi corrispondano a quelli in auth_utils.py
CLUBS = {
    "PierCrew": {
        "search": "Superba",
        "search_low": "superba",
        "search_phrase": "DELLA SUPERBA",
        "replace_phrase": "DEL PIER CREW",
        "logo": "logo_piercrew.jpg"
    },
    "Tigullio": {
        "search": "Superba",
        "search_low": "superba",
        "search_phrase": "DELLA SUPERBA",
        "replace_phrase": "DEL TIGULLIO",
        "logo": "logo_tigullio.jpg"
    }
}

# Lista dei file "Sorgente" (Club Superba)
FILES_TO_SYNC = [
    "TorneoSubbuteoItalianaSuperbaAllDB.py",
    "TorneoSubbuteoSvizzeroSuperbaAllDBNewVersion.py",
    "TorneoSubbuteoFasiFinaliItalianaSuperbaAllDB.py",
    "hubTorneiSubbuteoSuperbaAllDB.py",
    "editSuperbaClubAllDBNew.py"
]

def sync():
    print("--- Inizio sincronizzazione Club Subbuteo ---")
    generated_count = 0
    
    for club_name, config in CLUBS.items():
        print(f"\n--- Elaborazione Club: {club_name} ---")
        for filename in FILES_TO_SYNC:
            if not os.path.exists(filename):
                print(f"[!] Attenzione: File sorgente '{filename}' non trovato. Salto.")
                continue
            
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Sostituzioni basate sulla configurazione
            new_content = content.replace(config["search"], club_name)
            new_content = new_content.replace(config["search_low"], club_name.lower())
            new_content = new_content.replace(config["search_phrase"], config["replace_phrase"])
            
            # Sostituisce il logo
            new_content = new_content.replace("logo_superba.jpg", config["logo"])
            
            # Genera il nuovo nome file
            new_filename = filename.replace("Superba", club_name)
            
            with open(new_filename, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print(f"[OK] Generato: {new_filename}")
            generated_count += 1

    print(f"\nSincronizzazione completata! Generati {generated_count} file in totale.")
    print("Ora puoi caricare tutto su GitHub.")

if __name__ == "__main__":
    sync()
