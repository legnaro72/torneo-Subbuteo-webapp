import streamlit as st
import pandas as pd
import math
import os

# =========================
# Config & stile di pagina
# =========================
st.set_page_config(page_title="Fasi Finali", layout="wide")
st.markdown("""
<style>
.small-muted { font-size: 0.9rem; opacity: 0.8; }
hr { margin: 0.6rem 0 1rem 0; }
</style>
""", unsafe_allow_html=True)

# =========================
# Utilità comuni
# =========================
REQUIRED_COLS = ['Girone', 'Giornata', 'Casa', 'Ospite', 'GolCasa', 'GolOspite', 'Valida']


def check_csv_structure(df: pd.DataFrame) -> tuple[bool, str]:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        return False, f"Colonne mancanti nel CSV: {missing}"
    return True, ""


def to_bool_series(s):
    if s.dtype == bool:
        return s
    return s.astype(str).str.strip().str.lower().isin(["true", "1", "s", "si", "sì", "y", "yes"])


def tournament_is_complete(df: pd.DataFrame) -> tuple[bool, str]:
    # Tutte validate e gol presenti numerici
    v = to_bool_series(df['Valida'])
    if not v.all():
        return False, "Sono presenti partite non validate."
    try:
        gc_ok = pd.to_numeric(df['GolCasa'], errors='coerce').notna().all()
        go_ok = pd.to_numeric(df['GolOspite'], errors='coerce').notna().all()
        if not (gc_ok and go_ok):
            return False, "Sono presenti gol non numerici o mancanti."
    except Exception:
        return False, "Errore nel parsing dei gol."
    return True, ""


def classifica_complessiva(df: pd.DataFrame) -> pd.DataFrame:
    """Calcola la classifica complessiva (tutte le partite validate), 2 punti vittoria / 1 pareggio."""
    partite = df[to_bool_series(df['Valida'])].copy()
    partite['GolCasa'] = pd.to_numeric(partite['GolCasa'], errors='coerce').fillna(0).astype(int)
    partite['GolOspite'] = pd.to_numeric(partite['GolOspite'], errors='coerce').fillna(0).astype(int)

    squadre = pd.unique(partite[['Casa', 'Ospite']].values.ravel('K'))
    stats = {s: {'Punti':0,'V':0,'P':0,'S':0,'GF':0,'GS':0,'DR':0} for s in squadre}

    for _, r in partite.iterrows():
        casa, osp = r['Casa'], r['Ospite']
        gc, go = int(r['GolCasa']), int(r['GolOspite'])
        stats[casa]['GF'] += gc; stats[casa]['GS'] += go
        stats[osp]['GF'] += go; stats[osp]['GS'] += gc
        if gc > go:
            stats[casa]['Punti'] += 2; stats[casa]['V'] += 1; stats[osp]['S'] += 1
        elif gc < go:
            stats[osp]['Punti'] += 2; stats[osp]['V'] += 1; stats[casa]['S'] += 1
        else:
            stats[casa]['Punti'] += 1; stats[osp]['Punti'] += 1
        stats[casa]['P'] += 1; stats[osp]['P'] += 1

    rows = []
    for s, d in stats.items():
        d['DR'] = d['GF'] - d['GS']
        rows.append({'Squadra': s, **d})
    dfc = pd.DataFrame(rows)
    if dfc.empty:
        return dfc
    # Ordinamento con tie-breaker: Punti, DR, GF, V, poi nome (stabile)
    dfc = dfc.sort_values(by=['Punti','DR','GF','V','Squadra'], ascending=[False, False, False, False, True]).reset_index(drop=True)
    dfc.index = dfc.index + 1
    dfc.insert(0, 'Pos', dfc.index)
    return dfc.reset_index(drop=True)


def serpentino_seed(squadre_ordinate: list[str], num_gironi: int) -> list[list[str]]:
    """Distribuzione 1..N a serpentina: G1,G2,...,Gk, poi Gk,...,G1, ecc."""
    gironi = [[] for _ in range(num_gironi)]
    direction = 1
    g = 0
    for s in squadre_ordinate:
        gironi[g].append(s)
        if direction == 1 and g == num_gironi - 1:
            direction = -1
        elif direction == -1 and g == 0:
            direction = 1
        else:
            g += direction
    return gironi


def round_robin(teams: list[str], andata_ritorno: bool=False) -> pd.DataFrame:
    """Genera calendario round-robin (metodo circle). Ritorna DF con Giornata/Casa/Ospite."""
    teams = teams[:]
    if len(teams) < 2:
        return pd.DataFrame(columns=['Giornata','Casa','Ospite'])
    bye = None
    if len(teams) % 2 == 1:
        bye = "Riposo"
        teams.append(bye)
    n = len(teams)
    giornate = n - 1
    metà = n // 2
    curr = teams[:]
    rows = []
    for g in range(1, giornate+1):
        for i in range(metà):
            a = curr[i]; b = curr[-(i+1)]
            if a != bye and b != bye:
                rows.append({'Giornata': g, 'Casa': a, 'Ospite': b})
        curr = [curr[0]] + [curr[-1]] + curr[1:-1]
    df = pd.DataFrame(rows)
    if andata_ritorno:
        inv = df.copy()
        inv['Giornata'] = inv['Giornata'] + giornate
        inv = inv.rename(columns={'Casa':'Ospite','Ospite':'Casa'})
        df = pd.concat([df, inv], ignore_index=True)
    return df


def standings_from_matches(df: pd.DataFrame, key_group: str) -> pd.DataFrame:
    """Classifica per gruppi su DataFrame con colonne: key_group, Casa, Ospite, GolCasa, GolOspite, Valida"""
    if df.empty:
        return pd.DataFrame()
    partite = df[to_bool_series(df['Valida'])].copy()
    if partite.empty:
        return pd.DataFrame()
    partite['GolCasa'] = pd.to_numeric(partite['GolCasa'], errors='coerce').fillna(0).astype(int)
    partite['GolOspite'] = pd.to_numeric(partite['GolOspite'], errors='coerce').fillna(0).astype(int)
    out = []
    for gruppo, blocco in partite.groupby(key_group):
        squadre = pd.unique(blocco[['Casa','Ospite']].values.ravel('K'))
        stats = {s: {'Punti':0,'V':0,'P':0,'S':0,'GF':0,'GS':0,'DR':0} for s in squadre}
        for _, r in blocco.iterrows():
            c, o = r['Casa'], r['Ospite']
            gc, go = int(r['GolCasa']), int(r['GolOspite'])
            stats[c]['GF'] += gc; stats[c]['GS'] += go
            stats[o]['GF'] += go; stats[o]['GS'] += gc
            if gc > go:
                stats[c]['Punti'] += 2; stats[c]['V'] += 1; stats[o]['S'] += 1
            elif gc < go:
                stats[o]['Punti'] += 2; stats[o]['V'] += 1; stats[c]['S'] += 1
            else:
                stats[c]['Punti'] += 1; stats[o]['Punti'] += 1
            stats[c]['P'] += 1; stats[o]['P'] += 1
        for s, d in stats.items():
            d['DR'] = d['GF'] - d['GS']
            out.append({'Gruppo': gruppo, 'Squadra': s, **d})
    dfc = pd.DataFrame(out)
    if dfc.empty:
        return dfc
    dfc = dfc.sort_values(by=['Gruppo','Punti','DR','GF','V','Squadra'], ascending=[True,False,False,False,False,True])
    return dfc.reset_index(drop=True)


# ==================================
# Gestione stato applicazione
# ==================================

def reset_fase_finale():
    keys = [
        'fase_scelta','gironi_num','gironi_ar','gironi_seed',
        'df_finale_gironi','girone_sel','giornata_sel',
        'round_corrente','rounds_ko','seeds_ko','n_inizio_ko',
        'giornate_mode'
    ]
    for k in keys:
        if k in st.session_state:
            del st.session_state[k]


def reset_to_setup():
    reset_fase_finale()
    st.session_state['ui_show_pre'] = True
    st.session_state['fase_modalita'] = None


if 'ui_show_pre' not in st.session_state:
    st.session_state['ui_show_pre'] = True
if 'fase_modalita' not in st.session_state:
    st.session_state['fase_modalita'] = None

# ==============
# Header
# ==============
st.title("🏆 Fasi Finali")

# Mostra il nome torneo se già impostato (una sola volta)
if 'tournament_name' in st.session_state and st.session_state['tournament_name']:
    st.markdown(f"### 🏷️ {st.session_state['tournament_name']}")

# =========================
# Uploader CSV (vista PRE)
# =========================
if st.session_state['ui_show_pre']:
    file = st.file_uploader("📁 Carica CSV torneo concluso", type=["csv"]) 
    if file is None:
        st.info("Suggerimento: il CSV deve contenere le colonne: " + ", ".join(REQUIRED_COLS))
        st.stop()

    try:
        df_in = pd.read_csv(file)
    except Exception as e:
        st.error(f"Errore nel caricamento del CSV: {e}")
        st.stop()

    ok, msg = check_csv_structure(df_in)
    if not ok:
        st.error(f"❌ {msg}")
        st.stop()

    complete, why = tournament_is_complete(df_in)
    if not complete:
        st.error(f"❌ Il torneo **non** risulta completamente validato: {why}")
        st.stop()

    # ===== Nome torneo automatico dal CSV valido (rimuove suffissi comuni)
    filename = os.path.splitext(file.name)[0]
    base = filename
    for suf in ['_calendario_risultati', '_calendario', '_risultati']:
        if base.endswith(suf):
            base = base[: -len(suf)]
    base = base.rstrip('_')
    st.session_state['tournament_name'] = f"FASE FINALE {base}"

    # Mostra la classifica complessiva (pre)
    df_class = classifica_complessiva(df_in)
    st.success("✅ Torneo completo e valido! Classifica calcolata qui sotto.")
    st.dataframe(df_class, use_container_width=True)
    st.divider()

    # Scelta della Fase Finale (visibile solo prima della generazione)
    colA, colB = st.columns([1,1])
    with colA:
        fase_scelta = st.radio(
            "Formula fase finale",
            ["Gironi", "Eliminazione diretta"],
            key="fase_scelta",
            horizontal=True
        )
    st.markdown("<span class='small-muted'>Le squadre vengono **estratte dal CSV** e ordinate per piazzamento complessivo. I migliori affrontano i peggiori nelle fasi ad eliminazione; nei gironi la distribuzione è **a serpentina**.</span>", unsafe_allow_html=True)

    # -------------------------
    # Modalità A: Gironi (SETUP)
    # -------------------------
    if fase_scelta == "Gironi":
        with st.expander("⚙️ Impostazioni Gironi", expanded=True):
            num_gironi = st.number_input("Numero di gironi", min_value=1, max_value=16, value=2, step=1, key="gironi_num")
            andata_ritorno = st.checkbox("Andata e ritorno", value=False, key="gironi_ar")
            totale = len(df_class)
            max_per_girone = math.ceil(totale/num_gironi)
            n_partecipanti = st.slider("Numero partecipanti alla fase finale a gironi", min_value=num_gironi, max_value=totale, value=totale, step=1)
            st.caption(f"Distribuzione massima per girone ~ {max_per_girone} (con {totale} totali).")

        if st.button("🎲 Genera Gironi (serpentina)"):
            # Genera e passa alla VISTA POST (nascondendo classifica e scelta)
            reset_fase_finale()
            # Manteniamo il nome torneo
            # (già impostato in session_state)
            seeds = df_class['Squadra'].tolist()[:n_partecipanti]
            gironi = serpentino_seed(seeds, num_gironi)
            labels = [chr(ord('A') + i) for i in range(num_gironi)]
            assegnazione = {f"Girone {labels[i]}": gironi[i] for i in range(num_gironi)}

            # Genera calendario round-robin per ciascun girone
            rows = []
            for lab, teams in assegnazione.items():
                df_rr = round_robin(teams, andata_ritorno=andata_ritorno)
                if df_rr.empty:
                    continue
                df_rr['GironeFinale'] = lab
                df_rr['GolCasa'] = None
                df_rr['GolOspite'] = None
                df_rr['Valida'] = False
                rows.append(df_rr[['GironeFinale','Giornata','Casa','Ospite','GolCasa','GolOspite','Valida']])

            df_finale = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=['GironeFinale','Giornata','Casa','Ospite','GolCasa','GolOspite','Valida'])

            st.session_state['gironi_seed'] = assegnazione
            st.session_state['df_finale_gironi'] = df_finale
            st.session_state['ui_show_pre'] = False
            st.session_state['fase_modalita'] = "Gironi"
            st.session_state['giornate_mode'] = "Menu a tendina"
            st.rerun()

    # -------------------------
    # Modalità B: Eliminazione diretta (SETUP)
    # -------------------------
    if fase_scelta == "Eliminazione diretta":
        round_map = {"Ottavi":16, "Quarti":8, "Semifinali":4, "Finale":2}
        col1, col2 = st.columns([1,1])
        with col1:
            start_round_label = st.selectbox("Parti da", list(round_map.keys()))
        n_start = round_map[start_round_label]
        topN = len(df_class)
        if topN < n_start:
            st.warning(f"Servono almeno **{n_start}** squadre per partire da {start_round_label.lower()}. Nel CSV ci sono {topN} squadre.")
            st.stop()
        st.caption(f"Parteciperanno le **prime {n_start}** della classifica complessiva.")

        if st.button("🧩 Genera tabellone iniziale"):
            reset_fase_finale()
            seeds = df_class['Squadra'].tolist()[:n_start]
            st.session_state['seeds_ko'] = seeds
            st.session_state['n_inizio_ko'] = n_start
            st.session_state['round_corrente'] = start_round_label

            pairs = []
            for i in range(n_start//2):
                a = seeds[i]; b = seeds[-(i+1)]
                pairs.append({'Round': start_round_label, 'Match': i+1, 'SquadraA': a, 'SquadraB': b, 'GolA': None, 'GolB': None, 'Valida': False, 'Vincitore': None})

            st.session_state['rounds_ko'] = [pd.DataFrame(pairs)]
            st.session_state['ui_show_pre'] = False
            st.session_state['fase_modalita'] = "Eliminazione diretta"
            st.rerun()

# =========================
# VISTA POST (solo fase scelta)
# =========================
if not st.session_state['ui_show_pre']:
    # Mostra solo il nome torneo (se presente) e pulsante per tornare
    if 'tournament_name' in st.session_state and st.session_state['tournament_name']:
        st.markdown(f"### 🏷️ {st.session_state['tournament_name']}")

    st.button("⬅️ Torna a classifica e scelta fase finale", on_click=reset_to_setup)

    # ------ Modalità A: Gironi (POST) ------
    if st.session_state.get('fase_modalita') == "Gironi":
        if 'gironi_seed' in st.session_state:
            st.subheader("📋 Assegnazione Gironi (serpentina)")
            col1, col2 = st.columns(2)
            items = list(st.session_state['gironi_seed'].items())
            half = math.ceil(len(items)/2)
            with col1:
                for lab, teams in items[:half]:
                    st.write(f"**{lab}**: {', '.join(teams)}")
            with col2:
                for lab, teams in items[half:]:
                    st.write(f"**{lab}**: {', '.join(teams)}")

        if 'df_finale_gironi' in st.session_state and not st.session_state['df_finale_gironi'].empty:
            dfg = st.session_state['df_finale_gironi']
            gironi_labels = sorted(dfg['GironeFinale'].unique().tolist())
            if 'girone_sel' not in st.session_state and gironi_labels:
                st.session_state['girone_sel'] = gironi_labels[0]
            girone_sel = st.selectbox("Seleziona Girone Finale", gironi_labels, index=gironi_labels.index(st.session_state['girone_sel']))
            st.session_state['girone_sel'] = girone_sel

            if 'giornate_mode' not in st.session_state:
                st.session_state['giornate_mode'] = "Menu a tendina"
            giornate_mode = st.radio(
                "Selezione giornata con:",
                ["Menu a tendina", "Bottoni"],
                index=0 if st.session_state['giornate_mode'] == "Menu a tendina" else 1,
                horizontal=True
            )
            st.session_state['giornate_mode'] = giornate_mode

            giornate = sorted(dfg[dfg['GironeFinale']==girone_sel]['Giornata'].unique().tolist())
            if 'giornata_sel' not in st.session_state and giornate:
                st.session_state['giornata_sel'] = giornate[0]

            # --- Modalità menu a tendina (default) ---
            if giornate_mode == "Menu a tendina":
                giornata_sel = st.selectbox(
                    "Seleziona Giornata",
                    giornate,
                    index=giornate.index(st.session_state['giornata_sel']) if giornate else 0
                )
            else:
                # --- Modalità bottoni ---
                if giornate:
                    cols = st.columns(len(giornate))
                    for i, g in enumerate(giornate):
                        if cols[i].button(f"{g}", key=f"giornata_btn_{g}"):
                            st.session_state['giornata_sel'] = g
                giornata_sel = st.session_state.get('giornata_sel', giornate[0] if giornate else None)

            if giornata_sel is None:
                st.info("Nessuna giornata disponibile.")
            else:
                st.session_state['giornata_sel'] = giornata_sel
                st.write(f"📅 Giornata selezionata: {giornata_sel}")

                blocco = dfg[(dfg['GironeFinale']==girone_sel) & (dfg['Giornata']==giornata_sel)].copy()
                st.markdown("### ✏️ Inserisci risultati")
                for idx, row in blocco.iterrows():
                    c1, c2, c3, c4, c5 = st.columns([4,1.2,0.6,1.2,1.6])
                    with c1:
                        st.markdown(f"**{row['Casa']}** vs **{row['Ospite']}**")
                    with c2:
                        _ = st.number_input(" ", min_value=0, max_value=99, value=0 if pd.isna(row['GolCasa']) else int(row['GolCasa']), key=f"f_golc_{idx}", label_visibility="hidden")
                    with c3:
                        st.markdown("—")
                    with c4:
                        _ = st.number_input(" ", min_value=0, max_value=99, value=0 if pd.isna(row['GolOspite']) else int(row['GolOspite']), key=f"f_golo_{idx}", label_visibility="hidden")
                    with c5:
                        _ = st.checkbox("Valida", value=bool(row['Valida']), key=f"f_val_{idx}")

                def salva_giornata():
                    df_loc = st.session_state['df_finale_gironi']
                    loc_idx = (df_loc['GironeFinale']==girone_sel) & (df_loc['Giornata']==giornata_sel)
                    idxs = df_loc[loc_idx].index.tolist()
                    for i in idxs:
                        df_loc.at[i,'GolCasa'] = st.session_state.get(f"f_golc_{i}", 0)
                        df_loc.at[i,'GolOspite'] = st.session_state.get(f"f_golo_{i}", 0)
                        df_loc.at[i,'Valida'] = st.session_state.get(f"f_val_{i}", False)
                    st.session_state['df_finale_gironi'] = df_loc
                    st.success("✅ Risultati salvati.")

                st.button("💾 Salva risultati giornata", on_click=salva_giornata)

                st.markdown("### 📊 Classifica del girone selezionato")
                class_g = standings_from_matches(
                    st.session_state['df_finale_gironi'][st.session_state['df_finale_gironi']['GironeFinale']==girone_sel].rename(columns={'GironeFinale':'Gruppo'}),
                    key_group='Gruppo'
                )
                if class_g.empty:
                    st.info("Nessuna partita validata finora nel girone selezionato.")
                else:
                    st.dataframe(class_g, use_container_width=True)

                st.download_button(
                    "📥 Esporta calendario fase a gironi (CSV)",
                    data=st.session_state['df_finale_gironi'].to_csv(index=False).encode('utf-8'),
                    file_name="fase_finale_gironi_calendario.csv",
                    mime="text/csv",
                )

    # ------ Modalità B: Eliminazione Diretta (POST) ------
    if st.session_state.get('fase_modalita') == "Eliminazione diretta":
        def render_round(df_round: pd.DataFrame):
            st.markdown(f"### 🏁 {df_round['Round'].iloc[0]}")
            for _, row in df_round.iterrows():
                rnd = row['Round']
                match_n = int(row['Match'])
                c1, c2, c3, c4, c5, c6 = st.columns([3,1,0.5,1,1.6,2.2])
                with c1:
                    st.markdown(f"**{row['SquadraA']}** vs **{row['SquadraB']}**")
                ga_key = f"ko_ga_{rnd}_{match_n}"
                gb_key = f"ko_gb_{rnd}_{match_n}"
                val_key = f"ko_val_{rnd}_{match_n}"
                win_key = f"ko_w_{rnd}_{match_n}"

                with c2:
                    _ = st.number_input(" ", min_value=0, max_value=99, value=0 if pd.isna(row['GolA']) else int(row['GolA']), key=ga_key, label_visibility="hidden")
                with c3:
                    st.markdown("—")
                with c4:
                    _ = st.number_input(" ", min_value=0, max_value=99, value=0 if pd.isna(row['GolB']) else int(row['GolB']), key=gb_key, label_visibility="hidden")
                with c5:
                    _ = st.checkbox("Valida", value=bool(row['Valida']), key=val_key)

                options = [row['SquadraA'], row['SquadraB']]
                default_index = 0
                if pd.notna(row.get('Vincitore')) and row.get('Vincitore') in options:
                    default_index = options.index(row.get('Vincitore'))
                with c6:
                    _ = st.selectbox("Vincitore (se pari)", options=options, index=default_index, key=win_key)

        def salva_round():
            # salva i valori del round corrente (ultimo)
            if 'rounds_ko' not in st.session_state or not st.session_state['rounds_ko']:
                return
            df_round = st.session_state['rounds_ko'][-1].copy()
            for _, row in df_round.iterrows():
                rnd = row['Round']
                match_n = int(row['Match'])
                ga_key = f"ko_ga_{rnd}_{match_n}"
                gb_key = f"ko_gb_{rnd}_{match_n}"
                val_key = f"ko_val_{rnd}_{match_n}"
                win_key = f"ko_w_{rnd}_{match_n}"
                df_round.at[_,'GolA'] = st.session_state.get(ga_key, 0)
                df_round.at[_,'GolB'] = st.session_state.get(gb_key, 0)
                df_round.at[_,'Valida'] = st.session_state.get(val_key, False)
                df_round.at[_,'Vincitore'] = st.session_state.get(win_key, df_round.at[_,'SquadraA'])

            # assegna indietro
            st.session_state['rounds_ko'][-1] = df_round
            st.success("✅ Risultati del turno salvati.")

        def all_matches_have_winners(df_round: pd.DataFrame) -> bool:
            for _, r in df_round.iterrows():
                if not bool(r['Valida']):
                    return False
                ga = 0 if pd.isna(r['GolA']) else int(r['GolA'])
                gb = 0 if pd.isna(r['GolB']) else int(r['GolB'])
                if ga == gb:
                    if pd.isna(r['Vincitore']) or r['Vincitore'] not in [r['SquadraA'], r['SquadraB']]:
                        return False
            return True

        def compute_winners(df_round: pd.DataFrame) -> list[str]:
            winners = []
            for _, r in df_round.iterrows():
                ga = 0 if pd.isna(r['GolA']) else int(r['GolA'])
                gb = 0 if pd.isna(r['GolB']) else int(r['GolB'])
                if ga > gb:
                    winners.append(r['SquadraA'])
                elif gb > ga:
                    winners.append(r['SquadraB'])
                else:
                    winners.append(r['Vincitore'])
            return winners

        def next_round_label(curr: str) -> str | None:
            order = ["Ottavi","Quarti","Semifinali","Finale"]
            if curr == "Finale":
                return None
            try:
                idx = order.index(curr)
                return order[idx+1]
            except ValueError:
                # gestione flessibile
                if curr == "Quarti":
                    return "Semifinali"
                if curr == "Semifinali":
                    return "Finale"
                return None

        if 'rounds_ko' in st.session_state and st.session_state['rounds_ko']:
            round_corr = st.session_state['rounds_ko'][-1]
            render_round(round_corr)

            colx, coly = st.columns([1,1])
            with colx:
                if st.button("➡️ Genera turno successivo"):
                    # prima salviamo per sicurezza
                    salva_round()
                    round_corr = st.session_state['rounds_ko'][-1]
                    if not all_matches_have_winners(round_corr):
                        st.error("Per avanzare, **tutte** le partite del turno devono essere **validate** e con **vincitore** determinato.")
                    else:
                        winners = compute_winners(round_corr)
                        if len(winners) == 1:
                            st.balloons()
                            st.success(f"🏆 Campione: **{winners[0]}**")
                        else:
                            nxt = next_round_label(round_corr['Round'].iloc[0])
                            if nxt is None:
                                st.error("Impossibile determinare il turno successivo.")
                            else:
                                pairs = []
                                for i in range(0, len(winners), 2):
                                    a, b = winners[i], winners[i+1]
                                    pairs.append({'Round': nxt, 'Match': (i//2)+1, 'SquadraA': a, 'SquadraB': b, 'GolA': None, 'GolB': None, 'Valida': False, 'Vincitore': None})
                                st.session_state['rounds_ko'].append(pd.DataFrame(pairs))
                                st.session_state['round_corrente'] = nxt
                                st.rerun()
            with coly:
                if st.button("🔁 Reimposta fase KO"):
                    reset_fase_finale()
                    st.rerun()

            # Export semplice del tabellone corrente (tutti i turni)
            all_rounds_df = pd.concat(st.session_state['rounds_ko'], ignore_index=True)
            st.download_button(
                "📥 Esporta tabellone (CSV)",
                data=all_rounds_df.to_csv(index=False).encode('utf-8'),
                file_name="fase_finale_tabellone.csv",
                mime="text/csv",
            )

# Fine script
