"""Swiss tournaments in the original PierCrewSvizzero document format."""
import hashlib
from datetime import datetime

from bson import ObjectId
from fastapi import Depends, HTTPException, Response
from pydantic import BaseModel, Field, ConfigDict
from pymongo.errors import DuplicateKeyError

from .models import CreateParticipant, Result, TeamBadge
from .report import render_tournament_pdf
from .tournaments import save, version


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class CreateSwiss(Input):
    name: str = Field(min_length=1, max_length=160)
    participants: list[CreateParticipant] = Field(min_length=3, max_length=64)
    badges: dict[str, TeamBadge] = Field(default_factory=dict, max_length=64)
    mode: str = Field(pattern='^(fisso|illimitati)$')
    max_rounds: int = Field(default=5, ge=1, le=50)
    request_id: str = Field(pattern=r'^[0-9a-f-]{36}$')


class SaveSwiss(Input):
    version: str = Field(pattern=r'^[a-f0-9]{64}$')
    results: list[Result] = Field(min_length=1, max_length=1000)


class SwissAction(Input):
    version: str = Field(pattern=r'^[a-f0-9]{64}$')


def load(store, tournament_id):
    if not ObjectId.is_valid(tournament_id):
        raise HTTPException(404, 'Torneo svizzero non trovato.')
    doc = store.swiss_tournaments.find_one({'_id': ObjectId(tournament_id)})
    if not doc or not isinstance(doc.get('df_torneo'), list):
        raise HTTPException(404, 'Torneo svizzero non trovato.')
    return doc


def standings(doc):
    teams = {str(p['Squadra']): dict(Squadra=str(p['Squadra']), Potenziale=float(p.get('Potenziale') or 0), Punti=0, G=0, V=0, N=0, P=0, GF=0, GS=0, DR=0)
             for p in doc.get('df_squadre', []) if p.get('Squadra')}
    matches = doc.get('df_torneo', [])
    for row in matches:
        for key in ('Casa', 'Ospite'):
            name = str(row.get(key) or '')
            if name and name != 'RIPOSA' and name not in teams:
                teams[name] = dict(Squadra=name, Potenziale=0, Punti=0, G=0, V=0, N=0, P=0, GF=0, GS=0, DR=0)
    for row in matches:
        if not row.get('Validata') or row.get('Casa') == 'RIPOSA' or row.get('Ospite') == 'RIPOSA':
            continue
        home, away = teams.get(row.get('Casa')), teams.get(row.get('Ospite'))
        if not home or not away:
            continue
        a, b = int(row.get('GolCasa') or 0), int(row.get('GolOspite') or 0)
        home['G'] += 1; away['G'] += 1
        home['GF'] += a; home['GS'] += b; away['GF'] += b; away['GS'] += a
        if a > b:
            home['Punti'] += 2; home['V'] += 1; away['P'] += 1
        elif a < b:
            away['Punti'] += 2; away['V'] += 1; home['P'] += 1
        else:
            home['Punti'] += 1; away['Punti'] += 1; home['N'] += 1; away['N'] += 1
    for team in teams.values():
        team['DR'] = team['GF'] - team['GS']
    def direct_points(name, peers):
        total = 0
        for row in matches:
            if not row.get('Validata') or name not in (row.get('Casa'), row.get('Ospite')):
                continue
            opponent = row['Ospite'] if row['Casa'] == name else row['Casa']
            if opponent not in peers:
                continue
            ours = int(row.get('GolCasa') or 0) if row['Casa'] == name else int(row.get('GolOspite') or 0)
            theirs = int(row.get('GolOspite') or 0) if row['Casa'] == name else int(row.get('GolCasa') or 0)
            total += 2 if ours > theirs else 1 if ours == theirs else 0
        return total
    rows = list(teams.values())
    rows.sort(key=lambda x: (-x['Punti'], -direct_points(x['Squadra'], {p['Squadra'] for p in rows if p['Punti'] == x['Punti']}), -x['DR'], -x['GF'], x['Squadra'].casefold()))
    return rows


def pairings(doc, round_number):
    ranked = standings(doc)
    potential_order = sorted(ranked, key=lambda x: (-x['Potenziale'], x['Squadra'].casefold()))
    if round_number <= 2:
        ordered = potential_order
    elif round_number <= 4:
        positions = {r['Squadra']: i for i, r in enumerate(potential_order)}
        ordered = sorted(ranked, key=lambda x: (positions[x['Squadra']] + ranked.index(x), ranked.index(x)))
    else:
        ordered = ranked
    names = [r['Squadra'] for r in ordered]
    bye = None
    if len(names) % 2:
        rested = {r['Casa'] for r in doc.get('df_torneo', []) if r.get('Ospite') == 'RIPOSA'}
        candidates = [n for n in names if n not in rested] or names
        bye = min(candidates, key=lambda n: (next(x['Potenziale'] for x in ranked if x['Squadra'] == n), n)) if round_number <= 2 else next(n for n in reversed(names) if n in candidates)
        names.remove(bye)
    played = {frozenset((r['Casa'], r['Ospite'])) for r in doc.get('df_torneo', []) if r.get('Casa') != 'RIPOSA' and r.get('Ospite') != 'RIPOSA'}
    def backtrack(remaining):
        if not remaining:
            return []
        first = remaining[0]
        for index, opponent in enumerate(remaining[1:], 1):
            if frozenset((first, opponent)) in played:
                continue
            rest = backtrack(remaining[1:index] + remaining[index+1:])
            if rest is not None:
                return [(first, opponent)] + rest
        return None
    pairs = backtrack(names)
    if pairs is None:
        return []
    rows = [dict(Casa=a, Ospite=b, GolCasa=0, GolOspite=0, Validata=False, Turno=round_number) for a, b in pairs]
    if bye:
        rows.append(dict(Casa=bye, Ospite='RIPOSA', GolCasa=0, GolOspite=0, Validata=True, Turno=round_number))
    return rows


def view(doc):
    matches = []
    for index, row in enumerate(doc.get('df_torneo', [])):
        if row.get('Casa') == 'RIPOSA' or row.get('Ospite') == 'RIPOSA':
            continue
        matches.append(dict(index=index, round=int(row.get('Turno') or 1), home=str(row['Casa']), away=str(row['Ospite']), home_goals=int(row.get('GolCasa') or 0), away_goals=int(row.get('GolOspite') or 0), valid=bool(row.get('Validata'))))
    return dict(id=str(doc['_id']), name=doc['nome_torneo'], version=version(doc), matches=matches, standings=standings(doc),
                badges=doc.get('_piercrew_badges', {}),
                active_round=int(doc.get('turno_attivo') or 1), started=bool(doc.get('torneo_iniziato', True)),
                finished=bool(doc.get('torneo_finito')), mode=doc.get('modalita_turni', 'fisso'), max_rounds=int(doc.get('max_turni') or 5),
                participants=doc.get('df_squadre', []), byes=[dict(team=r['Casa'], round=int(r.get('Turno') or 1)) for r in doc.get('df_torneo', []) if r.get('Ospite') == 'RIPOSA'])


def award(store, doc):
    ranking = standings(doc)
    if not ranking:
        return
    winner = ranking[0]['Squadra']
    player_name = winner.split('-', 1)[1].strip() if '-' in winner else winner
    player = store.players.find_one({'$or': [{'Giocatore': player_name}, {'Squadra': winner}]})
    if not player:
        return
    name = doc['nome_torneo'].removeprefix('finito_').strip()
    previous = player.get('listaCampionatiVinti', [])
    if not isinstance(previous, list) or any(str(value).removeprefix('finito_').strip().casefold() == name.casefold() for value in previous):
        return
    store.players.update_one({'_id': player['_id'], '_piercrew_award_ids': {'$ne': f"swiss:{doc['_id']}"}, 'listaCampionatiVinti': {'$ne': name}},
                             {'$addToSet': {'listaCampionatiVinti': name, '_piercrew_award_ids': f"swiss:{doc['_id']}"}, '$inc': {'NCampionatiVinti': 1}})


def install(app, current_user, writer, store_dep, require_tournament_write):
    @app.get('/api/swiss')
    def listing(user=Depends(current_user), store=Depends(store_dep)):
        return [dict(id=str(d['_id']), name=d.get('nome_torneo', ''), rounds=int(d.get('turno_attivo') or 1), finished=bool(d.get('torneo_finito')))
                for d in store.swiss_tournaments.find({'df_torneo': {'$type': 'array'}}, {'nome_torneo': 1, 'turno_attivo': 1, 'torneo_finito': 1}).sort('_id', -1)]

    @app.get('/api/swiss/{tournament_id}')
    def get(tournament_id: str, user=Depends(current_user), store=Depends(store_dep)):
        return view(load(store, tournament_id))

    @app.post('/api/swiss')
    def create(data: CreateSwiss, user=Depends(writer), store=Depends(store_dep)):
        name = data.name.strip()
        require_tournament_write(user, name)
        if not name or name.lower().startswith(('finito_', 'completato_')):
            raise HTTPException(422, 'Nome torneo non valido.')
        labels = [f'{p.team.strip()} - {p.name}' if p.team.strip() else p.name for p in data.participants]
        if len({s.casefold() for s in labels}) != len(labels) or any(s.casefold() == 'riposa' for s in labels):
            raise HTTPException(422, 'I nomi dei partecipanti devono essere distinti.')
        if not set(data.badges) <= set(labels):
            raise HTTPException(422, 'Le immagini devono appartenere ai partecipanti selezionati.')
        source_ids = [p.source_id for p in data.participants if not p.guest]
        if any(not x or not ObjectId.is_valid(x) for x in source_ids) or len(source_ids) != len(set(source_ids)):
            raise HTTPException(422, 'Giocatore registrato non valido.')
        players = {str(p['_id']): p for p in store.players.find({'_id': {'$in': [ObjectId(x) for x in source_ids]}}, {'Giocatore': 1})}
        for p in data.participants:
            if p.guest and p.source_id or not p.guest and (p.source_id not in players or players[p.source_id]['Giocatore'] != p.name):
                raise HTTPException(422, 'Giocatore non presente in anagrafica. Usa ospite per un nome esterno.')
        payload = data.model_dump_json(exclude={'request_id'})
        digest = hashlib.sha256(payload.encode()).hexdigest()
        object_id = ObjectId(hashlib.sha256((user['id'] + data.request_id).encode()).hexdigest()[:24])
        existing = store.swiss_tournaments.find_one({'_id': object_id})
        if existing:
            if existing.get('_piercrew_create_hash') != digest:
                raise HTTPException(409, 'Richiesta di creazione già utilizzata.')
            return view(existing)
        now = datetime.utcnow()
        teams = [dict(Giocatore=p.name, Squadra=label, Potenziale=p.potential) for p, label in zip(data.participants, labels)]
        doc = dict(_id=object_id, nome_torneo=name, df_torneo=[], df_squadre=teams, turno_attivo=1,
                   _piercrew_badges={key: badge.model_dump(exclude_none=True) for key, badge in data.badges.items()},
                   torneo_iniziato=True, torneo_finito=False, modalita_turni=data.mode, max_turni=data.max_rounds,
                   data_creazione=now, data_modifica=now, _piercrew_create_hash=digest, _piercrew_revision=0)
        doc['df_torneo'] = pairings(doc, 1)
        if not doc['df_torneo']:
            raise HTTPException(422, 'Impossibile generare il primo turno.')
        try:
            store.swiss_tournaments.insert_one(doc)
        except DuplicateKeyError:
            return view(load(store, str(object_id)))
        return view(doc)

    @app.patch('/api/swiss/{tournament_id}/results')
    def results(tournament_id: str, data: SaveSwiss, user=Depends(writer), store=Depends(store_dep)):
        doc = load(store, tournament_id)
        require_tournament_write(user, doc['nome_torneo'])
        if doc.get('torneo_finito'):
            raise HTTPException(409, 'Torneo concluso.')
        rows = [dict(r) for r in doc['df_torneo']]
        indices = [r.index for r in data.results]
        if len(set(indices)) != len(indices) or any(i >= len(rows) for i in indices):
            raise HTTPException(422, 'Partita non valida.')
        for change in data.results:
            row = rows[change.index]
            if row.get('Turno') != doc.get('turno_attivo') or row.get('Ospite') == 'RIPOSA':
                raise HTTPException(422, 'Puoi modificare solo le partite del turno attivo.')
            row.update(GolCasa=change.home, GolOspite=change.away, Validata=change.valid)
        return view(save(store, doc, data.version, {'df_torneo': rows}, collection=store.swiss_tournaments))

    @app.post('/api/swiss/{tournament_id}/advance')
    def advance(tournament_id: str, data: SwissAction, user=Depends(writer), store=Depends(store_dep)):
        doc = load(store, tournament_id)
        require_tournament_write(user, doc['nome_torneo'])
        if doc.get('torneo_finito'):
            raise HTTPException(409, 'Torneo concluso.')
        round_number = int(doc.get('turno_attivo') or 1)
        current = [r for r in doc['df_torneo'] if int(r.get('Turno') or 1) == round_number]
        if not current or not all(r.get('Validata') for r in current):
            raise HTTPException(422, 'Valida tutte le partite del turno prima di avanzare.')
        new_round = round_number + 1
        more = [] if doc.get('modalita_turni') == 'fisso' and round_number >= int(doc.get('max_turni') or 5) else pairings(doc, new_round)
        changes = {'turno_attivo': new_round if more else round_number, 'df_torneo': doc['df_torneo'] + more}
        if not more:
            changes['torneo_finito'] = True
        saved = save(store, doc, data.version, changes, collection=store.swiss_tournaments)
        if not more:
            award(store, saved)
        return view(saved)

    @app.post('/api/swiss/{tournament_id}/finish')
    def finish(tournament_id: str, data: SwissAction, user=Depends(writer), store=Depends(store_dep)):
        doc = load(store, tournament_id)
        require_tournament_write(user, doc['nome_torneo'])
        if doc.get('torneo_finito'):
            raise HTTPException(409, 'Torneo già concluso.')
        if not all(r.get('Validata') for r in doc['df_torneo']):
            raise HTTPException(422, 'Valida tutte le partite prima di concludere.')
        saved = save(store, doc, data.version, {'torneo_finito': True}, collection=store.swiss_tournaments)
        award(store, saved)
        return view(saved)

    @app.get('/api/swiss/{tournament_id}/export.pdf')
    def pdf(tournament_id: str, user=Depends(current_user), store=Depends(store_dep)):
        data = view(load(store, tournament_id))
        adapted = dict(name=data['name'], standings=[{**r, 'Girone':'Classifica', 'P':r['N'], 'S':r['P']} for r in data['standings']],
                       matches=[dict(group='Classifica', day=r['round'], **{k:r[k] for k in ('home', 'away', 'home_goals', 'away_goals', 'valid')}) for r in data['matches']])
        return Response(render_tournament_pdf(adapted), media_type='application/pdf', headers={'Content-Disposition': 'attachment; filename="gazzettino-svizzero.pdf"'})
