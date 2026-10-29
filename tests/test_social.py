"""Players together: public profiles and privacy, friends, friends' verdicts after a case, ratings, communities."""
import re
import secrets
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def people(new_browser, db):
    """Signs up players on demand: make('Аня') → (browser, login, user id)."""
    def make(name='Судья'):
        b = new_browser()
        login = b.register(name + ' ' + secrets.token_hex(2))
        return b, login, int(db.value('SELECT id FROM users WHERE login = %s', (login,)))
    return make


def approved(db):
    return [r['id'] for r in db.rows("SELECT id FROM situations WHERE status = 'approved' ORDER BY id")]


def befriend(a, b, b_login):
    a.form('/u/%s' % b_login, {'action': 'add'})
    b.get('/friends')
    b.post('/friends', {'_csrf': b.csrf(), 'action': 'accept', 'user_id': re.search(r'name="user_id" value="(\d+)"', b.html).group(1)})


def set_profile(b, visibility, bio='', in_ratings=True):
    data = {'action': 'profile', 'bio': bio, 'visibility': visibility}
    if in_ratings:
        data['in_ratings'] = '1'
    b.form('/account', data)


def board_logins(b, url):
    b.get(url)
    return re.findall(r'class="who[^"]*" href="/u/([^"]+)"', b.html)


# ---------- Profiles ----------

def test_public_profile_and_privacy(people, new_browser, db):
    a, a_login, _ = people('Аня')
    for sid in approved(db)[:2]:
        a.vote(sid, 'A')
    guest = new_browser()
    guest.get('/u/%s' % a_login)
    assert 'Аня' in guest.html and '<b>20 XP</b>' in guest.html and 'Добавить в друзья' in guest.html
    assert guest.get('/u/nobody-here').status_code == 404

    set_profile(a, 'friends', bio='Люблю дела о власти.')
    guest.get('/u/%s' % a_login)
    assert 'Профиль скрыт' in guest.html and 'Люблю дела о власти.' not in guest.html
    b, b_login, _ = people('Боря')
    b.get('/u/%s' % a_login)
    assert 'Профиль скрыт' in b.html
    befriend(b, a, a_login)
    b.get('/u/%s' % a_login)
    assert 'Люблю дела о власти.' in b.html and 'ваш друг' in b.html and '<b>20 XP</b>' in b.html

    set_profile(a, 'private')
    b.get('/u/%s' % a_login)
    assert 'Игрок решил не показывать свой профиль.' in b.html
    a.get('/u/%s' % a_login)
    assert 'это вы' in a.html and 'Профиль видят: только мне' in a.html


def test_profile_shows_trophies_but_not_codes(people, db):
    a, a_login, uid = people('Трофей')
    a.vote(approved(db)[3], 'A')
    voter = db.value('SELECT voter FROM players WHERE user_id = %s', (uid,))
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for kind, name, code in (('badge', 'Знак отваги', None), ('code', 'Код на футболку', 'SECRET-123')):
        db.rows("INSERT INTO gift_grants (voter, source, kind, name, icon, xp, text, code, created_at) VALUES (%s, 'admin', %s, %s, 'gift', 0, '', %s, %s)",
                (voter, kind, name, code, now))
    a.get('/u/%s' % a_login)
    assert 'Знак отваги' in a.html and 'SECRET-123' not in a.html and 'Код на футболку' not in a.html


# ---------- Friends ----------

def test_friend_requests(people):
    a, a_login, a_id = people('Аня')
    b, b_login, b_id = people('Боря')
    a.form('/friends', {'action': 'add', 'login': b_login})
    a.get('/friends')
    assert 'Ждут ответа' in a.html and b_login in a.html
    b.get('/friends')
    assert 'Хотят дружить' in b.html
    b.post('/friends', {'_csrf': b.csrf(), 'action': 'accept', 'user_id': a_id})
    b.get('/friends')
    assert 'Хотят дружить' not in b.html and a_login in b.html
    a.get('/friends')
    assert b_login in a.html and 'Ждут ответа' not in a.html

    a.post('/friends', {'_csrf': a.csrf(), 'action': 'remove', 'user_id': b_id})
    a.get('/u/%s' % b_login)
    assert 'Добавить в друзья' in a.html

    # asking someone who already asked you makes you friends
    b.form('/u/%s' % a_login, {'action': 'add'})
    a.form('/u/%s' % b_login, {'action': 'add'})
    a.get('/u/%s' % b_login)
    assert 'Вы друзья' in a.html

    a.form('/friends', {'action': 'add', 'login': a_login})
    a.get('/friends')
    assert 'Это вы.' in ' '.join(a.toasts())
    a.form('/friends', {'action': 'add', 'login': 'no-such-login'})
    a.get('/friends')
    assert 'не найден' in ' '.join(a.toasts())


def test_decline_and_cancel(people, db):
    a, a_login, a_id = people('Аня')
    b, b_login, b_id = people('Боря')
    a.form('/friends', {'action': 'add', 'login': b_login})
    b.form('/friends', {'action': 'decline', 'user_id': str(a_id)})
    assert db.value('SELECT COUNT(*) FROM friendships WHERE user_id = %s', (a_id,)) == 0
    a.form('/friends', {'action': 'add', 'login': b_login})
    a.form('/friends', {'action': 'cancel', 'user_id': str(b_id)})
    assert db.value('SELECT COUNT(*) FROM friendships WHERE user_id = %s OR friend_id = %s', (a_id, a_id)) == 0


def test_friends_verdicts_after_a_case(people, db):
    a, a_login, _ = people('Аня')
    b, b_login, _ = people('Боря')
    befriend(a, b, b_login)
    sid = approved(db)[6]
    b.vote(sid, 'A')
    _, data = a.vote(sid, 'B')
    assert 'Как решили друзья' in data['html'] and 'Боря' in data['html'] and '0 из 1 — как вы' in data['html']
    set_profile(b, 'private')
    _, data = a.vote(approved(db)[6], 'A', mode='full')
    assert 'Как решили друзья' not in data['html']
    assert a.get('/case/%d' % sid).status_code == 200 and a.get('/quick/%d' % sid).status_code == 200


# ---------- Ratings ----------

def test_ratings_scopes_and_season(people, db, app):
    ids = approved(db)
    a, a_login, a_id = people('Аня')
    b, b_login, b_id = people('Боря')
    c, c_login, c_id = people('Вера')
    for sid in ids[10:13]:
        a.vote(sid, 'A')
    for sid in ids[10:12]:
        b.vote(sid, 'A')
    c.vote(ids[10], 'A')
    befriend(a, b, b_login)
    assert board_logins(a, '/ratings?scope=friends') == [a_login, b_login]
    a.get('/ratings?scope=friends')
    assert 'Ваше место из 2' in a.html

    # a re-vote doesn't move a case into this season: what counts is when it was judged first
    a_voter = db.value('SELECT voter FROM players WHERE user_id = %s', (a_id,))
    last_month = datetime.now(timezone.utc).replace(tzinfo=None).replace(day=1) - timedelta(days=3)
    db.rows('UPDATE votes SET first_at = %s, created_at = %s WHERE voter = %s', (last_month, last_month, a_voter))
    a.vote(ids[10], 'B')  # re-judged today
    assert board_logins(a, '/ratings?scope=friends&board=season') == [b_login]
    assert board_logins(a, '/ratings?scope=friends&board=all') == [a_login, b_login]

    set_profile(b, 'public', in_ratings=False)
    assert b_login not in board_logins(c, '/ratings?board=all')
    db.rows('UPDATE players SET blocked = 1 WHERE user_id = %s', (c_id,))
    assert c_login not in board_logins(a, '/ratings?board=all')
    db.rows('UPDATE players SET blocked = 0 WHERE user_id = %s', (c_id,))


def test_ratings_accuracy_streak_and_ties(people, db, app):
    from verdict import social
    from verdict.career import today
    a, a_login, a_id = people('Аня')
    b, b_login, b_id = people('Боря')
    for p in (a, b):
        for sid in approved(db)[:10]:
            p.vote(sid, 'A')
    for uid, right in ((a_id, 7), (b_id, 9)):
        voter = db.value('SELECT voter FROM players WHERE user_id = %s', (uid,))
        db.rows('UPDATE votes SET guess_correct = 0 WHERE voter = %s', (voter,))
        db.rows('UPDATE votes SET guess_correct = 1 WHERE voter = %s ORDER BY id LIMIT %s', (voter, right))
    db.rows('UPDATE players SET streak = 4, last_day = %s WHERE user_id IN (%s, %s)', (today(), a_id, b_id))
    with app.test_request_context():
        acc = [r for r in social.board('accuracy', [a_id, b_id])]
        assert [(r['login'], r['value'], r['note']) for r in acc] == [(b_login, 90, '9 из 10'), (a_login, 70, '7 из 10')]
        streak = social.board('streak', [a_id, b_id])
        assert [r['place'] for r in streak] == [1, 1] and all(r['value'] == 4 for r in streak)


# ---------- Communities ----------

def test_open_community_with_rules(people, db):
    owner, o_login, o_id = people('Основатель')
    owner.form('/communities', {'name': 'Клуб строгих судей', 'description': 'Только власть.', 'rules': '1. Уважать вердикты.',
                                'access': 'open', 'icon': 'gavel', 'hue': '260'})
    slug = db.value('SELECT slug FROM communities WHERE owner_id = %s', (o_id,))
    assert slug.startswith('klub-strogikh-sudey')
    assert db.value("SELECT role FROM community_members WHERE user_id = %s", (o_id,)) == 'owner'

    m, m_login, m_id = people('Участник')
    m.form('/c/%s' % slug, {'action': 'join'})
    m.get('/c/%s' % slug)
    assert 'примите правила' in ' '.join(m.toasts())
    m.form('/c/%s' % slug, {'action': 'join', 'accept_rules': '1'})
    assert db.value('SELECT status FROM community_members WHERE user_id = %s', (m_id,)) == 'active'
    m.vote(approved(db)[20], 'A')
    assert m_login in board_logins(m, '/ratings?scope=c:%s&board=all' % slug)
    assert board_logins(m, '/ratings?scope=c:%s&board=all' % slug) == [m_login]  # the owner hasn't played yet
    m.form('/c/%s' % slug, {'action': 'leave'})
    assert db.value('SELECT COUNT(*) FROM community_members WHERE user_id = %s', (m_id,)) == 0
    owner.form('/c/%s' % slug, {'action': 'leave'})
    owner.get('/c/%s' % slug)
    assert 'Основатель не может выйти' in ' '.join(owner.toasts())


def test_request_community_and_roles(people, db):
    owner, _, o_id = people('Основатель')
    owner.form('/communities', {'name': 'По заявке', 'rules': '', 'access': 'request', 'icon': 'shield', 'hue': '190'})
    slug = db.value('SELECT slug FROM communities WHERE owner_id = %s', (o_id,))
    a, _, a_id = people('Аня')
    b, _, b_id = people('Боря')
    for p in (a, b):
        p.form('/c/%s' % slug, {'action': 'join'})
    assert {r['status'] for r in db.rows('SELECT status FROM community_members WHERE user_id IN (%s, %s)', (a_id, b_id))} == {'requested'}
    owner.get('/c/%s' % slug)
    assert 'Заявки' in owner.html
    owner.form('/c/%s' % slug, {'action': 'approve', 'user_id': str(a_id)})
    owner.form('/c/%s' % slug, {'action': 'approve', 'user_id': str(b_id)})
    owner.form('/c/%s' % slug, {'action': 'promote', 'user_id': str(a_id)})
    assert db.value('SELECT role FROM community_members WHERE user_id = %s', (a_id,)) == 'moderator'
    # a moderator removes members, but not another moderator or the founder
    b.form('/c/%s' % slug, {'action': 'promote', 'user_id': str(b_id)})
    assert db.value('SELECT role FROM community_members WHERE user_id = %s', (b_id,)) == 'member'
    a.form('/c/%s' % slug, {'action': 'remove', 'user_id': str(o_id)})
    assert db.value('SELECT COUNT(*) FROM community_members WHERE user_id = %s', (o_id,)) == 1
    a.form('/c/%s' % slug, {'action': 'remove', 'user_id': str(b_id)})
    assert db.value('SELECT COUNT(*) FROM community_members WHERE user_id = %s', (b_id,)) == 0


def test_invite_only_community(people, db):
    owner, _, o_id = people('Основатель')
    owner.form('/communities', {'name': 'Тайный суд', 'rules': 'Молчать о делах.', 'access': 'invite', 'icon': 'lock', 'hue': '0'})
    slug, code = db.one('SELECT slug, invite_code FROM communities WHERE owner_id = %s', (o_id,)).values()
    owner.get('/c/%s' % slug)
    assert 'invite=%s' % code in owner.html
    g, _, g_id = people('Гость')
    g.form('/c/%s' % slug, {'action': 'join', 'accept_rules': '1'})
    assert db.value('SELECT COUNT(*) FROM community_members WHERE user_id = %s', (g_id,)) == 0
    g.get('/c/%s?invite=%s' % (slug, code))
    assert 'Вас пригласили' in g.html
    g.form('/c/%s' % slug, {'action': 'join', 'accept_rules': '1', 'code': code}, page='/c/%s?invite=%s' % (slug, code))
    assert db.value('SELECT status FROM community_members WHERE user_id = %s', (g_id,)) == 'active'
    owner.form('/c/%s' % slug, {'action': 'regen'})
    assert db.value('SELECT invite_code FROM communities WHERE slug = %s', (slug,)) != code
    h, _, h_id = people('Поздний')
    h.form('/c/%s' % slug, {'action': 'join', 'accept_rules': '1', 'code': code})
    assert db.value('SELECT COUNT(*) FROM community_members WHERE user_id = %s', (h_id,)) == 0


def test_community_limits_editing_and_removal(people, new_browser, db):
    owner, _, o_id = people('Основатель')
    for i in range(5):
        owner.form('/communities', {'name': 'Сообщество %d' % i, 'access': 'open', 'icon': 'users', 'hue': '190'})
    owner.form('/communities', {'name': 'Шестое', 'access': 'open', 'icon': 'users', 'hue': '190'})
    assert 'это предел' in owner.html and db.value('SELECT COUNT(*) FROM communities WHERE owner_id = %s', (o_id,)) == 5
    owner.form('/communities', {'name': 'X', 'access': 'open'})
    assert 'Название: от 3 до 80 символов.' in owner.html
    slug = db.value('SELECT slug FROM communities WHERE owner_id = %s ORDER BY id LIMIT 1', (o_id,))
    owner.form('/c/%s' % slug, {'action': 'save', 'name': 'Новое имя', 'description': 'Новое описание', 'rules': '',
                                'access': 'request', 'icon': 'crown', 'hue': '50'})
    row = db.one('SELECT name, access, icon, hue FROM communities WHERE slug = %s', (slug,))
    assert (row['name'], row['access'], row['icon'], int(row['hue'])) == ('Новое имя', 'request', 'crown', 50)
    stranger, _, _ = people('Чужой')
    stranger.form('/c/%s' % slug, {'action': 'delete'})
    assert db.value('SELECT COUNT(*) FROM communities WHERE slug = %s', (slug,)) == 1
    team = new_browser()
    team.login()
    team.get('/admin/communities')
    assert 'Новое имя' in team.html
    cid = db.value('SELECT id FROM communities WHERE slug = %s', (slug,))
    team.form('/admin/communities', {'id': str(cid)})
    assert db.value('SELECT COUNT(*) FROM communities WHERE slug = %s', (slug,)) == 0
    owner.form('/c/%s' % db.value('SELECT slug FROM communities WHERE owner_id = %s LIMIT 1', (o_id,)), {'action': 'delete'})
    assert db.value('SELECT COUNT(*) FROM communities WHERE owner_id = %s', (o_id,)) == 3


def test_guests_are_invited_to_sign_up(new_browser, db):
    g = new_browser()
    g.get('/ratings')
    assert 'Заведите аккаунт' in g.html and 'href="/ratings"' in g.html
    r = g.get('/friends')
    assert r.status_code == 302 and '/login' in r.headers['Location']
    r = g.get('/ratings?scope=friends')
    assert r.status_code == 302
    g.get('/communities')
    assert 'Создавать сообщества и вступать в них можно с аккаунтом' in g.html
    g.get('/')
    assert 'href="/ratings"' in g.html


# ---------- Game API ----------

def test_social_api(people, app, db):
    a, a_login, a_id = people('Аня')
    a.vote(approved(db)[30], 'A')
    a.form('/communities', {'name': 'API клуб', 'rules': 'Правило.', 'access': 'open', 'icon': 'rocket', 'hue': '320'})
    slug = db.value('SELECT slug FROM communities WHERE owner_id = %s', (a_id,))
    client = app.test_client()
    r = client.get('/api/v1/ratings?board=all&community=%s' % slug).get_json()
    assert r['ok'] and [x['login'] for x in r['rows']] == [a_login] and r['rows'][0]['rank']['key']
    u = client.get('/api/v1/users/%s' % a_login).get_json()['user']
    assert u['visible'] and u['xp'] >= 10 and u['communities'][0]['slug'] == slug
    set_profile(a, 'private')
    u = client.get('/api/v1/users/%s' % a_login).get_json()['user']
    assert u == {'login': a_login, 'display_name': u['display_name'], 'visible': False, 'friends': 0}
    cs = client.get('/api/v1/communities').get_json()['communities']
    assert any(c['slug'] == slug and c['rules'] == 'Правило.' for c in cs)
    one = client.get('/api/v1/communities/%s' % slug).get_json()
    assert one['community']['people'][0]['role'] == 'owner' and 'invite_code' not in one['community']
    assert client.get('/api/v1/communities/nope').status_code == 404
    assert client.get('/api/v1/users/nope').status_code == 404
