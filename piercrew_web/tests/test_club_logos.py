import unittest
from unittest.mock import patch

from backend.club_logos import lookup, search_club_logos
from backend.badge_sources import search_football_logos, search_football_data, search_sportmonks
from backend.models import TeamBadge
from pydantic import ValidationError


class ClubLogoLookupTests(unittest.TestCase):
    def tearDown(self):
        search_club_logos.cache_clear()

    def test_club_flag_is_available_when_logo_is_missing(self):
        search = {'search': [{'id': 'Q2074', 'label': 'Genoa CFC',
                              'description': 'squadra di calcio italiana'}]}
        details = {'entities': {'Q2074': {'claims': {'P41': [
            {'mainsnak': {'datavalue': {'value': 'Genoa flag.svg'}}}]}}}}
        commons = {'query': {'pages': {'1': {'title': 'File:Genoa flag.svg', 'imageinfo': [{
            'url': 'https://upload.wikimedia.org/wikipedia/commons/a/ab/Genoa_flag.svg',
            'thumburl': 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Genoa_flag.svg/128px-Genoa_flag.svg.png',
            'extmetadata': {}}]}}}}
        with patch('backend.club_logos._json', side_effect=[search, details, commons]):
            result = search_club_logos('Genoa CFC')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['type'], 'bandiera')
        self.assertEqual(result[0]['name'], 'Genoa CFC')

    def test_football_logos_contains_genoa_and_accepts_partial_search(self):
        found = search_football_logos('Genoa CFC')
        self.assertTrue(any(row['name'] == 'Genoa' for row in found))
        self.assertTrue(search_football_logos('Samp'))
        for row in found:
            self.assertEqual(TeamBadge(kind='club', ref=row['ref'], url=row['url']).ref, row['ref'])

    def test_lookup_unites_sources_and_survives_one_failure(self):
        wiki = {'ref': 'File:Genoa flag.svg', 'url': 'https://upload.wikimedia.org/a.svg'}
        archive = {'ref': 'football-logos:logos/italy/Genoa.svg', 'url': 'https://raw.githubusercontent.com/JoseArroyave/football-logos/main/logos/italy/Genoa.svg'}
        with patch('backend.club_logos.search_club_logos', return_value=[wiki]), \
             patch('backend.club_logos.search_football_logos', return_value=[archive]), \
             patch('backend.club_logos.search_football_data', side_effect=TimeoutError), \
             patch('backend.club_logos.search_sportmonks', return_value=[]):
            self.assertEqual([row['ref'] for row in lookup('Genoa CFC')], [wiki['ref'], archive['ref']])

    def test_optional_api_sources_and_url_validation(self):
        with patch.dict('os.environ', {'FOOTBALL_DATA_TOKEN': 'dummy', 'SPORTMONKS_TOKEN': 'dummy'}), \
             patch('backend.badge_sources._football_data_teams', return_value=[{'id': 123, 'name': 'Genoa CFC', 'crest': 'https://crests.football-data.org/123.svg', 'area': None}]), \
             patch('backend.badge_sources._sportmonks_search', return_value=[{'id': 456, 'name': 'Genoa CFC', 'image_path': 'https://cdn.sportmonks.com/images/soccer/teams/456.png'}]):
            rows = search_football_data('Genoa') + search_sportmonks('Genoa')
        self.assertEqual(len(rows), 2)
        for row in rows:
            TeamBadge(kind='club', ref=row['ref'], url=row['url'])
        for ref, url in [('football-logos:logos/italy/Genoa.svg', 'https://evil.example/Genoa.svg'),
                         ('sportmonks:456', 'https://cdn.sportmonks.com/evil/456.png'),
                         ('football-data:123', 'https://crests.football-data.org/123.svg?tracking=1')]:
            with self.assertRaises(ValidationError):
                TeamBadge(kind='club', ref=ref, url=url)


if __name__ == '__main__':
    unittest.main()
