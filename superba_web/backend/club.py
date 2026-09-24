"""Club management API. No reads have database side effects."""
import csv
import io
from datetime import datetime
from typing import Literal

from bson import ObjectId
from fastapi import Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints
from typing import Annotated
from pymongo.errors import PyMongoError

from .club_report import render_club_pdf
from .security import verify_password
from .tournaments import version


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Team = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
Role = Literal['R', 'W', 'A']


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class PlayerInput(Input):
    name: Name
    team: Team = ''
    potential: StrictInt = Field(ge=1, le=10)
    role: Role | None = None


class PlayerEdit(PlayerInput):
    version: str = Field(pattern=r'^[a-f0-9]{64}$')


class BulkPlayerEdit(PlayerEdit):
    id: str = Field(pattern=r'^[a-fA-F0-9]{24}$')


class BulkEdit(Input):
    players: list[BulkPlayerEdit] = Field(min_length=1, max_length=200)


class DeletePlayer(Input):
    version: str = Field(pattern=r'^[a-f0-9]{64}$')


class TournamentTarget(Input):
    scope: Literal['italiana', 'svizzero']
    id: str = Field(pattern=r'^[a-fA-F0-9]{24}$')
    name: Name


class DeleteTournaments(Input):
    targets: list[TournamentTarget] = Field(min_length=1, max_length=1000)
    all_except_championships: bool = False
    clear_scope: Literal['italiana', 'svizzero', 'all'] | None = None
    password: str = Field(default='', max_length=256)


TROPHIES = (
    ('NCampionatiVinti', 'listaCampionatiVinti'),
    ('NGironiFFVinti', 'listaGironiFFVinti'),
    ('NFFElimDirettaVinte', 'listaFFElimDirettaVinte'),
)


def player_view(doc):
    trophies = {}
    for count, names in TROPHIES:
        try:
            trophies[count] = int(doc.get(count) or 0)
        except (ValueError, TypeError):
            trophies[count] = 0
        raw = doc.get(names, [])
        trophies[names] = [str(item).strip() for item in raw if str(item).strip()] if isinstance(raw, list) else [s.strip() for s in raw.split(',') if s.strip()] if isinstance(raw, str) else []
    try:
        potential = int(doc.get('Potenziale') or 0)
    except (ValueError, TypeError):
        potential = 0
    return {'id': str(doc['_id']), 'version': version(doc), 'name': str(doc.get('Giocatore') or ''),
            'team': str(doc.get('Squadra') or ''), 'potential': potential,
            'role': doc.get('Ruolo') if doc.get('Ruolo') in ('R', 'W', 'A') else 'R',
            'password_set': doc.get('SetPwd') == 1, **trophies}


def audit(store, user, action, details):
    try:
        store.audit.insert_one({'at': datetime.utcnow(), 'user_id': user['id'], 'action': action, 'details': details})
    except PyMongoError:
        pass


def require_admin(user):
    if user['role'] != 'A':
        raise HTTPException(403, 'Operazione riservata agli amministratori.')


def object_id(value):
    if not ObjectId.is_valid(value):
        raise HTTPException(404, 'Record non trovato.')
    return ObjectId(value)


def check_password(store, user, password):
    player = store.players.find_one({'_id': object_id(user['id'])})
    if not player or not verify_password(password, player.get('Password')):
        raise HTTPException(403, 'Conferma la tua password di accesso per questa eliminazione.')


def update_one(store, original, data, user):
    if version(original) != data.version:
        raise HTTPException(409, 'Il giocatore è cambiato. Ricarica l’anagrafica prima di salvare.')
    if data.role is not None and user['role'] != 'A':
        raise HTTPException(403, 'Solo un amministratore può modificare i ruoli.')
    if str(original['_id']) == user['id'] and data.role is not None and data.role != 'A' and user['role'] == 'A':
        raise HTTPException(409, 'Non puoi rimuovere il tuo ruolo amministratore mentre sei connesso.')
    changes = {'Giocatore': data.name, 'Squadra': data.team, 'Potenziale': data.potential}
    if data.role is not None:
        changes['Ruolo'] = data.role
    conditions = [{field: {'$eq': value, '$exists': True}} for field, value in original.items() if field != '_id']
    if '_club_revision' not in original:
        conditions.append({'_club_revision': {'$exists': False}})
    changes['_club_revision'] = int(original.get('_club_revision', 0)) + 1
    result = store.players.update_one({'_id': original['_id'], '$and': conditions}, {'$set': changes})
    if result.matched_count != 1:
        raise HTTPException(409, 'Modifica concorrente: ricarica l’anagrafica.')
    audit(store, user, 'club_player_edit', {'id': str(original['_id']), 'fields': list(changes)})
    return player_view({**original, **changes})


def install(app, current_user, writer, store_dep):
    def admin(user=Depends(writer)):
        require_admin(user)
        return user

    @app.get('/api/club/players')
    def club_players(user=Depends(current_user), store=Depends(store_dep)):
        return [player_view(p) for p in store.players.find({}).sort('Giocatore', 1)]

    @app.post('/api/club/players')
    def create_player(data: PlayerInput, user=Depends(writer), store=Depends(store_dep)):
        if data.role is not None and user['role'] != 'A':
            raise HTTPException(403, 'Solo un amministratore può assegnare ruoli.')
        if store.user(data.name):
            raise HTTPException(409, 'Esiste già un giocatore con questo nome.')
        role = data.role or 'R'
        doc = {'Giocatore': data.name, 'Squadra': data.team, 'Potenziale': data.potential,
               'Ruolo': role, 'Password': None, 'SetPwd': 0, '_club_revision': 0}
        for count, names in TROPHIES:
            doc[count], doc[names] = 0, []
        result = store.players.insert_one(doc)
        doc['_id'] = result.inserted_id
        audit(store, user, 'club_player_create', {'id': str(doc['_id'])})
        return player_view(doc)

    @app.patch('/api/club/players/{player_id}')
    def edit_player(player_id: str, data: PlayerEdit, user=Depends(writer), store=Depends(store_dep)):
        original = store.players.find_one({'_id': object_id(player_id)})
        if not original:
            raise HTTPException(404, 'Giocatore non trovato.')
        collision = store.user(data.name)
        if collision and collision['_id'] != original['_id']:
            raise HTTPException(409, 'Esiste già un giocatore con questo nome.')
        return update_one(store, original, data, user)

    @app.post('/api/club/players/bulk')
    def bulk_players(data: BulkEdit, user=Depends(admin), store=Depends(store_dep)):
        edits = [(item.id, item) for item in data.players]
        ids = [value for value, _ in edits]
        if len(set(ids)) != len(ids):
            raise HTTPException(422, 'Giocatore duplicato nella tabella.')
        existing = {str(p['_id']): p for p in store.players.find({})}
        if any(player_id not in existing for player_id in ids):
            raise HTTPException(409, 'Un giocatore non è più nell’anagrafica.')
        unchanged_names = {str(doc.get('Giocatore') or '').casefold() for player_id, doc in existing.items() if player_id not in ids}
        names = [item.name.casefold() for _, item in edits]
        if len(set(names)) != len(names) or any(name in unchanged_names for name in names):
            raise HTTPException(409, 'Nomi duplicati nell’anagrafica.')
        if any(version(existing[player_id]) != item.version for player_id, item in edits):
            raise HTTPException(409, 'La tabella è cambiata. Ricarica prima di salvare.')
        for player_id, item in edits:
            update_one(store, existing[player_id], item, user)
        return {'updated': len(edits)}

    @app.delete('/api/club/players/{player_id}')
    def delete_player(player_id: str, data: DeletePlayer, user=Depends(admin), store=Depends(store_dep)):
        original = store.players.find_one({'_id': object_id(player_id)})
        if not original:
            raise HTTPException(404, 'Giocatore non trovato.')
        if player_id == user['id']:
            raise HTTPException(409, 'Non puoi eliminare il tuo account mentre sei connesso.')
        if version(original) != data.version:
            raise HTTPException(409, 'Il giocatore è cambiato. Ricarica prima di eliminare.')
        result = store.players.delete_one({'_id': original['_id'], 'Giocatore': original.get('Giocatore'), '_club_revision': original.get('_club_revision', 0)}) if '_club_revision' in original else store.players.delete_one({'_id': original['_id'], 'Giocatore': original.get('Giocatore'), '_club_revision': {'$exists': False}})
        if result.deleted_count != 1:
            raise HTTPException(409, 'Il giocatore è cambiato. Ricarica prima di eliminare.')
        audit(store, user, 'club_player_delete', {'id': player_id, 'name': original.get('Giocatore')})
        return {'deleted': 1}

    @app.post('/api/club/players/{player_id}/reset-password')
    def reset_password(player_id: str, user=Depends(admin), store=Depends(store_dep)):
        original = store.players.find_one({'_id': object_id(player_id)})
        if not original:
            raise HTTPException(404, 'Giocatore non trovato.')
        if player_id == user['id']:
            raise HTTPException(409, 'Per cambiare la tua password usa il percorso del tuo account.')
        result = store.players.update_one({'_id': original['_id'], 'Password': original.get('Password')},
                                          {'$set': {'Password': None, 'SetPwd': 0}, '$inc': {'_club_revision': 1}})
        if result.matched_count != 1:
            raise HTTPException(409, 'Il giocatore è cambiato. Ricarica prima del reset.')
        store.sessions.update_many({'user_id': player_id}, {'$set': {'revoked': True}})
        audit(store, user, 'club_password_reset', {'id': player_id})
        return {'ok': True}

    @app.get('/api/club/tournaments')
    def club_tournaments(user=Depends(current_user), store=Depends(store_dep)):
        values = []
        for scope, collection in (('italiana', store.tournaments), ('svizzero', store.swiss_tournaments)):
            for doc in collection.find({}, {'nome_torneo': 1}).sort('nome_torneo', 1):
                name = str(doc.get('nome_torneo') or '')
                values.append({'id': str(doc['_id']), 'scope': scope, 'name': name,
                               'championship': 'campionato' in name.casefold()})
        return values

    @app.post('/api/club/tournaments/delete')
    def delete_tournaments(data: DeleteTournaments, user=Depends(admin), store=Depends(store_dep)):
        if data.all_except_championships != (data.clear_scope is not None):
            raise HTTPException(422, 'Ambito dell’eliminazione globale non valido.')
        targets = [(item.scope, item.id, item.name) for item in data.targets]
        if len(set((scope, player_id) for scope, player_id, _ in targets)) != len(targets):
            raise HTTPException(422, 'Torneo duplicato nella richiesta.')
        collections = {'italiana': store.tournaments, 'svizzero': store.swiss_tournaments}
        docs = []
        for scope, tournament_id, name in targets:
            doc = collections[scope].find_one({'_id': object_id(tournament_id)})
            if not doc or doc.get('nome_torneo') != name:
                raise HTTPException(409, 'L’archivio è cambiato. Ricarica prima di eliminare.')
            if data.all_except_championships and 'campionato' in name.casefold():
                raise HTTPException(422, 'L’eliminazione globale esclude i Campionati.')
            docs.append((scope, doc))
        if data.all_except_championships:
            selected_collections = collections.items() if data.clear_scope == 'all' else [(data.clear_scope, collections[data.clear_scope])]
            eligible = {(scope, str(doc['_id'])) for scope, collection in selected_collections for doc in collection.find({}, {'nome_torneo': 1})
                        if 'campionato' not in str(doc.get('nome_torneo') or '').casefold()}
            if eligible != {(scope, str(doc['_id'])) for scope, doc in docs}:
                raise HTTPException(409, 'L’archivio è cambiato. Ricarica l’anteprima delle eliminazioni.')
        if data.all_except_championships or any('campionato' in str(doc.get('nome_torneo') or '').casefold() for _, doc in docs):
            check_password(store, user, data.password)
        deleted = 0
        for scope, doc in docs:
            result = collections[scope].delete_one({'_id': doc['_id'], 'nome_torneo': doc['nome_torneo']})
            if result.deleted_count != 1:
                raise HTTPException(409, f'{deleted} eliminati; un torneo è cambiato. Ricarica l’archivio.')
            deleted += 1
        audit(store, user, 'club_tournament_delete', {'count': deleted, 'scopes': sorted({scope for scope, _ in docs}),
                                                     'all_except_championships': data.all_except_championships})
        return {'deleted': deleted}

    @app.get('/api/club/export.csv')
    def club_csv(user=Depends(current_user), store=Depends(store_dep)):
        out = io.StringIO()
        csv_writer = csv.writer(out)
        headers = ['Giocatore', 'Squadra', 'Potenziale', 'Ruolo', 'NCampionatiVinti', 'listaCampionatiVinti',
                   'NGironiFFVinti', 'listaGironiFFVinti', 'NFFElimDirettaVinte', 'listaFFElimDirettaVinte']
        csv_writer.writerow(headers)
        def safe(value):
            value = str(value)
            return "'" + value if value.startswith(('=', '+', '-', '@', '\t', '\r')) else value
        for doc in store.players.find({}).sort('Giocatore', 1):
            row = player_view(doc)
            names = {'Giocatore': 'name', 'Squadra': 'team', 'Potenziale': 'potential', 'Ruolo': 'role'}
            csv_writer.writerow([safe(', '.join(row[names.get(key, key)]) if isinstance(row[names.get(key, key)], list) else row[names.get(key, key)]) for key in headers])
        return Response(out.getvalue().encode('utf-8-sig'), media_type='text/csv',
                        headers={'Content-Disposition': 'attachment; filename="giocatori-superba.csv"'})

    @app.get('/api/club/export.pdf')
    def club_pdf(user=Depends(current_user), store=Depends(store_dep)):
        players = [player_view(doc) for doc in store.players.find({}).sort('Giocatore', 1)]
        italian = [str(doc.get('nome_torneo') or '') for doc in store.tournaments.find({}, {'nome_torneo': 1}).sort('nome_torneo', 1)]
        swiss = [str(doc.get('nome_torneo') or '') for doc in store.swiss_tournaments.find({}, {'nome_torneo': 1}).sort('nome_torneo', 1)]
        return Response(render_club_pdf(players, italian, swiss), media_type='application/pdf',
                        headers={'Content-Disposition': 'attachment; filename="Gazzetta-Club-Superba.pdf"'})
