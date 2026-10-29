"""Treasure hunts and gifts: the team makes gifts and hunts and places spots on pages; players find them."""
import json
import re
import secrets
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def team(new_browser):
    b = new_browser()
    b.login()
    return b


@pytest.fixture(autouse=True)
def end_hunts(db):
    yield
    db.rows("UPDATE challenges SET status = 'ended'")  # a hunt left running would show up in other tests


def tag():
    return secrets.token_hex(3)


def make_gift(team, db, **over):
    data = {'kind': 'badge', 'name': 'Трофей ' + tag(), 'icon': 'medal', 'xp': '0', 'text': 'Поздравляем!', 'link': '',
            'active': '1', **over}
    data = {k: v for k, v in data.items() if v is not None}
    team.form('/admin/gifts', data)
    return int(db.value('SELECT id FROM gifts WHERE name = %s', (data['name'],)))


def make_hunt(team, db, **over):
    data = {'title': 'Охота ' + tag(), 'intro': 'На сайте спрятаны тайники.', 'status': 'active', 'starts_at': '',
            'ends_at': '', 'banner': '1', 'prize_gift_id': '', **over}
    data = {k: v for k, v in data.items() if v is not None}
    team.form('/admin/hunts', data)
    return int(db.value('SELECT id FROM challenges WHERE title = %s', (data['title'],)))


def add_spot(team, db, hunt_id, place=True, **over):
    data = {'action': 'add_spot', 'label': 'Тайник ' + tag(), 'page': 'index', 'path': '', 'gift_id': '', 'hint': 'Под заголовком',
            'icon': 'gem', 'size': '24', 'visibility': 'subtle', 'max_finds': '0', 'active': '1', **over}
    team.form('/admin/hunts/%d' % hunt_id, data)
    sid = int(db.value('SELECT id FROM spots WHERE label = %s', (data['label'],)))
    if place:
        r = put(team, sid, page=data['page'] if data['page'] != 'unity' else 'index', path=data['path'] or '/')
        assert r.get_json()['ok'], r.get_json()
    return sid


def put(team, sid, page='index', path='/', selector='#main > section:nth-of-type(1)', x=12.5, y=40, scope='page'):
    team.get('/admin/spots/%d' % sid)
    return team.client.post('/admin/spots/%d/place' % sid, json={'page': page, 'path': path, 'selector': selector, 'x': x,
                            'y': y, 'scope': scope}, headers={'X-CSRF-Token': team.csrf()})


def hunt_data(b, url='/'):
    b.get(url)
    m = re.search(r'<script type="application/json" id="hunt-data">(.*?)</script>', b.html, re.S)
    return json.loads(m.group(1)) if m else None


def spot_on(b, sid, url='/'):
    data = hunt_data(b, url)
    return next((s for s in (data or {}).get('spots', []) if s['id'] == sid), None)


def claim(b, sid, url='/'):
    s = spot_on(b, sid, url)
    assert s, 'spot %d is not on %s' % (sid, url)
    r = b.post('/api/hunt', {'_csrf': b.csrf(), 'spot': sid, 'token': s['token'], 'back': url})
    return r.status_code, r.get_json()


def xp(b):
    b.get('/judge')
    return int(re.search(r'<p class="cp-next"><b>(\d+) XP</b>', b.html).group(1))


# ---------- The team's side ----------

def test_admin_is_for_the_team(new_browser, team):
    guest = new_browser()
    for url in ('/admin/', '/admin/players', '/admin/hunts', '/admin/gifts', '/admin/game'):
        r = guest.get(url)
        assert r.status_code == 302 and '/login' in r.headers['Location']
    author = new_browser()
    author.register()
    r = author.get('/admin/')
    assert r.status_code == 302 and r.headers['Location'].endswith('/')
    for url in ('/admin/', '/admin/players', '/admin/hunts', '/admin/gifts', '/admin/game'):
        assert team.get(url).status_code == 200, url
    team.get('/')
    assert 'href="/admin/"' in team.html and 'Админка' in team.html


def test_forms_check_their_fields(team, db):
    team.form('/admin/gifts', {'kind': 'xp', 'name': 'X', 'xp': '0', 'icon': 'gift', 'active': '1'})
    assert 'Название: от 2 до 120 символов.' in team.html and 'Сколько опыта даёт подарок?' in team.html
    team.form('/admin/gifts', {'kind': 'message', 'name': 'Письмо', 'link': 'javascript:alert(1)', 'icon': 'gift'})
    assert 'Ссылка начинается с https:// или с «/».' in team.html
    team.form('/admin/hunts', {'title': '', 'status': 'active', 'starts_at': '2026-11-02T10:00', 'ends_at': '2026-11-01T10:00'})
    assert 'Назовите охоту' in team.html and 'Конец охоты должен быть позже начала.' in team.html
    hid = make_hunt(team, db)
    team.form('/admin/hunts/%d' % hid, {'action': 'add_spot', 'page': 'case', 'path': 'case/1', 'icon': 'gem', 'size': '24',
                                        'visibility': 'subtle', 'max_finds': '0', 'active': '1'})
    assert 'Адрес страницы начинается с «/»' in team.html
    team.form('/admin/hunts/%d' % hid, {'action': 'add_spot', 'page': 'nowhere', 'icon': 'gem', 'size': '24'})
    assert 'Выберите страницу сайта' in team.html


def test_placing_a_spot(team, new_browser, db):
    hid = make_hunt(team, db)
    sid = add_spot(team, db, hid, place=False)
    team.get('/?hunt_place=%d' % sid)
    tools = json.loads(re.search(r'id="hunt-tools">(.*?)</script>', team.html, re.S).group(1))
    assert tools['mode'] == 'place' and tools['page'] == 'index' and tools['allowed'] and tools['spot']['id'] == sid
    assert 'id="hunt-data"' not in team.html  # no live spots in placement mode
    player = new_browser()
    player.get('/?hunt_place=%d' % sid)
    assert 'id="hunt-tools"' not in player.html

    assert put(team, sid, page='case', path='/case/3', x=33.333, y=150).get_json()['ok']
    row = db.one('SELECT page, path, selector, x, y FROM spots WHERE id = %s', (sid,))
    assert (row['page'], row['path'], float(row['x']), float(row['y'])) == ('case', '/case/3', 33.33, 100.0)
    assert put(team, sid, page='case', path='/case/3', scope='kind').get_json()['ok']
    assert db.value('SELECT path FROM spots WHERE id = %s', (sid,)) == ''
    assert put(team, sid, page='quick', path='/quick', scope='site').get_json()['ok']
    assert db.value('SELECT page FROM spots WHERE id = %s', (sid,)) == '*'
    assert put(team, sid, page='admin.dashboard').status_code == 422
    r = player.client.post('/admin/spots/%d/place' % sid, json={'page': 'index', 'selector': 'body'})
    assert r.status_code == 302  # not the team: sent to log in


# ---------- Finding spots ----------

def test_spot_shows_only_where_and_when_it_should(team, new_browser, db):
    gift = make_gift(team, db)
    hid = make_hunt(team, db)
    home = add_spot(team, db, hid, gift_id=gift)
    case = add_spot(team, db, hid, page='case', path='/case/2', gift_id=gift)
    p = new_browser()
    assert spot_on(p, home, '/') and not spot_on(p, home, '/play')
    assert spot_on(p, case, '/case/2') and not spot_on(p, case, '/case/3')
    s = spot_on(p, home, '/')
    assert s['selector'] == '#main > section:nth-of-type(1)' and s['x'] == 12.5 and s['opacity'] == 0.34 and '<svg' in s['svg']
    assert 'data-hunt-badge' in p.html and 'Под заголовком' in p.html

    later = (datetime.now(timezone.utc) + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
    team.form('/admin/hunts/%d' % hid, {'action': 'save', 'title': 'Скоро', 'intro': '', 'status': 'active', 'starts_at': later,
                                        'ends_at': '', 'banner': '1'})
    assert not spot_on(p, home, '/')
    past = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
    team.form('/admin/hunts/%d' % hid, {'action': 'save', 'title': 'Прошла', 'intro': '', 'status': 'active', 'starts_at': '',
                                        'ends_at': past, 'banner': '1'})
    assert not spot_on(p, home, '/')
    team.form('/admin/hunts/%d' % hid, {'action': 'save', 'title': 'Черновик', 'intro': '', 'status': 'draft', 'banner': '1'})
    assert not spot_on(p, home, '/')
    team.form('/admin/hunts/%d' % hid, {'action': 'start'})
    team.form('/admin/hunts/%d' % hid, {'action': 'save', 'title': 'Снова', 'intro': '', 'status': 'active', 'banner': '1'})
    assert spot_on(p, home, '/')


def test_finding_a_spot_gives_the_gift(team, new_browser, db):
    gift = make_gift(team, db, kind='xp', name='Бонус ' + tag(), icon='zap', xp='40', text='Опыт за внимательность.')
    hid = make_hunt(team, db)
    sid = add_spot(team, db, hid, gift_id=gift)
    p = new_browser()
    before = xp(p)
    s = spot_on(p, sid)
    bad = p.post('/api/hunt', {'_csrf': p.csrf(), 'spot': sid, 'token': 'x' * 24})
    assert bad.status_code == 403 and bad.get_json()['code'] == 'token'
    code, data = claim(p, sid)
    assert code == 200 and data['ok'] and data['found'] == 1 and data['total'] == 1 and data['spot'] == sid
    assert 'Опыт за внимательность.' in data['html'] and '+40 XP' in data['html']
    assert xp(p) == before + 40
    r = p.post('/api/hunt', {'_csrf': p.csrf(), 'spot': sid, 'token': s['token']})
    assert r.status_code == 409 and r.get_json()['code'] == 'found'
    assert not spot_on(p, sid)  # a found spot is gone from the page
    other = new_browser()
    other.get('/')
    stolen = other.post('/api/hunt', {'_csrf': other.csrf(), 'spot': sid, 'token': s['token']})
    assert stolen.status_code == 403  # a token is tied to the player it was given to
    assert db.value('SELECT COUNT(*) FROM spot_finds WHERE spot_id = %s', (sid,)) == 1


def test_first_finders_and_codes(team, new_browser, db):
    gift = make_gift(team, db, kind='code', name='Код ' + tag(), icon='ticket', text='Скидка в магазине.',
                     codes='AAA-1\nAAA-2\nAAA-1')
    assert db.value('SELECT COUNT(*) FROM gift_codes WHERE gift_id = %s', (gift,)) == 2
    hid = make_hunt(team, db)
    first = add_spot(team, db, hid, gift_id=gift, max_finds='1')
    second = add_spot(team, db, hid, gift_id=gift)
    a, b, c = new_browser(), new_browser(), new_browser()
    assert 'AAA-1' in claim(a, first)[1]['html']
    sb = spot_on(b, first)
    assert sb is None  # the only gift of that spot is taken: it no longer shows
    code, data = claim(b, second)
    assert code == 200 and 'AAA-2' in data['html']
    code, data = claim(c, second)
    assert code == 200 and 'Коды закончились' in data['html']
    assert db.value('SELECT COUNT(*) FROM gift_grants WHERE gift_id = %s AND code IS NULL', (gift,)) == 1
    team.get('/admin/')
    assert 'не осталось кодов' in team.html


def test_gift_for_accounts_only(team, new_browser, db):
    gift = make_gift(team, db, kind='message', name='Футболка ' + tag(), icon='gift', text='Напишите нам.', needs_account='1')
    hid = make_hunt(team, db)
    sid = add_spot(team, db, hid, gift_id=gift)
    p = new_browser()
    code, data = claim(p, sid)
    assert code == 401 and data['code'] == 'account' and data['login'].startswith('/login?back=')
    assert spot_on(p, sid)  # still there to take after signing in
    p.register()
    code, data = claim(p, sid)
    assert code == 200 and 'Напишите нам.' in data['html']


def test_blocked_player(team, new_browser, db):
    hid = make_hunt(team, db)
    sid = add_spot(team, db, hid, gift_id=make_gift(team, db))
    p = new_browser()
    p.get('/')
    p.get('/')  # the second view records activity, so the team can find the player
    vid = p.cookie('verdict_vid')
    team.form('/admin/players/%s' % vid, {'action': 'block'})
    code, data = claim(p, sid)
    assert code == 403 and data['code'] == 'blocked'
    team.form('/admin/players/%s' % vid, {'action': 'unblock'})
    assert claim(p, sid)[0] == 200


def test_main_prize_for_all_spots(team, new_browser, db):
    prize = make_gift(team, db, kind='title', name='Искатель ' + tag(), icon='crown', xp='25')
    hid = make_hunt(team, db, prize_gift_id=str(prize))
    one = add_spot(team, db, hid, gift_id=make_gift(team, db))
    two = add_spot(team, db, hid, page='play', path='/play')
    p = new_browser()
    first = claim(p, one)[1]
    assert first['found'] == 1 and first['total'] == 2 and 'Осталось найти: 1' in first['html']
    second = claim(p, two, '/play')[1]
    assert second['found'] == 2 and 'Все тайники найдены — главный приз' in second['html']
    assert db.value('SELECT COUNT(*) FROM gift_grants WHERE prize_of = %s', (hid,)) == 1
    p.get('/judge')
    title = db.value('SELECT name FROM gifts WHERE id = %s', (prize,))
    assert 'class="cp-title"' in p.html and title in p.html and 'id="gifts"' in p.html


def test_titles_and_gifts_on_the_judge_page(team, new_browser, db):
    t1 = make_gift(team, db, kind='title', name='Первый ' + tag(), icon='tag')
    t2 = make_gift(team, db, kind='title', name='Второй ' + tag(), icon='tag')
    hid = make_hunt(team, db)
    s1, s2 = add_spot(team, db, hid, gift_id=t1), add_spot(team, db, hid, gift_id=t2)
    p = new_browser()
    p.get('/judge')
    assert 'Подарков пока нет' in p.html
    claim(p, s1)
    claim(p, s2)
    name1, name2 = (db.value('SELECT name FROM gifts WHERE id = %s', (g,)) for g in (t1, t2))
    p.get('/judge')
    assert '<span class="cp-title">' in p.html and name2 in p.html and p.html.count('class="gift-card') == 2
    p.form('/judge/title', {'title': name1}, page='/judge')
    p.get('/judge')
    assert re.search(r'class="cp-title">.*?' + re.escape(name1), p.html, re.S)
    p.form('/judge/title', {'title': 'Чужой титул'}, page='/judge')
    p.get('/judge')
    assert 'Такого титула у вас нет.' in p.html
    p.form('/judge/title', {'title': ''}, page='/judge')
    p.get('/judge')
    assert 'class="cp-title"' not in p.html


def test_team_gives_and_takes_back_a_gift(team, new_browser, db):
    gift = make_gift(team, db, kind='xp', name='Награда ' + tag(), icon='zap', xp='30')
    p = new_browser()
    p.get('/')
    p.get('/')
    vid = p.cookie('verdict_vid')
    before = xp(p)
    team.form('/admin/players/%s' % vid, {'action': 'grant', 'gift_id': str(gift), 'note': 'конкурс'})
    assert xp(p) == before + 30
    grant = db.value('SELECT id FROM gift_grants WHERE voter = %s AND gift_id = %s', (vid, gift))
    team.get('/admin/players/%s' % vid)
    assert 'конкурс' in team.html and 'выдан командой' in team.html
    team.form('/admin/players/%s' % vid, {'action': 'revoke', 'grant_id': str(grant)})
    assert xp(p) == before
    p.get('/judge')
    assert 'Подарков пока нет' in p.html


def test_hunt_in_the_game_client(team, new_browser, db):
    gift = make_gift(team, db, kind='xp', name='Игровой ' + tag(), icon='zap', xp='15')
    hid = make_hunt(team, db)
    team.form('/admin/hunts/%d' % hid, {'action': 'add_spot', 'label': 'В зале суда', 'page': 'unity', 'scene': 'Courtroom',
                                        'gift_id': str(gift), 'hint': 'За молотком', 'icon': 'key', 'size': '32',
                                        'visibility': 'faint', 'max_finds': '0', 'active': '1'})
    usid = int(db.value("SELECT id FROM spots WHERE challenge_id = %s AND page = 'unity:courtroom'", (hid,)))
    web = add_spot(team, db, hid, gift_id=gift)
    client = new_browser().client
    me = {'X-Voter-Id': secrets.token_hex(16)}
    state = client.get('/api/v1/hunt', headers=me).get_json()
    spot = next(s for s in state['spots'] if s['id'] == usid)
    assert spot['scene'] == 'courtroom' and spot['opacity'] == 0.14 and spot['hint'] == 'За молотком'
    assert all(s['id'] != web for s in state['spots'])
    hunt = next(h for h in state['hunts'] if h['id'] == hid)
    assert hunt['total'] == 2 and hunt['found'] == 0
    r = client.post('/api/v1/hunt/spots/%d/claim' % usid, headers=me).get_json()
    assert r['ok'] and r['gift']['xp'] == 15 and r['gift']['kind'] == 'xp' and r['career']['xp'] >= 15
    assert client.post('/api/v1/hunt/spots/%d/claim' % usid, headers=me).status_code == 409
    assert client.post('/api/v1/hunt/spots/%d/claim' % web, headers=me).status_code == 404
    gifts = client.get('/api/v1/gifts', headers=me).get_json()['gifts']
    assert [g['name'] for g in gifts] == [db.value('SELECT name FROM gifts WHERE id = %s', (gift,))]
    assert client.get('/api/v1/hunt').status_code == 400


def test_deleting_keeps_what_players_got(team, new_browser, db):
    gift = make_gift(team, db)
    hid = make_hunt(team, db)
    sid = add_spot(team, db, hid, gift_id=gift)
    p = new_browser()
    claim(p, sid)
    team.form('/admin/spots/%d' % sid, {'action': 'delete'})
    assert db.value('SELECT COUNT(*) FROM spots WHERE id = %s', (sid,)) == 0
    team.form('/admin/gifts/%d' % gift, {'action': 'delete'})
    team.form('/admin/hunts/%d' % hid, {'action': 'delete'})
    p.get('/judge')
    assert p.html.count('class="gift-card') == 1


def test_tokens_agree_between_processes_without_a_configured_key(app, db):
    """Without VERDICT_SECRET_KEY every process makes up its own Flask key; claim tokens must not depend on it."""
    from verdict import create_app, hunt
    from conftest import DB
    other = create_app({'db': DB, 'admin_password': 'verdict-admin', 'secret_key': ''})
    another = create_app({'db': DB, 'admin_password': 'verdict-admin', 'secret_key': ''})
    assert other.secret_key != another.secret_key
    with other.test_request_context():
        first = hunt.token(1, 'a' * 32)
    with another.test_request_context():
        assert hunt.token(1, 'a' * 32) == first
        assert hunt.token(2, 'a' * 32) != first
    assert len(db.value("SELECT meta_value FROM meta WHERE meta_key = 'hunt_secret'")) == 64
