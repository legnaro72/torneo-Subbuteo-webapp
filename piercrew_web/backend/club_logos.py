"""Key-free football club logo lookup via Wikidata and Wikimedia Commons."""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from fastapi import HTTPException

from .badge_sources import search_football_data, search_football_logos, search_sportmonks


def _json(host, params):
    url = f'https://{host}/w/api.php?' + urlencode(params)
    request = Request(url, headers={'User-Agent': 'PierCrewPortal/1.0 (https://piercrewweb.vercel.app; club-logo-picker)'})
    with urlopen(request, timeout=7) as response:
        return json.load(response)


@lru_cache(maxsize=128)
def search_club_logos(query):
    found = _json('www.wikidata.org', {'action': 'wbsearchentities', 'search': query, 'language': 'it',
                                        'uselang': 'it', 'type': 'item', 'limit': 25, 'format': 'json'})
    candidates = [item for item in found.get('search', [])
                  if re.search(r'calci|football club|soccer club|club de fútbol|clube de futebol|futebol club', item.get('description', ''), re.I)
                  and not re.search(r'canale|televis|programma|stagione|season|femminile? under|categoria|giocatore|calciatore', item.get('description', ''), re.I)][:10]
    if not candidates:
        found = _json('www.wikidata.org', {'action': 'wbsearchentities', 'search': query, 'language': 'en',
                                            'uselang': 'en', 'type': 'item', 'limit': 25, 'format': 'json'})
        candidates = [item for item in found.get('search', [])
                      if re.search(r'football club|soccer club|association football', item.get('description', ''), re.I)][:10]
    if not candidates:
        return []
    details = _json('www.wikidata.org', {'action': 'wbgetentities', 'ids': '|'.join(item['id'] for item in candidates),
                                         'props': 'claims', 'format': 'json'})
    files = []
    for item in candidates:
        claims = details.get('entities', {}).get(item['id'], {}).get('claims', {})
        for property_id, image_type in [('P154', 'logo'), ('P41', 'bandiera'), ('P94', 'stemma')]:
            for claim in claims.get(property_id, []):
                filename = claim.get('mainsnak', {}).get('datavalue', {}).get('value')
                if isinstance(filename, str) and filename:
                    files.append({'name': item['label'], 'description': item.get('description', ''),
                                  'ref': 'File:' + filename.removeprefix('File:'), 'type': image_type})
    if not files:
        return []
    images = _json('commons.wikimedia.org', {'action': 'query', 'titles': '|'.join(file['ref'] for file in files),
                                              'prop': 'imageinfo', 'iiprop': 'url|mime|extmetadata',
                                              'iiurlwidth': 128, 'format': 'json'})
    result = []
    for page in images.get('query', {}).get('pages', {}).values():
        info = (page.get('imageinfo') or [{}])[0]
        original = urlunsplit((*urlsplit(info.get('url', ''))[:3], '', ''))
        url = urlunsplit((*urlsplit(info.get('thumburl') or info.get('url', ''))[:3], '', ''))
        if urlsplit(url).hostname not in ('upload.wikimedia.org', 'thumb.wikimedia.org') or not re.search(r'\.(svg|png|jpe?g|webp)$', original, re.I):
            continue
        metadata = info.get('extmetadata') or {}
        def clean(value):
            return re.sub(r'<[^>]*>', '', value or '').replace('&amp;', '&').strip()
        ref = page['title']
        source = next((file for file in files if file['ref'].replace('_', ' ') == ref.replace('_', ' ')), {})
        result.append({'ref': ref, 'name': source.get('name', ref[5:]), 'description': source.get('description', ''),
                       'type': source.get('type', 'logo'), 'source': 'Wikidata / Commons',
                       'url': url, 'credit': clean((metadata.get('Artist') or metadata.get('Credit') or {}).get('value', 'Wikimedia Commons'))[:240],
                       'license': clean((metadata.get('LicenseShortName') or {}).get('value', 'Verifica su Commons'))[:100]})
    result.sort(key=lambda row: next((i for i, file in enumerate(files) if file['ref'].replace('_', ' ') == row['ref'].replace('_', ' ')), len(files)))
    return result


def lookup(query):
    query = query.strip()
    if len(query) < 3 or len(query) > 80:
        raise HTTPException(422, 'Inserisci da 3 a 80 caratteri per cercare un club.')
    providers = (search_club_logos, search_football_logos, search_football_data, search_sportmonks)
    found, successful = [], 0
    with ThreadPoolExecutor(max_workers=len(providers)) as pool:
        futures = [pool.submit(provider, query) for provider in providers]
        for future in futures:
            try:
                found.extend(future.result())
                successful += 1
            except Exception:
                # One external service must not hide results from the others.
                pass
    if not successful:
        raise HTTPException(503, 'Ricerca stemmi temporaneamente non disponibile.')
    unique = {}
    for item in found:
        unique.setdefault(item['url'], item)
    return list(unique.values())
