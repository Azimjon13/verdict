"""Accounts, roles and permissions."""
import re
import time

import bcrypt
from flask import g, session

from .catalog import ROLES
from .db import execute, insert, now, query, query_one, scalar

LOGIN_PATTERN = re.compile(r'^[A-Za-z0-9_.\-]{3,40}$')
PASSWORD_MIN = 8


# ---------- Passwords (bcrypt, compatible with PHP password_hash) ----------

def _secret(password):
    # bcrypt reads at most 72 bytes; PHP silently cut longer passwords, so do the same to keep old hashes valid.
    return password.encode('utf-8')[:72]


def hash_password(password):
    # Stored with PHP's $2y$ prefix (the same algorithm as $2b$), so the PHP version accepts it too.
    return '$2y$' + bcrypt.hashpw(_secret(password), bcrypt.gensalt(rounds=10)).decode('ascii')[4:]


def check_password(password, hashed):
    if not hashed or not hashed.startswith(('$2y$', '$2b$', '$2a$')):
        return False
    try:
        return bcrypt.checkpw(_secret(password), ('$2b$' + hashed[4:]).encode('ascii'))
    except ValueError:
        return False


_DUMMY_HASH = None


# ---------- Current user ----------

def current_user():
    if 'user' not in g:
        uid = session.get('uid')
        g.user = user_find(int(uid)) if uid else None
        if uid and g.user is None:
            session.pop('uid', None)
    return g.user


def current_user_id():
    u = current_user()
    return int(u['id']) if u else None


def is_logged_in():
    return current_user() is not None


def is_admin():
    u = current_user()
    return bool(u) and u['role'] == 'admin'


def owns_situation(s):
    uid = current_user_id()
    return uid is not None and s.get('user_id') == uid


def can_edit_situation(s):
    """The team edits everything; an author only their own drafts and situations on review."""
    return is_admin() or (owns_situation(s) and s['status'] in ('draft', 'pending'))


def can_view_situation(s):
    """Drafts are seen by their author and the team only; everything else is open to all."""
    return s['status'] != 'draft' or is_admin() or owns_situation(s)


def can_save_draft(s):
    """A new situation, or the author's own one until it passes review, can be saved as a draft."""
    return s is None or (owns_situation(s) and s['status'] in ('draft', 'pending'))


def can_see_hidden(s):
    """Hidden information is for the team and the author."""
    return is_admin() or owns_situation(s)


# ---------- Users ----------

def user_find(user_id):
    return query_one('SELECT id, login, display_name, role, created_at, last_login_at, bio, visibility, in_ratings'
                     ' FROM users WHERE id = %s', (user_id,))


def user_find_by_login(login):
    return query_one('SELECT * FROM users WHERE login = %s', (login,))


def users_all():
    """All users with their situation counts."""
    return query("SELECT u.id, u.login, u.display_name, u.role, u.created_at, u.last_login_at,"
                 " COUNT(s.id) AS situations, COALESCE(SUM(s.status = 'approved'), 0) AS approved"
                 " FROM users u LEFT JOIN situations s ON s.user_id = u.id"
                 " GROUP BY u.id ORDER BY u.role = 'admin' DESC, u.id")


def user_create(login, display_name, password, role='author'):
    return insert('INSERT INTO users (login, display_name, password_hash, role, created_at) VALUES (%s, %s, %s, %s, %s)',
                  (login, display_name, hash_password(password), role, now()))


def user_update_name(user_id, display_name):
    execute('UPDATE users SET display_name = %s WHERE id = %s', (display_name, user_id))
    # The author's name is stored in their situations too — keep the signature in sync.
    execute('UPDATE situations SET author = %s WHERE user_id = %s', (display_name, user_id))


def user_set_password(user_id, password):
    execute('UPDATE users SET password_hash = %s WHERE id = %s', (hash_password(password), user_id))


def user_set_role(user_id, role):
    execute('UPDATE users SET role = %s WHERE id = %s', (role, user_id))


def admins_count():
    return int(scalar("SELECT COUNT(*) FROM users WHERE role = 'admin'"))


# ---------- Login and logout ----------

def auth_attempt(login, password):
    global _DUMMY_HASH
    user = user_find_by_login(login)
    # The hash is checked for unknown logins too, so response time doesn't reveal whether a login exists.
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password('verdict-timing-guard')
    valid = check_password(password, user['password_hash'] if user else _DUMMY_HASH)
    return user if user and valid else None


def auth_login(user):
    session.regenerate()
    session['uid'] = int(user['id'])
    session.pop('login_fail', None)
    g.pop('user', None)
    execute('UPDATE users SET last_login_at = %s WHERE id = %s', (now(), user['id']))


def auth_logout():
    session.pop('uid', None)
    g.pop('user', None)
    session.regenerate()


def login_lock_seconds():
    """Seconds until the next login attempt is allowed (0 — go ahead)."""
    f = session.get('login_fail')
    if not f or f['n'] < 5:
        return 0
    return max(0, int(f['until'] - time.time()))


def login_register_failure():
    f = dict(session.get('login_fail') or {'n': 0, 'until': 0})
    f['n'] += 1
    if f['n'] >= 5:
        f['until'] = time.time() + min(300, 30 * 2 ** (f['n'] - 5))
    session['login_fail'] = f


# ---------- Form checks ----------

def registration_validate(login, name, password, confirm):
    e = {}
    if not LOGIN_PATTERN.match(login):
        e['login'] = 'Логин: 3–40 символов — латинские буквы, цифры, точка, дефис или подчёркивание.'
    elif user_find_by_login(login):
        e['login'] = 'Такой логин уже занят.'
    for k, v in name_validate(name).items():
        e.setdefault(k, v)
    for k, v in password_validate(password, confirm).items():
        e.setdefault(k, v)
    return e


def name_validate(name):
    return {'display_name': 'Имя или ник: от 2 до 80 символов.'} if not 2 <= len(name) <= 80 else {}


def password_validate(password, confirm):
    if len(password) < PASSWORD_MIN:
        return {'password': 'Пароль должен быть не короче %d символов.' % PASSWORD_MIN}
    if len(password.encode('utf-8')) > 200:
        return {'password': 'Пароль слишком длинный.'}
    if password != confirm:
        return {'password_confirm': 'Пароли не совпадают.'}
    return {}


def role_name(role):
    return ROLES.get(role, role)
