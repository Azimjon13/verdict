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
