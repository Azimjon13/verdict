"""Notifications: who is told what (friends, communities, the team's decisions on cases, gifts, reports), the bell in
the header, the page that marks them read, the case-of-the-day reminder, and the game API."""
import re
import secrets

import pytest


@pytest.fixture
def people(new_browser, db):
    def make(name='Судья'):
        b = new_browser()
        login = b.register(name + ' ' + secrets.token_hex(2))
        return b, login, int(db.value('SELECT id FROM users WHERE login = %s', (login,)))
    return make


def notes(db, user_id):
    return db.rows('SELECT kind, text, link, read_at FROM notifications WHERE user_id = %s ORDER BY id', (user_id,))


def bell(b):
    b.get('/play')
    m = re.search(r'class="bell-count"[^>]*>(\d+)<', b.html)
    return int(m.group(1)) if m else 0


def test_friends_are_told_and_the_bell_counts(people, db):
    a, a_login, a_id = people('Аня')
    b, b_login, b_id = people('Боря')
    assert bell(b) == 0 and 'class="icon-btn bell' in b.html
    a.form('/u/%s' % b_login, {'action': 'add'})
    [n] = notes(db, b_id)
    assert n['kind'] == 'friend_request' and 'хочет добавить вас в друзья' in n['text'] and n['link'] == '/friends'
    assert bell(b) == 1
    b.get('/notifications')
    assert 'хочет добавить вас в друзья' in b.html and 'новое' in b.html
    assert bell(b) == 0  # seen
    b.get('/notifications')
    assert 'новое' not in b.html
    a.form('/u/%s' % b_login, {'action': 'add'})  # asking again doesn't repeat it
    assert len(notes(db, b_id)) == 1
    b.form('/u/%s' % a_login, {'action': 'add'})  # asking back accepts
    [n] = notes(db, a_id)
    assert n['kind'] == 'friend_accepted' and n['link'] == '/u/%s' % b_login


def test_communities_tell_founders_and_members(people, db):
    owner, _, o_id = people('Основатель')
    owner.form('/communities', {'name': 'Совет ' + secrets.token_hex(2), 'rules': '', 'access': 'request', 'icon': 'shield', 'hue': '190'})
    slug, name = db.one('SELECT slug, name FROM communities WHERE owner_id = %s', (o_id,)).values()
    m, _, m_id = people('Мира')
    m.form('/c/%s' % slug, {'action': 'join'})
    [n] = notes(db, o_id)
    assert n['kind'] == 'community_request' and name in n['text'] and n['link'] == '/c/%s#members' % slug
    owner.form('/c/%s' % slug, {'action': 'approve', 'user_id': str(m_id)})
    owner.form('/c/%s' % slug, {'action': 'promote', 'user_id': str(m_id)})
    assert [(x['kind'], x['link']) for x in notes(db, m_id)] == [('community_joined', '/c/%s' % slug),
                                                                ('community_role', '/c/%s' % slug)]
    assert 'модератор' in notes(db, m_id)[1]['text']


def test_authors_hear_the_teams_decision(people, new_browser, db):
    author, _, a_id = people('Автор')
    sid = db.value("SELECT id FROM situations WHERE status = 'approved' ORDER BY id DESC LIMIT 1")
    db.rows("UPDATE situations SET status = 'pending', user_id = %s WHERE id = %s", (a_id, sid))
    title = db.value('SELECT title FROM situations WHERE id = %s', (sid,))
    team = new_browser()
    team.login()
    team.form('/action', {'id': str(sid), 'action': 'rejected', 'back': '/library'}, page='/library')
    team.form('/action', {'id': str(sid), 'action': 'approved', 'back': '/library'}, page='/library')
    team.form('/action', {'id': str(sid), 'action': 'approved', 'back': '/library'}, page='/library')  # no change: no news
    assert [(n['kind'], n['link']) for n in notes(db, a_id)] == [('case_rejected', '/view/%d' % sid), ('case_approved', '/case/%d' % sid)]
    assert title in notes(db, a_id)[1]['text']


def test_gifts_and_reports(people, new_browser, db):
    p, p_login, p_id = people('Игрок')
    voter = db.value('SELECT voter FROM players WHERE user_id = %s', (p_id,))
    team = new_browser()
    team.login()
    team.form('/admin/gifts', {'kind': 'badge', 'name': 'Значок за помощь', 'icon': 'star', 'xp': '5', 'text': 'Спасибо!', 'active': '1'})
    gid = db.value("SELECT id FROM gifts WHERE name = 'Значок за помощь' ORDER BY id DESC LIMIT 1")
    team.form('/admin/players/%s' % voter, {'action': 'grant', 'gift_id': str(gid), 'note': ''})
    anon = secrets.token_hex(16)
    db.rows('INSERT INTO player_days (voter, day, hits) VALUES (%s, CURDATE(), 1)', (anon,))
    team.form('/admin/players/%s' % anon, {'action': 'grant', 'gift_id': str(gid), 'note': ''})  # no account: nobody to tell
    assert [(n['kind'], n['link']) for n in notes(db, p_id)] == [('gift', '/judge#gifts')]

    bad, bad_login, bad_id = people('Нарушитель')
    p.form('/report', {'target_type': 'user', 'target_id': str(bad_id), 'reason': 'spam', 'text': '', 'back': '/u/' + bad_login},
           page='/u/' + bad_login)
    rid = db.value('SELECT id FROM reports WHERE target_id = %s AND reporter_id = %s', (bad_id, p_id))
    team.form('/admin/reports', {'id': str(rid), 'action': 'dismiss'})
    assert notes(db, p_id)[-1]['kind'] == 'report' and 'не нашла нарушений' in notes(db, p_id)[-1]['text']


def test_daily_reminder_and_guests(people, new_browser, app, db):
    p, _, _ = people('Игрок')
    p.get('/notifications')
    assert 'Дело дня ждёт' in p.html
    did = app.test_client().get('/api/v1/daily').get_json()['case']['id']
    p.vote(did, 'A')
    p.get('/notifications')
    assert 'Дело дня ждёт' not in p.html
    guest = new_browser()
    guest.get('/play')
    assert 'class="icon-btn bell' not in guest.html
    assert guest.get('/notifications').status_code == 302


def test_notifications_api(app, db):
    c = app.test_client()
    out = [c.post('/api/v1/auth/register', json={'login': 'n' + secrets.token_hex(4), 'display_name': n, 'password': 'password123'})
           .get_json() for n in ('Первый', 'Второй')]
    first, second = ({'Authorization': 'Bearer ' + o['token']} for o in out)
    assert c.get('/api/v1/notifications').status_code == 401
    c.post('/api/v1/friends', json={'login': out[1]['user']['login']}, headers=first)
    c.post('/api/v1/friends', json={'login': out[0]['user']['login']}, headers=second)  # accepts
    me = c.get('/api/v1/me', headers=second).get_json()
    assert me['notifications_unread'] == 1
    got = c.get('/api/v1/notifications', headers=first).get_json()
    assert got['unread'] == 1 and got['items'][0]['kind'] == 'friend_accepted' and got['items'][0]['read'] is False
    assert got['items'][0]['icon'] and got['items'][0]['created_at'].endswith('Z')
    r = c.post('/api/v1/notifications/read', json={'ids': [got['items'][0]['id']]}, headers=first).get_json()
    assert r['marked'] == 1 and r['unread'] == 0
    assert c.post('/api/v1/notifications/read', json={}, headers=second).get_json()['unread'] == 0
