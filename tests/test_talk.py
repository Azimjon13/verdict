"""Discussion under a case: open only after a verdict, accounts write (with their verdict), others back comments,
filters by friends and community, limits, the team hides, reports, the result screen teaser, and the game API."""
import re
import secrets

import pytest

from verdict import talk


@pytest.fixture
def people(new_browser, db):
    def make(name='Судья'):
        b = new_browser()
        login = b.register(name + ' ' + secrets.token_hex(2))
        return b, login, int(db.value('SELECT id FROM users WHERE login = %s', (login,)))
    return make


@pytest.fixture
def case(db):
    """A case in play nobody has discussed yet."""
    return db.value("SELECT s.id FROM situations s LEFT JOIN comments c ON c.situation_id = s.id"
                    " WHERE s.status = 'approved' AND c.id IS NULL ORDER BY s.id DESC LIMIT 1")


def say(b, sid, text):
    return b.form('/talk/%d' % sid, {'action': 'post', 'text': text})


def ids_on_page(b, sid, query=''):
    b.get('/talk/%d%s' % (sid, query))
    return [int(x) for x in re.findall(r'<li id="c(\d+)"', b.html)]


def test_judge_first_then_talk(people, new_browser, db, case):
    a, a_login, a_id = people('Аня')
    a.get('/talk/%d' % case)
    assert 'Обсуждение откроется после вашего вердикта' in a.html and 'name="text"' not in a.html
    r = say(a, case, 'Мне кажется, всё ясно.')
    assert db.value('SELECT COUNT(*) FROM comments WHERE situation_id = %s', (case,)) == 0 and r.status_code in (200, 302)
    a.vote(case, 'B')
    r = say(a, case, 'Выбрал B: закон один для всех,\n\nдаже для царя.')
    assert r.status_code == 302 and r.headers['Location'].endswith('#c%d' % db.value('SELECT MAX(id) FROM comments'))
    row = db.one('SELECT * FROM comments WHERE situation_id = %s', (case,))
    assert (row['user_id'], row['option_key'], row['status']) == (a_id, 'B', 'visible')
    a.get('/talk/%d' % case)
    assert 'закон один для всех' in a.html and '<p>даже для царя.</p>' in a.html and 'Ваш вердикт' in a.html

    guest = new_browser()
    guest.get('/talk/%d' % case)
    assert 'Обсуждение откроется' in guest.html  # a guest who hasn't judged doesn't see it
    guest.vote(case, 'A')
    guest.get('/talk/%d' % case)
    assert 'закон один для всех' in guest.html and 'Войдите' in guest.html and 'name="text"' not in guest.html
    assert guest.get('/talk/999999').status_code == 404


def test_result_screen_shows_the_discussion(people, db, case):
    a, _, _ = people('Аня')
    a.vote(case, 'A')
    say(a, case, 'Короткий довод в пользу A.')
    b, _, _ = people('Боря')
    status, out = b.vote(case, 'B')
    assert status == 200 and 'Обсуждение' in out['html'] and 'Короткий довод в пользу A.' in out['html']
    assert '/talk/%d' % case in out['html']


def test_limits(people, db, case, monkeypatch):
    a, _, a_id = people('Аня')
    a.vote(case, 'A')
    say(a, case, 'а')
    assert 'хотя бы пару слов' in a.html and db.value('SELECT COUNT(*) FROM comments WHERE user_id = %s', (a_id,)) == 0
    say(a, case, 'х' * (talk.MAX_LEN + 1))
    assert 'Слишком длинно' in a.html
    say(a, case, 'Первый довод.')
    say(a, case, 'Второй довод сразу же.')
    assert 'Не так быстро' in a.html and 'Второй довод сразу же.' in a.html  # the text stays in the form
    monkeypatch.setattr(talk, 'GAP_SECONDS', 0)
    monkeypatch.setattr(talk, 'PER_DAY', 2)
    say(a, case, 'Второй довод.')
    say(a, case, 'Третий довод.')
    assert 'не больше 2 комментариев в день' in a.html
    monkeypatch.setattr(talk, 'PER_DAY', 30)
    b, _, b_id = people('Боря')
    b.vote(case, 'B')
    db.rows('UPDATE players SET blocked = 1 WHERE user_id = %s', (b_id,))  # the team barred Боря
    try:
        say(b, case, 'Можно мне сказать?')
        assert 'Команда закрыла вам обсуждения' in b.html
        assert db.value('SELECT COUNT(*) FROM comments WHERE user_id = %s', (b_id,)) == 0
        first = db.value('SELECT MIN(id) FROM comments WHERE user_id = %s', (a_id,))
        b.form('/talk/%d' % case, {'action': 'like', 'comment_id': str(first)})
        assert db.value('SELECT likes FROM comments WHERE id = %s', (first,)) == 0
    finally:
        db.rows('UPDATE players SET blocked = 0 WHERE user_id = %s', (b_id,))


def test_backing_sorting_and_notifications(people, db, case):
    a, _, a_id = people('Аня')
    b, _, b_id = people('Боря')
    c, _, _ = people('Вера')
    for p, opt in ((a, 'A'), (b, 'B'), (c, 'A')):
        p.vote(case, opt)
    say(a, case, 'Довод Ани.')
    say(b, case, 'Довод Бори.')
    first, second = [r['id'] for r in db.rows('SELECT id FROM comments WHERE situation_id = %s ORDER BY id', (case,))]
    a.form('/talk/%d' % case, {'action': 'like', 'comment_id': str(first)})  # one's own: no
    c.form('/talk/%d' % case, {'action': 'like', 'comment_id': str(first)})
    c.form('/talk/%d' % case, {'action': 'like', 'comment_id': str(first)})  # twice: once
    b.form('/talk/%d' % case, {'action': 'like', 'comment_id': str(first)})
    assert db.value('SELECT likes FROM comments WHERE id = %s', (first,)) == 2
    note = db.one("SELECT text, link FROM notifications WHERE user_id = %s AND kind = 'comment_liked'", (a_id,))
    assert 'поддержали: 1' in note['text'] and note['link'] == '/talk/%d#c%d' % (case, first)
    assert ids_on_page(c, case) == [first, second] and ids_on_page(c, case, '?sort=new') == [second, first]
    c.get('/talk/%d' % case)
    assert 'aria-pressed="true"' in c.html and 'как вы' in c.html  # Вера judged like Аня
    b.form('/talk/%d' % case, {'action': 'unlike', 'comment_id': str(first)})
    assert db.value('SELECT likes FROM comments WHERE id = %s', (first,)) == 1
    c.form('/talk/%d' % case, {'action': 'delete', 'comment_id': str(second)})  # not hers
    b.form('/talk/%d' % case, {'action': 'delete', 'comment_id': str(second)})
    assert db.value('SELECT COUNT(*) FROM comments WHERE situation_id = %s', (case,)) == 1


def test_friends_and_community_filters(people, db, case):
    a, a_login, a_id = people('Аня')
    b, b_login, b_id = people('Боря')
    c, _, c_id = people('Вера')
    for p in (a, b, c):
        p.vote(case, 'A')
        say(p, case, 'Мой довод, %s.' % secrets.token_hex(2))
    mine = {u: db.value('SELECT id FROM comments WHERE user_id = %s AND situation_id = %s', (u, case)) for u in (a_id, b_id, c_id)}
    a.form('/u/%s' % b_login, {'action': 'add'})
    b.form('/u/%s' % a_login, {'action': 'add'})
    assert sorted(ids_on_page(a, case, '?scope=friends')) == sorted([mine[a_id], mine[b_id]])
    c.form('/communities', {'name': 'Спорщики ' + secrets.token_hex(2), 'rules': '', 'access': 'open', 'icon': 'users', 'hue': '190'})
    slug = db.value('SELECT slug FROM communities WHERE owner_id = %s', (c_id,))
    assert ids_on_page(a, case, '?scope=c:' + slug) == [mine[c_id]]


def test_team_hides_and_reports(people, new_browser, db, case):
    a, _, a_id = people('Аня')
    r, _, r_id = people('Рита')
    for p in (a, r):
        p.vote(case, 'A')
    say(a, case, 'Грубый довод, который нарушает правила.')
    cid = db.value('SELECT id FROM comments WHERE user_id = %s', (a_id,))
    r.get('/talk/%d' % case)
    r.post('/report', {'_csrf': r.csrf(), 'target_type': 'comment', 'target_id': str(cid), 'reason': 'abuse', 'text': '',
                       'back': '/talk/%d' % case})
    rid = db.value("SELECT id FROM reports WHERE target_type = 'comment' AND target_id = %s", (cid,))
    team = new_browser()
    team.login()
    team.get('/admin/reports')
    assert 'Грубый довод' in team.html and 'Скрыть комментарий' in team.html
    team.form('/admin/reports', {'action': 'hide_comment', 'id': str(rid), 'target_id': str(cid)})
    assert db.value('SELECT status FROM comments WHERE id = %s', (cid,)) == 'hidden'
    assert db.value('SELECT status FROM reports WHERE id = %s', (rid,)) == 'resolved'
    assert db.value("SELECT COUNT(*) FROM notifications WHERE user_id = %s AND kind = 'comment_hidden'", (a_id,)) == 1
    assert cid not in ids_on_page(r, case)
    assert cid in ids_on_page(team, case)  # the team still sees it, marked
    team.get('/admin/talk?status=hidden')
    assert 'Грубый довод' in team.html
    team.form('/admin/talk?status=hidden', {'action': 'show', 'comment_id': str(cid)})
    assert cid in ids_on_page(r, case)
    team.form('/talk/%d' % case, {'action': 'remove', 'comment_id': str(cid)})
    assert db.value('SELECT COUNT(*) FROM comments WHERE id = %s', (cid,)) == 0
    r.form('/talk/%d' % case, {'action': 'remove', 'comment_id': '1'})  # players can't


def test_talk_api(app, db, case):
    c = app.test_client()
    out = [c.post('/api/v1/auth/register', json={'login': 't' + secrets.token_hex(4), 'display_name': n,
                                                  'password': 'password123'}).get_json() for n in ('Пётр', 'Ольга')]
    p, o = ({'Authorization': 'Bearer ' + x['token']} for x in out)
    r = c.get('/api/v1/cases/%d/comments' % case, headers=p)
    assert r.status_code == 403 and 'count' in r.get_json()
    assert c.post('/api/v1/cases/%d/comments' % case, json={'text': 'Рано.'}, headers=p).get_json()['code'] == 'judge'
    for h in (p, o):
        c.post('/api/v1/cases/%d/verdict' % case, json={'option': 'A'}, headers=h)
    assert c.post('/api/v1/cases/%d/comments' % case, json={'text': 'Без входа.'}).status_code == 401
    got = c.post('/api/v1/cases/%d/comments' % case, json={'text': 'Довод из игры.'}, headers=p).get_json()
    assert got['ok'] and got['comment']['option'] == 'A' and got['comment']['mine'] is True
    cid = got['comment']['id']
    assert c.post('/api/v1/cases/%d/comments' % case, json={'text': 'Ещё один.'}, headers=p).status_code == 429
    assert c.post('/api/v1/comments/%d/like' % cid, headers=o).get_json() == {'ok': True, 'done': True, 'likes': 1}
    listed = c.get('/api/v1/cases/%d/comments?sort=new' % case, headers=o).get_json()
    assert listed['my_verdict'] == 'A' and listed['comments'][0]['liked'] is True and listed['comments'][0]['author']['display_name'] == 'Пётр'
    assert c.post('/api/v1/comments/%d/delete' % cid, headers=o).get_json()['done'] is False
    assert c.post('/api/v1/comments/%d/delete' % cid, headers=p).get_json()['done'] is True
    assert c.get('/api/v1/cases/%d/comments' % case, headers=o).get_json()['count'] == 0
