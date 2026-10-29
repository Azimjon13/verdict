"""Signing in from the game client, its social actions; reports to the team, barred players; link previews."""
import secrets


def api(app):
    return app.test_client()


def sign_up(c, name='Игрок', voter=None):
    login = 'g' + secrets.token_hex(4)
    headers = {'X-Voter-Id': voter} if voter else {}
    r = c.post('/api/v1/auth/register', json={'login': login, 'display_name': name, 'password': 'password123'}, headers=headers)
    assert r.status_code == 200, r.get_json()
    return login, r.get_json()


def bearer(token):
    return {'Authorization': 'Bearer ' + token}


def test_register_login_and_the_same_player_everywhere(app, new_browser, db):
    c = api(app)
    device = secrets.token_hex(16)
    sid = db.value("SELECT id FROM situations WHERE status = 'approved' ORDER BY id LIMIT 1")
    c.post('/api/v1/cases/%d/verdict' % sid, json={'option': 'A'}, headers={'X-Voter-Id': device})
    login, out = sign_up(c, 'Из игры', device)
    assert out['voter_id'] == device and out['token']  # the device's anonymous progress belongs to the new account
    me = c.get('/api/v1/me', headers=bearer(out['token'])).get_json()
    assert me['user']['login'] == login and me['career']['xp'] >= 10

    # the same account on the website: the browser switches to this player
    b = new_browser()
    b.login(login, 'password123')
    assert b.cookie('verdict_vid') == device

    # signing in on a second device returns the account's player and merges that device's anonymous verdicts
    other = secrets.token_hex(16)
    sid2 = db.value("SELECT id FROM situations WHERE status = 'approved' ORDER BY id LIMIT 1 OFFSET 1")
    c.post('/api/v1/cases/%d/verdict' % sid2, json={'option': 'A'}, headers={'X-Voter-Id': other})
    second = c.post('/api/v1/auth/login', json={'login': login, 'password': 'password123'}, headers={'X-Voter-Id': other}).get_json()
    assert second['voter_id'] == device and db.value('SELECT COUNT(*) FROM votes WHERE voter = %s', (device,)) == 2
    # with a token the X-Voter-Id doesn't matter: verdicts go to the account
    r = c.post('/api/v1/cases/%d/verdict' % sid, json={'option': 'B'}, headers=bearer(second['token'])).get_json()
    assert r['ok'] and db.value('SELECT option_key FROM votes WHERE voter = %s AND situation_id = %s', (device, sid)) == 'B'
    assert c.post('/api/v1/auth/logout', headers=bearer(second['token'])).get_json()['ok']
    assert c.get('/api/v1/me', headers=bearer(second['token'])).status_code == 401
    assert db.value('SELECT COUNT(*) FROM api_tokens WHERE user_id = %s', (me['user']['id'],)) == 1


def test_wrong_passwords_are_slowed_down(app):
    c = api(app)
    login, _ = sign_up(c)
    for _ in range(10):
        assert c.post('/api/v1/auth/login', json={'login': login, 'password': 'nope'}).status_code == 401
    assert c.post('/api/v1/auth/login', json={'login': login, 'password': 'password123'}).status_code == 429
    bad = c.post('/api/v1/auth/register', json={'login': 'x', 'display_name': 'A', 'password': '1'})
    assert bad.status_code == 422 and bad.get_json()['errors']


def test_friends_and_communities_from_the_game(app, db):
    c = api(app)
    a_login, a = sign_up(c, 'Аня')
    b_login, b = sign_up(c, 'Боря')
    assert c.post('/api/v1/friends', json={'login': b_login}, headers=bearer(a['token'])).get_json()['result'] == 'requested'
    fb = c.get('/api/v1/friends', headers=bearer(b['token'])).get_json()
    assert [x['login'] for x in fb['incoming']] == [a_login]
    assert c.post('/api/v1/friends/%s/accept' % a_login, headers=bearer(b['token'])).get_json()['ok']
    fa = c.get('/api/v1/friends', headers=bearer(a['token'])).get_json()
    assert [x['login'] for x in fa['friends']] == [b_login]

    sid = db.value("SELECT id FROM situations WHERE status = 'approved' ORDER BY id LIMIT 1 OFFSET 5")
    c.post('/api/v1/cases/%d/verdict' % sid, json={'option': 'A'}, headers=bearer(b['token']))
    r = c.post('/api/v1/cases/%d/verdict' % sid, json={'option': 'B'}, headers=bearer(a['token'])).get_json()
    assert r['friends'] == [{'login': b_login, 'display_name': 'Боря', 'option': 'A'}]
    board = c.get('/api/v1/ratings?board=all&scope=friends', headers=bearer(a['token'])).get_json()
    assert sorted(x['login'] for x in board['rows']) == sorted([a_login, b_login])
    assert c.get('/api/v1/ratings?scope=friends').status_code == 401

    a_id = c.get('/api/v1/me', headers=bearer(a['token'])).get_json()['user']['id']
    db.rows("INSERT INTO communities (slug, name, description, rules, access, invite_code, icon, hue, owner_id, created_at, updated_at)"
            " VALUES ('api-club', 'API клуб', '', 'Правило.', 'open', 'code123', 'users', 190, %s, NOW(), NOW())", (a_id,))
    assert c.post('/api/v1/communities/api-club/join', json={}, headers=bearer(b['token'])).status_code == 422
    assert c.post('/api/v1/communities/api-club/join', json={'accept_rules': True}, headers=bearer(b['token'])).get_json()['result'] == 'joined'
    me = c.get('/api/v1/me', headers=bearer(b['token'])).get_json()
    assert me['communities'][0]['slug'] == 'api-club'
    assert c.post('/api/v1/communities/api-club/leave', headers=bearer(b['token'])).get_json()['ok']
    assert c.post('/api/v1/me/profile', json={'visibility': 'private'}, headers=bearer(b['token'])).get_json()['ok']
    assert c.get('/api/v1/users/%s' % b_login).get_json()['user']['visible'] is False


def test_reports_reach_the_team(new_browser, db):
    reporter = new_browser()
    reporter.register('Внимательный')
    bad = new_browser()
    bad_login = bad.register('Нарушитель')
    bad.vote(db.value("SELECT id FROM situations WHERE status = 'approved' ORDER BY id LIMIT 1"), 'A')
    bad_id = db.value('SELECT id FROM users WHERE login = %s', (bad_login,))
    reporter.form('/report', {'target_type': 'user', 'target_id': str(bad_id), 'reason': 'abuse', 'text': 'Оскорбляет в сообществе',
                              'back': '/u/%s' % bad_login}, page='/u/%s' % bad_login)
    reporter.form('/report', {'target_type': 'user', 'target_id': str(bad_id), 'reason': 'abuse', 'back': '/'}, page='/')
    assert db.value("SELECT COUNT(*) FROM reports WHERE target_id = %s AND target_type = 'user'", (bad_id,)) == 1  # no duplicates
    guest = new_browser()
    guest.get('/')
    r = guest.post('/report', {'_csrf': guest.csrf(), 'target_type': 'user', 'target_id': bad_id, 'reason': 'abuse'})
    assert r.status_code == 302 and '/login' in r.headers['Location']

    team = new_browser()
    team.login()
    team.get('/admin/')
    assert 'Жалоб ждут решения' in team.html
    team.get('/admin/reports')
    assert 'Нарушитель' in team.html and 'Оскорбляет в сообществе' in team.html
    rid = db.value("SELECT id FROM reports WHERE target_id = %s AND target_type = 'user'", (bad_id,))
    voter = db.value('SELECT voter FROM players WHERE user_id = %s', (bad_id,))
    team.form('/admin/reports', {'action': 'block', 'id': str(rid), 'voter': voter})
    assert db.value('SELECT status FROM reports WHERE id = %s', (rid,)) == 'resolved'
    assert db.value('SELECT blocked FROM players WHERE voter = %s', (voter,)) == 1
    # barred: no friend requests, no communities
    bad.form('/friends', {'action': 'add', 'login': db.value('SELECT login FROM users WHERE display_name = %s', ('Внимательный',))})
    bad.get('/friends')
    assert 'ограничила вам общение' in ' '.join(bad.toasts())
    bad.form('/communities', {'name': 'Мой клуб', 'access': 'open', 'icon': 'users', 'hue': '190'})
    assert 'ограничила вам создание сообществ' in bad.html


def test_link_previews_and_share_buttons(new_browser, db):
    b = new_browser()
    sid = db.value("SELECT id FROM situations WHERE title = 'Три ампулы'")
    b.get('/case/%d' % sid)
    assert '<meta property="og:title" content="Три ампулы">' in b.html
    assert '<meta property="og:description" content="Вы — смотритель поселения' in b.html
    _, data = b.vote(sid, 'A')
    assert 'data-share-link' in data['html'] and 't.me/share/url?url=' in data['html'] and 'Пожаловаться' in data['html']
