"""The comic engine gives exactly what the PHP version gave for every demo case
(fixtures/comic_expected.json was dumped from the PHP site): cast, name search, portraits, frames, speakers, scenes."""
import json
from pathlib import Path

import pytest

from verdict import comic
from verdict.catalog import CONTENT

EXPECTED = json.loads((Path(__file__).parent / 'fixtures' / 'comic_expected.json').read_text(encoding='utf-8'))


def load(name):
    s = json.loads((CONTENT / 'cases' / name).read_text(encoding='utf-8'))
    for k in ('facts', 'unknowns', 'witnesses', 'participants'):
        s.setdefault(k, [])
    return s


@pytest.mark.parametrize('name', sorted(EXPECTED['cases']))
def test_case_matches_php(name):
    want = EXPECTED['cases'][name]
    s = load(name)
    cast = comic.cast_of(s)
    assert len(cast) == len(want['cast'])
    for c, w in zip(cast, want['cast']):
        assert (c['short'], c['hue'], c['roleHead'], c['witness'], c['claim']) == (w['short'], w['hue'], w['roleHead'], w['witness'], w['claim'])
        assert (c['regex'].pattern if c['regex'] else None) == (w['regex'][1:-2] if w['regex'] else None)
        assert comic.avatar_body(c['avatar']) == w['avatar']
    assert json.loads(json.dumps(comic.panels_of(s, cast, True), ensure_ascii=False)) == want['panels']
    assert comic.highlight(s['story'], cast) == want['highlight']


@pytest.mark.parametrize('world', sorted(EXPECTED['scenes']))
def test_scene_matches_php(world):
    assert comic.scene(world, 200) == EXPECTED['scenes'][world]


def test_speech_detection():
    cast = comic.cast_of({'participants': [{'name': 'Бранн', 'role': 'Кузнец'}, {'name': 'Ирма', 'role': 'Вдова мельника'}],
                          'witnesses': []})
    segments, speakers = comic.segments_of('Бранн встал. «Я не брал зерно у вдовы», — сказал он. Вдова молчала.', cast)
    assert [x['type'] for x in segments] == ['caption', 'speech', 'caption']
    assert segments[1]['who'] == 0 and speakers == [0]
    segments, _ = comic.segments_of('Ирма ответила: «Он лжёт мне в лицо».', cast)
    assert segments[1]['who'] == 1
    segments, _ = comic.segments_of('На двери было написано «Щит».', cast)
    assert [x['type'] for x in segments] == ['caption']
