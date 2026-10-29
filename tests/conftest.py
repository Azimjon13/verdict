"""Test setup: a throwaway MySQL database, rebuilt for every test run, and a small «browser» over Flask's test client.

The database server comes from VERDICT_TEST_DB_HOST / _PORT / _USER / _PASSWORD (default 127.0.0.1:3306 root);
the database VERDICT_TEST_DB_NAME (default verdict_pytest) is DROPPED and recreated.
"""
import json
import os
import re
import sys
from pathlib import Path

import pymysql
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from verdict import create_app  # noqa: E402

DB = {
    'host': os.environ.get('VERDICT_TEST_DB_HOST', '127.0.0.1'),
    'port': int(os.environ.get('VERDICT_TEST_DB_PORT', 3306)),
    'user': os.environ.get('VERDICT_TEST_DB_USER', 'root'),
    'password': os.environ.get('VERDICT_TEST_DB_PASSWORD', ''),
    'name': os.environ.get('VERDICT_TEST_DB_NAME', 'verdict_pytest'),
}


@pytest.fixture(scope='session')
def app():
    conn = pymysql.connect(host=DB['host'], port=DB['port'], user=DB['user'], password=DB['password'])
    with conn.cursor() as cur:
        cur.execute('DROP DATABASE IF EXISTS `%s`' % DB['name'])
    conn.close()
    application = create_app({'db': DB, 'admin_password': 'verdict-admin', 'secret_key': 'test'})
    application.config['TESTING'] = True
    with application.test_client() as c:
        c.get('/')  # builds the database
    return application


@pytest.fixture(scope='session')
def db(app):
    """A plain connection for checking what was stored."""
    conn = pymysql.connect(host=DB['host'], port=DB['port'], user=DB['user'], password=DB['password'], database=DB['name'],
                           charset='utf8mb4', autocommit=True, cursorclass=pymysql.cursors.DictCursor)
    yield Db(conn)
    conn.close()


class Db:
    def __init__(self, conn):
        self.conn = conn

    def rows(self, sql, params=()):
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())

    def one(self, sql, params=()):
        rows = self.rows(sql, params)
        return rows[0] if rows else None

    def value(self, sql, params=()):
        row = self.one(sql, params)
        return None if row is None else next(iter(row.values()))

    def data(self, situation_id):
        return json.loads(self.value('SELECT data FROM situations WHERE id = %s', (situation_id,)))


def flatten(data, prefix=''):
    """{'decisions': [{'text': 'A'}]} → [('decisions[0][text]', 'A')] — how a browser posts the creator form."""
    out = []
    items = data.items() if isinstance(data, dict) else enumerate(data)
    for key, value in items:
        name = '%s[%s]' % (prefix, key) if prefix else str(key)
        if isinstance(value, (dict, list)):
            out.extend(flatten(value, name))
        elif value is not None:
            out.append((name, str(value) if not isinstance(value, bool) else ('1' if value else '')))
    return out


class Browser:
    """One visitor with its own cookies."""

    def __init__(self, app):
        self.client = app.test_client()
        self.html = ''

    def get(self, url):
        r = self.client.get(url)
        self.html = r.get_data(as_text=True)
        return r

    def post(self, url, data):
        from werkzeug.datastructures import MultiDict
        r = self.client.post(url, data=MultiDict(flatten(data)))
        self.html = r.get_data(as_text=True)
        return r

    def csrf(self, html=None):
        html = self.html if html is None else html
        m = re.search(r'name="_csrf" value="([^"]+)"', html) or re.search(r'data-csrf="([^"]+)"', html)
        return m.group(1)

    def form(self, url, data, page=None):
        """Opens a page (for the CSRF token) and posts a form to url."""
        self.get(page or url)
        return self.post(url, {'_csrf': self.csrf(), **data})

    def login(self, login='admin', password='verdict-admin'):
        return self.form('/login', {'login': login, 'password': password, 'back': ''})

    def register(self, name='Автор'):
        import secrets
        login = 'u' + secrets.token_hex(4)
        self.form('/register', {'login': login, 'display_name': name, 'password': 'password123',
                                'password_confirm': 'password123', 'back': ''})
        return login

    def vote(self, situation_id, option, guess='', mode='quick', ms=12000, reasoning=''):
        self.get('/quick/%d' % situation_id if mode == 'quick' else '/case/%d' % situation_id)
        r = self.post('/api/vote', {'_csrf': self.csrf(), 'situation_id': situation_id, 'option': option, 'guess': guess,
                                    'mode': mode, 'duration_ms': ms, 'reasoning': reasoning})
        return r.status_code, r.get_json()

    def cookie(self, name):
        c = self.client.get_cookie(name)
        return c.value if c else None

    def toasts(self):
        return re.findall(r'<div class="toast toast-\w+">.*?<span>(.*?)</span>', self.html, re.S)

    def errors(self):
        return re.findall(r'class="field-error" role="alert">.*?</svg>(.*?)</p>', self.html, re.S)


@pytest.fixture
def browser(app):
    return Browser(app)


@pytest.fixture
def new_browser(app):
    return lambda: Browser(app)
