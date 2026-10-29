"""Server-side sessions in the MySQL `sessions` table (same table as the PHP version).

Each row records user_id, so changing the password or «Выйти на других устройствах» can end a user's other
sessions. Data is stored as JSON; a row the PHP version wrote (PHP serialize format) is not read — the visitor
simply gets a new session.
"""
import json
import re
import secrets
import time

from flask.sessions import SessionInterface, SessionMixin
from werkzeug.datastructures import CallbackDict

from .db import DatabaseUnavailable, execute, query_one

COOKIE = 'verdict_sid'
_SID = re.compile(r'^[A-Za-z0-9,-]{22,128}$')


def new_sid():
    return secrets.token_hex(24)


class DbSession(CallbackDict, SessionMixin):
    def __init__(self, initial=None, sid=None, new=False):
        def on_update(_self):
            _self.modified = True
        super().__init__(initial, on_update)
        self.sid = sid or new_sid()
        self.new = new
        self.modified = False
        self.dropped_sid = None

    def regenerate(self):
        """New session id for the same data (after login, logout, password change); the old row is deleted."""
        if self.dropped_sid is None and not self.new:
            self.dropped_sid = self.sid
        self.sid = new_sid()
        self.new = False
        self.modified = True


class DbSessionInterface(SessionInterface):
    def __init__(self, lifetime):
        self.lifetime = lifetime

    def open_session(self, app, request):
        sid = request.cookies.get(COOKIE, '')
        if sid and _SID.match(sid):
            try:
                row = query_one('SELECT data, last_activity FROM sessions WHERE id = %s', (sid,))
            except DatabaseUnavailable:
                return self.make_null_session(app)  # the view's own query shows the «database unavailable» page
            if row and int(row['last_activity']) >= time.time() - self.lifetime:
                try:
                    data = json.loads(bytes(row['data']).decode('utf-8'))
                except (ValueError, UnicodeDecodeError):
                    data = None
                if isinstance(data, dict):
                    return DbSession(data, sid)
        return DbSession(new=True)

    def save_session(self, app, session, response):
        if not isinstance(session, DbSession):
            return
        if session.dropped_sid:
            execute('DELETE FROM sessions WHERE id = %s', (session.dropped_sid,))
        if not session:
            if not session.new:
                execute('DELETE FROM sessions WHERE id = %s', (session.sid,))
                response.delete_cookie(COOKIE, path=self.get_cookie_path(app))
            return
        uid = session.get('uid')
        data = json.dumps(dict(session), ensure_ascii=False).encode('utf-8')
        ts = int(time.time())
        execute('INSERT INTO sessions (id, user_id, data, last_activity) VALUES (%s, %s, %s, %s)'
                ' ON DUPLICATE KEY UPDATE user_id = %s, data = %s, last_activity = %s',
                (session.sid, uid, data, ts, uid, data, ts))
        # The cookie is renewed on every visit, so an active author isn't logged out after 14 days of work.
        response.set_cookie(COOKIE, session.sid, max_age=self.lifetime, path=self.get_cookie_path(app),
                            secure=_is_https(), httponly=True, samesite='Lax')
        if secrets.randbelow(100) == 0:
            execute('DELETE FROM sessions WHERE last_activity < %s', (ts - self.lifetime,))


def _is_https():
    from flask import request
    return request.is_secure


def revoke_others(user_id, current_sid):
    return execute('DELETE FROM sessions WHERE user_id = %s AND id <> %s', (user_id, current_sid))


def active_count(user_id, lifetime):
    row = query_one('SELECT COUNT(*) AS n FROM sessions WHERE user_id = %s AND last_activity >= %s',
                    (user_id, int(time.time()) - lifetime))
    return int(row['n'])
