import streamlit as st

import tkinter as tk
from tkinter import simpledialog, messagebox
import webbrowser
import os

def genera_calendario_html(num_gironi, nomi_giocatori):
    # Dividi i giocatori in gironi il piu equamente possibile
    giocatori_per_girone = len(nomi_giocatori) // num_gironi
    extra = len(nomi_giocatori) % num_gironi

    gironi = []
    start = 0
    for i in range(num_gironi):
        end = start + giocatori_per_girone + (1 if i < extra else 0)
        gironi.append(nomi_giocatori[start:end])
        start = end

    # Costruisci il codice HTML come raw string per evitare problemi con \d e altri backslash
    html = r"""
<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8" />
<title>Calendario Gironi Torneo</title>
<style>
    body { font-family: Arial, sans-serif; background:#f5f5f5; margin:20px; }
    h2 { background:#004080; color:#fff; padding:10px; border-radius:5px; }
    table { border-collapse: collapse; width: 100%; max-width: 800px; margin-bottom: 40px; background:#fff; box-shadow: 0 0 5px #ccc; }
    th, td { border: 1px solid #ccc; padding: 8px; text-align: center; }
    th { background: #004080; color: white; }
    input[type=number] { width: 40px; }
    .container { margin-bottom: 60px; }
    .classifica { margin-top: 10px; }
    .btn-save {
        background:#004080; color:#fff; border:none; padding:10px 20px; cursor:pointer;
        border-radius:5px; font-size:16px; margin-bottom: 50px;
    }
    .btn-save:hover { background:#0066cc; }
</style>
</head>
<body>
<h1>Calendario e Classifica Torneo</h1>
"""

    # Costruiamo la struttura gironi, partite e classifica
    for idx, girone in enumerate(gironi, start=1):
        html += f'<div class="container">\n'
        html += f'<h2>Girone {idx}</h2>\n'
        html += '<table>\n<thead><tr><th>Casa</th><th>Risultato Casa</th><th>Risultato Ospite</th><th>Ospite</th></tr></thead>\n<tbody>\n'

        # Partite round robin (all'italiana)
        n = len(girone)
        for i in range(n):
            for j in range(i+1, n):
                casa = girone[i]
                ospite = girone[j]
                html += f'<tr>'
                html += f'<td>{casa}</td>'
                html += f'<td><input type="number" min="0" max="99" class="res_casa" data-girone="{idx}" data-casa="{casa}" data-ospite="{ospite}"></td>'
                html += f'<td><input type="number" min="0" max="99" class="res_ospite" data-girone="{idx}" data-casa="{casa}" data-ospite="{ospite}"></td>'
                html += f'<td>{ospite}</td>'
                html += '</tr>\n'
        html += '</tbody></table>\n'

        # Tabella classifica
        html += f'<h3>Classifica Girone {idx}</h3>\n'
        html += f'<table class="classifica" id="classifica_{idx}">\n<thead><tr><th>Pos.</th><th>Giocatore</th><th>Punti</th><th>V</th><th>P</th><th>S</th><th>GF</th><th>GS</th><th>DR</th></tr></thead>\n<tbody>\n'
        for giocatore in girone:
            html += f'<tr data-giocatore="{giocatore}"><td></td><td>{giocatore}</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td></tr>\n'
        html += '</tbody></table>\n'
        html += '</div>\n'

    # Suggerimenti semifinali/finale
    html += """
    <h2>Fasi Finali (Suggerite)</h2>
    <p id="fase_finale"></p>
    <button class="btn-save" onclick="salvaHTML()">Salva pagina modificata</button>

<script>
function aggiornaClassifiche() {
    const gironi = document.querySelectorAll('.container');
    gironi.forEach((container) => {
        const gironeNum = container.querySelector('h2').textContent.match(/\\d+/)[0];
        const risultatiCasa = container.querySelectorAll('.res_casa');
        const risultatiOspite = container.querySelectorAll('.res_ospite');
        const classifica = container.querySelector(`#classifica_${gironeNum} tbody`);
        // Reset classifica
        const squadre = {};
        classifica.querySelectorAll('tr').forEach(tr => {
            const giocatore = tr.dataset.giocatore;
            squadre[giocatore] = { punti:0, V:0, P:0, S:0, GF:0, GS:0 };
        });

        // Calcolo risultati
        for(let i=0; i<risultatiCasa.length; i++) {
            const r_casa = risultatiCasa[i].value;
            const r_ospite = risultatiOspite[i].value;
            const casa = risultatiCasa[i].dataset.casa;
            const ospite = risultatiCasa[i].dataset.ospite;

            if(/^\\d+$/.test(r_casa) && /^\\d+$/.test(r_ospite)) {
                let c = parseInt(r_casa);
                let o = parseInt(r_ospite);

                squadre[casa].GF += c;
                squadre[casa].GS += o;
                squadre[ospite].GF += o;
                squadre[ospite].GS += c;

                if(c > o) {
                    squadre[casa].punti += 2;
                    squadre[casa].V += 1;
                    squadre[ospite].S += 1;
                } else if(c === o) {
                    squadre[casa].punti += 1;
                    squadre[ospite].punti += 1;
                    squadre[casa].P += 1;
                    squadre[ospite].P += 1;
                } else {
                    squadre[ospite].punti += 2;
                    squadre[ospite].V += 1;
                    squadre[casa].S += 1;
                }
            }
        }

        // Ordina squadre per punti, differenza reti, gol fatti
        const sorted = Object.keys(squadre).sort((a,b) => {
            if(squadre[b].punti !== squadre[a].punti) return squadre[b].punti - squadre[a].punti;
            let drb = squadre[b].GF - squadre[b].GS;
            let dra = squadre[a].GF - squadre[a].GS;
            if(drb !== dra) return drb - dra;
            if(squadre[b].GF !== squadre[a].GF) return squadre[b].GF - squadre[a].GF;
            return a.localeCompare(b);
        });

        // Aggiorna tabella
        let pos = 1;
        sorted.forEach(giocatore => {
            const tr = classifica.querySelector(`tr[data-giocatore="${giocatore}"]`);
            tr.children[0].textContent = pos++;
            tr.children[2].textContent = squadre[giocatore].punti;
            tr.children[3].textContent = squadre[giocatore].V;
            tr.children[4].textContent = squadre[giocatore].P;
            tr.children[5].textContent = squadre[giocatore].S;
            tr.children[6].textContent = squadre[giocatore].GF;
            tr.children[7].textContent = squadre[giocatore].GS;
            tr.children[8].textContent = squadre[giocatore].GF - squadre[giocatore].GS;
        });

        // Calcolo quanti qualificati: assumiamo i primi 2 di ogni girone
let num_gironi = document.querySelectorAll('.container').length;
let qualificati = num_gironi * 2;

if(qualificati >= 4) {
    document.getElementById('fase_finale').innerHTML = `<strong>Si consiglia di organizzare semifinali e finale.</strong><br>
    Numero giocatori qualificati: ${qualificati}`;
} else if (qualificati === 2) {
    document.getElementById('fase_finale').innerHTML = `<strong>Solo finale diretta.</strong><br>
    Numero giocatori qualificati: ${qualificati}`;
} else {
    document.getElementById('fase_finale').innerHTML = `<strong>Numero insufficiente per semifinale/finale.</strong>`;
}

    });
}

document.querySelectorAll('.res_casa, .res_ospite').forEach(input => {
    input.addEventListener('input', aggiornaClassifiche);
});

// Primo calcolo appena caricato
window.onload = aggiornaClassifiche;

function salvaHTML() {
    let htmlContent = '<!DOCTYPE html>\\n' + document.documentElement.outerHTML;
    let blob = new Blob([htmlContent], {type: 'text/html'});
    let url = URL.createObjectURL(blob);
    let a = document.createElement('a');
    a.href = url;
    a.download = 'torneo_calendario.html';
    a.click();
    URL.revokeObjectURL(url);
}
</script>
</body>
</html>
"""
    return html

def main():
    root = tk.Tk()
    root.withdraw()

    # Chiedi il numero di gironi
    while True:
        try:
            num_gironi = simpledialog.askinteger("Input", "Inserisci il numero di gironi (minimo 1):", minvalue=1)
            if num_gironi is None:
                messagebox.showinfo("Info", "Operazione annullata.")
                return
            break
        except Exception:
            continue

    # Chiedi nomi giocatori separati da virgola
    nomi_str = simpledialog.askstring("Input", "Inserisci i nomi dei giocatori separati da virgola:")
    if nomi_str is None:
        messagebox.showinfo("Info", "Operazione annullata.")
        return

    nomi_giocatori = [n.strip() for n in nomi_str.split(",") if n.strip()]
    if len(nomi_giocatori) < num_gironi:
        messagebox.showerror("Errore", "Numero di giocatori minore del numero di gironi!")
        return

    # Genera HTML
    html = genera_calendario_html(num_gironi, nomi_giocatori)

    # Salva in file
    filename = "torneo_calendario.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)

    messagebox.showinfo("Fatto", f"File '{filename}' creato con successo.")
    # Apri il file nel browser predefinito
    webbrowser.open('file://' + os.path.realpath(filename))

if __name__ == "__main__":
    main()
