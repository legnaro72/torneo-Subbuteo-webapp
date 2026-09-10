"""Offline checks: no live database, app login, or tournament data required."""

import ast
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

from common.superba_results import compare_and_save, ConcurrentTournamentUpdate


class MemoryCollection:
    full_name = 'tests.superba'

    def __init__(self, document):
        self.document = deepcopy(document)

    def update_one(self, query, update):
        if self.document['_id'] != query['_id']:
            return SimpleNamespace(matched_count=0)
        for condition in query['$and']:
            for key, expected in condition.items():
                if (key in self.document) != expected['$exists']:
                    return SimpleNamespace(matched_count=0)
                if '$eq' in expected and self.document[key] != expected['$eq']:
                    return SimpleNamespace(matched_count=0)
        self.document.update(deepcopy(update['$set']))
        return SimpleNamespace(matched_count=1)


class ResultPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.original = {'_id': 'test', 'calendario': [{'GolCasa': 0}], 'nome_torneo': 'Test'}
        self.collection = MemoryCollection(self.original)

    def test_second_device_cannot_overwrite_first(self):
        compare_and_save(self.collection, self.original, {'calendario': [{'GolCasa': 3}]})
        with self.assertRaises(ConcurrentTournamentUpdate):
            compare_and_save(self.collection, self.original, {'calendario': [{'GolCasa': 1}]})
        self.assertEqual(self.collection.document['calendario'][0]['GolCasa'], 3)

    def test_legacy_writer_without_revision_is_detected(self):
        self.collection.document['calendario'][0]['GolCasa'] = 4
        with self.assertRaises(ConcurrentTournamentUpdate):
            compare_and_save(self.collection, self.original, {'calendario': [{'GolCasa': 1}]})

    def test_success_updates_baseline_for_next_save(self):
        saved = compare_and_save(self.collection, self.original, {'calendario': [{'GolCasa': 3}]})
        second = compare_and_save(self.collection, saved, {'calendario': [{'GolCasa': 5}]})
        self.assertEqual(second['_superba_revision'], 2)
        self.assertEqual(second['data_modifica'].microsecond % 1000, 0)

    def test_failure_does_not_mutate_original(self):
        original = deepcopy(self.original)
        with patch.object(self.collection, 'update_one', side_effect=OSError('offline')):
            with self.assertRaises(OSError):
                compare_and_save(self.collection, self.original, {'calendario': []})
        self.assertEqual(self.original, original)

    def test_metadata_changes_are_not_overwritten(self):
        self.collection.document['nome_torneo'] = 'Other name'
        with self.assertRaises(ConcurrentTournamentUpdate):
            compare_and_save(self.collection, self.original, {'nome_torneo': 'Test', 'calendario': []})


class FakeStreamlit:
    def __init__(self):
        self.session_state = {'tournament_id': 'test'}
        self.callbacks = {}

    def number_input(self, label, *args, key, on_change, **kwargs):
        self.callbacks[key] = on_change
        return self.session_state[key]

    checkbox = number_input


class DraftTests(unittest.TestCase):
    def test_change_view_and_widget_cleanup_preserve_draft(self):
        from common.superba_results import result_number_input, draft_value, has_unsaved_results, mark_saved
        fake = FakeStreamlit()
        with patch.dict(sys.modules, {'streamlit': fake}):
            result_number_input('Goals', key='comp_golcasa_match', value=0)
            fake.session_state['comp_golcasa_match'] = 3
            fake.callbacks['comp_golcasa_match']()
            del fake.session_state['comp_golcasa_match']
            self.assertEqual(result_number_input('Goals', key='prem_golcasa_match', value=0), 3)
            self.assertEqual(draft_value('golcasa_match'), 3)
            self.assertTrue(has_unsaved_results())
            mark_saved('golcasa_match', 3)
            self.assertFalse(has_unsaved_results())

    def test_drafts_do_not_leak_between_tournaments(self):
        from common.superba_results import mark_saved, draft_value
        fake = FakeStreamlit()
        with patch.dict(sys.modules, {'streamlit': fake}):
            mark_saved('ko_gola_0_0', 4)
            fake.session_state['tournament_id'] = 'other'
            self.assertEqual(draft_value('ko_gola_0_0', 0), 0)


class KnockoutSaveTests(unittest.TestCase):
    def load_save(self, permitted=True, save_ok=True):
        import pandas as pd
        import common.superba_results as results
        fake = FakeStreamlit()
        frame = pd.DataFrame([
            {'Round': 'Semifinali', 'SquadraA': 'A', 'SquadraB': 'B', 'GolA': 2, 'GolB': 0, 'Valida': True},
            {'Round': 'Semifinali', 'SquadraA': 'C', 'SquadraB': 'D', 'GolA': 0, 'GolB': 0, 'Valida': False}
        ])
        calendar = frame.rename(columns={'SquadraA': 'Casa', 'SquadraB': 'Ospite', 'GolA': 'GolCasa', 'GolB': 'GolOspite'})
        calendar['Girone'] = 'Eliminazione Diretta'
        calendar['Giornata'] = 1
        fake.session_state.update(rounds_ko=[frame], df_torneo_preliminare=calendar,
                                  tournament_name='fasefinale_Test', user={}, player_map={})
        fake.secrets = {'MONGO_URI_TOURNEMENTS': 'unused'}
        fake.error = fake.warning = fake.toast = fake.balloons = lambda *a, **k: None
        saved_payloads = []
        def save(collection, tournament_id, changes):
            saved_payloads.append(changes)
            return save_ok
        filename = Path(__file__).resolve().parents[1] / 'TorneoSubbuteoFasiFinaliItalianaSuperbaAllDB.py'
        tree = ast.parse(filename.read_text(encoding='utf-8-sig'))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'salva_risultati_ko')
        namespace = dict(st=fake, pd=pd, verify_write_access=lambda: permitted,
                         init_mongo_connection=lambda *a: object(), db_name='test', col_name='test',
                         draft_value=lambda key, default: default, mark_saved=lambda *a: None,
                         save_document=save, log=SimpleNamespace(log_action=lambda **k: None))
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(filename), 'exec'), namespace)
        return fake, namespace['salva_risultati_ko'], saved_payloads

    def test_partial_round_can_be_saved_without_advancing(self):
        fake, save, payloads = self.load_save()
        self.assertTrue(save())
        self.assertEqual(len(fake.session_state['rounds_ko']), 1)
        self.assertEqual(len(payloads[0]['calendario']), 2)

    def test_failed_save_does_not_advance(self):
        fake, save, payloads = self.load_save(save_ok=False)
        frame = fake.session_state['rounds_ko'][0]
        frame.loc[1, ['GolA', 'Valida']] = [1, True]
        self.assertFalse(save(genera_prossimo=True))
        self.assertEqual(len(fake.session_state['rounds_ko']), 1)

    def test_success_saves_current_and_next_round_in_one_write(self):
        fake, save, payloads = self.load_save()
        fake.session_state['rounds_ko'][0].loc[1, ['GolA', 'Valida']] = [1, True]
        self.assertTrue(save(genera_prossimo=True))
        self.assertEqual(len(payloads), 1)
        self.assertEqual(len(payloads[0]['calendario']), 3)
        self.assertEqual(len(fake.session_state['rounds_ko']), 2)

    def test_read_only_cannot_save(self):
        _, save, payloads = self.load_save(permitted=False)
        self.assertFalse(save())
        self.assertEqual(payloads, [])


class SwissPairingTests(unittest.TestCase):
    def test_next_round_uses_its_own_phase(self):
        import pandas as pd
        filename = Path(__file__).resolve().parents[1] / 'TorneoSubbuteoSvizzeroSuperbaAllDBNewVersion.py'
        tree = ast.parse(filename.read_text(encoding='utf-8-sig'))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'genera_accoppiamenti')
        teams = pd.DataFrame({'Squadra': ['A', 'B', 'C', 'D'], 'Potenziale': [4, 3, 2, 1]})
        for upcoming in (3, 5):
            calls = []
            state = SimpleNamespace(df_squadre=teams, df_torneo=pd.DataFrame())
            state.get = lambda key, default=None: upcoming - 1 if key == 'turno_attivo' else default
            fake = SimpleNamespace(session_state=state, warning=lambda *a: None, error=lambda *a: None)
            def standings(df):
                calls.append(True)
                return teams.iloc[::-1].reset_index(drop=True)
            namespace = dict(st=fake, pd=pd, aggiorna_classifica=standings)
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(filename), 'exec'), namespace)
            matches = namespace['genera_accoppiamenti'](teams, set(), turno=upcoming)
            self.assertTrue(calls)
            self.assertEqual(set(matches['Turno']), {upcoming})
            self.assertEqual(len(matches), 2)


if __name__ == '__main__':
    unittest.main()
