"""Sign-in from the game client: a long random token per device, stored only as its SHA-256. The client sends it as
`Authorization: Bearer <token>`; the account's player id then comes with every answer, so verdicts made in the game
and on the website are one career."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from .db import execute, now, query_one, scalar

FAILURE_WINDOW = timedelta(minutes=15)
MAX_FAILURES = 10


def _hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def issue(user_id, label=''):
    token = secrets.token_urlsafe(32)
    ts = now()
    execute('INSERT INTO api_tokens (token_hash, user_id, label, created_at, used_at) VALUES (%s, %s, %s, %s, %s)',
            (_hash(token), user_id, label[:60], ts, ts))
    return token


def user_for(token):
    if not token or len(token) > 200:
        return None
    row = query_one('SELECT u.id, u.login, u.display_name, u.role, u.bio, u.visibility, u.in_ratings, t.used_at'
                    ' FROM api_tokens t JOIN users u ON u.id = t.user_id WHERE t.token_hash = %s', (_hash(token),))
    if row and (datetime.now(timezone.utc).replace(tzinfo=None) - row['used_at']) > timedelta(hours=1):
        execute('UPDATE api_tokens SET used_at = %s WHERE token_hash = %s', (now(), _hash(token)))
    return row


def revoke(token):
    return execute('DELETE FROM api_tokens WHERE token_hash = %s', (_hash(token),))


def locked(login):
    """Too many wrong passwords for this login lately: sign-in waits."""
    since = (datetime.now(timezone.utc) - FAILURE_WINDOW).strftime('%Y-%m-%d %H:%M:%S')
    return int(scalar('SELECT COUNT(*) FROM auth_failures WHERE login = %s AND failed_at > %s', (login.lower(), since))) >= MAX_FAILURES


def failed(login):
    execute('INSERT INTO auth_failures (login, failed_at) VALUES (%s, %s)', (login.lower()[:40], now()))
    execute('DELETE FROM auth_failures WHERE failed_at < %s',
            ((datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'),))
