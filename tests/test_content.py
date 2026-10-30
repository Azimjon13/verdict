"""Every demo case in content/cases is a complete dossier: it passes the creator's own checks at level 3 (Досье), has
4–6 decisions lettered from A with world effects within ±3 (as the editor allows), a known world type, a story of a
playable length, a unique title, and draws as a comic."""
import json
import string

import pytest

from verdict import comic
from verdict.catalog import CATEGORIES, CONTENT, METRICS, SITUATION_TYPES, WORLD_NAMES
from verdict.helpers import word_count
from verdict.repository import situation_level, situation_validate

FILES = sorted((CONTENT / 'cases').glob('*.json'))


def load(path):
    s = json.loads(path.read_text(encoding='utf-8'))
    for k in ('facts', 'unknowns', 'witnesses', 'participants'):
        s.setdefault(k, [])
    s.setdefault('hidden', '')
    return s


def test_titles_are_unique():
    titles = [load(f)['title'] for f in FILES]
    assert len(titles) == len(set(titles))


@pytest.mark.parametrize('path', FILES, ids=[f.stem for f in FILES])
def test_case_is_a_complete_dossier(path):
    s = load(path)
    assert situation_validate(s) == {}
    assert situation_level(s) == 3, 'not a full dossier'
    assert s['category'] in CATEGORIES and s['type'] in SITUATION_TYPES and s['world']['setting'] in WORLD_NAMES
    words = word_count(s['story'])
    assert 60 <= words <= 320, words
    keys = [d['key'] for d in s['decisions']]
    assert 4 <= len(keys) <= 6 and keys == list(string.ascii_uppercase[:len(keys)])
    for d in s['decisions']:
        assert set(d.get('effects', {})) <= set(METRICS) and all(-3 <= v <= 3 for v in d.get('effects', {}).values())
    if s['type'] == 'private':
        assert not s['witnesses']
    cast = comic.cast_of(s)
    assert comic.panels_of(s, cast, True)
