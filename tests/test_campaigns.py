"""Story campaigns: chapters seeded out of the archive, an archive verdict carried in, bridges, the campaign's own world,
endings, the completion trophy, replays, the game API."""
import re
import secrets


def chapter_ids(db, *titles):
    return [db.value('SELECT id FROM situations WHERE title = %s ORDER BY id LIMIT 1', (t,)) for t in titles]


def choose(b, key, option):
    b.get('/campaign/%s' % key)
    return b.post('/campaign/%s' % key, {'_csrf': b.csrf(), 'action': 'choose', 'option': option})


def test_chapters_are_seeded_outside_the_archive(app, db):
    rows = db.rows("SELECT title, status FROM situations WHERE title IN ('Пленник из лагеря', 'Весенний паводок', 'Отчёт о шлюзах', 'Новая «Каира»')")
    assert {r['status'] for r in rows} == {'campaign'} and len(rows) == 4
    client = app.test_client()
    titles = [c['title'] for c in client.get('/api/v1/cases').get_json()['cases']]
    assert 'Пленник из лагеря' not in titles and 'Три ампулы' in titles
    assert db.value("SELECT COUNT(*) FROM meta WHERE meta_key LIKE 'campaign:%%'") == 2


def test_a_whole_campaign(new_browser, db):
    b = new_browser()
    b.get('/campaigns')
    assert 'Последний Рубеж' in b.html and 'Гелиос-7' in b.html
    b.get('/campaign/rubezh')
    assert 'Начать кампанию' in b.html
    b.form('/campaign/rubezh', {'action': 'start'})
    b.get('/campaign/rubezh')
    assert 'Глава 1 из 3' in b.html and 'Три ампулы' in b.html and 'К чему привели' not in b.html

    r = choose(b, 'rubezh', 'F')
    assert r.status_code == 302 and 'after=ampoules' in r.headers['Location']
    b.get(r.headers['Location'])
    assert 'Ваш вердикт' in b.html and 'Глава 2' in b.html
    assert db.value('SELECT option_key FROM votes WHERE voter = %s AND situation_id = %s',
                    (b.cookie('verdict_vid'), chapter_ids(db, 'Три ампулы')[0])) == 'F'  # an archive case: a real verdict

    b.get('/campaign/rubezh')
    assert 'Пленник из лагеря' in b.html and 'Аран и Лея ушли за стены' in b.html  # the exile carried into chapter 2
    choose(b, 'rubezh', 'A')
    b.get('/campaign/rubezh')
    assert 'Весенний паводок' in b.html and 'Тело Шеста висело у ворот' in b.html
    assert 'вместе с ним единственный человек, который знал затворы' in b.html  # chapter 1 still echoes in chapter 3
    choose(b, 'rubezh', 'A')
    b.get('/campaign/rubezh')
    assert 'Финал кампании' in b.html and 'Крепость на плотине' in b.html and 'Пройти заново' in b.html
    voter = b.cookie('verdict_vid')
    assert db.value("SELECT xp FROM gift_grants WHERE voter = %s AND source = 'campaign'", (voter,)) == 40
    assert db.value("SELECT ending FROM campaign_runs WHERE voter = %s AND campaign = 'rubezh'", (voter,)) == 'fortress'

    # a replay starts from chapter 1, doesn't change the split and gives no second trophy
    b.form('/campaign/rubezh', {'action': 'start'})
    choose(b, 'rubezh', 'B')
    assert db.value('SELECT option_key FROM votes WHERE voter = %s AND situation_id = %s',
                    (voter, chapter_ids(db, 'Три ампулы')[0])) == 'F'
    for opt in ('B', 'D'):
        choose(b, 'rubezh', opt)
    b.get('/campaign/rubezh')
    assert 'Общий дом' in b.html or 'Хрупкое равновесие' in b.html or 'Голодная весна' in b.html
    assert db.value("SELECT COUNT(*) FROM gift_grants WHERE voter = %s AND source = 'campaign'", (voter,)) == 1


def test_an_archive_verdict_is_carried_in(new_browser, db):
    b = new_browser()
    sid = chapter_ids(db, 'Протокол «Тихий час»')[0]
    _, data = b.vote(sid, 'B')
    assert 'У этой истории есть продолжение' in data['html'] and 'Гелиос-7' in data['html']
    b.form('/campaign/helios', {'action': 'start'})
    b.get('/campaign/helios')
    assert 'Отчёт о шлюзах' in b.html and 'Колония мёрзла вместе двое суток' in b.html
    b.get('/campaign/helios?after=silence')
    assert 'ваш вердикт из архива' in b.html


def test_choice_is_checked_and_chapters_stay_in_the_campaign(new_browser):
    b = new_browser()
    b.form('/campaign/rubezh', {'action': 'start'})
    r = choose(b, 'rubezh', 'Z')
    b.get(r.headers['Location'])
    assert 'Выберите один из вариантов.' in ' '.join(b.toasts())
    assert b.get('/campaign/nope').status_code == 404


def test_campaign_case_page_redirects_players(new_browser, db):
    sid = chapter_ids(db, 'Пленник из лагеря')[0]
    b = new_browser()
    r = b.get('/case/%d' % sid)
    assert r.status_code == 302 and r.headers['Location'].endswith('/campaigns')
    team = new_browser()
    team.login()
    assert team.get('/case/%d' % sid).status_code == 200


def test_campaigns_in_the_game_api(app):
    c = app.test_client()
    me = {'X-Voter-Id': secrets.token_hex(16)}
    items = c.get('/api/v1/campaigns', headers=me).get_json()['campaigns']
    assert [x['key'] for x in items] == ['rubezh', 'helios'] and items[0]['progress']['started'] is False
    assert c.post('/api/v1/campaigns/helios/choose', json={'option': 'A'}, headers=me).status_code == 422
    st = c.post('/api/v1/campaigns/helios/start', headers=me).get_json()['campaign']
    assert st['chapter']['index'] == 0 and st['chapter']['case']['allows_own_decision'] is False
    for opt in ('A', 'A', 'A'):
        r = c.post('/api/v1/campaigns/helios/choose', json={'option': opt}, headers=me).get_json()
        assert r['ok'], r
    end = r['campaign']['progress']
    assert end['finished'] and end['ending']['key'] == 'clockwork'
    assert r['campaign']['progress']['meters']['trust'] < 50
    mid = c.get('/api/v1/campaigns/helios', headers=me).get_json()['campaign']
    assert 'chapter' not in mid and mid['progress']['ending']['title'] == 'Станция под присмотром'
    assert c.post('/api/v1/campaigns/helios/start', headers=me).status_code == 200  # a replay


def test_home_page_shows_campaigns(new_browser):
    b = new_browser()
    b.get('/')
    assert 'id="campaigns"' in b.html and re.search(r'href="/campaign/rubezh"', b.html)
