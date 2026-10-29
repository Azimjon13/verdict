"""Every page renders, old PHP links redirect, headers and access rules hold."""
import pytest


PUBLIC = ['/', '/play', '/play?category=crime', '/quick', '/quick/1', '/case/1', '/judge', '/judge?a=wise', '/brief',
          '/library', '/library?status=approved&sort=heat', '/library?sort=title', '/view/1', '/login', '/register']


@pytest.mark.parametrize('url', PUBLIC)
def test_public_pages_render(browser, url):
    r = browser.get(url)
    assert r.status_code == 200, url
    assert '</html>' in browser.html
    assert r.headers['X-Content-Type-Options'] == 'nosniff'
    assert r.headers['X-Frame-Options'] == 'SAMEORIGIN'


@pytest.mark.parametrize('url', ['/create', '/account', '/users'])
def test_private_pages_ask_to_log_in(browser, url):
    r = browser.get(url)
    assert r.status_code == 302
    assert r.headers['Location'].startswith('/login?back=')


@pytest.mark.parametrize('url', ['/create', '/create/1', '/account', '/users', '/library', '/view/27'])
def test_team_pages_render(browser, url):
    browser.login()
    assert browser.get(url).status_code == 200, url


DEMO = "author IN ('Команда VERDICT', 'Демо-автор')"


def test_seeded_content(db):
    assert db.value("SELECT COUNT(*) FROM situations WHERE " + DEMO) == 52  # 48 cases + 4 chapters of campaigns
    assert db.value("SELECT COUNT(*) FROM situations WHERE status = 'campaign' AND " + DEMO) == 4
    assert db.value("SELECT COUNT(*) FROM situations WHERE status = 'approved' AND " + DEMO) == 46
    assert db.value("SELECT COUNT(*) FROM situations WHERE user_id IS NULL AND author = 'Команда VERDICT'") == 0
    assert db.value("SELECT meta_value FROM meta WHERE meta_key = 'seed_version'") == '3'
    assert db.value("SELECT meta_value FROM meta WHERE meta_key = 'schema_version'") == '8'


@pytest.mark.parametrize('old, new', [
    ('/index.php', '/'), ('/case.php?id=3', '/case/3'), ('/view.php?id=7', '/view/7'), ('/create.php?edit=5', '/create/5'),
    ('/quick.php?id=2', '/quick/2'), ('/quick.php', '/quick'), ('/library.php?status=approved', '/library?status=approved'),
    ('/play.php?category=crime', '/play?category=crime'), ('/judge.php?a=wise', '/judge?a=wise'), ('/case.php', '/play'),
])
def test_old_php_links_redirect(browser, old, new):
    r = browser.get(old)
    assert r.status_code == 301
    assert r.headers['Location'] == new


def test_old_vote_endpoint_keeps_post(browser):
    r = browser.client.post('/api/vote.php', data={'x': '1'})
    assert r.status_code == 307 and r.headers['Location'] == '/api/vote'


def test_missing_things(browser):
    assert browser.get('/case/99999').status_code == 404
    assert 'Дело не найдено' in browser.html
    assert browser.get('/no-such-page').status_code == 404
    r = browser.get('/view/99999')
    assert r.status_code == 302 and r.headers['Location'] == '/library'


def test_assets_are_served_with_version(browser):
    browser.get('/')
    assert '/assets/css/style.css?v=' in browser.html
    r = browser.get('/assets/js/app.js')
    assert r.status_code == 200 and 'document' in browser.html


def test_vote_url_is_given_to_scripts(browser):
    browser.get('/case/1')
    assert 'data-vote-url="/api/vote"' in browser.html


def test_export_is_team_only(browser, db):
    r = browser.get('/api/export')
    assert r.status_code == 403
    browser.login()
    r = browser.get('/api/export?status=all')
    data = r.get_json()
    assert r.headers['Content-Disposition'].startswith('attachment; filename="verdict-situations-')
    assert data['count'] == db.value('SELECT COUNT(*) FROM situations') and data['situations'][0]['id'] == 1
    assert browser.get('/api/export').get_json()['count'] == db.value("SELECT COUNT(*) FROM situations WHERE status = 'approved'")
    one = browser.get('/api/export?id=2').get_json()
    assert one['count'] == 1 and isinstance(one['situations'][0]['votes'], dict)


def test_back_parameter_only_accepts_own_pages(browser):
    r = browser.form('/login', {'login': 'admin', 'password': 'verdict-admin', 'back': 'https://evil.example/'})
    assert r.headers['Location'] == '/library'
    assert browser.get('/login?back=//evil.example').headers['Location'] == '/library'
    assert browser.get('/login?back=/view/3').headers['Location'] == '/view/3'
