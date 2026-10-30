"""The Telegram bot. A player links a chat to their account from the profile (a one-time code in a t.me link); the chat
then gets the account's notifications, a reminder of the case of the day, and — when the password is forgotten — a
one-time link to set a new one. Commands: /today, /me, /stop, /help.

The bot works only with VERDICT_TELEGRAM_TOKEN set and the webhook connected from admin → «Игра». Telegram calls
/telegram/hook (checked by a secret header); replies go back in the webhook answer itself. Notifications are sent
after the page has been answered, so a slow Telegram never slows the site. Reminders go out from /cron/<key>, which
the host's cron calls every hour."""
import hashlib
import hmac
import html
import json
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from flask import current_app, g, request

from .db import execute, now, query, query_one, scalar

CODE_TTL = timedelta(hours=1)
RESET_TTL = timedelta(minutes=30)
RESET_GAP = timedelta(minutes=2)
COMMANDS = [('today', 'Дело дня'), ('me', 'Мой судья: ранг, опыт, серия'), ('stop', 'Отключить бота от аккаунта'),
            ('help', 'Что умеет бот')]


class TelegramError(Exception):
    pass


def _http(url, payload, timeout):
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


transport = _http  # tests put a fake Telegram here


def token():
    return current_app.config['VERDICT'].get('telegram_token') or ''


def enabled():
    return bool(token())


def bot_name():
    """The bot's @username, learnt when the team connected it."""
    return scalar("SELECT meta_value FROM meta WHERE meta_key = 'telegram_bot'") or ''


def ready():
    """Players can link: a token, and the bot is connected."""
    return enabled() and bool(bot_name())


def _post(tok, method, params, timeout=6):
    try:
        out = transport('https://api.telegram.org/bot%s/%s' % (tok, method), params, timeout)
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise TelegramError(str(e)) from e
    if not out.get('ok'):
        raise TelegramError(out.get('description') or 'Telegram error')
    return out.get('result')


def call(method, **params):
    if not enabled():
        raise TelegramError('Бот не настроен: нет VERDICT_TELEGRAM_TOKEN.')
    return _post(token(), method, params)


def secret():
    """What Telegram sends in X-Telegram-Bot-Api-Secret-Token: derived from the token, so nothing to store."""
    return hashlib.sha256(('verdict-hook:' + token()).encode('utf-8')).hexdigest()[:40]


def absolute(link):
    if not link or link.startswith('http'):
        return link
    return request.host_url.rstrip('/') + link


def message(chat_id, text, button=None):
    """sendMessage parameters: HTML text (already escaped by the caller), an optional button (label, url)."""
    params = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
    if button and button[1].startswith('https://'):  # Telegram takes only https buttons
        params['reply_markup'] = {'inline_keyboard': [[{'text': button[0], 'url': button[1]}]]}
    elif button:
        params['text'] += '\n' + html.escape(button[1])
    return params


# ---------- Sending after the answer ----------

def later(chat_id, text, button=None):
    """Queue a message for when the page has been answered (see flush)."""
    if enabled():
        g.setdefault('telegram_outbox', []).append(message(chat_id, text, button))


def flush(response):
    """after_request: send the queue once the response is out. Failures are ignored — the site never waits."""
    outbox = g.pop('telegram_outbox', None)
    if outbox:
        tok = token()

        def deliver():
            for params in outbox:
                try:
                    _post(tok, 'sendMessage', params, timeout=5)
                except TelegramError:
                    pass
        response.call_on_close(deliver)
    return response


def link_of(user_id):
    return query_one('SELECT * FROM telegram_links WHERE user_id = %s', (user_id,)) if user_id else None


def notify(user_id, text, link=''):
    """A notification for the account: also to its Telegram, if linked and wanted."""
    if not enabled():
        return
    row = link_of(user_id)
    if row and row['notify']:
        later(row['chat_id'], html.escape(text), ('Открыть', absolute(link)) if link else None)


# ---------- Linking ----------

def new_code(user_id):
    execute('DELETE FROM telegram_codes WHERE user_id = %s OR created_at < %s', (user_id, _ago(CODE_TTL)))
    code = secrets.token_hex(12)
    execute('INSERT INTO telegram_codes (code, user_id, created_at) VALUES (%s, %s, %s)', (code, user_id, now()))
    return code


def deep_link(code):
    return 'https://t.me/%s?start=%s' % (bot_name(), code)


def _ago(delta):
    return (datetime.now(timezone.utc) - delta).strftime('%Y-%m-%d %H:%M:%S')


def link(code, chat_id, username):
    """/start <code> → the user it links, or None for an unknown or old code."""
    row = query_one('SELECT user_id FROM telegram_codes WHERE code = %s AND created_at > %s', (code, _ago(CODE_TTL)))
    if not row:
        return None
    uid = int(row['user_id'])
    execute('DELETE FROM telegram_codes WHERE user_id = %s', (uid,))
    execute('DELETE FROM telegram_links WHERE chat_id = %s AND user_id <> %s', (chat_id, uid))  # one account per chat
    execute('INSERT INTO telegram_links (user_id, chat_id, username, linked_at) VALUES (%s, %s, %s, %s)'
            ' ON DUPLICATE KEY UPDATE chat_id = VALUES(chat_id), username = VALUES(username), linked_at = VALUES(linked_at)',
            (uid, chat_id, (username or '')[:64], now()))
    return uid


def unlink(user_id):
    return execute('DELETE FROM telegram_links WHERE user_id = %s', (user_id,))


def settings(user_id, notify_on, daily_on):
    execute('UPDATE telegram_links SET notify = %s, daily = %s WHERE user_id = %s', (int(notify_on), int(daily_on), user_id))


# ---------- The bot's answers ----------

def _user_by_chat(chat_id):
    return query_one('SELECT u.id, u.login, u.display_name FROM telegram_links t JOIN users u ON u.id = t.user_id'
                     ' WHERE t.chat_id = %s', (chat_id,))


def _today_text():
    from . import career
    from .repository import situation_find
    sid = career.daily_case_id()
    s = situation_find(sid) if sid else None
    if not s:
        return 'Дела дня сегодня нет.', None
    return ('<b>Дело дня:</b> «%s»\n+%d XP, если рассудить его сегодня.' % (html.escape(s['title']), career.XP['daily']),
            ('Рассудить', absolute('/quick/%d' % s['id'])))


def _me_text(user):
    from . import career, social
    voter = scalar('SELECT voter FROM players WHERE user_id = %s ORDER BY updated_at DESC LIMIT 1', (user['id'],))
    sm = career.summary(voter) if voter else None
    if not sm:
        return 'Вы ещё не вынесли ни одного вердикта. /today — начать с дела дня.'
    place = next((r['place'] for r in social.board('season') if r['user_id'] == user['id']), None)
    return ('<b>%s</b>\nРанг: %s · %d XP\nВердиктов: %d · дней подряд: %d%s' % (
        html.escape(user['display_name']), html.escape(sm['rank']['name']), sm['xp'], sm['verdicts'], sm['streak'],
        '\nМесто в сезоне: %d' % place if place else ''))


HELP = ('Это бот игры VERDICT — суда над спорными делами.\n'
        '/today — дело дня\n/me — ваш судья: ранг, опыт, серия\n/stop — отключить бота от аккаунта\n\n'
        'Уведомления и напоминание о деле дня приходят сюда, когда бот подключён в профиле на сайте.')


def handle(update):
    """One update from the webhook → the reply as a webhook answer (a sendMessage), or None."""
    msg = update.get('message') or {}
    chat = (msg.get('chat') or {}).get('id')
    text = (msg.get('text') or '').strip()
    if not chat or not text.startswith('/'):
        return None
    command, _, arg = text.partition(' ')
    command = command.split('@')[0].lower()
    user = _user_by_chat(chat)
    button = None
    if command == '/start' and arg.strip():
        uid = link(arg.strip(), chat, (msg.get('from') or {}).get('username', ''))
        if uid:
            name = scalar('SELECT display_name FROM users WHERE id = %s', (uid,))
            reply = ('Готово, %s! Теперь сюда приходят уведомления VERDICT и напоминание о деле дня.\n\n'
                     '/today — дело дня, /me — ваш судья, /stop — отключить.' % html.escape(name))
        else:
            reply = 'Ссылка устарела. Откройте профиль на сайте и нажмите «Подключить Telegram» ещё раз.'
            button = ('Профиль', absolute('/account#telegram'))
    elif command == '/today':
        reply, button = _today_text()
    elif command == '/me':
        if user:
            reply = _me_text(user)
        else:
            reply, button = 'Бот ещё не подключён к аккаунту.', ('Подключить в профиле', absolute('/account#telegram'))
    elif command == '/stop':
        if user:
            unlink(user['id'])
            reply = 'Бот отключён от аккаунта «%s». Подключить снова можно в профиле.' % html.escape(user['display_name'])
        else:
            reply = 'Бот и так не подключён ни к одному аккаунту.'
    else:
        reply = HELP
        if not user:
            button = ('Подключить в профиле', absolute('/account#telegram'))
    return {'method': 'sendMessage', **message(chat, reply, button)}


# ---------- The team connects the bot ----------

def connect():
    """getMe, then the webhook and the command menu. Returns the bot's username."""
    me = call('getMe')
    execute('INSERT INTO meta (meta_key, meta_value) VALUES (%s, %s) ON DUPLICATE KEY UPDATE meta_value = VALUES(meta_value)',
            ('telegram_bot', me['username']))
    call('setWebhook', url=absolute('/telegram/hook').replace('http://', 'https://', 1), secret_token=secret(),
         allowed_updates=['message'], drop_pending_updates=True)
    call('setMyCommands', commands=[{'command': c, 'description': d} for c, d in COMMANDS])
    return me['username']


def status():
    return {'enabled': enabled(), 'bot': bot_name(), 'links': int(scalar('SELECT COUNT(*) FROM telegram_links') or 0),
            'daily_hour': current_app.config['VERDICT']['daily_hour_utc']}


# ---------- The case of the day ----------

def daily_run(at=None):
    """Reminds every linked chat that wants it, once a day after daily_hour_utc, unless the case is judged already.
    Returns {sent, skipped, failed}."""
    from . import career
    out = {'sent': 0, 'skipped': 0, 'failed': 0}
    at = at or datetime.now(timezone.utc)
    if not enabled() or at.hour < current_app.config['VERDICT']['daily_hour_utc']:
        return out
    day = at.date()
    text, button = _today_text()
    if not button:
        return out
    for row in query('SELECT t.user_id, t.chat_id FROM telegram_links t WHERE t.daily = 1'
                     ' AND (t.last_daily IS NULL OR t.last_daily < %s)', (day,)):
        if not execute('UPDATE telegram_links SET last_daily = %s WHERE user_id = %s AND (last_daily IS NULL OR last_daily < %s)',
                       (day, row['user_id'], day)):
            continue  # another cron run took it
        voter = scalar('SELECT voter FROM players WHERE user_id = %s ORDER BY updated_at DESC LIMIT 1', (row['user_id'],))
        if voter and career.daily(voter)['judged']:
            out['skipped'] += 1
            continue
        try:
            _post(token(), 'sendMessage', message(row['chat_id'], text, button), timeout=5)
            out['sent'] += 1
        except TelegramError as e:
            out['failed'] += 1
            if 'blocked' in str(e) or 'chat not found' in str(e) or 'deactivated' in str(e):
                unlink(row['user_id'])  # the player blocked the bot: stop trying
    return out


# ---------- A new password through Telegram ----------

def _hash(raw):
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def send_reset(login):
    """«Забыли пароль?»: a one-time link to the account's Telegram. Says nothing about whether the account exists."""
    if not ready():
        return
    user = query_one('SELECT u.id, u.display_name, t.chat_id FROM users u JOIN telegram_links t ON t.user_id = u.id'
                     ' WHERE u.login = %s', (login,))
    if not user or scalar('SELECT COUNT(*) FROM password_resets WHERE user_id = %s AND created_at > %s',
                          (user['id'], _ago(RESET_GAP))):
        return
    raw = secrets.token_urlsafe(24)
    execute('INSERT INTO password_resets (token_hash, user_id, created_at) VALUES (%s, %s, %s)', (_hash(raw), user['id'], now()))
    later(user['chat_id'], 'Кто-то (надеемся, вы) попросил новый пароль для «%s». Ссылка действует 30 минут. '
                           'Если это были не вы — просто ничего не делайте.' % html.escape(user['display_name']),
          ('Задать новый пароль', absolute('/reset/' + raw)))


def reset_user(raw):
    """The account a reset link opens, or None (unknown, used, older than 30 minutes)."""
    if not raw or len(raw) > 100:
        return None
    return query_one('SELECT u.id, u.login, u.display_name FROM password_resets r JOIN users u ON u.id = r.user_id'
                     ' WHERE r.token_hash = %s AND r.used_at IS NULL AND r.created_at > %s', (_hash(raw), _ago(RESET_TTL)))


def reset_used(raw, user_id):
    execute('UPDATE password_resets SET used_at = %s WHERE user_id = %s AND used_at IS NULL', (now(), user_id))


def housekeeping():
    execute('DELETE FROM telegram_codes WHERE created_at < %s', (_ago(CODE_TTL),))
    execute('DELETE FROM password_resets WHERE created_at < %s', (_ago(timedelta(days=2)),))


def hook_allowed():
    return enabled() and hmac.compare_digest(request.headers.get('X-Telegram-Bot-Api-Secret-Token', ''), secret())
