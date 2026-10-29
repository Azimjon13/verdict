"""Accounts: registration, login lockout, PHP password hashes, sessions in MySQL, roles."""
from verdict.auth import check_password, hash_password

# password_hash('test-password', PASSWORD_DEFAULT) from PHP 8.2 — accounts created by the PHP site keep working.
PHP_HASH = '$2y$10$.C.dP1IIA3DV9F01VqlLgu.R8poQu/.2GyHZUWR.5zsjk3PZjg7AS'


def test_php_password_hashes():
    assert check_password('test-password', PHP_HASH)
    assert not check_password('wrong', PHP_HASH)
    h = hash_password('пароль-123')
    assert h.startswith('$2y$10$') and check_password('пароль-123', h)
    assert check_password('x' * 80, hash_password('x' * 72))  # bcrypt reads 72 bytes, as PHP did
    assert not check_password('anything', '') and not check_password('anything', 'plain')


def test_registration_rules(browser, db):
    browser.form('/register', {'login': 'a', 'display_name': 'Я', 'password': 'short', 'password_confirm': 'other', 'back': ''})
    errors = browser.errors()
    assert any('Логин: 3–40 символов' in e for e in errors)
    assert any('Имя или ник: от 2 до 80 символов' in e for e in errors)
    assert any('не короче 8 символов' in e for e in errors)
    browser.form('/register', {'login': 'admin', 'display_name': 'Ещё админ', 'password': 'password123',
                               'password_confirm': 'password123', 'back': ''})
    assert any('Такой логин уже занят' in e for e in browser.errors())
    r = browser.form('/register', {'login': 'newauthor', 'display_name': 'Новый автор', 'password': 'password123',
                                   'password_confirm': 'password123', 'back': '/library'})
    assert r.headers['Location'] == '/library'
    user = db.one("SELECT role, password_hash FROM users WHERE login = 'newauthor'")
    assert user['role'] == 'author' and user['password_hash'].startswith('$2y$')


def test_login_lockout(browser):
    for _ in range(5):
        browser.form('/login', {'login': 'admin', 'password': 'nope', 'back': ''})
        assert 'Неверный логин или пароль' in browser.html
    browser.form('/login', {'login': 'admin', 'password': 'verdict-admin', 'back': ''})
    assert 'Слишком много неудачных попыток' in browser.html


def test_login_logout_and_session_rows(new_browser, db):
    a = new_browser()
    login = a.register('Сеансы')
    sid_before = a.cookie('verdict_sid')
    uid = db.value('SELECT id FROM users WHERE login = %s', (login,))
    assert db.value('SELECT user_id FROM sessions WHERE id = %s', (sid_before,)) == uid

    b = new_browser()
    b.form('/login', {'login': login, 'password': 'password123', 'back': ''})
    b.get('/account')
    assert '2 активных сеанса' in b.html

    # Changing the password ends the other sessions.
    r = b.form('/account', {'action': 'password', 'current_password': 'password123', 'new_password': 'password456',
                            'new_password_confirm': 'password456'})
    assert r.headers['Location'] == '/account'
    b.get('/account')
    assert 'Другие сеансы входа завершены: 1' in b.html and '1 активный сеанс' in b.html
    assert a.get('/account').status_code == 302  # a's session is gone

    b.form('/account', {'action': 'name', 'display_name': 'Новое имя'})
    b.get('/account')
    assert 'Новое имя' in b.html
    old_sid = b.cookie('verdict_sid')
    b.form('/logout', {}, page='/account')
    assert b.cookie('verdict_sid') != old_sid
    assert db.value('SELECT COUNT(*) FROM sessions WHERE id = %s', (old_sid,)) == 0
    assert b.get('/account').status_code == 302


def test_roles(new_browser, db):
    author = new_browser()
    login = author.register('Будущий член команды')
    uid = db.value('SELECT id FROM users WHERE login = %s', (login,))
    assert author.get('/users').headers['Location'] == '/account'

    team = new_browser()
    team.login()
    team.form('/users', {'id': uid, 'role': 'admin'})
    assert db.value('SELECT role FROM users WHERE id = %s', (uid,)) == 'admin'
    assert author.get('/users').status_code == 200
    team.form('/users', {'id': uid, 'role': 'author'})
    assert db.value('SELECT role FROM users WHERE id = %s', (uid,)) == 'author'

    admin_id = db.value("SELECT id FROM users WHERE login = 'admin'")
    if db.value("SELECT COUNT(*) FROM users WHERE role = 'admin'") == 1:
        team.form('/users', {'id': admin_id, 'role': 'author'})
        team.get('/users')
        assert 'Нельзя снять права с последнего участника команды' in team.html
        assert db.value('SELECT role FROM users WHERE id = %s', (admin_id,)) == 'admin'


def test_hidden_info_visibility(new_browser):
    anon = new_browser()
    anon.get('/view/1')
    assert 'Засекречено' in anon.html
    team = new_browser()
    team.login()
    team.get('/view/1')
    assert 'Засекречено' not in team.html
