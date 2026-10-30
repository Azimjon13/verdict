"""The Telegram bot, against a fake Telegram: the team connects it, a player links a chat with a one-time code,
notifications follow to Telegram after the page is answered, commands, the case-of-the-day reminder from cron,
and a new password through a one-time link."""
import re
import secrets
from datetime import datetime, timezone

import pytest

from verdict import telegram


class FakeTelegram:
    def __init__(self):
        self.calls = []

    def __call__(self, url, payload, timeout):
        method = url.rsplit('/', 1)[1]
        self.calls.append((method, payload))
        if method == 'getMe':
            return {'ok': True, 'result': {'id': 1, 'username': 'verdict_test_bot'}}
        if method == 'sendMessage' and payload.get('chat_id') == 666:
            return {'ok': False, 'description': 'Forbidden: bot was blocked by the user'}
        return {'ok': True, 'result': True}

    def sent(self, chat_id=None):
        return [p for m, p in self.calls if m == 'sendMessage' and (chat_id is None or p['chat_id'] == chat_id)]


@pytest.fixture
def tg(app, monkeypatch, db):
    fake = FakeTelegram()
    monkeypatch.setattr(telegram, 'transport', fake)
    app.config['VERDICT']['telegram_token'] = '123:TEST'
    yield fake
    app.config['VERDICT']['telegram_token'] = ''


@pytest.fixture
def people(new_browser, db):
    def make(name='Судья'):
        b = new_browser()
        login = b.register(name + ' ' + secrets.token_hex(2))
        return b, login, int(db.value('SELECT id FROM users WHERE login = %s', (login,)))
    return make


def hook(app, update, secret=None):
    with app.test_request_context('/'):
        secret = telegram.secret() if secret is None else secret
    return app.test_client().post('/telegram/hook', json=update, headers={'X-Telegram-Bot-Api-Secret-Token': secret})


def say(app, chat_id, text, username='anna'):
    r = hook(app, {'update_id': 1, 'message': {'chat': {'id': chat_id}, 'from': {'username': username}, 'text': text}})
    assert r.status_code == 200
    return r.get_json()


def connect(new_browser):
    team = new_browser()
    team.login()
    team.form('/admin/game', {'action': 'tg_connect'})
    return team


def linked(app, b, chat_id):
    """The player presses «Подключить Telegram» and then «Запустить» in the bot."""
    b.get('/account')
    r = b.post('/account', {'_csrf': b.csrf(), 'action': 'tg_link'})
    code = re.match(r'https://t\.me/verdict_test_bot\?start=([0-9a-f]{24})$', r.headers['Location']).group(1)
    return say(app, chat_id, '/start ' + code)


def test_without_a_token_there_is_no_telegram(people, app):
    b, _, _ = people()
    b.get('/account')
    assert 'id="telegram"' not in b.html
    assert hook(app, {'message': {}}, secret='x').status_code == 403
    b.get('/forgot')


def test_team_connects_the_bot(tg, new_browser, db):
    team = connect(new_browser)
    methods = [m for m, _ in tg.calls]
    assert methods == ['getMe', 'setWebhook', 'setMyCommands']
    hookset = tg.calls[1][1]
    assert hookset['url'].endswith('/telegram/hook') and hookset['url'].startswith('https://')
    assert hookset['secret_token'] and hookset['allowed_updates'] == ['message']
    assert db.value("SELECT meta_value FROM meta WHERE meta_key = 'telegram_bot'") == 'verdict_test_bot'
    team.get('/admin/game')
    assert '@verdict_test_bot' in team.html and '/cron/' in team.html


def test_linking_notifications_and_commands(tg, app, people, new_browser, db):
    connect(new_browser)
    a, a_login, a_id = people('Аня')
    b, b_login, b_id = people('Боря')
    reply = linked(app, a, 5001)
    assert reply['method'] == 'sendMessage' and reply['chat_id'] == 5001 and 'Готово' in reply['text']
    assert db.one('SELECT chat_id, username FROM telegram_links WHERE user_id = %s', (a_id,)) == {'chat_id': 5001, 'username': 'anna'}
    a.get('/account')
    assert 'Подключён <b>@anna</b>' in a.html

    # a notification follows to Telegram once the page has been answered
    tg.calls.clear()
    b.form('/u/%s' % a_login, {'action': 'add'})
    [m] = tg.sent(5001)
    # the test site is on http: Telegram takes only https buttons, so the link goes into the text
    assert 'хочет добавить вас в друзья' in m['text'] and m['text'].endswith('/friends') and 'reply_markup' not in m
    # notifications turned off: no more
    a.form('/account', {'action': 'tg_settings', 'daily': '1'})
    tg.calls.clear()
    c, _, _ = people('Вера')
    c.form('/u/%s' % a_login, {'action': 'add'})
    assert tg.sent(5001) == []

    assert 'Дело дня' in say(app, 5001, '/today')['text']
    me = say(app, 5001, '/me')['text']
    assert 'Ранг' in me or 'ни одного вердикта' in me
    assert 'не подключён' in say(app, 7777, '/me')['text']
    assert 'устарела' in say(app, 7777, '/start ' + 'f' * 24)['text']
    assert '/today' in say(app, 7777, '/help')['text']
    assert 'отключён' in say(app, 5001, '/stop')['text']
    assert db.value('SELECT COUNT(*) FROM telegram_links WHERE user_id = %s', (a_id,)) == 0
    assert hook(app, {'message': {'chat': {'id': 1}, 'text': '/help'}}, secret='wrong').status_code == 403


def test_daily_reminder_from_cron(tg, app, people, new_browser, db):
    connect(new_browser)
    a, _, a_id = people('Аня')
    b, _, b_id = people('Боря')
    blocked, _, x_id = people('Ушедший')
    linked(app, a, 6001)
    linked(app, b, 6002)
    linked(app, blocked, 666)
    did = app.test_client().get('/api/v1/daily').get_json()['case']['id']
    b.vote(did, 'A')  # Боря already judged it
    with app.test_request_context('/'):
        from verdict.views.api import cron_key
        key = cron_key()
    assert app.test_client().get('/cron/wrong').status_code == 404
    hour = app.config['VERDICT']['daily_hour_utc']
    app.config['VERDICT']['daily_hour_utc'] = 0
    try:
        tg.calls.clear()
        out = app.test_client().get('/cron/' + key).get_json()
        assert out['daily']['sent'] >= 1 and out['daily']['skipped'] >= 1
        [m] = tg.sent(6001)
        assert 'Дело дня' in m['text'] and m['text'].endswith('/quick/%d' % did)
        assert tg.sent(6002) == []
        assert db.value('SELECT COUNT(*) FROM telegram_links WHERE user_id = %s', (x_id,)) == 0  # blocked the bot: unlinked
        tg.calls.clear()
        assert app.test_client().get('/cron/' + key).get_json()['daily']['sent'] == 0  # once a day
        assert tg.sent(6001) == []
    finally:
        app.config['VERDICT']['daily_hour_utc'] = hour
    with app.test_request_context('/'):
        early = datetime.now(timezone.utc).replace(hour=0)
        app.config['VERDICT']['daily_hour_utc'] = 23
        try:
            assert telegram.daily_run(early) == {'sent': 0, 'skipped': 0, 'failed': 0}
        finally:
            app.config['VERDICT']['daily_hour_utc'] = hour


def test_new_password_through_telegram(tg, app, people, new_browser, db):
    connect(new_browser)
    a, a_login, a_id = people('Аня')
    linked(app, a, 8001)
    guest = new_browser()
    guest.get('/login')
    assert 'href="/forgot"' in guest.html
    tg.calls.clear()
    guest.form('/forgot', {'login': a_login})
    assert 'бот VERDICT уже прислал' in guest.html
    [m] = tg.sent(8001)
    path = '/reset/' + re.search(r'/reset/(\S+)$', m['text']).group(1)
    guest.form('/forgot', {'login': a_login})  # again within two minutes: nothing more
    guest.form('/forgot', {'login': 'nobody-' + secrets.token_hex(3)})  # unknown: the same answer, nothing sent
    assert 'бот VERDICT уже прислал' in guest.html and len(tg.sent(8001)) == 1

    guest.get(path)
    assert a_login in guest.html
    guest.form(path, {'new_password': 'short', 'new_password_confirm': 'short'})
    assert db.value('SELECT used_at FROM password_resets WHERE user_id = %s', (a_id,)) is None
    r = guest.form(path, {'new_password': 'brand-new-pass-1', 'new_password_confirm': 'brand-new-pass-1'})
    assert r.status_code == 302 and r.headers['Location'].endswith('/login')
    assert guest.get(path).status_code == 302  # used: gone
    old = new_browser()
    old.form('/login', {'login': a_login, 'password': 'password123', 'back': ''})
    assert 'Неверный логин или пароль' in old.html
    assert new_browser().form('/login', {'login': a_login, 'password': 'brand-new-pass-1', 'back': ''}).status_code == 302
    assert guest.get('/reset/' + 'x' * 32).status_code == 302
