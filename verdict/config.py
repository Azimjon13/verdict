"""Settings. Environment variables (VERDICT_*) win over config.json in the project root, which wins over the defaults.

MySQL 5.7+/8.0 or MariaDB 10.3+. If the user may CREATE DATABASE, the database and tables are created on the
first request; otherwise create the database and import database/schema.sql by hand.
"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULTS = {
    'db': {
        'host': '127.0.0.1',
        'port': 3306,
        'name': 'verdict',
        'user': 'root',
        'password': '',
        # Unix socket of MySQL. Empty: with host «localhost» the usual socket files are tried first, like PHP does.
        'socket': '',
    },
    # Password of the first team account (login: admin). Used ONCE, when the database is created.
    # Change it on the «Профиль» page right after the first login.
    'admin_password': 'verdict-admin',
    # How long a session lives without activity (seconds). Sessions are stored in MySQL, table `sessions`.
    'session_lifetime': 60 * 60 * 24 * 14,
    # Signs nothing important (sessions live in MySQL), but Flask wants one. Set it in production.
    'secret_key': '',
    # A sign-up form sent sooner than this after it was opened is a bot's (people need a few seconds to type).
    'min_signup_seconds': 3,
    # New accounts an hour, in all and from one address (0 = no limit). The per-address limit works only when the site
    # sees real visitor addresses; the admin «Игра» page shows what it sees.
    'max_signups_per_hour': 30,
    'max_signups_per_ip': 5,
    # Behind a proxy that passes the visitor's address only in X-Forwarded-For: how many proxies to trust (usually 1).
    'trusted_proxies': 0,
}

ENV = {
    ('db', 'host'): 'VERDICT_DB_HOST',
    ('db', 'port'): 'VERDICT_DB_PORT',
    ('db', 'name'): 'VERDICT_DB_NAME',
    ('db', 'user'): 'VERDICT_DB_USER',
    ('db', 'password'): 'VERDICT_DB_PASSWORD',
    ('db', 'socket'): 'VERDICT_DB_SOCKET',
    ('admin_password',): 'VERDICT_ADMIN_PASSWORD',
    ('session_lifetime',): 'VERDICT_SESSION_LIFETIME',
    ('secret_key',): 'VERDICT_SECRET_KEY',
    ('max_signups_per_hour',): 'VERDICT_MAX_SIGNUPS_PER_HOUR',
    ('max_signups_per_ip',): 'VERDICT_MAX_SIGNUPS_PER_IP',
    ('trusted_proxies',): 'VERDICT_TRUSTED_PROXIES',
}


def load(overrides=None):
    cfg = json.loads(json.dumps(DEFAULTS))
    local = ROOT / 'config.json'
    if local.is_file():
        _merge(cfg, json.loads(local.read_text(encoding='utf-8')))
    for path, var in ENV.items():
        value = os.environ.get(var)
        if value is None or (value == '' and var != 'VERDICT_DB_PASSWORD'):
            continue
        target = cfg
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
    if overrides:
        _merge(cfg, overrides)
    cfg['db']['port'] = int(cfg['db']['port'])
    cfg['session_lifetime'] = int(cfg['session_lifetime'])
    cfg['min_signup_seconds'] = float(cfg['min_signup_seconds'])
    for key in ('max_signups_per_hour', 'max_signups_per_ip', 'trusted_proxies'):
        cfg[key] = int(cfg[key])
    return cfg


def _merge(base, extra):
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
