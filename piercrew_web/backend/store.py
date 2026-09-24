"""Lazy connections: importing the API never opens or writes a live database."""
import os
import re
from datetime import datetime
from functools import lru_cache

from bson import ObjectId
from pymongo import MongoClient

from .domain import genera_calendario_from_list
from .security import hash_password


class Store:
    def __init__(self, players_client, tournaments_client, auth_client, *, demo=False):
        self.demo = demo
        self.players = players_client['giocatori_subbuteo']['piercrew_players']
        self.tournaments = tournaments_client['TorneiSubbuteo']['PierCrew']
        self.swiss_tournaments = tournaments_client['TorneiSubbuteo']['PierCrewSvizzero']
        auth = auth_client['auth_subbuteo']
        self.sessions = auth['portal_sessions']
        self.handoffs = auth['auth_handoffs']
        self.attempts = auth['portal_login_attempts']
        self.audit = auth['portal_audit']
        self.system_passwords = auth_client['Password']['auth_password']

    def user(self, name):
        return self.players.find_one({'Giocatore': {'$regex': '^' + re.escape(name.strip()) + '$', '$options': 'i'}})

    def seed(self):
        names = [('Andrea', 'Genoa'), ('Luca', 'Sampdoria'), ('Marco', 'Bologna'), ('Paolo', 'Fiorentina')]
        for i, (name, team) in enumerate(names):
            self.players.insert_one({'Giocatore': name, 'Squadra': team, 'Potenziale': 10-i, 'Ruolo': 'A' if i == 0 else 'W', 'SetPwd': 1, 'Password': hash_password('piercrew-demo')})
        teams = [f'{team}-{name}' for name, team in names]
        calendar = genera_calendario_from_list([teams]).to_dict('records')
        calendar[0].update(GolCasa=2, GolOspite=1, Valida=True)
        calendar[1].update(GolCasa=1, GolOspite=1, Valida=True)
        self.tournaments.insert_one({'_id': ObjectId('000000000000000000000001'), 'nome_torneo': 'Campionato PierCrew · Demo', 'calendario': calendar, 'data_creazione': datetime.utcnow(), '_piercrew_revision': 0})
        completed = genera_calendario_from_list([teams]).to_dict('records')
        for index, match in enumerate(completed):
            match.update(GolCasa=2 if index % 2 == 0 else 1, GolOspite=0 if index % 2 == 0 else 1, Valida=True)
        self.tournaments.insert_one({'_id': ObjectId('000000000000000000000003'), 'nome_torneo': 'completato_Torneo PierCrew · Demo', 'calendario': completed, 'data_creazione': datetime.utcnow(), '_piercrew_revision': 0})
        self.swiss_tournaments.insert_one({'_id': ObjectId('000000000000000000000002'), 'nome_torneo': 'Svizzero PierCrew · Demo', 'calendario': [], 'data_creazione': datetime.utcnow()})


@lru_cache
def get_store():
    if os.getenv('PIERCREW_DEMO', '').lower() == 'true':
        if os.getenv('VERCEL'):
            raise RuntimeError('La modalità demo in memoria è disponibile soltanto in locale.')
        import mongomock
        client = mongomock.MongoClient()
        store = Store(client, client, client, demo=True)
        store.seed()
        return store
    uri = os.getenv('MONGO_URI')
    if not uri:
        raise RuntimeError('Configurare MONGO_URI oppure avviare la demo locale.')
    def connect(value):
        return MongoClient(value, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000, tz_aware=False)
    players = connect(uri)
    auth_uri = os.getenv('MONGO_URI_AUTH') or uri
    tournaments_uri = os.getenv('MONGO_URI_TOURNEMENTS') or uri
    return Store(players, connect(tournaments_uri), connect(auth_uri))
