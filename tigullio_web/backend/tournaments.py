import hashlib
from copy import deepcopy
from datetime import datetime

import pandas as pd
from bson import ObjectId, json_util
from fastapi import HTTPException

from .domain import aggiorna_classifica


def version(document):
    # Full document fingerprint also detects writers that do not increment revisions.
    return hashlib.sha256(json_util.dumps(document, sort_keys=True).encode()).hexdigest()


def is_italiana(document):
    name = document.get('nome_torneo', '')
    bare = name.removeprefix('completato_').removeprefix('finito_')
    if bare.startswith('fasefinale') and not bare.startswith('fasefinaleAGironi'):
        return False
    rows = document.get('calendario')
    return isinstance(rows, list) and bool(rows) and all(
        isinstance(r, dict) and {'Girone', 'Giornata', 'Casa', 'Ospite', 'GolCasa', 'GolOspite', 'Valida'} <= r.keys()
        and r['Girone'] != 'Eliminazione Diretta' for r in rows)


def load(store, tournament_id):
    if not ObjectId.is_valid(tournament_id):
        raise HTTPException(404, 'Torneo non trovato.')
    doc = store.tournaments.find_one({'_id': ObjectId(tournament_id)})
    if not doc or not is_italiana(doc):
        raise HTTPException(404, 'Torneo all’italiana non trovato.')
    return doc


def normalized_rows(doc):
    rows = []
    for i, original in enumerate(doc['calendario']):
        try:
            valid = original['Valida']
            if not isinstance(valid, bool):
                if valid not in (0, 1):
                    raise ValueError('Validazione non booleana')
                valid = bool(valid)
            rows.append({'index': i, 'group': str(original['Girone']), 'day': int(original['Giornata']),
                         'home': str(original['Casa']), 'away': str(original['Ospite']),
                         'home_goals': int(original['GolCasa'] or 0), 'away_goals': int(original['GolOspite'] or 0), 'valid': valid})
        except (ValueError, TypeError, OverflowError):
            raise HTTPException(422, 'Il calendario contiene dati non compatibili. Aprilo nella versione precedente.')
    return rows


def view(doc):
    rows = normalized_rows(doc)
    frame = pd.DataFrame([{'Girone': r['group'], 'Giornata': r['day'], 'Casa': r['home'], 'Ospite': r['away'],
                           'GolCasa': r['home_goals'], 'GolOspite': r['away_goals'], 'Valida': r['valid']} for r in rows])
    standings = aggiorna_classifica(frame, doc.get('_tigullio_withdrawals', []))
    return {'id': str(doc['_id']), 'name': doc['nome_torneo'], 'version': version(doc), 'matches': rows,
            'badges': doc.get('_tigullio_badges', {}),
            'standings': standings.to_dict('records'), 'complete': all(r['valid'] for r in rows),
            'withdrawals': doc.get('_tigullio_withdrawals', []),
            'closed': bool(doc.get('_tigullio_closed', False)) or doc['nome_torneo'].startswith('completato_'),
            'archived': bool(doc.get('_tigullio_source_id')) or doc['nome_torneo'].startswith('completato_')}


def save(store, original, expected_version, changes, *, collection=None):
    if version(original) != expected_version:
        raise HTTPException(409, 'Il torneo è cambiato su un altro dispositivo. Le tue modifiche sono ancora disponibili: ricarica il torneo prima di riprovare.')
    # Snapshot compare + atomic write. Preserve unknown legacy fields.
    conditions = [{field: {'$eq': value, '$exists': True}} for field, value in original.items() if field != '_id']
    if '_tigullio_revision' not in original:
        conditions.append({'_tigullio_revision': {'$exists': False}})
    updated = deepcopy(changes)
    now = datetime.utcnow()
    updated['data_modifica'] = now.replace(microsecond=now.microsecond // 1000 * 1000)
    updated['_tigullio_revision'] = int(original.get('_tigullio_revision', 0)) + 1
    target = collection if collection is not None else store.tournaments
    result = target.update_one({'_id': original['_id'], '$and': conditions}, {'$set': updated})
    if result.matched_count != 1:
        raise HTTPException(409, 'Salvataggio concorrente rilevato. Ricarica il torneo; le bozze sono conservate.')
    return {**original, **updated}
