"""Creator form: levels, drafts, privacy, autosave stash, submission."""
import re

from verdict.repository import situation_blank, situation_level

STORY = 'Механик говорит, что искал лекарство для больной дочери ночью у склада. ' * 6


def full(over=None):
    f = {'intent': 'submit', 'category': 'moral', 'type': 'private', 'title': 'Полная',
         'world': {'setting': '', 'place': 'Река', 'era': '', 'circumstances': 'Засуха.'}, 'story': STORY,
         'participants': [{'name': 'Аран', 'age': '', 'role': '', 'relations': '', 'description': ''}],
         'facts': ['Зерно пропало'], 'ambiguity': {'conflict': 'Ребёнок против поселения'}, 'continuation_possible': 'no',
         'decisions': [{'text': t} for t in ('Виновен', 'Невиновен', 'Простить', 'Изгнать')]}
    f.update(over or {})
    return f


def view_level(html):
    m = re.search(r'create-layout" data-level="(\d)"', html)
    return m.group(1) if m else '?'


# ---------- Levels ----------

def test_level_rules():
    idea = {**situation_blank(), 'category': 'moral', 'title': 'T', 'story': 'слово ' * 20,
            'decisions': [{'text': 'A'}, {'text': 'B'}]}
    assert situation_level(idea) == 1
    assert situation_level({**idea, 'story': 'слово ' * 19}) == 0
    assert situation_level({**idea, 'decisions': [{'text': 'A'}]}) == 0
    assert situation_level({**idea, 'category': ''}) == 0


def test_demo_cases_are_at_least_level_2(app):
    with app.app_context():
        from verdict.repository import situations_list
        levels = [situation_level(s) for s in situations_list()]
    assert len(levels) == 52 and min(levels) >= 2  # 48 cases + 4 chapters of campaigns


def test_levels_through_the_form(browser, db):
    browser.register('Уровни')
    browser.get('/create')
    assert view_level(browser.html) == '1'
    assert browser.html.count('data-level-tab=') == 3
    assert browser.html.count('decision-item') == 4  # 3 rows + the <template>
    assert 'data-level-next' in browser.html

    story = 'Ночью пропал мешок зерна со склада поселения, и охранник нашёл у ворот обрывок плаща механика, который просит о снисхождении ради больной дочери.'
    r = browser.form('/create', {'intent': 'draft', 'category': 'survival', 'type': 'private', 'title': 'Мешок зерна',
                                 'story': story, 'decisions': [{'text': 'Простить'}, {'text': 'Наказать'}, {'text': ''}]})
    location = r.headers['Location']
    assert re.fullmatch(r'/create/\d+', location)
    browser.get(location)
    assert 'готов уровень 1 из 3' in browser.html
    assert view_level(browser.html) == '2'
    assert browser.html.count('level-step is-done') == 1
    browser.get('/library?status=draft')
    assert 'Ур. 1 · Идея' in browser.html

    r = browser.form('/create', {'intent': 'draft', 'title': 'Только название'})
    browser.get(r.headers['Location'])
    assert view_level(browser.html) == '1'
    browser.get('/account')
    assert 'Набросок' in browser.html

    browser.form('/create', {'intent': 'submit', 'title': 'Сразу на отбор', 'story': 'коротко'})
    assert view_level(browser.html) == '2' and len(browser.errors()) > 3

    browser.get('/view/1')
    assert re.search(r'chip-level lvl-[23]', browser.html)


# ---------- Drafts ----------

def test_drafts(new_browser, db):
    a = new_browser()
    a.register('Автор А')
    a.get('/create')
    assert 'data-intent-value="draft"' in a.html
    assert re.search(r'data-autosave="verdict:create:u\d+:new"', a.html)

    a.post('/create', {'_csrf': a.csrf(), 'intent': 'draft', 'title': '', 'story': 'идея'})
    assert 'Дайте черновику название' in a.html

    r = a.post('/create', {'_csrf': a.csrf(), 'intent': 'draft', 'title': 'Идея про зерно 23636', 'story': 'Короткая идея.'})
    assert r.status_code == 302 and r.headers['Location'].startswith('/create/')
    draft_id = int(r.headers['Location'].rsplit('/', 1)[1])
    a.get(r.headers['Location'])
    assert 'Черновик: Идея про зерно 23636' in a.html and 'сохранён' in a.html
    assert 'data-autosave-clear=' in a.html and ':new&#34;]' in a.html
    assert 'Короткая идея.' in a.html

    r = a.post('/create/%d' % draft_id, {'_csrf': a.csrf(), 'intent': 'draft', 'title': 'Идея про зерно 23636',
                                          'story': 'Длиннее идея.', 'category': 'crime'})
    assert r.headers['Location'] == '/create/%d' % draft_id
    a.get('/library?status=draft')
    assert 'Идея про зерно 23636' in a.html and 'Черновики' in a.html
    a.get('/library')
    assert 'Идея про зерно 23636' not in a.html
    a.get('/account')
    assert '/create/%d">Идея про зерно 23636' % draft_id in a.html

    a.form('/create/%d' % draft_id, {'intent': 'submit', 'title': 'Идея про зерно 23636'})
    assert a.html and len(a.errors()) >= 5
    r = a.post('/create/%d' % draft_id, {'_csrf': a.csrf(), **full({'title': 'Идея про зерно 23636'})})
    assert r.headers['Location'] == '/view/%d' % draft_id
    a.get('/view/%d' % draft_id)
    assert 'status-pending' in a.html

    r = a.form('/create', {'intent': 'draft', 'title': 'Секретный черновик 8315'})
    secret = int(r.headers['Location'].rsplit('/', 1)[1])

    b = new_browser()
    b.register('Автор Б')
    assert b.get('/view/%d' % secret).status_code == 302
    assert b.get('/case/%d' % secret).status_code == 404
    r = b.get('/create/%d' % secret)
    assert r.status_code == 302 and r.headers['Location'] != '/create/%d' % secret
    b.get('/library?status=draft')
    assert 'Секретный черновик 8315' not in b.html
    b.form('/action', {'id': secret, 'action': 'delete'}, page='/library')
    assert db.value('SELECT COUNT(*) FROM situations WHERE id = %s', (secret,)) == 1
    assert b.get('/quick/%d' % secret).headers['Location'] == '/quick'

    a.get('/view/%d' % secret)
    assert 'Удалить черновик' in a.html
    r = a.post('/action', {'_csrf': a.csrf(), 'id': secret, 'action': 'delete'})
    assert r.headers['Location'] == '/account'
    assert a.get('/view/%d' % secret).status_code == 302
    a.form('/action', {'id': draft_id, 'action': 'delete'}, page='/library')
    assert a.get('/view/%d' % draft_id).status_code == 200  # an author can't delete a case on review


def test_text_survives_an_expired_session(new_browser):
    a = new_browser()
    login = a.register('Сессия')
    a.get('/create')
    a.client.delete_cookie('verdict_sid')
    r = a.post('/create', {'_csrf': 'x', **full({'title': 'Написано до конца сессии'})})
    assert r.headers['Location'].startswith('/login?back=/create')
    r = a.form('/login', {'login': login, 'password': 'password123', 'back': '/create'})
    assert r.headers['Location'] == '/create'
    a.get('/create')
    assert 'Написано до конца сессии' in a.html and 'Мы вернули текст' in a.html
    assert 'data-fresh-input' in a.html
    a.get('/create')
    assert 'Мы вернули текст' not in a.html


def test_full_submission_and_moderation(new_browser, db):
    a = new_browser()
    a.register('Автор В')
    r = a.form('/create', full({'title': 'Сразу на отбор', 'type': 'witness',
                                'witnesses': [{'name': 'Агафья', 'claim': 'Видела механика', 'trust': '', 'interest': ''}],
                                'checklist': [0, 1, 99]}))
    sid = int(r.headers['Location'].rsplit('/', 1)[1])
    data = db.data(sid)
    assert data['author'] == 'Автор В' and data['checklist'] == [0, 1]
    assert [d['key'] for d in data['decisions']] == ['A', 'B', 'C', 'D'] and all(d['uid'] for d in data['decisions'])
    assert db.value('SELECT status FROM situations WHERE id = %s', (sid,)) == 'pending'

    team = new_browser()
    team.login()
    r = team.form('/action', {'id': sid, 'action': 'approved', 'back': '/view/%d' % sid}, page='/view/%d' % sid)
    assert r.headers['Location'] == '/view/%d' % sid
    assert db.value('SELECT status FROM situations WHERE id = %s', (sid,)) == 'approved'
    a.get('/view/%d' % sid)
    assert 'Она уже прошла отбор' in a.html
    assert a.get('/create/%d' % sid).status_code == 302  # approved: only the team edits


def test_private_case_drops_witnesses(browser, db):
    browser.register('Автор Г')
    r = browser.form('/create', full({'title': 'Без свидетелей',
                                      'witnesses': [{'name': 'Лишний', 'claim': 'Не должен сохраниться'}]}))
    sid = int(r.headers['Location'].rsplit('/', 1)[1])
    assert db.data(sid)['witnesses'] == []


def test_csrf_is_required(browser):
    browser.register('Автор Д')
    browser.get('/create')
    browser.post('/create', full({'_csrf': 'wrong', 'title': 'Подделка'}))
    assert 'Сессия устарела' in browser.html
