"""Deleting an account (the profile page, the game API, the team), the privacy page, Android App Links."""
import json
import secrets


def bearer(token):
    return {'Authorization': 'Bearer ' + token}


def api_login(app, login):
    out = app.test_client().post('/api/v1/auth/login', json={'login': login, 'password': 'password123'}).get_json()
    return out['token']


def uid(db, login):
    return db.value('SELECT id FROM users WHERE login = %s', (login,))


def approved(db, n):
    return [r['id'] for r in db.rows("SELECT id FROM situations WHERE status = 'approved' ORDER BY id LIMIT %s", (n,))]


def make_community(db, owner_id, name, access='open'):
    slug = 'club-' + secrets.token_hex(3)
    db.rows("INSERT INTO communities (slug, name, description, rules, access, invite_code, icon, hue, owner_id, created_at, updated_at)"
            " VALUES (%s, %s, '', '', %s, 'code', 'users', 190, %s, NOW(), NOW())", (slug, name, access, owner_id))
    cid = db.value('SELECT id FROM communities WHERE slug = %s', (slug,))
    db.rows("INSERT INTO community_members (community_id, user_id, role, status, joined_at) VALUES (%s, %s, 'owner', 'active', NOW())",
            (cid, owner_id))
    return cid, slug


def member(db, cid, user_id, role='member', minutes_ago=10):
    db.rows("INSERT INTO community_members (community_id, user_id, role, status, joined_at)"
            " VALUES (%s, %s, %s, 'active', NOW() - INTERVAL %s MINUTE)", (cid, user_id, role, minutes_ago))


def test_deleting_ones_account_on_the_website(app, new_browser, db):
    a = new_browser()
    a_login = a.register('Аня Удаляемая')
    a_id = uid(db, a_login)
    b = new_browser()
    b_login = b.register('Боря')
    b_id = uid(db, b_login)
    c = new_browser()
    c_login = c.register('Вера')
    c_id = uid(db, c_login)
    cases = approved(db, 3)
    a.vote(cases[0], 'A', reasoning='Потому что закон')
    voter = a.cookie('verdict_vid')
    assert db.value('SELECT COUNT(*) FROM votes WHERE voter = %s', (voter,)) == 1

    # what an account gathers: a game sign-in, a comment and support for another's, a friend, notifications,
    # Telegram, a campaign run, a draft and a case on review, two communities, a place in a closed season, a report
    ta, tb = api_login(app, a_login), api_login(app, b_login)
    api = app.test_client()
    api.post('/api/v1/cases/%d/verdict' % cases[1], json={'option': 'A'}, headers=bearer(ta))
    api.post('/api/v1/cases/%d/verdict' % cases[1], json={'option': 'B'}, headers=bearer(tb))
    mine = api.post('/api/v1/cases/%d/comments' % cases[1], json={'text': 'Мой комментарий'}, headers=bearer(ta)).get_json()['comment']['id']
    theirs = api.post('/api/v1/cases/%d/comments' % cases[1], json={'text': 'Комментарий Бори'}, headers=bearer(tb)).get_json()['comment']['id']
    assert api.post('/api/v1/comments/%d/like' % theirs, headers=bearer(ta)).get_json()['likes'] == 1
    api.post('/api/v1/friends', json={'login': a_login}, headers=bearer(tb))
    api.post('/api/v1/friends/%s/accept' % b_login, headers=bearer(ta))
    api.post('/api/v1/campaigns/rubezh/start', headers=bearer(ta))
    db.rows('INSERT INTO telegram_links (user_id, chat_id, username, linked_at) VALUES (%s, 4242, %s, NOW())', (a_id, 'anna'))
    for status, title in (('draft', 'Черновик Ани'), ('pending', 'Дело Ани на отборе')):
        db.rows("INSERT INTO situations (category, type, title, author, user_id, status, data, created_at, updated_at)"
                " VALUES ('law', 'case', %s, 'Аня Удаляемая', %s, %s, '{}', NOW(), NOW())", (title, a_id, status))
    pending = db.value("SELECT id FROM situations WHERE title = 'Дело Ани на отборе'")
    shared, shared_slug = make_community(db, a_id, 'Клуб Ани')
    member(db, shared, c_id, minutes_ago=30)
    member(db, shared, b_id, role='moderator', minutes_ago=5)  # a moderator comes first, even if newer
    alone, _ = make_community(db, a_id, 'Пустой клуб Ани')
    season = '1987-06'  # a closed season of its own (test_seasons checks that 1999-01 doesn't exist); removed at the end
    db.rows('DELETE FROM seasons WHERE season = %s', (season,))
    board = [{'place': 1, 'user_id': a_id, 'login': a_login, 'display_name': 'Аня Удаляемая', 'title': 'Чемпион', 'value': 90, 'xp': 90},
             {'place': 2, 'user_id': b_id, 'login': b_login, 'display_name': 'Боря', 'title': None, 'value': 40, 'xp': 40}]
    db.rows('INSERT INTO seasons (season, name, closed_at, players, board) VALUES (%s, %s, NOW(), 2, %s)',
            (season, 'Старый сезон', json.dumps(board, ensure_ascii=False)))
    api.post('/api/v1/reports', json={'target': 'user', 'login': b_login, 'reason': 'spam'}, headers=bearer(ta))
    # what others were told about her: a friend request, an accepted request, a request to join
    api.post('/api/v1/friends', json={'login': c_login}, headers=bearer(ta))
    _, veras = make_community(db, c_id, 'Клуб Веры', access='request')
    assert api.post('/api/v1/communities/%s/join' % veras, json={'accept_rules': True}, headers=bearer(ta)).get_json()['result'] == 'requested'
    told = "SELECT COUNT(*) FROM notifications WHERE user_id = %s AND kind = %s AND text LIKE %s"
    assert db.value(told, (c_id, 'friend_request', 'Аня Удаляемая%')) == 1
    assert db.value(told, (c_id, 'community_request', 'Аня Удаляемая%')) == 1
    assert db.value(told, (b_id, 'friend_accepted', 'Аня Удаляемая%')) == 1

    # a wrong password changes nothing
    a.form('/account', {'action': 'delete', 'delete_password': 'not-my-password'})
    assert 'Пароль указан неверно.' in a.errors()
    assert uid(db, a_login) == a_id

    r = a.form('/account', {'action': 'delete', 'delete_password': 'password123'})
    assert r.status_code == 302 and r.headers['Location'].endswith('/')
    a.get('/')
    assert 'Аккаунт удалён' in ' '.join(a.toasts())
    assert a.cookie('verdict_vid') != voter  # the browser plays as a new anonymous player
    assert a.get('/account').status_code == 302  # signed out

    assert db.value('SELECT COUNT(*) FROM users WHERE id = %s', (a_id,)) == 0
    for table in ('votes', 'players', 'player_days', 'campaign_runs', 'gift_grants', 'spot_finds'):
        assert db.value('SELECT COUNT(*) FROM %s WHERE voter = %%s' % table, (voter,)) == 0, table
    for table in ('api_tokens', 'friendships', 'notifications', 'telegram_links', 'sessions', 'comment_likes'):
        assert db.value('SELECT COUNT(*) FROM %s WHERE user_id = %%s' % table, (a_id,)) == 0, table
    assert db.value('SELECT COUNT(*) FROM friendships WHERE friend_id = %s', (a_id,)) == 0
    for who, kind in ((c_id, 'friend_request'), (c_id, 'community_request'), (b_id, 'friend_accepted')):
        assert db.value(told, (who, kind, 'Аня Удаляемая%')) == 0, kind
    assert db.value('SELECT COUNT(*) FROM comments WHERE id = %s', (mine,)) == 0
    assert db.value('SELECT likes FROM comments WHERE id = %s', (theirs,)) == 0
    assert api.get('/api/v1/me', headers=bearer(ta)).status_code == 401

    # what stays, without the name
    assert db.value("SELECT COUNT(*) FROM situations WHERE title = 'Черновик Ани'") == 0
    assert db.one('SELECT user_id, author FROM situations WHERE id = %s', (pending,)) == {'user_id': None, 'author': ''}
    assert db.value('SELECT owner_id FROM communities WHERE id = %s', (shared,)) == b_id
    assert db.value('SELECT role FROM community_members WHERE community_id = %s AND user_id = %s', (shared, b_id)) == 'owner'
    note = db.one("SELECT text, link FROM notifications WHERE user_id = %s AND kind = 'community_role' ORDER BY id DESC LIMIT 1", (b_id,))
    assert 'Клуб Ани' in note['text'] and note['link'] == '/c/%s' % shared_slug
    assert db.value('SELECT COUNT(*) FROM communities WHERE id = %s', (alone,)) == 0
    kept = json.loads(db.value('SELECT board FROM seasons WHERE season = %s', (season,)))
    assert kept[0] == {'place': 1, 'user_id': None, 'login': None, 'display_name': 'Удалённый судья', 'title': None,
                       'value': 90, 'xp': 90}
    assert kept[1]['login'] == b_login
    assert db.value('SELECT reporter_id FROM reports WHERE target_type = %s AND target_id = %s', ('user', b_id)) is None
    page = new_browser()
    page.get('/seasons/%s' % season)
    assert 'Удалённый судья' in page.html and 'аккаунт удалён' in page.html and '/u/None' not in page.html
    page.get('/u/%s' % a_login)
    assert 'Удалённый судья' not in page.html
    db.rows('DELETE FROM seasons WHERE season = %s', (season,))


def test_deleting_from_the_game_client(app, db):
    c = app.test_client()
    login = 'g' + secrets.token_hex(4)
    device = secrets.token_hex(16)
    out = c.post('/api/v1/auth/register', json={'login': login, 'display_name': 'Из игры', 'password': 'password123'},
                 headers={'X-Voter-Id': device}).get_json()
    sid = approved(db, 1)[0]
    c.post('/api/v1/cases/%d/verdict' % sid, json={'option': 'A'}, headers=bearer(out['token']))
    assert c.post('/api/v1/me/delete', json={'password': 'wrong'}, headers=bearer(out['token'])).status_code == 403
    assert c.post('/api/v1/me/delete', json={'password': 'password123'}).status_code == 401
    assert c.post('/api/v1/me/delete', json={'password': 'password123'}, headers=bearer(out['token'])).get_json() == {'ok': True}
    assert db.value('SELECT COUNT(*) FROM users WHERE login = %s', (login,)) == 0
    assert db.value('SELECT COUNT(*) FROM votes WHERE voter = %s', (device,)) == 0
    assert c.get('/api/v1/me', headers=bearer(out['token'])).status_code == 401
    assert c.post('/api/v1/auth/login', json={'login': login, 'password': 'password123'}).status_code == 401


def test_the_team_keeps_its_accounts_and_deletes_others(app, new_browser, db):
    team = new_browser()
    team.login()
    team.get('/account')
    assert 'Аккаунт команды так удалить нельзя' in team.html
    team.form('/account', {'action': 'delete', 'delete_password': 'verdict-admin'})
    assert db.value("SELECT COUNT(*) FROM users WHERE login = 'admin'") == 1
    token = app.test_client().post('/api/v1/auth/login', json={'login': 'admin', 'password': 'verdict-admin'}).get_json()['token']
    r = app.test_client().post('/api/v1/me/delete', json={'password': 'verdict-admin'}, headers=bearer(token))
    assert r.status_code == 403 and 'команды' in r.get_json()['error']

    # someone who can't sign in asks the team: admin → player → «Удалить аккаунт»
    p = new_browser()
    login = p.register('Забывчивый')
    p.vote(approved(db, 1)[0], 'A')
    voter = p.cookie('verdict_vid')
    team.get('/admin/players/%s' % voter)
    assert 'Удалить аккаунт' in team.html
    team.form('/admin/players/%s' % voter, {'action': 'erase_account'})
    assert db.value('SELECT COUNT(*) FROM users WHERE login = %s', (login,)) == 0
    assert db.value('SELECT COUNT(*) FROM votes WHERE voter = %s', (voter,)) == 0
    team.get('/admin/players')
    assert 'Аккаунт @%s и его данные удалены.' % login in ' '.join(team.toasts())


def test_privacy_page_and_app_links(app, new_browser):
    guest = new_browser()
    guest.get('/')
    assert 'href="/privacy"' in guest.html and 'href="/privacy#delete"' in guest.html
    r = guest.get('/privacy')
    assert r.status_code == 200
    for text in ('Что мы храним', 'Удаление аккаунта и данных', 'verdict_vid', 'Google Fonts', '14 дней', 'bcrypt'):
        assert text in guest.html, text
    assert 'настройка <code>contact</code>' not in guest.html  # the team's hint is for the team
    guest.get('/register')
    assert 'href="/privacy"' in guest.html

    cfg = app.config['VERDICT']
    cfg['contact'] = 'team@example.com'
    try:
        guest.get('/privacy')
        assert 'href="mailto:team@example.com"' in guest.html
    finally:
        cfg['contact'] = ''
    team = new_browser()
    team.login()
    team.get('/privacy')
    assert 'настройка <code>contact</code>' in team.html

    assert guest.get('/.well-known/assetlinks.json').status_code == 404
    cfg['android_cert_sha256'] = 'aa:bb:cc, DD:EE:FF'
    try:
        r = app.test_client().get('/.well-known/assetlinks.json')
        links = r.get_json()
        assert links[0]['target'] == {'namespace': 'android_app', 'package_name': 'uz.azero.verdict',
                                      'sha256_cert_fingerprints': ['AA:BB:CC', 'DD:EE:FF']}
        assert links[0]['relation'] == ['delegate_permission/common.handle_all_urls']
    finally:
        cfg['android_cert_sha256'] = ''
