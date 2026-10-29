"""Security quick wins: per-login lockout, the sign-up brake, game tokens that expire and end with a new password,
the team's password reset and default-password warning, the Secure player cookie, campaign chapters on the board."""
import re
import secrets
from datetime import datetime, timedelta, timezone


def test_web_login_is_locked_per_login_not_per_browser(new_browser):
    owner = new_browser()
    login = owner.register('Жертва')
    for _ in range(10):  # each attempt from a fresh browser: the session lock never sees more than one
        new_browser().form('/login', {'login': login, 'password': 'wrong-password', 'back': ''})
    late = new_browser()
    late.form('/login', {'login': login, 'password': 'password123', 'back': ''})
    assert 'Слишком много неудачных попыток войти в этот аккаунт' in late.html
    assert late.cookie('verdict_sid') is None or '/account' not in late.html


def test_signup_brake(new_browser, app, db):
    bot = new_browser()
    login = 'bot' + secrets.token_hex(3)
    bot.form('/register', {'login': login, 'display_name': 'Бот', 'password': 'password123', 'password_confirm': 'password123',
                           'website': 'http://spam.example', 'back': ''})
    assert 'Не удалось создать аккаунт' in bot.html
    assert db.value('SELECT COUNT(*) FROM users WHERE login = %s', (login,)) == 0
    cfg = app.config['VERDICT']
    cfg['min_signup_seconds'] = 30
    try:
        fast = new_browser()
        fast.form('/register', {'login': login, 'display_name': 'Быстрый', 'password': 'password123',
                                'password_confirm': 'password123', 'back': ''})
        assert 'Не удалось создать аккаунт' in fast.html
        assert db.value('SELECT COUNT(*) FROM users WHERE login = %s', (login,)) == 0
    finally:
        cfg['min_signup_seconds'] = 0
    person = new_browser()
    person.form('/register', {'login': login, 'display_name': 'Человек', 'password': 'password123',
                              'password_confirm': 'password123', 'back': ''})
    assert db.value('SELECT COUNT(*) FROM users WHERE login = %s', (login,)) == 1


def api_sign_up(app):
    c = app.test_client()
    login = 'g' + secrets.token_hex(4)
    out = c.post('/api/v1/auth/register', json={'login': login, 'display_name': 'Игрок', 'password': 'password123'}).get_json()
    return c, login, out['token'], out['user']['id']


def test_game_tokens_expire(app, db):
    c, _, token, uid = api_sign_up(app)
    auth = {'Authorization': 'Bearer ' + token}
    assert c.get('/api/v1/me', headers=auth).status_code == 200
    old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=91)
    db.rows('UPDATE api_tokens SET used_at = %s WHERE user_id = %s', (old, uid))
    assert c.get('/api/v1/me', headers=auth).status_code == 401
    assert db.value('SELECT COUNT(*) FROM api_tokens WHERE user_id = %s', (uid,)) == 0


def test_new_password_signs_out_the_game(app, new_browser, db):
    c, login, token, uid = api_sign_up(app)
    b = new_browser()
    b.login(login, 'password123')
    b.form('/account', {'action': 'password', 'current_password': 'password123', 'new_password': 'another-pass-1',
                        'new_password_confirm': 'another-pass-1'})
    assert c.get('/api/v1/me', headers={'Authorization': 'Bearer ' + token}).status_code == 401


def test_team_resets_a_password(app, new_browser, db):
    c, login, token, uid = api_sign_up(app)
    voter = c.get('/api/v1/me', headers={'Authorization': 'Bearer ' + token}).get_json()['voter_id']
    team = new_browser()
    team.login()
    team.form('/admin/players/%s' % voter, {'action': 'password'})
    team.get('/admin/players/%s' % voter)
    new = re.search(r'Новый пароль для @%s: (\S+) —' % login, ' '.join(team.toasts())).group(1)
    assert c.get('/api/v1/me', headers={'Authorization': 'Bearer ' + token}).status_code == 401
    old = new_browser()
    old.form('/login', {'login': login, 'password': 'password123', 'back': ''})
    assert 'Неверный логин или пароль' in old.html
    fresh = new_browser()
    r = fresh.form('/login', {'login': login, 'password': new, 'back': ''})
    assert r.status_code == 302


def test_default_admin_password_warning(new_browser):
    team = new_browser()
    team.login()  # the test database keeps the setup password
    team.get('/admin/')
    assert 'всё ещё стандартный пароль' in team.html


def test_player_cookie_is_secure_on_https(app):
    def vid(base):
        cookies = app.test_client().get('/', base_url=base).headers.getlist('Set-Cookie')
        return next(c for c in cookies if c.startswith('verdict_vid='))
    assert 'Secure' not in vid('http://localhost') and 'Secure' in vid('https://localhost')


def test_campaign_chapters_stay_out_of_moderation(new_browser, db):
    sid = db.value("SELECT id FROM situations WHERE status = 'campaign' ORDER BY id LIMIT 1")
    team = new_browser()
    team.login()
    team.get('/view/%d' % sid)
    assert 'name="action" value="approved"' not in team.html and 'status-campaign' in team.html
    team.form('/action', {'id': str(sid), 'action': 'approved', 'back': '/view/%d' % sid}, page='/view/%d' % sid)
    assert db.value('SELECT status FROM situations WHERE id = %s', (sid,)) == 'campaign'
    team.get('/view/%d' % sid)
    assert 'глава сюжетной кампании' in ' '.join(team.toasts())


def sign_up_api(c, ip=None):
    env = {'REMOTE_ADDR': ip} if ip else {}
    return c.post('/api/v1/auth/register', json={'login': 'b' + secrets.token_hex(4), 'display_name': 'Бот',
                                                 'password': 'password123'}, environ_base=env)


def test_signup_limits(app, db, new_browser):
    """Per address only for real (public) addresses; the hourly total for everyone; the web form and the API alike."""
    cfg = app.config['VERDICT']
    c = app.test_client()
    db.rows('DELETE FROM signup_log')
    cfg['max_signups_per_ip'] = 2
    try:
        assert [sign_up_api(c, '93.184.216.34').status_code for _ in range(3)] == [200, 200, 429]
        assert 'С этого адреса' in sign_up_api(c, '93.184.216.34').get_json()['error']
        assert sign_up_api(c, '93.184.216.35').status_code == 200  # another address
        assert [sign_up_api(c).status_code for _ in range(3)] == [200, 200, 200]  # 127.0.0.1: can't tell visitors apart
        assert db.value('SELECT COUNT(*) FROM signup_log') == 6  # addresses only as a hash
        assert db.value("SELECT COUNT(*) FROM signup_log WHERE ip_hash LIKE '93.%%'") == 0
        cfg['max_signups_per_hour'] = 6
        assert sign_up_api(c, '198.51.100.7').status_code == 429
        b = new_browser()
        b.form('/register', {'login': 'w' + secrets.token_hex(4), 'display_name': 'Человек', 'password': 'password123',
                             'password_confirm': 'password123', 'back': ''})
        assert 'слишком много новых аккаунтов' in b.html
    finally:
        cfg['max_signups_per_ip'] = cfg['max_signups_per_hour'] = 0


def test_trusted_proxy_address(app):
    from verdict import signups
    cfg = app.config['VERDICT']
    with app.test_request_context('/', environ_base={'REMOTE_ADDR': '127.0.0.1'},
                                  headers={'X-Forwarded-For': '10.0.0.1, 93.184.216.34'}):
        assert signups.client_ip() == '127.0.0.1' and not signups.is_public('127.0.0.1')
        cfg['trusted_proxies'] = 1
        try:
            assert signups.client_ip() == '93.184.216.34' and signups.is_public(signups.client_ip())
        finally:
            cfg['trusted_proxies'] = 0


def test_admin_sees_what_address_the_site_sees(new_browser):
    team = new_browser()
    team.login()
    team.get('/admin/game')
    assert 'Сайт видит ваш адрес как' in team.html and 'ограничение по адресу отключено' in team.html


def test_health(app, monkeypatch):
    c = app.test_client()
    r = c.get('/health')
    body = r.get_json()
    assert r.status_code == 200 and body['ok'] and body['database'] == 'ok' and body['schema'] == body['expected_schema']
    assert r.headers['Cache-Control'] == 'no-store'
    import verdict.db as dbmod

    def down(*_a, **_k):
        raise dbmod.DatabaseUnavailable('test')
    monkeypatch.setattr(dbmod, 'scalar', down)
    r = c.get('/health')
    assert r.status_code == 503 and r.get_json()['ok'] is False
