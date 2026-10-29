"""Seasons: a finished month closes once with its final board, trophies for the top places (one per player and
season, XP for the career but not for the next season), notifications, the «Сезоны» pages and the API."""
import json
import re
import secrets
from datetime import date, datetime, timedelta

import pytest

from verdict import seasons, social


@pytest.fixture
def people(new_browser, db):
    def make(name='Судья'):
        b = new_browser()
        login = b.register(name + ' ' + secrets.token_hex(2))
        uid = int(db.value('SELECT id FROM users WHERE login = %s', (login,)))
        return b, login, uid, db.value('SELECT voter FROM players WHERE user_id = %s', (uid,))
    return make


def months_ago(n):
    d = date.today().replace(day=1)
    for _ in range(n):
        d = (d - timedelta(days=1)).replace(day=1)
    return d


def judge_in(db, voter, month, count, start=0):
    """count verdicts first judged in that month (on different cases in play)."""
    ids = [r['id'] for r in db.rows("SELECT id FROM situations WHERE status = 'approved' ORDER BY id")]
    at = datetime.combine(month, datetime.min.time()) + timedelta(days=3, hours=12)
    for sid in ids[start:start + count]:
        db.rows("INSERT INTO votes (situation_id, option_key, reasoning, voter, mode, created_at, first_at)"
                " VALUES (%s, 'A', '', %s, 'quick', %s, %s)", (sid, voter, at, at))


def test_a_season_closes_once_with_trophies(app, db, people):
    month = months_ago(14)  # far from the months other tests play in
    key = seasons.key_of(month)
    (a, a_login, a_id, a_v), (b, b_login, b_id, b_v), (c, c_login, c_id, c_v), (d, d_login, d_id, d_v) = \
        [people(n) for n in ('Аня', 'Боря', 'Вера', 'Гоша')]
    judge_in(db, a_v, month, 5)
    judge_in(db, b_v, month, 3)
    judge_in(db, c_v, month, 3, start=10)
    judge_in(db, d_v, month, 1)
    before = {u: int(db.value("SELECT COALESCE(SUM(xp), 0) FROM gift_grants WHERE voter = %s", (v,))) for u, v in
              ((a_id, a_v), (d_id, d_v))}

    with app.test_request_context('/'):
        assert seasons.close(month) is True
        assert seasons.close(month) is False  # closed already: nothing twice
        name = seasons.display_name(month)
        assert name[0].isupper() and name[1:] == social.season_name(month)[1:]

    row = db.one('SELECT * FROM seasons WHERE season = %s', (key,))
    board = json.loads(row['board'])
    assert row['players'] == 4 and row['name'] == name
    assert [(r['login'], r['place'], r['value']) for r in board] == [(a_login, 1, 50), (b_login, 2, 30), (c_login, 2, 30),
                                                                     (d_login, 4, 10)]
    grants = {r['voter']: r for r in db.rows('SELECT * FROM gift_grants WHERE season = %s', (key,))}
    assert len(grants) == 4
    assert (grants[a_v]['kind'], grants[a_v]['name'], grants[a_v]['xp']) == ('title', 'Чемпион сезона «%s»' % name, 100)
    assert {grants[v]['name'] for v in (b_v, c_v)} == {'Призёр сезона «%s»' % name} and grants[b_v]['xp'] == 50
    assert grants[d_v]['name'] == 'Десятка сезона «%s»' % name and grants[d_v]['xp'] == 20
    assert db.value('SELECT title FROM players WHERE voter = %s', (a_v,)) == 'Чемпион сезона «%s»' % name
    texts = {r['user_id']: r['text'] for r in db.rows("SELECT user_id, text FROM notifications WHERE kind = 'season'"
                                                      " AND link = %s", ('/seasons/' + key,))}
    assert set(texts) == {a_id, b_id, c_id, d_id}
    assert 'вы на 1 месте' in texts[a_id] and '+100 XP' in texts[a_id] and 'вы на 4 месте' in texts[d_id]

    # trophy XP is career XP, but doesn't start the winner ahead in the new season
    a.get('/judge')
    assert '%d XP' % (50 + 100 + before[a_id]) in a.html
    with app.test_request_context('/'):
        assert a_id not in [r['user_id'] for r in social.board('season')]

    # pages
    a.get('/seasons')
    assert name in a.html and a_login in a.html and 'Вся таблица' in a.html
    a.get('/seasons/' + key)
    assert 'Ваше место из 4' in a.html and d_login in a.html and 'rating-row is-me' in a.html
    assert a.get('/seasons/2020-13').status_code == 404 and a.get('/seasons/nonsense').status_code == 404
    a.get('/u/' + a_login)
    assert 'Чемпион сезона' in a.html  # a trophy on the profile

    # API
    api = app.test_client()
    past = api.get('/api/v1/seasons').get_json()
    assert past['current']['trophies'][0]['xp'] == 100
    mine = next(s for s in past['past'] if s['key'] == key)
    assert [r['login'] for r in mine['podium']] == [a_login, b_login, c_login]
    one = api.get('/api/v1/seasons/' + key).get_json()
    assert one['players'] == 4 and one['rows'][3]['login'] == d_login and one['rows'][0]['rank']['key']
    assert api.get('/api/v1/seasons/1999-01').status_code == 404


def test_finished_months_close_by_themselves(app, db):
    """close_due closes every finished month since the seasons began, once — here in 2001, when nobody played."""
    since = db.value("SELECT meta_value FROM meta WHERE meta_key = 'seasons_since'")
    db.rows("UPDATE meta SET meta_value = '2001-01' WHERE meta_key = 'seasons_since'")
    try:
        with app.test_request_context('/'):
            seasons._checked = None
            assert seasons.close_due(date(2001, 4, 15)) == ['2001-01', '2001-02', '2001-03']
            assert seasons.close_due(date(2001, 4, 20)) == []  # one look per month
            seasons._checked = None
            assert seasons.close_due(date(2001, 4, 20)) == []  # and closed only once
        assert db.value("SELECT players FROM seasons WHERE season = '2001-02'") == 0
    finally:
        db.rows("UPDATE meta SET meta_value = %s WHERE meta_key = 'seasons_since'", (since,))
        seasons._checked = None


def test_seasons_page_shows_what_the_current_season_gives(new_browser):
    b = new_browser()
    b.get('/seasons')
    assert 'Идёт сезон' in b.html and 'Чемпион сезона' in b.html and '+100 XP' in b.html
    b.get('/ratings')
    assert re.search(r'href="/seasons"[^>]*>трофеи', b.html)
