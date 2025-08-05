import streamlit as st

def genera_calendario_html(num_gironi, nomi_giocatori):
    giocatori_per_girone = len(nomi_giocatori) // num_gironi
    extra = len(nomi_giocatori) % num_gironi

    gironi = []
    start = 0
    for i in range(num_gironi):
        end = start + giocatori_per_girone + (1 if i < extra else 0)
        gironi.append(nomi_giocatori[start:end])
        start = end

    # Inserisci qui il tuo codice HTML completo (quello che hai già)
    with open("template.html", "r", encoding="utf-8") as f:
        template = f.read()

    # Sostituisci i dati dinamici nel template
    sezioni = ""
    for idx, girone in enumerate(gironi, start=1):
        sezioni += f"<div class='container'>\n"
        sezioni += f"<h2>Girone {idx}</h2>\n"
        sezioni += "<table>\n<thead><tr><th>Casa</th><th>Risultato Casa</th><th>Risultato Ospite</th><th>Ospite</th></tr></thead>\n<tbody>\n"
        n = len(girone)
        for i in range(n):
            for j in range(i+1, n):
                casa = girone[i]
                ospite = girone[j]
                sezioni += f'<tr><td>{casa}</td><td><input type="number" class="res_casa" data-girone="{idx}" data-casa="{casa}" data-ospite="{ospite}"></td>'
                sezioni += f'<td><input type="number" class="res_ospite" data-girone="{idx}" data-casa="{casa}" data-ospite="{ospite}"></td><td>{ospite}</td></tr>\n'
        sezioni += "</tbody></table>\n"

        sezioni += f"<h3>Classifica Girone {idx}</h3>\n"
        sezioni += f"<table class='classifica' id='classifica_{idx}'><thead><tr><th>Pos.</th><th>Giocatore</th><th>Punti</th><th>V</th><th>P</th><th>S</th><th>GF</th><th>GS</th><th>DR</th></tr></thead><tbody>\n"
        for giocatore in girone:
            sezioni += f'<tr data-giocatore="{giocatore}"><td></td><td>{giocatore}</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>\n'
        sezioni += "</tbody></table>\n</div>\n"

    final_html = template.replace("<!--GIRONE_PLACEHOLDER-->", sezioni)
    return final_html


st.title("Calendario Torneo")

num_gironi = st.number_input("Numero di gironi", min_value=1, max_value=10, value=2)

nomi_str = st.text_area("Inserisci i nomi dei giocatori separati da virgola", "")
if st.button("Genera Calendario"):
    nomi_giocatori = [n.strip() for n in nomi_str.split(",") if n.strip()]
    if len(nomi_giocatori) < num_gironi:
        st.error("Numero di giocatori minore del numero di gironi!")
    else:
        html = genera_calendario_html(num_gironi, nomi_giocatori)
        st.download_button("Scarica HTML", html, file_name="torneo_calendario.html")
        st.components.v1.html(html, height=800, scrolling=True)
