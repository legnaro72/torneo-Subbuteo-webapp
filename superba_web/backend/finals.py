"""Final stages compatible with the classic Superba calendar format."""
import hashlib
from datetime import datetime

from bson import ObjectId
from fastapi import Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from pymongo.errors import DuplicateKeyError

from .domain import genera_calendario_from_list
from .models import Result
from .report import render_knockout_pdf
from .tournaments import is_italiana, load as load_italiana, normalized_rows, save, version


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class CreateFinals(Input):
    source_id: str
    mode: str = Field(pattern='^(ko|groups)$')
    qualifiers: int = Field(ge=2, le=64)
    group_count: int = Field(default=1, ge=1, le=8)
    return_matches: bool = False
    groups: list[list[str]] | None = None
    request_id: str = Field(pattern=r'^[0-9a-f-]{36}$')


class SaveFinals(Input):
    version: str = Field(pattern=r'^[a-f0-9]{64}$')
    results: list[Result] = Field(min_length=1, max_length=1000)


class FinalAction(Input):
    version: str = Field(pattern=r'^[a-f0-9]{64}$')


def is_final(doc):
    name = doc.get('nome_torneo', '').removeprefix('finito_')
    return name.startswith('fasefinaleEliminazionediretta_') and isinstance(doc.get('calendario'), list)


def load(store, tournament_id):
    if not ObjectId.is_valid(tournament_id):
        raise HTTPException(404, 'Fase finale non trovata.')
    doc = store.tournaments.find_one({'_id': ObjectId(tournament_id)})
    if not doc or not is_final(doc):
        raise HTTPException(404, 'Fase finale non trovata.')
    return doc


def base_name(name):
    for prefix in ('completato_', 'finito_', 'fasefinaleAGironi_', 'fasefinaleEliminazionediretta_'):
        if name.startswith(prefix):
            return base_name(name[len(prefix):])
    return name


def preliminary_ranking(doc):
    rows = normalized_rows(doc)
    if not rows or not all(r['valid'] for r in rows):
        raise HTTPException(422, 'Il torneo preliminare deve avere tutte le partite validate.')
    teams = {r[key] for r in rows for key in ('home', 'away')}
    stats = {name: dict(team=name, points=0, played=0, wins=0, gf=0, ga=0, difference=0) for name in teams}
    for row in rows:
        a, b = stats[row['home']], stats[row['away']]
        x, y = row['home_goals'], row['away_goals']
        a['played'] += 1; b['played'] += 1
        a['gf'] += x; a['ga'] += y; b['gf'] += y; b['ga'] += x
        if x > y:
            a['points'] += 2; a['wins'] += 1
        elif y > x:
            b['points'] += 2; b['wins'] += 1
        else:
            a['points'] += 1; b['points'] += 1
    for r in stats.values():
        r['difference'] = r['gf'] - r['ga']
    return sorted(stats.values(), key=lambda x: (-x['points'], -x['difference'], -x['gf'], -x['wins'], x['team'].casefold()))


def round_name(teams):
    return {32:'Sedicesimi di finale', 16:'Ottavi di finale', 8:'Quarti di finale', 4:'Semifinali', 2:'Finale'}.get(teams, f'Turno a {teams}')


def ko_rows(teams, day, phase_id, player_map):
    pairs = [(teams[i], teams[-i-1]) for i in range(len(teams)//2)]
    return [dict(Round=round_name(len(teams)), Match=i+1, Casa=a, Ospite=b, GolCasa=None, GolOspite=None,
                 Valida=False, Vincitore=None, GiocatoreCasa=player_map.get(a, a.split('-', 1)[-1].strip()),
                 GiocatoreOspite=player_map.get(b, b.split('-', 1)[-1].strip()), Girone='Eliminazione Diretta',
                 Giornata=day, PhaseID=phase_id, PhaseMode='KO') for i, (a,b) in enumerate(pairs)]


def view(doc):
    matches = []
    for index, row in enumerate(doc.get('calendario', [])):
        if row.get('Girone') != 'Eliminazione Diretta':
            continue
        matches.append(dict(index=index, round=int(row.get('Giornata') or 1), round_name=row.get('Round') or round_name(2*sum(r.get('Giornata') == row.get('Giornata') for r in doc['calendario'])),
                            home=str(row['Casa']), away=str(row['Ospite']), home_goals=int(row.get('GolCasa') or 0), away_goals=int(row.get('GolOspite') or 0),
                            valid=bool(row.get('Valida')), winner=row.get('Vincitore')))
    current = max((r['round'] for r in matches), default=1)
    final = next((r for r in matches if r['round_name'] == 'Finale' and r['valid']), None)
    winner = final['winner'] if final else None
    if final and not winner:
        winner = final['home'] if final['home_goals'] > final['away_goals'] else final['away']
    return dict(id=str(doc['_id']), name=doc['nome_torneo'], version=version(doc), matches=matches,
                badges=doc.get('_superba_badges', {}),
                active_round=current, finished=bool(doc.get('_superba_closed')) or doc['nome_torneo'].startswith('finito_'), winner=winner)


def award(store, doc, winner):
    if not winner:
        return
    name = base_name(doc['nome_torneo']).strip()
    player_name = winner.split('-', 1)[1].strip() if '-' in winner else winner
    player = store.players.find_one({'$or': [{'Giocatore': player_name}, {'Squadra': winner}]})
    if not player:
        return
    previous = player.get('listaFFElimDirettaVinte', [])
    if not isinstance(previous, list) or any(base_name(str(p)).casefold() == name.casefold() for p in previous):
        return
    store.players.update_one({'_id': player['_id'], '_superba_award_ids': {'$ne': f"ff:{doc['_id']}"}, 'listaFFElimDirettaVinte': {'$ne': name}},
                             {'$addToSet': {'listaFFElimDirettaVinte': name, '_superba_award_ids': f"ff:{doc['_id']}"}, '$inc': {'NFFElimDirettaVinte': 1}})


def install(app, current_user, writer, store_dep, require_tournament_write):
    @app.get('/api/finals/sources')
    def sources(user=Depends(current_user), store=Depends(store_dep)):
        result = []
        for doc in store.tournaments.find({'nome_torneo': {'$regex': '^completato_'}}, {'nome_torneo': 1, 'calendario': 1}):
            if not is_italiana(doc) or doc['nome_torneo'].startswith('completato_fasefinale'):
                continue
            try:
                rank = preliminary_ranking(doc)
            except HTTPException:
                continue
            result.append(dict(id=str(doc['_id']), name=doc['nome_torneo'], ranking=rank))
        return result

    @app.get('/api/finals')
    def listing(user=Depends(current_user), store=Depends(store_dep)):
        result = []
        for doc in store.tournaments.find({'nome_torneo': {'$regex': '^(finito_)?fasefinale'}}, {'nome_torneo': 1, 'calendario': 1, '_superba_closed': 1}).sort('_id', -1):
            if is_final(doc):
                data = view(doc)
                result.append(dict(id=data['id'], name=data['name'], mode='ko', finished=data['finished']))
            elif is_italiana(doc):
                result.append(dict(id=str(doc['_id']), name=doc['nome_torneo'], mode='groups', finished=bool(doc.get('_superba_closed'))))
        return result

    @app.get('/api/finals/{tournament_id}')
    def get(tournament_id: str, user=Depends(current_user), store=Depends(store_dep)):
        return view(load(store, tournament_id))

    @app.post('/api/finals')
    def create(data: CreateFinals, user=Depends(writer), store=Depends(store_dep)):
        source = load_italiana(store, data.source_id)
        require_tournament_write(user, source['nome_torneo'])
        if not source['nome_torneo'].startswith('completato_'):
            raise HTTPException(422, 'Seleziona una copia preliminare completata.')
        ranked = preliminary_ranking(source)
        if data.qualifiers > len(ranked):
            raise HTTPException(422, 'Qualificati superiori ai partecipanti.')
        qualifiers = [row['team'] for row in ranked[:data.qualifiers]]
        name = ('fasefinaleEliminazionediretta_' if data.mode == 'ko' else 'fasefinaleAGironi_') + base_name(source['nome_torneo'])
        require_tournament_write(user, name)
        if data.mode == 'ko' and (data.qualifiers & (data.qualifiers - 1) or data.qualifiers > 32):
            raise HTTPException(422, 'Per l’eliminazione diretta scegli 2, 4, 8, 16 o 32 qualificati.')
        if data.mode == 'groups' and (data.qualifiers < 4 or data.group_count > data.qualifiers // 4):
            raise HTTPException(422, 'Servono almeno quattro qualificati per girone.')
        digest = hashlib.sha256(data.model_dump_json(exclude={'request_id'}).encode()).hexdigest()
        object_id = ObjectId(hashlib.sha256((user['id'] + data.request_id).encode()).hexdigest()[:24])
        existing = store.tournaments.find_one({'_id': object_id})
        if existing:
            if existing.get('_superba_create_hash') != digest:
                raise HTTPException(409, 'Richiesta di creazione già utilizzata.')
            return dict(id=str(object_id), mode=data.mode)
        if store.tournaments.find_one({'nome_torneo': name}, {'_id': 1}):
            raise HTTPException(409, 'Esiste già una fase finale con questo nome.')
        player_map = {str(r[k]): str(r.get('Giocatore'+suffix) or str(r[k]).split('-',1)[-1].strip()) for r in source['calendario'] for k,suffix in [('Casa','Casa'),('Ospite','Ospite')]}
        if data.mode == 'ko':
            rows = ko_rows(qualifiers, 1, str(object_id), player_map)
        else:
            if data.groups is not None:
                groups = data.groups
                if len(groups) != data.group_count or sorted(x for g in groups for x in g) != sorted(qualifiers) or any(len(g)<4 for g in groups):
                    raise HTTPException(422, 'Distribuzione dei qualificati non valida.')
            else:
                groups = [[] for _ in range(data.group_count)]
                for i, team in enumerate(qualifiers):
                    cycle=i//data.group_count
                    index=i%data.group_count if cycle%2==0 else data.group_count-1-i%data.group_count
                    groups[index].append(team)
            rows = genera_calendario_from_list(groups, 'Andata e ritorno' if data.return_matches else 'Solo andata').to_dict('records')
            for row in rows:
                row['GiocatoreCasa'] = player_map.get(row['Casa'])
                row['GiocatoreOspite'] = player_map.get(row['Ospite'])
        now = datetime.utcnow()
        doc = dict(_id=object_id, nome_torneo=name, calendario=rows, data_creazione=now, data_modifica=now,
                   _superba_badges={key: value for key, value in source.get('_superba_badges', {}).items() if key in qualifiers},
                   phase_metadata=dict(phase_id=str(object_id), phase_mode='KO' if data.mode=='ko' else 'GIRONI'),
                   _superba_preliminary_id=data.source_id, _superba_create_hash=digest, _superba_revision=0)
        try:
            store.tournaments.insert_one(doc)
        except DuplicateKeyError:
            existing = store.tournaments.find_one({'_id': object_id})
            if not existing or existing.get('_superba_create_hash') != digest:
                raise HTTPException(409, 'Creazione concorrente. Ricarica la pagina.')
        return dict(id=str(object_id), mode=data.mode)

    @app.patch('/api/finals/{tournament_id}/results')
    def results(tournament_id: str, data: SaveFinals, user=Depends(writer), store=Depends(store_dep)):
        doc = load(store, tournament_id)
        require_tournament_write(user, doc['nome_torneo'])
        if view(doc)['finished']:
            raise HTTPException(409, 'Fase finale già conclusa.')
        rows = [dict(row) for row in doc['calendario']]
        active = max(int(r.get('Giornata') or 1) for r in rows)
        indices = [r.index for r in data.results]
        if len(set(indices)) != len(indices) or any(i >= len(rows) for i in indices):
            raise HTTPException(422, 'Partita non valida.')
        for change in data.results:
            row = rows[change.index]
            if int(row.get('Giornata') or 1) != active:
                raise HTTPException(422, 'Puoi modificare solo il turno attivo.')
            if change.valid and change.home == change.away:
                raise HTTPException(422, 'In eliminazione diretta il risultato validato non può essere pari.')
            row.update(GolCasa=change.home, GolOspite=change.away, Valida=change.valid,
                       Vincitore=(row['Casa'] if change.home > change.away else row['Ospite']) if change.valid else None)
        return view(save(store, doc, data.version, {'calendario': rows}))

    @app.post('/api/finals/{tournament_id}/advance')
    def advance(tournament_id: str, data: FinalAction, user=Depends(writer), store=Depends(store_dep)):
        doc = load(store, tournament_id)
        require_tournament_write(user, doc['nome_torneo'])
        if view(doc)['finished']:
            raise HTTPException(409, 'Fase finale già conclusa.')
        active = max(int(r.get('Giornata') or 1) for r in doc['calendario'])
        current = [r for r in doc['calendario'] if int(r.get('Giornata') or 1) == active]
        if not current or not all(r.get('Valida') and r.get('GolCasa') != r.get('GolOspite') for r in current):
            raise HTTPException(422, 'Valida tutte le partite con un vincitore prima di avanzare.')
        winners = [r.get('Vincitore') or (r['Casa'] if r['GolCasa'] > r['GolOspite'] else r['Ospite']) for r in current]
        if len(winners) == 1:
            saved = save(store, doc, data.version, {'nome_torneo': 'finito_'+doc['nome_torneo'], '_superba_closed': True})
            award(store, saved, winners[0])
            return view(saved)
        player_map = {r['Casa']: r.get('GiocatoreCasa') for r in current} | {r['Ospite']: r.get('GiocatoreOspite') for r in current}
        phase = doc.get('phase_metadata', {}).get('phase_id', str(doc['_id']))
        new_rows = ko_rows(winners, active+1, phase, player_map)
        return view(save(store, doc, data.version, {'calendario': doc['calendario'] + new_rows}))

    @app.get('/api/finals/{tournament_id}/export.pdf')
    def pdf(tournament_id: str, user=Depends(current_user), store=Depends(store_dep)):
        data = view(load(store, tournament_id))
        return Response(render_knockout_pdf(data), media_type='application/pdf', headers={'Content-Disposition': 'attachment; filename="gazzettino-finali.pdf"'})
