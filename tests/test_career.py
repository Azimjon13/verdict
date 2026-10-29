"""Judge career: case of the day, XP and ranks, day streaks, the persistent world and its events, achievements."""
import json
import re
import secrets
from datetime import datetime, timedelta, timezone

import pytest


def player():
    return {'X-Voter-Id': secrets.token_hex(16)}


def utc_today():
    return datetime.now(timezone.utc).date()


@pytest.fixture(scope='module')
def api(app):
    return app.test_client()


@pytest.fixture(scope='module')
def cases(db):
    return {r['id']: json.loads(r['data'])['decisions']
            for r in db.rows("SELECT id, data FROM situations WHERE status = 'approved' ORDER BY id")}


def verdict(api, me, sid, option, **extra):
    r = api.post('/api/v1/cases/%d/verdict' % sid, json={'option': option, **extra}, headers=me)
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def best_for(decisions, meter):
    return max(decisions, key=lambda d: int((d.get('effects') or {}).get(meter, 0)))['key']


def daily_id(api):
    return api.get('/api/v1/daily').get_json()['case']['id']


# ---------- Case of the day ----------

def test_daily_case_is_stable_and_in_play(api, db):
    first = daily_id(api)
    assert first == daily_id(api)
    assert db.value('SELECT status FROM situations WHERE id = %s', (first,)) == 'approved'
    assert db.value('SELECT meta_value FROM meta WHERE meta_key = %s', ('daily:' + utc_today().isoformat(),)) == str(first)
    body = api.get('/api/v1/daily').get_json()
    assert body['bonus_xp'] == 15 and 0 < body['seconds_left'] <= 86400 and body['judged'] is None


def test_daily_case_avoids_recent_ones_and_replaces_a_withdrawn_one(app, db):
    from verdict import career
    with app.test_request_context():
        day = utc_today() + timedelta(days=400)  # a day no other test touches
        approved = [r['id'] for r in db.rows("SELECT id FROM situations WHERE status = 'approved' ORDER BY id")]
        for i, sid in enumerate(approved[:-3]):  # every case but three was a recent case of the day
            db.rows('REPLACE INTO meta (meta_key, meta_value) VALUES (%s, %s)', ('daily:' + (day - timedelta(days=1 + i % 30)).isoformat(), str(sid)))
        recent = {int(r['meta_value']) for r in db.rows("SELECT meta_value FROM meta WHERE meta_key IN (%s)"
                  % ', '.join(['%s'] * 30), ['daily:' + (day - timedelta(days=d)).isoformat() for d in range(1, 31)])}
        pick = career.daily_case_id(day)
        assert pick not in recent and pick in approved
        db.rows("UPDATE situations SET status = 'pending' WHERE id = %s", (pick,))
        try:
            again = career.daily_case_id(day)
            assert again != pick and again in approved
        finally:
            db.rows("UPDATE situations SET status = 'approved' WHERE id = %s", (pick,))


def test_play_button_serves_the_case_of_the_day_first(new_browser, api):
    sid = daily_id(api)
    p = new_browser()
    p.get('/quick')
    assert 'data-quick data-situation="%d"' % sid in p.html
    assert 'chip-daily' in p.html and '+15 XP' in p.html
    _, data = p.vote(sid, 'A')
    assert 'Дело дня рассмотрено: +15 XP' in data['html']
    p.get('/quick')
    assert 'data-quick data-situation="%d"' % sid not in p.html and 'Дело дня ещё ждёт' not in p.html
    p.get('/')
    assert 'id="daily"' in p.html and 'Вердикт вынесен — посмотреть итог' in p.html

    other = new_browser()
    other.get('/quick/%d' % next(i for i in range(1, 60) if i != sid and other.get('/quick/%d' % i).status_code == 200))
    assert 'Дело дня ещё ждёт вас' in other.html
    other.get('/')
    assert 'Судить дело дня' in other.html


# ---------- XP, ranks, streak ----------

def test_xp_and_ranks(api, cases, db):
    me = player()
    sid0 = daily_id(api)
    ids = [i for i in cases if i != sid0]
    first = verdict(api, me, ids[0], 'A')
    c = first['career']
    assert c['xp'] == 10 and c['xp_gained'] == 10 and c['rank']['key'] == 'intern' and not c['rank_up']
    assert c['rank']['next']['key'] == 'clerk' and c['rank']['to_next'] == 20 and c['streak'] == 1 and c['streak_up']
    assert verdict(api, me, ids[0], 'B')['career']['xp_gained'] == 0  # judging the same case again earns nothing
    second = verdict(api, me, ids[1], 'A')
    assert second['career']['xp'] == 20 and not second['career']['streak_up']
    third = verdict(api, me, ids[2], 'A')
    assert third['career']['rank_up'] and third['career']['rank']['name'] == 'Секретарь суда'
    daily = verdict(api, me, sid0, 'A')
    assert daily['career']['daily'] and daily['career']['xp_gained'] == 25
    assert not verdict(api, me, sid0, 'B')['career']['daily']  # the bonus is taken once a day
    prof = api.get('/api/v1/profile', headers=me).get_json()['career']
    assert prof['xp'] == 55 and prof['daily_done'] == 1 and prof['streak'] == 1


def test_right_guesses_earn_xp(api, cases):
    sid = list(cases)[-1]
    for _ in range(2):
        verdict(api, player(), sid, 'A')
    me = player()
    out = verdict(api, me, sid, 'B', mode='quick', guess='A')
    assert out['guess']['correct'] is True and out['career']['xp_gained'] == 15


def test_day_streak(api, cases, db):
    me = player()
    ids = list(cases)
    verdict(api, me, ids[3], 'A')
    vid = me['X-Voter-Id']
    yesterday = utc_today() - timedelta(days=1)
    db.rows('UPDATE players SET last_day = %s, streak = 4, best_streak = 4 WHERE voter = %s', (yesterday, vid))
    out = verdict(api, me, ids[4], 'A')['career']
    assert out['streak'] == 5 and out['streak_up']
    db.rows('UPDATE players SET last_day = %s WHERE voter = %s', (utc_today() - timedelta(days=3), vid))
    out = verdict(api, me, ids[5], 'A')['career']
    assert out['streak'] == 1
    prof = api.get('/api/v1/profile', headers=me).get_json()['career']
    assert prof['best_streak'] == 5 and prof['streak'] == 1
    keys = {a['key'] for a in prof['achievements'] if a['unlocked']}
    assert {'streak3', 'first'} <= keys and 'streak7' not in keys


# ---------- The world ----------

def test_world_is_kept_with_the_votes(new_browser, cases, db):
    a = new_browser()
    sid = list(cases)[6]
    a.vote(sid, 'A', mode='full')
    a.get('/play')
    first = re.findall(r'data-metric="(\w+)".*?data-value>(\d+)<', a.html, re.S)
    assert '<b data-world-count>1</b>' in a.html

    b = new_browser()  # same player, new browser session (cookie copied, session cookie not)
    b.client.set_cookie('verdict_vid', a.cookie('verdict_vid'))
    b.get('/play')
    assert re.findall(r'data-metric="(\w+)".*?data-value>(\d+)<', b.html, re.S) == first

    b.form('/api/world', {'back': '/play'}, page='/play')
    b.get('/play')
    assert '<b data-world-count>0</b>' in b.html and 'data-value>50<' in b.html
    a.get('/judge')
    assert '<b>10 XP</b>' in a.html  # the career stays after a world reset


def test_world_events(api, cases):
    me = player()
    events, peak = [], None
    for sid, decisions in cases.items():
        out = verdict(api, me, sid, best_for(decisions, 'trust'))['career']
        events += [e['key'] for e in out['events']]
        if out['world']['metrics']['trust'] == 100 and peak is None:
            peak = sid
            break
    assert events.count('trust_high') == 1 and events.count('trust_peak') == 1
    assert events.index('trust_high') < events.index('trust_peak')
    w = api.get('/api/v1/world', headers=me).get_json()['world']
    assert any(e['key'] == 'trust_peak' and e['tone'] == 'up' for e in w['active'])
    assert w['metrics']['trust'] == 100

    later = verdict(api, me, list(cases)[-2], best_for(cases[list(cases)[-2]], 'trust'))['career']
    assert 'trust_peak' not in [e['key'] for e in later['events']]  # announced once per world
    prof = api.get('/api/v1/profile', headers=me).get_json()['career']
    assert any(a['key'] == 'world' and a['unlocked'] for a in prof['achievements'])

    reset = api.post('/api/v1/world/reset', headers=me).get_json()['world']
    assert reset['count'] == 0 and reset['active'] == [] and set(reset['metrics'].values()) == {50}


def test_world_event_on_the_result_screen(new_browser, cases):
    p = new_browser()
    html = ''
    for sid, decisions in cases.items():
        _, data = p.vote(sid, best_for(decisions, 'authority'), mode='full')
        html += data['html']
        if 'Мир откликается' in html:
            break
    assert 'world-news' in html and 'Железная рука' in html
    p.get('/play')
    assert 'class="world-event tone-up"' in p.html and 'Железная рука' in p.html


# ---------- Achievements ----------

def fresh_cases(app, db, n=4):
    """Cases nobody else has judged, with mild effects, so «bold» and «world» can't join the achievements under test."""
    from verdict.repository import situation_insert
    base = json.loads(db.value("SELECT data FROM situations WHERE status = 'approved' ORDER BY id LIMIT 1"))
    ids = []
    with app.test_request_context():
        for _ in range(n):
            s = json.loads(json.dumps(base))
            s['title'] = 'Тихое дело ' + secrets.token_hex(3)
            s['author'] = 'Тест'
            for d in s['decisions']:
                d['effects'] = {'trust': 1}
            ids.append(situation_insert(s, 'approved'))
    return ids


def test_achievements(api, cases, db, app):
    me = player()
    ids = fresh_cases(app, db)
    try:
        first = verdict(api, me, ids[0], 'A')['career']['achievements']
        assert [a['key'] for a in first] == ['first']
        own = verdict(api, me, ids[1], 'other', reasoning='Созвать совет и решить вместе')['career']['achievements']
        assert [a['key'] for a in own] == ['own']
        slow = verdict(api, me, ids[2], 'A', duration_ms=130000)['career']['achievements']
        assert [a['key'] for a in slow] == ['thinker']
        assert verdict(api, me, ids[3], 'A')['career']['achievements'] == []
        stored = json.loads(db.value('SELECT achievements FROM players WHERE voter = %s', (me['X-Voter-Id'],)))
        assert stored == ['first', 'own', 'thinker']
    finally:
        db.rows('DELETE FROM situations WHERE id IN (%s)' % ', '.join(['%s'] * len(ids)), ids)


def test_judge_page_shows_the_career(new_browser, cases):
    p = new_browser()
    p.get('/judge')
    assert 'id="career"' in p.html and 'Стажёр' in p.html and 'id="achievements"' in p.html
    assert p.html.count('class="ach"') == 13  # all locked
    p.vote(list(cases)[11], 'A')
    p.get('/judge')
    assert p.html.count('class="ach is-on"') == 1 and '<b>10 XP</b>' in p.html
    p.get('/quick')
    assert 'class="rank-chip"' in p.html and 'Стажёр' in p.html


def test_catalog_has_the_career(api):
    cat = api.get('/api/v1/catalog').get_json()
    assert [r['xp'] for r in cat['ranks']] == sorted(r['xp'] for r in cat['ranks'])
    assert len(cat['world_events']) == 20 and len(cat['achievements']) == 13 and cat['xp']['daily'] == 15


def test_xp_is_the_same_everywhere(app, api, db, cases):
    """The header (career), the team's players list, ratings cards and the rank chart count XP the same way — here for
    an account with the case of the day, a right guess, a gift and a revoked gift, and for every other player so far."""
    from verdict import analytics, career, players, social
    from verdict.catalog import XP
    out = api.post('/api/v1/auth/register', json={'login': 'xp' + secrets.token_hex(3), 'display_name': 'Счетовод',
                                                  'password': 'password123'}).get_json()
    me, voter = {'Authorization': 'Bearer ' + out['token']}, out['voter_id']
    did = daily_id(api)
    sid = min((s for s in cases if s != did),
              key=lambda s: db.value('SELECT COUNT(*) FROM votes WHERE situation_id = %s', (s,)))
    for _ in range(3):
        verdict(api, player(), sid, 'A')  # a clear majority to guess
    verdict(api, me, did, cases[did][0]['key'])
    assert verdict(api, me, sid, 'B', guess='A', mode='quick')['guess']['correct']
    ts = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    for xp, revoked in ((35, None), (500, ts)):
        db.rows("INSERT INTO gift_grants (voter, source, kind, name, icon, xp, text, created_at, revoked_at)"
                " VALUES (%s, 'admin', 'xp', 'Тест', 'zap', %s, '', %s, %s)", (voter, xp, ts, revoked))
    voters = [r['voter'] for r in db.rows("SELECT DISTINCT v.voter FROM votes v JOIN situations s ON s.id = v.situation_id"
                                          " WHERE s.status = 'approved'")]
    with app.test_request_context('/'):
        assert career.summary(voter)['xp'] == 2 * XP['verdict'] + XP['guess'] + XP['daily'] + 35
        header = {v: career.summary(v)['xp'] for v in voters}
        team = {r['voter']: int(r['xp']) for r in players.players_list(who='players', per_page=100000)[0]}
        assert {v: team[v] for v in voters} == header
        linked = {int(r['user_id']): r['voter'] for r in db.rows('SELECT user_id, voter FROM players WHERE user_id IS NOT NULL')}
        cards = {a['user_id']: a['xp'] for a in social.accounts(list(linked))}
        assert {u: cards[u] for u in linked if linked[u] in header} == {u: header[v] for u, v in linked.items() if v in header}
        tally = {}
        for xp in header.values():
            key = career.rank_of(xp)['key']
            tally[key] = tally.get(key, 0) + 1
        assert {r['key']: r['value'] for r in analytics.by_rank() if r['value']} == tally
