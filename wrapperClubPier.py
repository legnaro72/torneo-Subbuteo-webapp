import runpy

# Parametri cablati per il club Pier Crew
HUB_URL = "https://farm-tornei-subbuteo-piercrew-all-db.streamlit.app/"

# Esegue lo script passandogli il contesto necessario (Pier Crew)
runpy.run_path("editPierCrewClubAllDBNew.py", init_globals={"HUB_URL": HUB_URL, "CLUB_NAME": "Pier Crew"})