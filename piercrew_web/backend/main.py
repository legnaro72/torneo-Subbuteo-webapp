import csv
import hashlib
import io
import os
import re
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

from bson import ObjectId
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from .domain import genera_calendario_from_list
from .models import Activate, ActivationLookup, Complete, CreateTournament, Login, Rename, SaveBadges, SaveResults, Withdrawal
from .report import render_tournament_pdf
from .security import generate_token, hash_password, hash_token, password_needs_upgrade, verify_password
from .store import Store, get_store
from .tournaments import is_italiana, load, save, view

app = FastAPI(title='PierCrew', docs_url='/api/docs', openapi_url='/api/openapi.json')
COOKIE = 'piercrew_portal_session'
DESTINATIONS = {
    'finali': os.getenv('LEGACY_FINALI_URL', ''),
    'svizzero': os.getenv('LEGACY_SVIZZERO_URL', ''),
    'club': os.getenv('LEGACY_CLUB_URL', ''),
    'italiana-classica': os.getenv('LEGACY_ITALIANA_URL', ''),
}


@app.middleware('http')
async def guard(request: Request, call_next):
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        expected = os.getenv('PIERCREW_APP_ORIGIN', str(request.base_url).rstrip('/'))
        origin = request.headers.get('origin')
        if request.headers.get('x-piercrew-request') != '1' or (origin and origin != expected):
            return JSONResponse({'detail': 'Richiesta non autorizzata.'}, status_code=403)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


@app.exception_handler(PyMongoError)
async def database_error(request, exc):
    return JSONResponse({'detail': 'Database temporaneamente non disponibile. Riprova: le modifiche locali restano disponibili.'}, status_code=503)


def store_dep():
    try:
        return get_store()
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))


def identity(player, password_verified=False):
    return {'id': str(player['_id']), 'username': player.get('Giocatore', ''),
            'role': player.get('Ruolo', 'R'), 'password_verified': password_verified}


def current_user(request: Request, store: Store = Depends(store_dep)):
    token = request.cookies.get(COOKIE)
    session = store.sessions.find_one({'_id': hash_token(token), 'expires_at': {'$gt': datetime.utcnow()}, 'revoked': False}) if token else None
    if not session:
        raise HTTPException(401, 'Accedi al portale per continuare.')
    if session['user_id'] == 'guest':
        return {'id': 'guest', 'username': 'Ospite', 'role': 'G', 'password_verified': False}
    player = store.players.find_one({'_id': ObjectId(session['user_id'])})
    if not player or session.get('credential_version') != hash_token(str(player.get('Password', ''))):
        raise HTTPException(401, 'La sessione non è più valida. Accedi nuovamente.')
    # Reader sessions cannot acquire write privileges after a role change.
    result = identity(player, session.get('password_verified', False))
    if result['role'] in ('A', 'W') and not result['password_verified']:
        raise HTTPException(401, 'Il tuo ruolo è cambiato. Accedi con la password.')
    return result


def writer(user=Depends(current_user), store: Store = Depends(store_dep)):
    if user['role'] not in ('A', 'W') or not user['password_verified']:
        raise HTTPException(403, 'Il tuo profilo è in sola lettura.')
    if not store.demo and os.getenv('PIERCREW_WRITE_ENABLED', '').lower() != 'true':
        raise HTTPException(403, 'Questo ambiente è in sola lettura. I salvataggi devono essere abilitati dal gestore.')
    return user


def require_tournament_write(user, name):
    if 'Campionato' in name and user['role'] != 'A':
        raise HTTPException(403, 'Solo un amministratore può modificare i Campionati.')


def rate_limit(request, store, username):
    bucket = int(time.time() // 900)
    ip = request.client.host if request.client else 'unknown'
    for scope, value, limit in [('user', username.strip().casefold(), 10), ('ip', ip, 60)]:
        key = f'{scope}:{hash_token(value)}:{bucket}'
        item = store.attempts.find_one_and_update({'_id': key}, {'$inc': {'count': 1}, '$setOnInsert': {'expires_at': datetime.utcnow() + timedelta(minutes=30)}}, upsert=True, return_document=ReturnDocument.AFTER)
        if item['count'] > limit:
            raise HTTPException(429, 'Troppi tentativi. Riprova tra 15 minuti.')


def establish(response, store, player=None, *, remember=False, verified=False):
    token = generate_token()
    hours = 720 if remember else 2
    now = datetime.utcnow()
    user = identity(player, verified) if player else {'id': 'guest', 'username': 'Ospite', 'role': 'G', 'password_verified': False}
    store.sessions.insert_one({'_id': hash_token(token), 'user_id': user['id'], 'created_at': now,
                              'expires_at': now + timedelta(hours=hours), 'revoked': False,
                              'password_verified': verified, 'credential_version': hash_token(str(player.get('Password', ''))) if player else None})
    secure = bool(os.getenv('VERCEL')) or os.getenv('PIERCREW_APP_ORIGIN', '').startswith('https://')
    response.set_cookie(COOKIE, token, max_age=hours*3600, httponly=True, secure=secure, samesite='lax', path='/')
    return user


@app.get('/api/config')
def config():
    demo = os.getenv('PIERCREW_DEMO', '').lower() == 'true' and not os.getenv('VERCEL')
    return {'demo': demo, 'writes_enabled': demo or os.getenv('PIERCREW_WRITE_ENABLED', '').lower() == 'true'}


@app.get('/api/health')
def health(store: Store = Depends(store_dep)):
    # An unprivileged read verifies both database connections without exposing records.
    store.players.find_one({}, {'_id': 1})
    store.tournaments.find_one({}, {'_id': 1})
    store.swiss_tournaments.find_one({}, {'_id': 1})
    return {'database': 'ok'}


@app.post('/api/auth/login')
def login(data: Login, request: Request, response: Response, store: Store = Depends(store_dep)):
    rate_limit(request, store, data.username)
    player = store.user(data.username)
    if not player or player.get('Ruolo', 'R') not in ('A', 'W', 'R'):
        raise HTTPException(401, 'Credenziali non valide.')
    if player.get('Ruolo', 'R') == 'R':
        return establish(response, store, player, remember=data.remember)
    if player.get('SetPwd') != 1:
        raise HTTPException(403, 'Account da attivare: usa “Primo accesso”.')
    stored = str(player.get('Password', ''))
    if not verify_password(data.password, stored):
        raise HTTPException(401, 'Credenziali non valide.')
    if password_needs_upgrade(stored):
        upgraded = hash_password(data.password)
        changed = store.players.update_one({'_id': player['_id'], 'Password': player['Password']}, {'$set': {'Password': upgraded}})
        if changed.matched_count != 1:
            raise HTTPException(409, 'Credenziali modificate. Riprova il login.')
        player['Password'] = upgraded
    return establish(response, store, player, remember=data.remember, verified=True)


@app.post('/api/auth/activate')
def activate(data: Activate, request: Request, response: Response, store: Store = Depends(store_dep)):
    rate_limit(request, store, data.username)
    player = store.user(data.username)
    if not player or player.get('SetPwd') == 1 or player.get('Ruolo') not in ('A', 'W') or not store.system_passwords.find_one({'Password': data.system_password}):
        raise HTTPException(403, 'Attivazione non consentita. Verifica i dati con il gestore.')
    if len(data.password.encode()) > 72:
        raise HTTPException(422, 'Password troppo lunga: usa al massimo 72 byte UTF-8.')
    password = hash_password(data.password)
    result = store.players.update_one({'_id': player['_id'], 'SetPwd': {'$ne': 1}}, {'$set': {'Password': password, 'SetPwd': 1}})
    if result.matched_count != 1:
        raise HTTPException(409, 'Account già attivato. Accedi con la password.')
    player.update(Password=password, SetPwd=1)
    return establish(response, store, player, verified=True)


@app.post('/api/auth/activation-users')
def activation_users(data: ActivationLookup, request: Request, store: Store = Depends(store_dep)):
    rate_limit(request, store, 'activation-users')
    if not store.system_passwords.find_one({'Password': data.system_password}):
        raise HTTPException(403, 'Password di sistema non valida.')
    names = (p.get('Giocatore', '').strip() for p in store.players.find(
        {'Ruolo': {'$in': ['A', 'W']}, 'SetPwd': {'$ne': 1}}, {'Giocatore': 1}))
    return sorted((name for name in names if name), key=str.casefold)


@app.get('/api/auth/user-suggestions')
def user_suggestions(q: str, store: Store = Depends(store_dep)):
    query = q.strip()
    if len(query) < 2 or len(query) > 80:
        raise HTTPException(422, 'Digita da 2 a 80 caratteri.')
    players = store.players.find({
        'Giocatore': {'$regex': re.escape(query), '$options': 'i'},
        '$or': [{'Ruolo': {'$in': ['A', 'W', 'R']}}, {'Ruolo': {'$exists': False}}],
    }, {'Giocatore': 1}).sort('Giocatore', 1).limit(12)
    return [name for player in players if (name := str(player.get('Giocatore', '')).strip())]


@app.post('/api/auth/guest')
def guest(request: Request, response: Response, store: Store = Depends(store_dep)):
    rate_limit(request, store, 'guest')
    return establish(response, store)


@app.get('/api/auth/me')
def me(user=Depends(current_user)):
    return user


@app.post('/api/auth/logout')
def logout(request: Request, response: Response, store: Store = Depends(store_dep)):
    token = request.cookies.get(COOKIE)
    if token:
        store.sessions.update_one({'_id': hash_token(token)}, {'$set': {'revoked': True}})
    response.delete_cookie(COOKIE, path='/')
    return {'ok': True}


@app.post('/api/auth/open/{destination}')
def handoff(destination: str, user=Depends(current_user), store: Store = Depends(store_dep)):
    if destination not in DESTINATIONS or not DESTINATIONS[destination]:
        raise HTTPException(404, 'Destinazione non disponibile.')
    if store.demo:
        raise HTTPException(409, 'La demo non apre sessioni nelle applicazioni reali.')
    if user['id'] == 'guest':
        return {'url': DESTINATIONS[destination]}
    if destination == 'club' and user['role'] != 'A':
        raise HTTPException(403, 'Dal nuovo portale la gestione club è riservata agli amministratori.')
    token = generate_token()
    now = datetime.utcnow()
    store.handoffs.insert_one({'token_hash': hash_token(token), 'user_id': user['id'], 'username': user['username'],
                               'role': user['role'], 'collection': 'piercrew_players', 'created_at': now,
                               'expires_at': now + timedelta(minutes=5), 'consumed': False})
    return {'url': DESTINATIONS[destination] + '?' + urlencode({'auth_handoff': token})}


@app.get('/api/players')
def players(user=Depends(current_user), store: Store = Depends(store_dep)):
    return [{'id': str(p['_id']), 'name': p.get('Giocatore', ''), 'team': p.get('Squadra', ''), 'potential': str(p.get('Potenziale', ''))}
            for p in store.players.find({}, {'Giocatore': 1, 'Squadra': 1, 'Potenziale': 1}).sort('Giocatore', 1)]


@app.get('/api/tournaments')
def tournaments(user=Depends(current_user), store: Store = Depends(store_dep)):
    # Legacy type information lives inside calendars; do not infer type from name alone.
    result = []
    for doc in store.tournaments.find({}, {'nome_torneo': 1, 'calendario': 1, 'data_modifica': 1, 'data_creazione': 1}).sort([('data_modifica', -1), ('_id', -1)]):
        if is_italiana(doc):
            result.append({'id': str(doc['_id']), 'name': doc['nome_torneo'], 'matches': len(doc['calendario']),
                           'played': sum(r.get('Valida') is True for r in doc['calendario']),
                           'groups': len(set(r['Girone'] for r in doc['calendario']))})
    return result


@app.get('/api/tournaments/{tournament_id}')
def tournament(tournament_id: str, user=Depends(current_user), store: Store = Depends(store_dep)):
    return view(load(store, tournament_id))


@app.post('/api/tournaments')
def create(data: CreateTournament, user=Depends(writer), store: Store = Depends(store_dep)):
    require_tournament_write(user, data.name)
    flat = [name for group in data.groups for name in group]
    if not 3 <= len(flat) <= 64 or any(len(group) < 2 for group in data.groups) or len({x.casefold() for x in flat}) != len(flat):
        raise HTTPException(422, 'Servono da 3 a 64 partecipanti diversi e almeno 2 per girone.')
    if any(x.casefold() in ('riposo', 'riposa') for x in flat) or data.name.lower().startswith(('fasefinale', 'finito_', 'completato_')):
        raise HTTPException(422, 'Nome riservato: scegli un nome diverso per torneo o partecipanti.')
    if not set(data.badges) <= set(flat):
        raise HTTPException(422, 'Le immagini devono appartenere ai partecipanti selezionati.')
    if data.participants is None:
        roster = {f"{p['Squadra']}-{p['Giocatore']}" if p.get('Squadra') else p['Giocatore']
                  for p in store.players.find({}, {'Giocatore': 1, 'Squadra': 1}) if p.get('Giocatore')}
        if not set(flat) <= roster:
            raise HTTPException(422, 'Seleziona giocatori dell’anagrafica o aggiungi esplicitamente gli ospiti.')
    else:
        if len(data.participants) != len(flat):
            raise HTTPException(422, 'La lista dei partecipanti non corrisponde ai gironi.')
        source_ids = [p.source_id for p in data.participants if not p.guest]
        if any(not value or not ObjectId.is_valid(value) for value in source_ids):
            raise HTTPException(422, 'Giocatore dell’anagrafica non valido.')
        registered = {str(p['_id']): p for p in store.players.find({'_id': {'$in': [ObjectId(value) for value in source_ids]}}, {'Giocatore': 1})}
        labels = []
        for participant in data.participants:
            if participant.guest:
                if participant.source_id:
                    raise HTTPException(422, 'Un ospite non può avere un ID dell’anagrafica.')
            elif participant.source_id not in registered or registered[participant.source_id]['Giocatore'] != participant.name:
                raise HTTPException(422, 'Giocatore dell’anagrafica non trovato o modificato.')
            labels.append(f'{participant.team.strip()} - {participant.name}' if participant.team.strip() else participant.name)
        if len(set(source_ids)) != len(source_ids) or len(set(labels)) != len(labels) or set(labels) != set(flat):
            raise HTTPException(422, 'Assegnazione dei partecipanti ai gironi non valida.')
    payload_hash = hashlib.sha256(data.model_dump_json(exclude={'request_id'}).encode()).hexdigest()
    new_id = ObjectId(hashlib.sha256((user['id'] + data.request_id).encode()).hexdigest()[:24])
    existing = store.tournaments.find_one({'_id': new_id})
    if existing:
        if existing.get('_piercrew_create_hash') != payload_hash:
            raise HTTPException(409, 'Questa richiesta è già stata usata per un altro torneo.')
        return view(existing)
    calendar = genera_calendario_from_list(data.groups, 'Andata e ritorno' if data.return_matches else 'Solo andata')
    doc = {'_id': new_id, 'nome_torneo': data.name, 'calendario': calendar.to_dict('records'), 'data_creazione': datetime.utcnow(),
           'data_modifica': datetime.utcnow(), '_piercrew_revision': 0, '_piercrew_create_hash': payload_hash,
           '_piercrew_return_matches': data.return_matches}
    if data.badges:
        doc['_piercrew_badges'] = {key: badge.model_dump(exclude_none=True) for key, badge in data.badges.items()}
    if data.participants is not None:
        doc['_piercrew_participants'] = [p.model_dump() for p in data.participants]
    try:
        store.tournaments.insert_one(doc)
    except DuplicateKeyError:
        existing = store.tournaments.find_one({'_id': new_id})
        if not existing or existing.get('_piercrew_create_hash') != payload_hash:
            raise HTTPException(409, 'Creazione concorrente. Ricarica l’archivio.')
        return view(existing)
    return view(load(store, str(new_id)))


@app.patch('/api/tournaments/{tournament_id}/results')
def results(tournament_id: str, data: SaveResults, user=Depends(writer), store: Store = Depends(store_dep)):
    doc = load(store, tournament_id)
    require_tournament_write(user, doc['nome_torneo'])
    if view(doc)['closed']:
        raise HTTPException(409, 'Torneo concluso: usa la versione classica per le revisioni straordinarie.')
    rows = [dict(row) for row in doc['calendario']]
    indices = [r.index for r in data.results]
    if len(indices) != len(set(indices)) or any(i >= len(rows) for i in indices):
        raise HTTPException(422, 'Selezione delle partite non valida.')
    for change in data.results:
        rows[change.index].update(GolCasa=change.home, GolOspite=change.away, Valida=change.valid)
    saved = save(store, doc, data.version, {'calendario': rows})
    # Logging failure must never turn a successful tournament write into an apparent failure.
    try:
        store.audit.insert_one({'at': datetime.utcnow(), 'user_id': user['id'], 'tournament_id': tournament_id, 'action': 'results', 'indices': indices})
    except PyMongoError:
        pass
    return view(saved)


@app.patch('/api/tournaments/{tournament_id}/name')
def rename(tournament_id: str, data: Rename, user=Depends(writer), store: Store = Depends(store_dep)):
    doc = load(store, tournament_id)
    require_tournament_write(user, doc['nome_torneo'])
    require_tournament_write(user, data.name)
    if view(doc)['closed'] or data.name.lower().startswith(('fasefinale', 'finito_', 'completato_')):
        raise HTTPException(422, 'Rinomina non consentita per questo nome o stato.')
    return view(save(store, doc, data.version, {'nome_torneo': data.name}))


@app.post('/api/tournaments/{tournament_id}/withdrawals')
def withdrawal(tournament_id: str, data: Withdrawal, user=Depends(writer), store: Store = Depends(store_dep)):
    doc = load(store, tournament_id)
    require_tournament_write(user, doc['nome_torneo'])
    if view(doc)['closed']:
        raise HTTPException(409, 'Torneo già concluso.')
    participants = {r[k] for r in doc['calendario'] for k in ('Casa', 'Ospite')}
    if not set(data.teams) <= participants:
        raise HTTPException(422, 'Partecipante non trovato nel torneo.')
    retired = set(doc.get('_piercrew_withdrawals', [])) | set(data.teams)
    rows = [dict(row) for row in doc['calendario']]
    for row in rows:
        home, away = row['Casa'] in retired, row['Ospite'] in retired
        if home or away:
            row.update(GolCasa=3 if away and not home else 0, GolOspite=3 if home and not away else 0, Valida=True)
    return view(save(store, doc, data.version, {'calendario': rows, '_piercrew_withdrawals': sorted(retired)}))


@app.post('/api/tournaments/{tournament_id}/complete')
def complete(tournament_id: str, data: Complete, user=Depends(writer), store: Store = Depends(store_dep)):
    doc = load(store, tournament_id)
    require_tournament_write(user, doc['nome_torneo'])
    if doc.get('_piercrew_source_id') or doc['nome_torneo'].startswith('completato_'):
        raise HTTPException(409, 'Questa è una copia di archivio. Apri il torneo originale.')
    rendered = view(doc)
    if not rendered['complete']:
        raise HTTPException(422, 'Valida tutte le partite prima di concludere il torneo.')
    if doc.get('_piercrew_closed'):
        if doc.get('_piercrew_closed_from') != data.version and rendered['version'] != data.version:
            raise HTTPException(409, 'Ricarica il torneo prima di concluderlo.')
    else:
        doc = save(store, doc, data.version, {'_piercrew_closed': True, '_piercrew_closed_from': data.version})
    # Preserve the legacy completed snapshot. Deterministic ID makes retries harmless.
    archive_id = ObjectId(hashlib.sha256(('complete:' + tournament_id).encode()).hexdigest()[:24])
    completed_name = 'completato_' + doc['nome_torneo']
    if not store.tournaments.find_one({'nome_torneo': completed_name}):
        archive = {**doc, '_id': archive_id, 'nome_torneo': completed_name, '_piercrew_source_id': tournament_id}
        store.tournaments.update_one({'_id': archive_id}, {'$setOnInsert': archive}, upsert=True)
    groups = list(dict.fromkeys(r['group'] for r in rendered['matches']))
    list_field, count_field = ('listaGironiFFVinti', 'NGironiFFVinti') if doc['nome_torneo'].startswith('fasefinaleAGironi_') or len(groups) > 1 else ('listaCampionatiVinti', 'NCampionatiVinti')
    name = doc['nome_torneo']
    for value in ('_completed', '_incomplete', 'completato_', 'finito_'):
        name = name.replace(value, '')
    name = name.strip()
    warnings = []
    for group in groups:
        winner = next(row['Squadra'] for row in rendered['standings'] if row['Girone'] == group)
        player_name = winner.split('-', 1)[1].strip() if '-' in winner else winner
        player = store.players.find_one({'$or': [{'Giocatore': player_name}, {'Squadra': winner}]})
        if not player:
            warnings.append(f'Palmarès non assegnato a {winner}: partecipante non presente in anagrafica.')
            continue
        previous = player.get(list_field, [])
        if not isinstance(previous, list):
            raise HTTPException(409, 'Palmarès legacy non compatibile. Torneo salvato; richiedi la verifica dell’anagrafica.')
        def normalized(value):
            result = str(value)
            for prefix in ('_completed', '_incomplete', 'completato_', 'finito_'):
                result = result.replace(prefix, '')
            return result.strip().casefold()
        if any(normalized(value) == name.casefold() for value in previous):
            continue
        award_id = f'{tournament_id}:{group}'
        store.players.update_one({'_id': player['_id'], '_piercrew_award_ids': {'$ne': award_id}, list_field: {'$ne': name}},
                                 {'$addToSet': {list_field: name, '_piercrew_award_ids': award_id}, '$inc': {count_field: 1}})
    return {**view(doc), 'completion_warnings': warnings}


@app.get('/api/tournaments/{tournament_id}/export.csv')
def export_csv(tournament_id: str, user=Depends(current_user), store: Store = Depends(store_dep)):
    data = view(load(store, tournament_id))
    output = io.StringIO()
    writer_csv = csv.writer(output)
    writer_csv.writerow(['Girone', 'Giornata', 'Casa', 'Ospite', 'GolCasa', 'GolOspite', 'Valida'])
    def safe(value):
        return "'" + value if isinstance(value, str) and value.startswith(('=', '+', '-', '@', '\t', '\r')) else value
    for row in data['matches']:
        writer_csv.writerow([safe(row[k]) for k in ('group', 'day', 'home', 'away', 'home_goals', 'away_goals', 'valid')])
    return Response(output.getvalue().encode('utf-8-sig'), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="calendario-piercrew.csv"'})


@app.get('/api/tournaments/{tournament_id}/export.pdf')
def export_pdf(tournament_id: str, user=Depends(current_user), store: Store = Depends(store_dep)):
    data = view(load(store, tournament_id))
    return Response(render_tournament_pdf(data), media_type='application/pdf', headers={'Content-Disposition': 'attachment; filename="gazzettino-piercrew.pdf"'})


from .club import install as install_club_routes
from .club_logos import lookup as lookup_club_logos
from .swiss import install as install_swiss_routes
from .finals import install as install_finals_routes

install_club_routes(app, current_user, writer, store_dep)
install_swiss_routes(app, current_user, writer, store_dep, require_tournament_write)
install_finals_routes(app, current_user, writer, store_dep, require_tournament_write)


@app.get('/api/club-logos')
def club_logos(q: str, user=Depends(current_user)):
    return lookup_club_logos(q)


@app.patch('/api/{kind}/{tournament_id}/badges')
def save_badges(kind: str, tournament_id: str, data: SaveBadges, user=Depends(writer), store: Store = Depends(store_dep)):
    # Cosmetic metadata lives on the tournament and never changes the player registry.
    if kind == 'tournaments':
        doc, render, collection = load(store, tournament_id), view, store.tournaments
    elif kind == 'finals':
        from .finals import load as load_final, view as view_final
        doc, render, collection = load_final(store, tournament_id), view_final, store.tournaments
    elif kind == 'swiss':
        from .swiss import load as load_swiss, view as view_swiss
        doc, render, collection = load_swiss(store, tournament_id), view_swiss, store.swiss_tournaments
    else:
        raise HTTPException(404, 'Tipo di torneo non trovato.')
    require_tournament_write(user, doc['nome_torneo'])
    shown = render(doc)
    participants = {name for row in shown['matches'] for name in (row['home'], row['away'])}
    if not set(data.badges) <= participants:
        raise HTTPException(422, 'Associa immagini solo ai partecipanti di questo torneo.')
    return render(save(store, doc, data.version, {'_piercrew_badges': {key: badge.model_dump(exclude_none=True) for key, badge in data.badges.items()}}, collection=collection))
