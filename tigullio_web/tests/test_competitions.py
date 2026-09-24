"""Migrated competition flows use only mongomock, never a real database."""
import unittest
from datetime import datetime
from uuid import uuid4

import mongomock
from fastapi.testclient import TestClient

from backend.domain import genera_calendario_from_list
from backend.main import app, store_dep
from backend.security import hash_password
from backend.store import Store


class CompetitionTests(unittest.TestCase):
    def setUp(self):
        client = mongomock.MongoClient()
        self.store = Store(client, client, client, demo=True)
        self.players = []
        for i, name in enumerate(('Ada', 'Bruno', 'Carla', 'Dino')):
            ident = self.store.players.insert_one({'Giocatore': name, 'Squadra': f'Team{i+1}', 'Potenziale': 10-i,
                'Ruolo': 'W' if i == 0 else 'R', 'Password': hash_password('test-password') if i == 0 else '',
                'SetPwd': 1 if i == 0 else 0}).inserted_id
            self.players.append(dict(source_id=str(ident), name=name, team=f'Team{i+1}', potential=10-i, guest=False))
        calendar = genera_calendario_from_list([[f"{p['team']}-{p['name']}" for p in self.players]]).to_dict('records')
        for row in calendar:
            row.update(GolCasa=2, GolOspite=0, Valida=True)
        self.source_id = str(self.store.tournaments.insert_one({'nome_torneo':'completato_Test', 'calendario':calendar, 'data_creazione':datetime.utcnow()}).inserted_id)
        app.dependency_overrides[store_dep] = lambda: self.store
        self.client = TestClient(app)
        self.client.headers['X-Tigullio-Request'] = '1'
        response = self.client.post('/api/auth/login', json={'username':'Ada', 'password':'test-password'})
        self.assertEqual(response.status_code, 200, response.text)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    def swiss(self, participants=None):
        response = self.client.post('/api/swiss', json={'name':'Svizzero Test', 'participants':participants or self.players,
            'mode':'fisso', 'max_rounds':2, 'request_id':str(uuid4())})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_swiss_results_advance_and_standings(self):
        data = self.swiss()
        self.assertEqual(len(data['matches']), 2)
        updates = [dict(index=r['index'], home=2, away=1, valid=True) for r in data['matches']]
        saved = self.client.patch(f"/api/swiss/{data['id']}/results", json={'version':data['version'], 'results':updates})
        self.assertEqual(saved.status_code, 200, saved.text)
        advanced = self.client.post(f"/api/swiss/{data['id']}/advance", json={'version':saved.json()['version']})
        self.assertEqual(advanced.status_code, 200, advanced.text)
        self.assertEqual(advanced.json()['active_round'], 2)
        self.assertEqual(len(advanced.json()['matches']), 4)
        self.assertEqual(len({frozenset((r['home'],r['away'])) for r in advanced.json()['matches']}), 4)
        self.assertEqual(self.client.post(f"/api/swiss/{data['id']}/advance", json={'version':data['version']}).status_code, 422)

    def test_swiss_odd_players_have_bye_without_points(self):
        data = self.swiss(self.players[:3])
        self.assertEqual(len(data['matches']), 1)
        self.assertEqual(len(data['byes']), 1)
        self.assertTrue(all(row['Punti']==0 and row['G']==0 for row in data['standings']))

    def test_swiss_premium_badges_persist_without_changing_results(self):
        data = self.swiss()
        team = data['matches'][0]['home']
        response = self.client.patch(f"/api/swiss/{data['id']}/badges", json={
            'version': data['version'], 'badges': {team: {'kind': 'flag', 'ref': 'IT'}}})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['badges'][team]['ref'], 'IT')
        self.assertEqual(response.json()['matches'], data['matches'])

    def test_final_ko_bracket_and_finish(self):
        sources = self.client.get('/api/finals/sources')
        self.assertEqual(sources.status_code, 200)
        self.assertEqual(sources.json()[0]['id'], self.source_id)
        created = self.client.post('/api/finals', json={'source_id':self.source_id, 'mode':'ko', 'qualifiers':4,
            'request_id':str(uuid4())})
        self.assertEqual(created.status_code, 200, created.text)
        ident = created.json()['id']
        data = self.client.get(f'/api/finals/{ident}').json()
        self.assertEqual(len(data['matches']), 2)
        bad = self.client.patch(f'/api/finals/{ident}/results', json={'version':data['version'],
            'results':[dict(index=0,home=1,away=1,valid=True)]})
        self.assertEqual(bad.status_code, 422)
        changes = [dict(index=r['index'],home=2,away=0,valid=True) for r in data['matches']]
        saved = self.client.patch(f'/api/finals/{ident}/results', json={'version':data['version'],'results':changes})
        self.assertEqual(saved.status_code, 200, saved.text)
        final = self.client.post(f'/api/finals/{ident}/advance', json={'version':saved.json()['version']})
        self.assertEqual(final.status_code, 200, final.text)
        self.assertEqual(final.json()['matches'][-1]['round_name'], 'Finale')
        final_data = final.json()
        result = self.client.patch(f'/api/finals/{ident}/results',json={'version':final_data['version'],
            'results':[dict(index=2,home=1,away=0,valid=True)]})
        self.assertEqual(result.status_code, 200, result.text)
        done = self.client.post(f'/api/finals/{ident}/advance', json={'version':result.json()['version']})
        self.assertEqual(done.status_code, 200, done.text)
        self.assertTrue(done.json()['finished'])
        self.assertEqual(self.store.tournaments.find_one({'_id':self.store.tournaments.find_one({'nome_torneo':'completato_Test'})['_id']})['nome_torneo'],'completato_Test')

    def test_final_inherits_premium_badges_from_preliminary(self):
        from bson import ObjectId
        team = f"{self.players[0]['team']}-{self.players[0]['name']}"
        self.store.tournaments.update_one({'_id': ObjectId(self.source_id)}, {'$set': {'_tigullio_badges': {team: {'kind': 'flag', 'ref': 'IT'}}}})
        created = self.client.post('/api/finals', json={'source_id': self.source_id, 'mode': 'ko', 'qualifiers': 4,
                                                        'request_id': str(uuid4())})
        self.assertEqual(created.status_code, 200, created.text)
        final = self.client.get(f"/api/finals/{created.json()['id']}").json()
        self.assertEqual(final['badges'][team]['ref'], 'IT')

    def test_final_single_group_is_italiana_and_preliminary_preserved(self):
        response = self.client.post('/api/finals', json={'source_id':self.source_id, 'mode':'groups', 'qualifiers':4,
            'group_count':1, 'request_id':str(uuid4())})
        self.assertEqual(response.status_code,200,response.text)
        ident=response.json()['id']
        group=self.client.get(f'/api/tournaments/{ident}')
        self.assertEqual(group.status_code,200,group.text)
        self.assertEqual({m['group'] for m in group.json()['matches']},{'Girone 1'})
        self.assertIsNotNone(self.store.tournaments.find_one({'nome_torneo':'completato_Test'}))

    def test_reader_cannot_create_or_change_competitions(self):
        self.client.post('/api/auth/logout')
        self.client.post('/api/auth/login',json={'username':'Bruno','password':''})
        response=self.client.post('/api/finals',json={'source_id':self.source_id,'mode':'ko','qualifiers':4,'request_id':str(uuid4())})
        self.assertEqual(response.status_code,403)
        response=self.client.post('/api/swiss',json={'name':'Test','participants':self.players,'mode':'fisso','request_id':str(uuid4())})
        self.assertEqual(response.status_code,403)


if __name__ == '__main__':
    unittest.main()
