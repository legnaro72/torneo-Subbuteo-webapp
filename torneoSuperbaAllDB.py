import streamlit as st
import pandas as pd
from datetime import datetime
import random
import time
from fpdf import FPDF
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from bson import ObjectId

=============================

CONFIGURAZIONE PAGINA

=============================

st.set_page_config(page_title="⚽ Torneo Subbuteo - Full MongoDB", layout="wide")

=============================

UTILS UI

=============================

st.markdown( """ <style> ul, li { list-style-type: none !important; padding-left: 0 !important; margin-left: 0 !important; } .big-title { text-align: center; font-size: clamp(16px, 4vw, 36px); font-weight: bold; margin-top: 10px; margin-bottom: 20px; color: red; word-wrap: break-word; white-space: normal; } div[data-testid="stNumberInput"] label::before { content: none; } </style> """, unsafe_allow_html=True, )

def combined_style(df: pd.DataFrame): is_dark = st.get_option("theme.base") == "dark"

def apply_row_style(row):
    base = [""] * len(row)
    if row.name == 0:
        base = ['background-color: #d4edda; color: black'] * len(row)
    elif row.name <= 2:
        base = ['background-color: #fff3cd; color: black'] * len(row)
    return base

def hide_none(val):
    sval = str(val).strip().lower()
    if sval in ["none", "nan", ""]:
        return 'color: transparent; text-shadow: none;'
    return ''

styled_df = df.style.apply(apply_row_style, axis=1)
styled_df = styled_df.map(hide_none)
return styled_df

=============================

DATABASE LAYER

=============================

class DB: def init(self, uri: str): self.client = MongoClient(uri, server_api=ServerApi('1')) # DB esistente per i giocatori (già usato dall'utente) self.db_players = self.client.get_database("giocatori_subbuteo") self.players_col = self.db_players.get_collection("superba_players") # DB dell'app per tornei/partite/classifiche self.db_app = self.client.get_database("torneo_subbuteo_app") self.tournaments = self.db_app.get_collection("tournaments") self.matches = self.db_app.get_collection("matches") self.standings = self.db_app.get_collection("standings")

# --- PLAYERS ---
def get_players(self) -> pd.DataFrame:
    try:
        df = pd.DataFrame(list(self.players_col.find({}, {"_id": 0})))
        if df.empty or 'Giocatore' not in df.columns:
            return pd.DataFrame(columns=["Giocatore", "Squadra", "Potenziale"])  # fallback
        return df
    except Exception:
        return pd.DataFrame(columns=["Giocatore", "Squadra", "Potenziale"])  # fallback

# --- TOURNAMENTS ---
def create_tournament(self, name: str, num_groups: int, calendar_type: str, players_info: dict, groups_map: list):
    doc = {
        "name": name,
        "created_at": datetime.utcnow(),
        "num_groups": num_groups,
        "calendar_type": calendar_type,  # "Solo andata" | "Andata e ritorno"
        # players_info: { nickname: { Squadra: str, Potenziale: int } }
        "players_info": players_info,
        # groups_map: [["Squadra (Nome)", ...], ...]
        "groups_map": groups_map,
    }
    _id = self.tournaments.insert_one(doc).inserted_id
    return str(_id)

def get_tournament(self, tid: str):
    return self.tournaments.find_one({"_id": ObjectId(tid)})

def list_tournaments(self):
    cur = self.tournaments.find({}, {"name": 1, "created_at": 1})
    return [{"_id": str(x["_id"]), "name": x.get("name"), "created_at": x.get("created_at") } for x in cur]

# --- MATCHES ---
def insert_matches(self, tid: str, matches: list[dict]):
    # normalizza e inserisce in blocco
    for m in matches:
        m["tournament_id"] = tid
    if matches:
        self.matches.insert_many(matches)

def get_groups(self, tid: str):
    pipe = [
        {"$match": {"tournament_id": tid}},
        {"$group": {"_id": "$group", "giornate": {"$addToSet": "$round"}}},
        {"$project": {"group": "$_id", "giornate": 1, "_id": 0}},
        {"$sort": {"group": 1}},
    ]
    return list(self.matches.aggregate(pipe))

def get_rounds_for_group(self, tid: str, group_name: str):
    cur = self.matches.find({"tournament_id": tid, "group": group_name}, {"round": 1})
    return sorted(set([int(doc["round"]) for doc in cur]))

def get_matches(self, tid: str, group_name: str, round_num: int):
    cur = self.matches.find(
        {"tournament_id": tid, "group": group_name, "round": int(round_num)},
        {"_id": 0}
    ).sort([("group", 1), ("round", 1)])
    return pd.DataFrame(list(cur))

def update_match(self, tid: str, group_name: str, round_num: int, home: str, away: str, sh: int, sa: int, validated: bool):
    self.matches.update_one(
        {
            "tournament_id": tid,
            "group": group_name,
            "round": int(round_num),
            "home": home,
            "away": away,
        },
        {"$set": {"score_home": int(sh), "score_away": int(sa), "validated": bool(validated)}}
    )

def get_all_matches_df(self, tid: str) -> pd.DataFrame:
    cur = self.matches.find({"tournament_id": tid}, {"_id": 0})
    return pd.DataFrame(list(cur))

# --- STANDINGS ---
def recompute_and_store_standings(self, tid: str):
    df = self.get_all_matches_df(tid)
    if df.empty:
        self.standings.delete_many({"tournament_id": tid})
        return pd.DataFrame(columns=["group", "player", "points", "wins", "draws", "losses", "gf", "ga", "diff"])  # empty

    df = df[df.get("validated", False) == True]
    if df.empty:
        self.standings.delete_many({"tournament_id": tid})
        return pd.DataFrame(columns=["group", "player", "points", "wins", "draws", "losses", "gf", "ga", "diff"])  # empty

    groups = sorted(df['group'].dropna().unique().tolist())
    out_frames = []
    for g in groups:
        subset = df[df['group'] == g]
        teams = sorted(pd.unique(pd.concat([subset['home'], subset['away']])))
        stats = {t: {"points": 0, "wins": 0, "draws": 0, "losses": 0, "gf": 0, "ga": 0} for t in teams}
        for _, r in subset.iterrows():
            sh = int(r.get('score_home', 0) or 0)
            sa = int(r.get('score_away', 0) or 0)
            h = r['home']; a = r['away']
            stats[h]['gf'] += sh; stats[h]['ga'] += sa
            stats[a]['gf'] += sa; stats[a]['ga'] += sh
            if sh > sa:
                stats[h]['points'] += 2; stats[h]['wins'] += 1; stats[a]['losses'] += 1
            elif sh < sa:
                stats[a]['points'] += 2; stats[a]['wins'] += 1; stats[h]['losses'] += 1
            else:
                stats[h]['points'] += 1; stats[a]['points'] += 1
                stats[h]['draws'] += 1; stats[a]['draws'] += 1
        df_stat = pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index': 'player'})
        df_stat['diff'] = df_stat['gf'] - df_stat['ga']
        df_stat['group'] = g
        out_frames.append(df_stat)
    table = pd.concat(out_frames, ignore_index=True)
    # salva su collection standings (upsert per riga)
    for _, row in table.iterrows():
        self.standings.update_one(
            {"tournament_id": tid, "group": row['group'], "player": row['player']},
            {"$set": {
                "points": int(row['points']), "wins": int(row['wins']), "draws": int(row['draws']),
                "losses": int(row['losses']), "gf": int(row['gf']), "ga": int(row['ga']), "diff": int(row['diff'])
            }},
            upsert=True
        )
    # rimuove eventuali standings di giocatori non più presenti
    self.standings.delete_many({"tournament_id": tid, "group": {"$nin": list(table['group'].unique())}})
    return table

def get_standings_df(self, tid: str) -> pd.DataFrame:
    cur = self.standings.find({"tournament_id": tid}, {"_id": 0})
    df = pd.DataFrame(list(cur))
    if df.empty:
        return df
    df = df.sort_values(by=["group", "points", "diff"], ascending=[True, False, False])
    return df

=============================

BUSINESS LOGIC

=============================

def round_robin_from_groups(groups_map: list[list[str]], calendar_type: str): """Genera partite da groups_map [[p1,p2,...], [q1,q2,...], ...]. Restituisce lista di dict pronti per DB.matches """ matches = [] for idx, group in enumerate(groups_map, 1): group_name = f"Girone {idx}" teams = group[:] if len(teams) % 2 == 1: teams.append("Riposo") n = len(teams) half = n // 2 arr = teams[:] # andata for day in range(n - 1): for i in range(half): home, away = arr[i], arr[-(i+1)] if home != "Riposo" and away != "Riposo": matches.append({ "group": group_name, "round": day + 1, "home": home, "away": away, "score_home": None, "score_away": None, "validated": False, }) if calendar_type == "Andata e ritorno": matches.append({ "group": group_name, "round": day + 1 + (n - 1), "home": away, "away": home, "score_home": None, "score_away": None, "validated": False, }) arr = [arr[0]] + [arr[-1]] + arr[1:-1] return matches

def esporta_pdf(df_matches: pd.DataFrame, df_standings: pd.DataFrame) -> bytes: pdf = FPDF(orientation='P', unit='mm', format='A4') pdf.set_auto_page_break(auto=False) pdf.add_page() pdf.set_font("Arial", 'B', 16) pdf.cell(0, 10, "Calendario e Classifiche Torneo", ln=True, align='C')

line_height = 6
margin_bottom = 15
page_height = 297

gironi = sorted(df_matches['group'].dropna().unique().tolist())

for girone in gironi:
    pdf.set_font("Arial", 'B', 14)
    if pdf.get_y() + 8 + margin_bottom > page_height:
        pdf.add_page()
    pdf.cell(0, 8, f"{girone}", ln=True)

    giornate = sorted(set(df_matches[df_matches['group'] == girone]['round'].dropna().tolist()))

    for g in giornate:
        needed_space = 7 + line_height + line_height + margin_bottom
        if pdf.get_y() + needed_space > page_height:
            pdf.add_page()

        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 7, f"Giornata {int(g)}", ln=True)
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(60, 6, "Casa", border=1)
        pdf.cell(20, 6, "Gol", border=1, align='C')
        pdf.cell(20, 6, "Gol", border=1, align='C')
        pdf.cell(60, 6, "Ospite", border=1)
        pdf.ln()

        pdf.set_font("Arial", '', 11)
        partite = df_matches[(df_matches['group'] == girone) & (df_matches['round'] == g)]
        for _, row in partite.iterrows():
            if pdf.get_y() + line_height + margin_bottom > page_height:
                pdf.add_page()
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 7, f"Giornata {int(g)} (continua)", ln=True)
                pdf.set_font("Arial", 'B', 11)
                pdf.cell(60, 6, "Casa", border=1)
                pdf.cell(20, 6, "Gol", border=1, align='C')
                pdf.cell(20, 6, "Gol", border=1, align='C')
                pdf.cell(60, 6, "Ospite", border=1)
                pdf.ln()
                pdf.set_font("Arial", '', 11)

            if not bool(row.get('validated', False)):
                pdf.set_text_color(255, 0, 0)
            else:
                pdf.set_text_color(0, 0, 0)

            pdf.cell(60, 6, str(row['home']), border=1)
            sh = row['score_home'] if pd.notna(row.get('score_home')) else "-"
            sa = row['score_away'] if pd.notna(row.get('score_away')) else "-"
            pdf.cell(20, 6, str(int(sh) if sh != "-" else sh), border=1, align='C')
            pdf.cell(20, 6, str(int(sa) if sa != "-" else sa), border=1, align='C')
            pdf.cell(60, 6, str(row['away']), border=1)
            pdf.ln()
        pdf.ln(3)

    if pdf.get_y() + 40 + margin_bottom > page_height:
        pdf.add_page()

    pdf.set_font("Arial", 'B', 13)
    pdf.cell(0, 8, f"Classifica {girone}", ln=True)

    df_c = df_standings[df_standings['group'] == girone]
    pdf.set_font("Arial", 'B', 11)
    headers = ["Squadra", "Punti", "V", "P", "S", "GF", "GS", "DR"]
    col_widths = [60, 15, 15, 15, 15, 15, 15, 15]
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 6, h, border=1, align='C')
    pdf.ln()
    pdf.set_font("Arial", '', 11)
    for _, r in df_c.iterrows():
        if pdf.get_y() + line_height + margin_bottom > page_height:
            pdf.add_page()
            pdf.set_font("Arial", 'B', 11)
            for i, h in enumerate(headers):
                pdf.cell(col_widths[i], 6, h, border=1, align='C')
            pdf.ln()
            pdf.set_font("Arial", '', 11)
        pdf.cell(col_widths[0], 6, str(r['player']), border=1)
        pdf.cell(col_widths[1], 6, str(int(r['points'])), border=1, align='C')
        pdf.cell(col_widths[2], 6, str(int(r['wins'])), border=1, align='C')
        pdf.cell(col_widths[3], 6, str(int(r['draws'])), border=1, align='C')
        pdf.cell(col_widths[4], 6, str(int(r['losses'])), border=1, align='C')
        pdf.cell(col_widths[5], 6, str(int(r['gf'])), border=1, align='C')
        pdf.cell(col_widths[6], 6, str(int(r['ga'])), border=1, align='C')
        pdf.cell(col_widths[7], 6, str(int(r['diff'])), border=1, align='C')
        pdf.ln()
    pdf.ln(10)

pdf_bytes = pdf.output(dest='S').encode('latin1')
return pdf_bytes

=============================

APP

=============================

@st.cache_resource(show_spinner=False) def get_db() -> DB: uri = st.secrets["MONGO_URI"] return DB(uri)

def ui_header(title: str): st.markdown(f"<div class='big-title'>🏆⚽ {title} 🥇🥈🥉</div>", unsafe_allow_html=True)

def main(): st.info("Tentativo di connessione a MongoDB…") try: db = get_db() # test connessione giocatori _ = db.get_players() st.success("✅ Connessione a Mongo riuscita.") except Exception as e: st.error(f"❌ Errore di connessione a MongoDB: {e}") st.stop()

if "current_tid" not in st.session_state:
    st.session_state.current_tid = None

# =============================
# SEZIONE SELEZIONE / CREAZIONE TORNEO
# =============================
with st.expander("📂 Apri torneo esistente", expanded=st.session_state.current_tid is None):
    tornei = db.list_tournaments()
    if tornei:
        options = {f"{t['name']} — {t['created_at'].strftime('%d/%m/%Y %H:%M') if t.get('created_at') else ''}": t['_id'] for t in tornei}
        scelta = st.selectbox("Seleziona torneo", list(options.keys()))
        if st.button("Apri torneo"):
            st.session_state.current_tid = options[scelta]
            st.rerun()
    else:
        st.info("Nessun torneo presente. Crea un nuovo torneo qui sotto.")

with st.expander("✨ Crea nuovo torneo", expanded=st.session_state.current_tid is None):
    df_master = db.get_players()
    if df_master.empty:
        st.warning("⚠️ Nessun giocatore in DB o schema non conforme (manca colonna 'Giocatore').")
    else:
        oggi = datetime.now()
        mesi = {1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile", 5: "Maggio", 6: "Giugno", 7: "Luglio", 8: "Agosto", 9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre"}
        nome_default = f"TorneoSubbuteo_{oggi.day}{mesi[oggi.month]}{oggi.year}"

        nome_torneo = st.text_input("📝 Nome del torneo", value=nome_default)
        num_gironi = st.number_input("🔢 Numero di gironi", 1, 8, value=2)
        tipo_calendario = st.selectbox("📅 Tipo calendario", ["Solo andata", "Andata e ritorno"])
        n_giocatori = st.number_input("👥 Numero giocatori", 4, 64, value=8)

        st.markdown("### 👥 Seleziona Giocatori")
        amici = df_master['Giocatore'].dropna().tolist()
        all_seleziona = st.checkbox("Seleziona tutti", key="all_amici")
        amici_selezionati = st.multiselect("Amici nel torneo", amici, default=amici if all_seleziona else None)

        num_supplementari = max(0, n_giocatori - len(amici_selezionati))
        st.markdown(f"Giocatori supplementari da inserire: **{num_supplementari}**")

        extra = []
        for i in range(num_supplementari):
            use = st.checkbox(f"Aggiungi G{i+1}", key=f"supp_{i}_check")
            if use:
                nome = st.text_input(f"Nome G{i+1}", key=f"supp_{i}_nome")
                if nome.strip():
                    extra.append(nome.strip())

        giocatori_scelti = amici_selezionati + extra
        if st.button("Assegna Squadre/Potenziale"):
            if len(set(giocatori_scelti)) < 4:
                st.warning("⚠️ Inserisci almeno 4 giocatori diversi.")
            else:
                st.session_state.tmp_players = giocatori_scelti
                st.session_state.show_assign = True
                st.success("✅ Procedi con assegnazioni.")
                st.rerun()

        if st.session_state.get("show_assign"):
            st.markdown("### ⚽ Modifica Squadra e Potenziale")
            if 'tmp_info' not in st.session_state:
                st.session_state.tmp_info = {}
            for g in st.session_state.tmp_players:
                if g not in st.session_state.tmp_info:
                    if not df_master.empty and g in df_master['Giocatore'].values:
                        row = df_master[df_master['Giocatore'] == g].iloc[0]
                        squadra_default = str(row.get('Squadra', ''))
                        pot_default = int(row.get('Potenziale', 4) or 4)
                    else:
                        squadra_default = ""
                        pot_default = 4
                    st.session_state.tmp_info[g] = {"Squadra": squadra_default, "Potenziale": pot_default}

                st.session_state.tmp_info[g]["Squadra"] = st.text_input(f"Squadra per {g}", value=st.session_state.tmp_info[g]["Squadra"], key=f"sq_{g}")
                st.session_state.tmp_info[g]["Potenziale"] = st.slider(f"Potenziale per {g}", 1, 10, int(st.session_state.tmp_info[g]["Potenziale"]), key=f"pot_{g}")

            st.markdown("### ➡️ Modalità creazione gironi")
            modalita = st.radio("Scegli modalità", ["Popola Gironi Automaticamente", "Popola Gironi Manualmente"])

            if st.button("✅ Conferma modalità gironi"):
                if modalita == "Popola Gironi Manualmente":
                    st.session_state.show_groups_manual = True
                else:
                    # autogenerazione gruppi
                    gruppi = [[] for _ in range(int(num_gironi))]
                    gioc_fmt = [f"{st.session_state.tmp_info[g]['Squadra']} ({g})" for g in st.session_state.tmp_players]
                    random.shuffle(gioc_fmt)
                    for i, name in enumerate(gioc_fmt):
                        gruppi[i % int(num_gironi)].append(name)
                    # crea torneo + partite su DB
                    tid = db.create_tournament(nome_torneo, int(num_gironi), tipo_calendario, st.session_state.tmp_info, gruppi)
                    m = round_robin_from_groups(gruppi, tipo_calendario)
                    db.insert_matches(tid, m)
                    st.session_state.current_tid = tid
                    # pulizia
                    for k in ["show_assign", "tmp_players", "tmp_info", "show_groups_manual"]:
                        st.session_state.pop(k, None)
                    st.success("✅ Torneo creato e calendario generato su MongoDB.")
                    st.rerun()

            if st.session_state.get("show_groups_manual"):
                st.subheader("Assegna manualmente i gironi")
                gioc_fmt = [f"{st.session_state.tmp_info[g]['Squadra']} ({g})" for g in st.session_state.tmp_players]
                groups_manual = {}
                for i in range(int(num_gironi)):
                    key = f"manual_girone_{i+1}"
                    with st.expander(f"Girone {i+1}"):
                        default_val = st.session_state.get(key, [])
                        selezionati = st.multiselect(
                            f"Giocatori per Girone {i+1}",
                            options=[x for x in gioc_fmt if x not in sum([v for v in groups_manual.values()], [])],
                            default=default_val,
                            key=key,
                        )
                        groups_manual[f"Girone {i+1}"] = selezionati
                assegnati = set(sum(groups_manual.values(), []))
                st.markdown(f"**Assegnati: {len(assegnati)} / {len(gioc_fmt)}**")
                if len(assegnati) == len(gioc_fmt) and st.button("✅ Conferma e genera calendario"):
                    gruppi = list(groups_manual.values())
                    tid = db.create_tournament(nome_torneo, int(num_gironi), tipo_calendario, st.session_state.tmp_info, gruppi)
                    m = round_robin_from_groups(gruppi, tipo_calendario)
                    db.insert_matches(tid, m)
                    st.session_state.current_tid = tid
                    for k in ["show_assign", "tmp_players", "tmp_info", "show_groups_manual"]:
                        st.session_state.pop(k, None)
                    st.success("✅ Torneo creato e calendario generato su MongoDB.")
                    st.rerun()

# =============================
# SEZIONE GESTIONE TORNEO APERTO
# =============================
if st.session_state.current_tid:
    tdoc = db.get_tournament(st.session_state.current_tid)
    title = tdoc.get("name", "Torneo") if tdoc else "Torneo"
    ui_header(title)

    # GESTIONE NAVIGAZIONE GIRONE/GIORNATA
    groups_info = db.get_groups(st.session_state.current_tid)
    if not groups_info:
        st.info("Nessuna partita trovata.")
        return
    groups_names = sorted([g['group'] for g in groups_info])
    col_g, col_r = st.columns([1, 1])
    with col_g:
        sel_group_numero = st.selectbox("Girone", [g.replace("Girone ", "") for g in groups_names])
        group_sel = f"Girone {sel_group_numero}"
    with col_r:
        rounds = db.get_rounds_for_group(st.session_state.current_tid, group_sel)
        if not rounds:
            st.info("Nessuna giornata disponibile")
            return
        round_sel = st.selectbox("Giornata", rounds, index=0)

    # TABELLA PARTITE GIORNATA
    df_g = db.get_matches(st.session_state.current_tid, group_sel, int(round_sel))
    if df_g.empty:
        st.info("Nessuna partita in questa giornata.")
    else:
        st.subheader(f"{group_sel} – Giornata {int(round_sel)}")
        def safe_int(val):
            try:
                sval = str(val).strip().lower()
                if sval in ["none", "nan", ""] or not str(val).isdigit():
                    return 0
                return int(float(val))
            except Exception:
                return 0
        for idx, row in df_g.reset_index(drop=True).iterrows():
            c1, c2, c3, c4, c5 = st.columns([5, 1.5, 1, 1.5, 1])
            with c1:
                st.markdown(f"**{row['home']}** vs **{row['away']}**")
            with c2:
                st.number_input("", min_value=0, max_value=20, key=f"gA_{idx}", value=safe_int(row.get('score_home')), label_visibility="hidden")
            with c3:
                st.markdown("-")
            with c4:
                st.number_input("", min_value=0, max_value=20, key=f"gB_{idx}", value=safe_int(row.get('score_away')), label_visibility="hidden")
            with c5:
                st.checkbox("Valida", key=f"val_{idx}", value=bool(row.get('validated', False)))
            # separatore visivo
            if st.session_state.get(f"val_{idx}", False):
                st.markdown("<hr>", unsafe_allow_html=True)
            else:
                st.markdown('<div style="color:red; margin-bottom: 15px;">Partita non ancora validata ❌</div>', unsafe_allow_html=True)

        def salva_giornata():
            # rileggi per ordine e aggiornamento coerente
            df_to_upd = db.get_matches(st.session_state.current_tid, group_sel, int(round_sel))
            for i, r in df_to_upd.reset_index(drop=True).iterrows():
                sh = int(st.session_state.get(f"gA_{i}", 0))
                sa = int(st.session_state.get(f"gB_{i}", 0))
                v = bool(st.session_state.get(f"val_{i}", False))
                db.update_match(st.session_state.current_tid, group_sel, int(round_sel), r['home'], r['away'], sh, sa, v)
            # ricomputa standings e salva
            db.recompute_and_store_standings(st.session_state.current_tid)
            st.success("✅ Risultati salvati su Mongo.")

        st.button("💾 Salva Risultati Giornata", on_click=salva_giornata)

    # CLASSIFICA
    st.write("---")
    st.subheader(f"Classifica {group_sel}")
    df_stand = db.get_standings_df(st.session_state.current_tid)
    if df_stand.empty:
        st.info("⚽ Nessuna partita validata: classifica disponibile dopo la validazione.")
    else:
        styled = combined_style(df_stand[df_stand['group'] == group_sel].reset_index(drop=True))
        st.dataframe(styled, use_container_width=True)

    # SIDEBAR – FILTRI e DOWNLOAD
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Filtri partite da giocare")
    if st.sidebar.button("🎯 Filtra Giocatore"):
        st.session_state.sfilt_gioc = True; st.session_state.sfilt_gir = False
        st.rerun()
    if st.sidebar.button("🏆 Filtra Girone"):
        st.session_state.sfilt_gir = True; st.session_state.sfilt_gioc = False
        st.rerun()

    if st.session_state.get("sfilt_gioc"):
        all_df = db.get_all_matches_df(st.session_state.current_tid)
        if not all_df.empty:
            giocatori = sorted(pd.unique(pd.concat([all_df['home'], all_df['away']])))
            who = st.sidebar.selectbox("Giocatore", giocatori, key="sel_gioc")
            filt = all_df[((all_df['home'] == who) | (all_df['away'] == who)) & (all_df['validated'] == False)][['group', 'round', 'home', 'away']]
            if not filt.empty:
                st.sidebar.dataframe(filt, hide_index=True)
            else:
                st.sidebar.info(f"🎉 Nessuna partita da giocare per {who}!")

    if st.session_state.get("sfilt_gir"):
        all_df = db.get_all_matches_df(st.session_state.current_tid)
        if not all_df.empty:
            groups = sorted(all_df['group'].dropna().unique())
            gsel = st.sidebar.selectbox("Girone", groups, key="sel_gir")
            filt = all_df[(all_df['group'] == gsel) & (all_df['validated'] == False)][['group', 'round', 'home', 'away']]
            if not filt.empty:
                st.sidebar.dataframe(filt, hide_index=True)
            else:
                st.sidebar.info(f"🥳 Tutte le partite del {gsel} sono state giocate!")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📥 Download")
    all_df = db.get_all_matches_df(st.session_state.current_tid)
    if not all_df.empty:
        name = (tdoc or {}).get("name", "torneo")
        csv_data = all_df.to_csv(index=False).encode('utf-8')
        st.sidebar.download_button(label="📁 Esporta CSV (da Mongo)", data=csv_data, file_name=f"{name}_calendario_risultati.csv", mime="text/csv")

        if st.sidebar.button("📄 Esporta PDF (Calendario e Classifiche)"):
            df_st = db.get_standings_df(st.session_state.current_tid)
            try:
                pdf_bytes = esporta_pdf(all_df.rename(columns={"group":"group", "round":"round", "home":"home", "away":"away"}), df_st)
                st.sidebar.download_button(
                    label="Scarica PDF",
                    data=pdf_bytes,
                    file_name=f"{name}_riepilogo.pdf",
                    mime="application/pdf",
                )
            except Exception as e:
                st.sidebar.error(f"❌ Errore nella creazione del PDF: {e}")

if name == "main": main()

