"""Request-level helpers: CSRF, the anonymous player id, flash messages, safe redirects, rendering."""
import hmac
import re
import secrets

from flask import g, jsonify, make_response, redirect as _redirect, render_template, request, session, url_for

VOTER_COOKIE = 'verdict_vid'
VOTER_ID = re.compile(r'^[a-f0-9]{32}$')


# ---------- CSRF ----------

def csrf_token():
    if not session.get('csrf'):
        session['csrf'] = secrets.token_hex(16)
    return session['csrf']


def csrf_valid():
    token = request.form.get('_csrf') or request.headers.get('X-CSRF-Token', '')
    return bool(token) and hmac.compare_digest(csrf_token(), token)


# ---------- Anonymous player ----------

def voter_id():
    """The anonymous player id: a cookie kept for a year (set in after_request when new)."""
    if 'voter' not in g:
        vid = request.cookies.get(VOTER_COOKIE, '')
        if not VOTER_ID.match(vid):
            vid = secrets.token_hex(16)
            g.voter_new = True
        g.voter = vid
    return g.voter


def remember_voter(response):
    if g.get('voter_new'):
        response.set_cookie(VOTER_COOKIE, g.voter, max_age=31536000, path='/', httponly=True, samesite='Lax')
    return response


# ---------- Flash, autosave, redirects ----------

def flash(kind, message):
    session['flash'] = session.get('flash', []) + [{'type': kind, 'message': message}]


def take_flashes():
    return session.pop('flash', [])


def autosave_key(situation_id, user_id):
    """Key of the browser's copy of the creator form (localStorage): one per author and per situation."""
    return 'verdict:create:u%d:%s' % (user_id or 0, 's%d' % situation_id if situation_id else 'new')


def autosave_clear(key):
    """After the server saved the form, the browser drops its copy (app.js, data-autosave-clear)."""
    session['autosave_clear'] = session.get('autosave_clear', []) + [key]


def take_autosave_clear():
    keys = session.pop('autosave_clear', [])
    return list(dict.fromkeys(keys))


def safe_back(url):
    """Only our own pages: a local path, no scheme, host or backslashes."""
    url = url if isinstance(url, str) else ''
    root = request.script_root + '/'
    if (url.startswith(root) and not url.startswith('//') and '\\' not in url
            and re.match(r'^[\w\-./?=&%~+]*$', url)):
        return url
    return ''


def redirect(target, code=302):
    return _redirect(target, code=code)


def require_login(back, message='Войдите, чтобы продолжить.'):
    """Returns a redirect to the login page, or None when a user is logged in."""
    from .auth import is_logged_in
    if is_logged_in():
        return None
    flash('error', message)
    return redirect(url_for('login', back=back))


# ---------- Rendering ----------

def page(template, http_status=200, **context):
    return make_response(render_template(template, **context), http_status)


def json_response(data, status=200):
    response = jsonify(data)
    response.status_code = status
    return response
