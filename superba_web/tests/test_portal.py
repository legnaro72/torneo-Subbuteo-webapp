"""No live database, network calls or legacy application imports."""
import ast
import os
import sys
import unittest
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import mongomock
import pandas as pd
from bson import ObjectId
from fastapi.testclient import TestClient

from backend.domain import aggiorna_classifica, genera_calendario_from_list
from backend.main import app, store_dep
from backend.security import hash_password, hash_token
from backend.store import Store


class DomainParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[2] / 'TorneoSubbuteoItalianaSuperbaAllDB.py'
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('genera_calendario_from_list', 'aggiorna_classifica')]
        cls.namespace = {'pd': pd, 'st': SimpleNamespace(session_state={'giocatori_ritirati': ['B']})}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), cls.namespace)

    def test_calendars_match_original_odd_even_multiple_groups_and_return(self):
        for groups in ([['A','B','C']], [['A','B','C','D']], [['A','B'],['C','D','E']]):
            for mode in ('Solo andata', 'Andata e ritorno'):
                with self.subTest(groups=groups,mode=mode):
                    pd.testing.assert_frame_equal(genera_calendario_from_list(groups,mode), self.namespace['genera_calendario_from_list'](groups,mode))

    def test_standings_preserve_ties_validation_points_and_withdrawals(self):
        frame = genera_calendario_from_list([['A','B','C','D'],['E','F','G']])
        for i in range(len(frame)):
            frame.loc[i,['GolCasa','GolOspite','Valida']] = [i%4,(i+2)%3,i%3!=0]
        pd.testing.assert_frame_equal(aggiorna_classifica(frame,['B']),self.namespace['aggiorna_classifica'](frame))
        frame['Valida']=False
        self.assertTrue(aggiorna_classifica(frame).empty)


class PortalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = hash_password('test-password')

    def setUp(self):
        client = mongomock.MongoClient()
        self.store = Store(client,client,client,demo=True)
        self.writer_id=self.store.players.insert_one({'Giocatore':'Writer','Squadra':'A','Ruolo':'W','Password':self.password,'SetPwd':1}).inserted_id
        self.reader_id=self.store.players.insert_one({'Giocatore':'Reader','Squadra':'B','Ruolo':'R','Password':'','SetPwd':0}).inserted_id
        self.store.players.insert_one({'Giocatore':'Admin','Squadra':'C','Ruolo':'A','Password':self.password,'SetPwd':1})
        self.tid=str(self.store.tournaments.insert_one({'nome_torneo':'Torneo Test','calendario':genera_calendario_from_list([['A-Writer','B-Reader','C-Admin']]).to_dict('records'),'data_creazione':datetime.utcnow()}).inserted_id)
        app.dependency_overrides[store_dep]=lambda:self.store
        self.client=TestClient(app)
        self.client.headers['X-Superba-Request']='1'

    def tearDown(self):
        self.client.close();app.dependency_overrides.clear()

    def login(self,name='Writer',password='test-password'):
        response=self.client.post('/api/auth/login',json={'username':name,'password':password})
        self.assertEqual(response.status_code,200,response.text)
        return response

    def get(self):
        response=self.client.get('/api/tournaments/'+self.tid)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def save(self,version,**kwargs):
        return self.client.patch('/api/tournaments/'+self.tid+'/results',json={'version':version,'results':[{'index':0,'home':2,'away':1,'valid':True,**kwargs}]})

    def test_anonymous_cannot_read_or_write(self):
        self.assertEqual(self.client.get('/api/tournaments').status_code,401)
        self.assertEqual(self.save('0'*64).status_code,401)

    def test_first_access_user_list_requires_system_password_and_only_shows_activatable_accounts(self):
        self.store.system_passwords.insert_one({'Password': 'club-secret'})
        self.store.players.insert_one({'Giocatore': 'Nuovo Writer', 'Ruolo': 'W', 'SetPwd': 0})
        self.assertEqual(self.client.post('/api/auth/activation-users', json={'system_password': 'wrong'}).status_code, 403)
        response = self.client.post('/api/auth/activation-users', json={'system_password': 'club-secret'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), ['Nuovo Writer'])

    def test_login_suggestions_include_only_club_names_without_creating_sessions(self):
        self.store.players.insert_one({'Giocatore': 'Writer Extra', 'Ruolo': 'W'})
        self.store.players.insert_one({'Giocatore': 'Writer Revoked', 'Ruolo': 'X'})
        with patch.object(self.store.sessions, 'insert_one', side_effect=AssertionError('session write')):
            response = self.client.get('/api/auth/user-suggestions?q=wri')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), ['Writer', 'Writer Extra'])
        self.assertEqual(self.client.get('/api/auth/user-suggestions?q=w').status_code, 422)

    def test_health_reads_both_collections_without_auth_or_writes(self):
        with patch.object(self.store.players, 'find_one', wraps=self.store.players.find_one) as players_read, \
             patch.object(self.store.tournaments, 'find_one', wraps=self.store.tournaments.find_one) as tournaments_read:
            self.assertEqual(self.client.get('/api/health').json(), {'database':'ok'})
            players_read.assert_called_once_with({}, {'_id':1})
            tournaments_read.assert_called_once_with({}, {'_id':1})

    def test_cookie_and_payload_do_not_expose_credentials(self):
        response=self.login()
        self.assertIn('HttpOnly',response.headers['set-cookie'])
        self.assertIn('SameSite=lax',response.headers['set-cookie'])
        self.assertNotIn('test-password',response.text)
        self.assertNotIn('token',response.text)
        players=self.client.get('/api/players').json()
        self.assertEqual(set(players[0]),{'id','name','team','potential'})

    def test_reader_cannot_write_even_without_password(self):
        self.login('Reader','')
        self.assertEqual(self.save(self.get()['version']).status_code,403)

    def test_premium_badges_are_optional_versioned_and_role_guarded(self):
        self.login()
        initial = self.get()
        self.assertEqual(initial['badges'], {})
        badge = {'kind': 'flag', 'ref': 'IT'}
        response = self.client.patch('/api/tournaments/'+self.tid+'/badges', json={
            'version': initial['version'], 'badges': {'A-Writer': badge}})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['badges']['A-Writer'], badge)
        self.assertNotEqual(response.json()['version'], initial['version'])
        self.assertEqual(self.client.patch('/api/tournaments/'+self.tid+'/badges', json={
            'version': initial['version'], 'badges': {}}).status_code, 409)
        self.assertEqual(self.client.patch('/api/tournaments/'+self.tid+'/badges', json={
            'version': response.json()['version'], 'badges': {'Other': badge}}).status_code, 422)

    def test_premium_badge_rejects_untrusted_image_url(self):
        self.login()
        response = self.client.patch('/api/tournaments/'+self.tid+'/badges', json={
            'version': self.get()['version'], 'badges': {'A-Writer': {
                'kind': 'club', 'ref': 'File:Test.svg', 'url': 'https://example.com/tracker.svg'}}})
        self.assertEqual(response.status_code, 422)

    def test_guest_can_read_but_cannot_write(self):
        self.assertEqual(self.client.post('/api/auth/guest').status_code,200)
        self.assertEqual(self.save(self.get()['version']).status_code,403)

    def test_role_revocation_applies_to_existing_session(self):
        self.login();data=self.get()
        self.store.players.update_one({'_id':self.writer_id},{'$set':{'Ruolo':'R'}})
        self.assertEqual(self.save(data['version']).status_code,403)

    def test_reader_promoted_to_writer_must_authenticate(self):
        self.login('Reader','')
        self.store.players.update_one({'_id':self.reader_id},{'$set':{'Ruolo':'W'}})
        self.assertEqual(self.client.get('/api/auth/me').status_code,401)

    def test_logout_expiry_and_password_reset(self):
        self.login();self.client.post('/api/auth/logout')
        self.assertEqual(self.client.get('/api/auth/me').status_code,401)
        self.login();self.store.sessions.update_many({}, {'$set':{'expires_at':datetime.utcnow()-timedelta(seconds=1)}})
        self.assertEqual(self.client.get('/api/auth/me').status_code,401)
        self.login();self.store.players.update_one({'_id':self.writer_id},{'$set':{'Password':'changed'}})
        self.assertEqual(self.client.get('/api/auth/me').status_code,401)

    def test_csrf_and_cross_origin_rejected(self):
        self.client.headers.pop('X-Superba-Request')
        self.assertEqual(self.client.post('/api/auth/guest').status_code,403)
        self.client.headers['X-Superba-Request']='1'
        self.assertEqual(self.client.post('/api/auth/guest',headers={'Origin':'https://attacker.invalid'}).status_code,403)

    def test_save_and_concurrent_legacy_write_conflict(self):
        self.login();initial=self.get()
        saved=self.save(initial['version']);self.assertEqual(saved.status_code,200,saved.text)
        self.assertNotEqual(initial['version'],saved.json()['version'])
        self.assertEqual(self.save(initial['version'],home=4).status_code,409)
        new=self.get()
        from bson import ObjectId
        self.store.tournaments.update_one({'_id':ObjectId(self.tid)},{'$set':{'calendario.0.GolCasa':5}})
        self.assertEqual(self.save(new['version']).status_code,409)

    def test_atomic_compare_catches_write_between_load_and_save(self):
        self.login();initial=self.get();original=self.store.tournaments.update_one
        def race(query,update,*args,**kwargs):
            if '$and' in query:
                original({'_id':query['_id']},{'$set':{'calendario.0.GolCasa':8}})
            return original(query,update,*args,**kwargs)
        with patch.object(self.store.tournaments,'update_one',side_effect=race):
            self.assertEqual(self.save(initial['version']).status_code,409)

    def test_strict_scores_and_duplicate_indices(self):
        self.login();version=self.get()['version']
        for value in (-1,21,1.5,True,'2'):
            self.assertEqual(self.save(version,home=value).status_code,422)
        self.assertEqual(self.save(version,valid='false').status_code,422)
        self.assertEqual(self.save(version,index=999).status_code,422)

    def test_live_writes_require_explicit_enable(self):
        self.login();version=self.get()['version'];self.store.demo=False
        with patch.dict(os.environ,{'SUPERBA_WRITE_ENABLED':'false'}):
            self.assertEqual(self.save(version).status_code,403)

    def test_create_idempotency_and_validation(self):
        self.login()
        data={'name':'Nuovo','groups':[['A-Writer','B-Reader','C-Admin']],'return_matches':True,'request_id':'11111111-1111-1111-1111-111111111111'}
        one=self.client.post('/api/tournaments',json=data);two=self.client.post('/api/tournaments',json=data)
        self.assertEqual(one.status_code,200,one.text);self.assertEqual(one.json()['id'],two.json()['id'])
        self.assertEqual(len(one.json()['matches']),6)
        data['name']='Diverso';self.assertEqual(self.client.post('/api/tournaments',json=data).status_code,409)
        data['groups']=[['A','A','C']];self.assertEqual(self.client.post('/api/tournaments',json=data).status_code,422)
        data['groups']=[['A-Writer','B-Reader','Giocatore inventato']]
        self.assertEqual(self.client.post('/api/tournaments',json=data).status_code,422)

    def test_create_with_registered_players_and_explicit_guest(self):
        self.login()
        payload={'name':'Con ospite','groups':[['Azzurri - Writer','Ospiti - Nino','B - Reader']],
                 'participants':[{'source_id':str(self.writer_id),'name':'Writer','team':'Azzurri','potential':9,'guest':False},
                                 {'source_id':None,'name':'Nino','team':'Ospiti','potential':4,'guest':True},
                                 {'source_id':str(self.reader_id),'name':'Reader','team':'B','potential':5,'guest':False}],
                 'badges':{'Ospiti - Nino':{'kind':'flag','ref':'IT'}},
                 'return_matches':False,'request_id':'22222222-2222-2222-2222-222222222222'}
        response=self.client.post('/api/tournaments',json=payload)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual({r['home'] for r in response.json()['matches']}|{r['away'] for r in response.json()['matches']},set(payload['groups'][0]))
        self.assertEqual(response.json()['badges']['Ospiti - Nino']['ref'],'IT')
        self.assertEqual(self.store.players.count_documents({}),3)
        payload['participants'][1]['guest']=False
        self.assertEqual(self.client.post('/api/tournaments',json=payload).status_code,422)

    def test_only_admin_can_modify_campionato(self):
        self.login()
        self.store.tournaments.update_one({'_id':ObjectId(self.tid)},{'$set':{'nome_torneo':'Campionato Test'}})
        data=self.get()
        self.assertEqual(self.save(data['version']).status_code,403)
        self.assertEqual(self.client.post('/api/tournaments/'+self.tid+'/withdrawals',json={'version':data['version'],'teams':['A-Writer']}).status_code,403)
        self.assertEqual(self.client.patch('/api/tournaments/'+self.tid+'/name',json={'version':data['version'],'name':'Altro'}).status_code,403)
        self.login('Admin')
        self.assertEqual(self.save(data['version']).status_code,200)

    def test_completion_retry_does_not_duplicate_archive_or_awards(self):
        self.login();data=self.get()
        result=self.client.patch('/api/tournaments/'+self.tid+'/results',json={'version':data['version'],'results':[{'index':r['index'],'home':2,'away':1,'valid':True} for r in data['matches']]})
        self.assertEqual(result.status_code,200,result.text)
        request={'version':result.json()['version']}
        first=self.client.post('/api/tournaments/'+self.tid+'/complete',json=request)
        second=self.client.post('/api/tournaments/'+self.tid+'/complete',json=request)
        self.assertEqual(first.status_code,200,first.text);self.assertEqual(second.status_code,200,second.text)
        self.assertEqual(self.store.tournaments.count_documents({}),2)
        awarded=list(self.store.players.find({'NCampionatiVinti':{'$gt':0}}))
        self.assertEqual(len(awarded),1);self.assertEqual(awarded[0]['NCampionatiVinti'],1)
        self.assertEqual(self.save(first.json()['version']).status_code,409)

    def test_withdrawal_keeps_legacy_forfeit_rule(self):
        self.login();data=self.get()
        response=self.client.post('/api/tournaments/'+self.tid+'/withdrawals',json={'version':data['version'],'teams':['A-Writer']})
        self.assertEqual(response.status_code,200,response.text)
        for row in response.json()['matches']:
            if row['home']=='A-Writer':self.assertEqual((row['home_goals'],row['away_goals'],row['valid']),(0,3,True))
            elif row['away']=='A-Writer':self.assertEqual((row['home_goals'],row['away_goals'],row['valid']),(3,0,True))

    def test_handoff_allowlist_and_legacy_shape(self):
        self.login();self.store.demo=False
        self.assertEqual(self.client.post('/api/auth/open/evil').status_code,404)
        self.assertEqual(self.client.post('/api/auth/open/club').status_code,403)
        response=self.client.post('/api/auth/open/svizzero')
        self.assertEqual(response.status_code,200,response.text)
        from urllib.parse import parse_qs,urlparse
        token=parse_qs(urlparse(response.json()['url']).query)['auth_handoff'][0]
        doc=self.store.handoffs.find_one({'token_hash':hash_token(token)})
        self.assertEqual(doc['collection'],'superba_players');self.assertFalse(doc['consumed'])
        self.assertEqual(doc['user_id'],str(self.writer_id))

    def test_exports_are_authenticated_and_do_not_leak_player_fields(self):
        self.login()
        csv=self.client.get('/api/tournaments/'+self.tid+'/export.csv')
        pdf=self.client.get('/api/tournaments/'+self.tid+'/export.pdf')
        self.assertEqual(csv.status_code,200,csv.text);self.assertNotIn('Password',csv.text)
        self.assertEqual(pdf.status_code,200,pdf.text[:100] if pdf.status_code!=200 else '')
        self.assertTrue(pdf.content.startswith(b'%PDF'))

    def test_rate_limit_and_legacy_password_upgrade(self):
        self.store.players.update_one({'_id':self.writer_id},{'$set':{'Password':'legacy-pass'}})
        self.login(password='legacy-pass')
        self.assertTrue(self.store.players.find_one({'_id':self.writer_id})['Password'].startswith('$2'))
        for _ in range(9):self.client.post('/api/auth/login',json={'username':'Writer','password':'bad'})
        self.assertEqual(self.client.post('/api/auth/login',json={'username':'Writer','password':'bad'}).status_code,429)

    def test_club_roster_permissions_and_hidden_fields(self):
        self.login('Reader','')
        roster=self.client.get('/api/club/players')
        self.assertEqual(roster.status_code,200,roster.text)
        self.assertNotIn('Password',roster.text)
        self.assertNotIn(self.password,roster.text)
        self.assertEqual(self.client.post('/api/club/players',json={'name':'New','team':'X','potential':5}).status_code,403)
        self.login()
        self.assertEqual(self.client.post('/api/club/players',json={'name':'Promoted','team':'X','potential':5,'role':'A'}).status_code,403)
        created=self.client.post('/api/club/players',json={'name':'New','team':'X','potential':5})
        self.assertEqual(created.status_code,200,created.text)
        self.assertEqual(created.json()['role'],'R')
        self.assertEqual(created.json()['password_set'],False)
        self.assertEqual(self.store.players.count_documents({'Giocatore':'New'}),1)
        edited=self.client.patch('/api/club/players/'+created.json()['id'],json={'name':'New Name','team':'Y','potential':6,'version':created.json()['version']})
        self.assertEqual(edited.status_code,200,edited.text)
        self.assertEqual(self.store.players.find_one({'Giocatore':'New Name'})['SetPwd'],0)
        self.assertEqual(self.client.request('DELETE','/api/club/players/'+created.json()['id'],json={'version':edited.json()['version']}).status_code,403)

    def test_club_admin_bulk_preserves_trophies_password_and_conflicts(self):
        self.store.players.update_one({'_id':self.writer_id},{'$set':{'NCampionatiVinti':2,'listaCampionatiVinti':['Campionato A']}})
        self.login('Admin')
        roster=self.client.get('/api/club/players').json()
        writer=next(p for p in roster if p['name']=='Writer')
        payload={'players':[{'id':writer['id'],'version':writer['version'],'name':'Writer 2','team':'New team','potential':7,'role':'W'}]}
        result=self.client.post('/api/club/players/bulk',json=payload)
        self.assertEqual(result.status_code,200,result.text)
        saved=self.store.players.find_one({'_id':self.writer_id})
        self.assertEqual(saved['NCampionatiVinti'],2)
        self.assertEqual(saved['listaCampionatiVinti'],['Campionato A'])
        self.assertEqual(saved['Password'],self.password)
        self.assertEqual(self.client.post('/api/club/players/bulk',json=payload).status_code,409)
        csv_data=self.client.get('/api/club/export.csv')
        self.assertEqual(csv_data.status_code,200)
        self.assertIn('Writer 2',csv_data.text)
        self.assertNotIn(self.password,csv_data.text)
        self.assertNotIn('Password',csv_data.text)
        pdf=self.client.get('/api/club/export.pdf')
        self.assertEqual(pdf.status_code,200,pdf.text[:100] if pdf.status_code!=200 else '')
        self.assertTrue(pdf.content.startswith(b'%PDF'))

    def test_club_admin_password_reset_revokes_sessions(self):
        self.login()
        self.assertEqual(self.store.sessions.count_documents({'user_id':str(self.writer_id),'revoked':False}),1)
        self.login('Admin')
        response=self.client.post('/api/club/players/'+str(self.writer_id)+'/reset-password')
        self.assertEqual(response.status_code,200,response.text)
        player=self.store.players.find_one({'_id':self.writer_id})
        self.assertIsNone(player['Password'])
        self.assertEqual(player['SetPwd'],0)
        self.assertEqual(self.store.sessions.count_documents({'user_id':str(self.writer_id),'revoked':False}),0)

    def test_club_tournament_delete_scope_and_championship_protection(self):
        from bson import ObjectId
        self.store.tournaments.update_one({'_id':ObjectId(self.tid)},{'$set':{'nome_torneo':'Campionato Test'}})
        friendly_id=self.store.tournaments.insert_one({'nome_torneo':'Amichevole','calendario':[]}).inserted_id
        swiss_id=self.store.swiss_tournaments.insert_one({'nome_torneo':'Torneo Svizzero','calendario':[]}).inserted_id
        self.login('Admin')
        archive=self.client.get('/api/club/tournaments').json()
        self.assertEqual(len(archive),3)
        targets=[{'scope':'italiana','id':str(friendly_id),'name':'Amichevole'}]
        payload={'targets':targets,'all_except_championships':True,'clear_scope':'italiana','password':'bad'}
        self.assertEqual(self.client.post('/api/club/tournaments/delete',json=payload).status_code,403)
        payload['password']='test-password'
        result=self.client.post('/api/club/tournaments/delete',json=payload)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.store.tournaments.count_documents({}),1)
        self.assertEqual(self.store.swiss_tournaments.count_documents({}),1)
        payload={'targets':[{'scope':'italiana','id':self.tid,'name':'Campionato Test'}], 'password':'test-password'}
        result=self.client.post('/api/club/tournaments/delete',json=payload)
        self.assertEqual(result.status_code,200,result.text)
        self.assertIsNone(self.store.tournaments.find_one({'_id':ObjectId(self.tid)}))
        self.assertIsNotNone(self.store.swiss_tournaments.find_one({'_id':swiss_id}))


if __name__=='__main__':unittest.main()
