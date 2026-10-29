"""Brakes on mass sign-up, for the website form and the game API alike: at most `max_signups_per_hour` new accounts an
hour in all, and `max_signups_per_ip` an hour from one address. Addresses are kept only as a keyed hash, for a day.

The per-address limit works only when the site sees real visitor addresses. Behind a proxy that hides them every
visitor looks like 127.0.0.1, and a per-address limit would stop everyone — so for a private or local address it is
skipped (the hourly total still applies). `trusted_proxies` = N takes the address from the N-th last entry of
X-Forwarded-For instead, for hosts whose proxy adds it but doesn't pass the address on. The admin «Игра» page shows
what the site sees."""
import hashlib
import hmac
import ipaddress
from datetime import datetime, timedelta, timezone

from flask import current_app, request

from .db import execute, now, scalar


def _cfg():
    return current_app.config['VERDICT']


def client_ip():
    addr = request.remote_addr or ''
    hops = _cfg()['trusted_proxies']
    if hops:
        chain = [a.strip() for a in request.headers.get('X-Forwarded-For', '').split(',') if a.strip()]
        if len(chain) >= hops:
            addr = chain[-hops]
    return addr


def is_public(addr):
    try:
        return ipaddress.ip_address(addr).is_global
    except ValueError:
        return False


def _hash(addr):
    from .hunt import _secret
    return hmac.new(_secret(), addr.encode('utf-8'), hashlib.sha256).hexdigest()[:16]


def _since(hours):
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')


def refusal():
    """None when a sign-up may go ahead, else what to tell the visitor."""
    cfg = _cfg()
    hour = _since(1)
    if cfg['max_signups_per_hour'] and int(scalar('SELECT COUNT(*) FROM signup_log WHERE created_at > %s', (hour,))) \
            >= cfg['max_signups_per_hour']:
        return 'Сейчас слишком много новых аккаунтов. Попробуйте зарегистрироваться через час.'
    addr = client_ip()
    if cfg['max_signups_per_ip'] and is_public(addr) and int(scalar(
            'SELECT COUNT(*) FROM signup_log WHERE ip_hash = %s AND created_at > %s', (_hash(addr), hour))) >= cfg['max_signups_per_ip']:
        return 'С этого адреса за последний час уже создано несколько аккаунтов. Попробуйте позже.'
    return None


def record():
    """A sign-up went through."""
    execute('INSERT INTO signup_log (ip_hash, created_at) VALUES (%s, %s)', (_hash(client_ip()), now()))
    execute('DELETE FROM signup_log WHERE created_at < %s', (_since(24),))


def seen():
    """For the team: the address the site sees for this request, and whether the per-address limit can work."""
    addr = client_ip()
    return {'address': addr, 'public': is_public(addr), 'forwarded': request.headers.get('X-Forwarded-For', ''),
            'real_ip_header': request.headers.get('X-Real-IP', ''), 'trusted_proxies': _cfg()['trusted_proxies'],
            'per_ip': _cfg()['max_signups_per_ip'], 'per_hour': _cfg()['max_signups_per_hour']}
