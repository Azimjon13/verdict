"""Treasure hunts: the team hides spots on the site's pages (or in the game client's scenes); a player who finds
one and clicks it gets the gift the team put there. Gifts are set by the team: XP, a trophy, a title, a unique
code from a pool, or a message. A hunt can also have a main prize for finding all of its spots.

A spot on a page is tied to an element (a CSS selector) and a point inside it (x, y in % of its box), so it
stays in place when the layout reflows. A web spot is claimed with a token that only the page it sits on
carries, so spot ids can't simply be tried one by one.
"""
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone

from flask import current_app, g

from .catalog import GIFT_KINDS, HUNT
from .db import db, execute, insert, now, query, query_one, scalar
from .helpers import icon_html

STATUSES = {'draft': 'Черновик', 'active': 'Идёт', 'ended': 'Завершена'}
UNITY = 'unity:'  # spots of the game client: page = unity:<scene>

# Pages a spot can sit on: endpoint -> name (for the team). '*' — every page of the site.
PAGES = {
    '*': 'Все страницы сайта',
    'index': 'Главная',
    'quick': 'Быстрый суд',
    'quick_case': 'Быстрый суд — конкретное дело',
    'play': 'Архив дел',
    'case': 'Досье дела',
    'judge': 'Профиль судьи',
    'brief': 'Бриф для авторов',
    'create': 'Создать ситуацию',
    'library': 'Отбор',
    'view': 'Карточка ситуации в отборе',
    'login': 'Вход',
    'register': 'Регистрация',
    'account': 'Профиль автора',
}
# Pages with an id in the address: by default a spot placed there stays on that one page.
PAGES_WITH_ID = {'quick_case', 'case', 'view', 'edit'}


# ---------- Time ----------

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def running(c, at=None):
    """A hunt is on when it is active and now is inside its dates (UTC)."""
    at = at or utcnow()
    return (c['status'] == 'active' and (c['starts_at'] is None or c['starts_at'] <= at)
            and (c['ends_at'] is None or c['ends_at'] > at))


def state_of(c):
    """draft | soon | running | over | ended — what the team sees in the list."""
    if c['status'] == 'draft':
        return 'draft'
    if c['status'] == 'ended':
        return 'ended'
    at = utcnow()
    if c['starts_at'] and c['starts_at'] > at:
        return 'soon'
    if c['ends_at'] and c['ends_at'] <= at:
        return 'over'
    return 'running'


# ---------- Reading ----------

def gift_find(gift_id):
    return query_one('SELECT * FROM gifts WHERE id = %s', (gift_id,)) if gift_id else None


def gifts_all():
    return query('SELECT g.*, (SELECT COUNT(*) FROM gift_codes c WHERE c.gift_id = g.id) AS codes_total,'
                 ' (SELECT COUNT(*) FROM gift_codes c WHERE c.gift_id = g.id AND c.grant_id IS NULL) AS codes_free,'
                 ' (SELECT COUNT(*) FROM gift_grants r WHERE r.gift_id = g.id AND r.revoked_at IS NULL) AS granted'
                 ' FROM gifts g ORDER BY g.active DESC, g.id DESC')


def challenge_find(challenge_id):
    return query_one('SELECT * FROM challenges WHERE id = %s', (challenge_id,)) if challenge_id else None


def challenges_all():
    return query('SELECT c.*, (SELECT COUNT(*) FROM spots s WHERE s.challenge_id = c.id) AS spots,'
                 ' (SELECT COUNT(*) FROM spot_finds f WHERE f.challenge_id = c.id) AS finds,'
                 ' (SELECT COUNT(DISTINCT f.voter) FROM spot_finds f WHERE f.challenge_id = c.id) AS finders'
                 ' FROM challenges c ORDER BY c.id DESC')


def spot_find(spot_id):
    return query_one('SELECT * FROM spots WHERE id = %s', (spot_id,)) if spot_id else None


def spots_of(challenge_id):
    return query('SELECT s.*, g.name AS gift_name, g.kind AS gift_kind, g.icon AS gift_icon,'
                 ' (SELECT COUNT(*) FROM spot_finds f WHERE f.spot_id = s.id) AS finds'
                 ' FROM spots s LEFT JOIN gifts g ON g.id = s.gift_id WHERE s.challenge_id = %s ORDER BY s.id',
                 (challenge_id,))


def running_challenges():
    if 'hunt_running' not in g:
        g.hunt_running = [c for c in query("SELECT * FROM challenges WHERE status = 'active' ORDER BY id") if running(c)]
    return g.hunt_running


def _found_ids(voter, challenge_ids):
    if not challenge_ids:
        return set()
    return {int(r['spot_id']) for r in query('SELECT spot_id FROM spot_finds WHERE voter = %s AND challenge_id IN (%s)'
                                             % ('%s', ', '.join(['%s'] * len(challenge_ids))), [voter, *challenge_ids])}


def _counts(spot_ids):
    if not spot_ids:
        return {}
    return {int(r['spot_id']): int(r['n']) for r in query(
        'SELECT spot_id, COUNT(*) AS n FROM spot_finds WHERE spot_id IN (%s) GROUP BY spot_id' % ', '.join(['%s'] * len(spot_ids)),
        list(spot_ids))}


def _empty(spot, counts):
    return bool(spot['max_finds']) and counts.get(int(spot['id']), 0) >= int(spot['max_finds'])


def _secret():
    """The key that signs claim tokens: VERDICT_SECRET_KEY, or else one kept in the database. A random key per
    process would break claims on hosts that run several processes of the site (Passenger does)."""
    if 'hunt_secret' not in g:
        key = current_app.config['VERDICT'].get('secret_key')
        if not key:
            execute('INSERT IGNORE INTO meta (meta_key, meta_value) VALUES (%s, %s)', ('hunt_secret', secrets.token_hex(32)))
            key = scalar("SELECT meta_value FROM meta WHERE meta_key = 'hunt_secret'")
        g.hunt_secret = key.encode('utf-8')
    return g.hunt_secret


def token(spot_id, voter):
    return hmac.new(_secret(), ('spot:%d:%s' % (int(spot_id), voter)).encode('ascii'), hashlib.sha256).hexdigest()[:24]


def token_valid(spot_id, voter, value):
    return isinstance(value, str) and hmac.compare_digest(token(spot_id, voter), value)


def matches(spot, endpoint, path):
    if spot['page'].startswith(UNITY):
        return False
    if spot['page'] != '*' and spot['page'] != endpoint:
        return False
    return not spot['path'] or spot['path'] == path


def progress(voter):
    """Running hunts with the player's progress: found / total spots, hints for the ones still hidden."""
    out = []
    challenges = running_challenges()
    if not challenges:
        return out
    ids = [int(c['id']) for c in challenges]
    found = _found_ids(voter, ids)
    spots = query('SELECT s.*, g.name AS gift_name, g.icon AS gift_icon FROM spots s LEFT JOIN gifts g ON g.id = s.gift_id'
                  ' WHERE s.active = 1 AND s.challenge_id IN (%s) ORDER BY s.id' % ', '.join(['%s'] * len(ids)), ids)
    counts = _counts([int(s['id']) for s in spots])
    prizes = {int(r['prize_of']) for r in query('SELECT prize_of FROM gift_grants WHERE voter = %s AND prize_of IS NOT NULL', (voter,))}
    for c in challenges:
        mine = [s for s in spots if s['challenge_id'] == c['id']]
        web = [s for s in mine if not s['page'].startswith(UNITY)]
        prize = gift_find(c['prize_gift_id'])
        out.append({
            'id': int(c['id']), 'title': c['title'], 'intro': c['intro'], 'banner': bool(c['banner']),
            'ends_at': c['ends_at'], 'seconds_left': int((c['ends_at'] - utcnow()).total_seconds()) if c['ends_at'] else None,
            'total': len(mine), 'found': sum(1 for s in mine if int(s['id']) in found),
            'spots': [{'id': int(s['id']), 'found': int(s['id']) in found, 'hint': s['hint'],
                       'page': PAGES.get(s['page'], 'Игра') if not s['page'].startswith(UNITY) else 'Игра',
                       'gift': s['gift_name'] if int(s['id']) in found else None,
                       'empty': int(s['id']) not in found and _empty(s, counts)} for s in mine],
            'web': len(web),
            'prize': {'name': prize['name'], 'icon': prize['icon'], 'kind': prize['kind']} if prize else None,
            'prize_taken': int(c['id']) in prizes,
        })
    return out


def for_page(voter, endpoint, path):
    """What the page needs for the hunt: spots on it the player hasn't found (with claim tokens) and the hunts
    for the banner. None when no hunt is running."""
    hunts = progress(voter)
    if not hunts:
        return None
    ids = [h['id'] for h in hunts]
    rows = query('SELECT * FROM spots WHERE active = 1 AND challenge_id IN (%s) ORDER BY id' % ', '.join(['%s'] * len(ids)), ids)
    found = {s['id'] for h in hunts for s in h['spots'] if s['found']}
    counts = _counts([int(s['id']) for s in rows])
    spots = []
    for s in rows:
        if int(s['id']) in found or not matches(s, endpoint, path) or not s['selector'] or _empty(s, counts):
            continue
        spots.append({'id': int(s['id']), 'token': token(s['id'], voter), 'selector': s['selector'],
                      'x': float(s['x']), 'y': float(s['y']), 'size': int(s['size']), 'svg': icon_html(s['icon']),
                      'opacity': HUNT['visibility'].get(s['visibility'], HUNT['visibility']['subtle'])['opacity']})
    banner = [h for h in hunts if h['banner'] and h['web']]
    if not spots and not banner:
        return None
    return {'spots': spots, 'hunts': banner}


def unity_spots(voter):
    """Spots of the game client (page unity:<scene>) in running hunts that the player hasn't found yet.
    x, y are % of the scene's screen; the client draws them as it likes."""
    ids = [int(c['id']) for c in running_challenges()]
    if not ids:
        return []
    rows = query('SELECT * FROM spots WHERE active = 1 AND page LIKE %%s AND challenge_id IN (%s) ORDER BY id'
                 % ', '.join(['%s'] * len(ids)), [UNITY + '%', *ids])
    found = _found_ids(voter, ids)
    counts = _counts([int(s['id']) for s in rows])
    return [{'id': int(s['id']), 'hunt': int(s['challenge_id']), 'scene': s['page'][len(UNITY):], 'x': float(s['x']),
             'y': float(s['y']), 'size': int(s['size']), 'icon': s['icon'], 'visibility': s['visibility'],
             'opacity': HUNT['visibility'].get(s['visibility'], HUNT['visibility']['subtle'])['opacity'], 'hint': s['hint']}
            for s in rows if int(s['id']) not in found and not _empty(s, counts)]


# ---------- Finding a spot ----------

class HuntError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def _take_code(conn, gift_id, grant_id):
    """Gives one free code of the pool to this grant; None when the pool is empty."""
    taken = execute('UPDATE gift_codes SET grant_id = %s WHERE gift_id = %s AND grant_id IS NULL ORDER BY id LIMIT 1',
                    (grant_id, gift_id), conn)
    if not taken:
        return None
    return scalar('SELECT code FROM gift_codes WHERE grant_id = %s AND gift_id = %s', (grant_id, gift_id), conn)


def grant(voter, gift, source, spot_id=None, challenge_id=None, prize_of=None, note='', conn=None):
    """Gives a gift to the player (a copy of it, so later edits of the gift don't change what they got).
    A code gift takes a code from the pool; with the pool empty the grant is made without one (code None)."""
    conn = conn or db()
    gid = insert('INSERT INTO gift_grants (voter, gift_id, source, spot_id, challenge_id, prize_of, kind, name, icon, xp,'
                 ' text, link, note, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
                 (voter, gift['id'], source, spot_id, challenge_id, prize_of, gift['kind'], gift['name'], gift['icon'],
                  int(gift['xp']), gift['text'], gift['link'], note[:255], now()), conn)
    code = None
    if gift['kind'] == 'code':
        code = _take_code(conn, gift['id'], gid)
        if code:
            execute('UPDATE gift_grants SET code = %s WHERE id = %s', (code, gid), conn)
    if gift['kind'] == 'title':
        from .career import _ensure
        _ensure(voter)
        execute('UPDATE players SET title = %s, updated_at = %s WHERE voter = %s', (gift['name'], now(), voter), conn)
    return grant_find(gid, conn)


def grant_find(grant_id, conn=None):
    return query_one('SELECT * FROM gift_grants WHERE id = %s', (grant_id,), conn)


def claim(voter, spot_id, logged_in, check_token=None):
    """The player found a spot. Returns {spot, grant (or None), prize (or None), progress} or raises HuntError:
    gone (no such spot / hunt not running), found (already found), empty (others were faster),
    account (the gift needs an account), blocked (the team took the player out of the hunt), token."""
    from .career import player
    spot = spot_find(spot_id)
    c = challenge_find(spot['challenge_id']) if spot else None
    if not spot or not c or not spot['active'] or not running(c):
        raise HuntError('gone', 'Этот тайник уже исчез: охота закончилась или тайник убрали.')
    if check_token is not None and not token_valid(spot['id'], voter, check_token):
        raise HuntError('token', 'Не удалось открыть тайник. Обновите страницу и попробуйте ещё раз.')
    if int(player(voter).get('blocked') or 0):
        raise HuntError('blocked', 'Команда отстранила вас от охоты за тайниками.')
    gift = gift_find(spot['gift_id'])
    gift = gift if gift and gift['active'] else None
    if gift and gift['needs_account'] and not logged_in:
        raise HuntError('account', 'Этот подарок можно забрать только с аккаунтом. Войдите или зарегистрируйтесь — тайник никуда не денется.')

    conn = db()
    conn.begin()
    try:
        row = query_one('SELECT id, max_finds FROM spots WHERE id = %s FOR UPDATE', (spot['id'],), conn)
        if scalar('SELECT COUNT(*) FROM spot_finds WHERE spot_id = %s AND voter = %s', (spot['id'], voter), conn):
            raise HuntError('found', 'Вы уже нашли этот тайник.')
        if row['max_finds'] and scalar('SELECT COUNT(*) FROM spot_finds WHERE spot_id = %s', (spot['id'],), conn) >= row['max_finds']:
            raise HuntError('empty', 'Тайник пуст: другие игроки успели раньше.')
        given = grant(voter, gift, 'spot', spot['id'], c['id'], conn=conn) if gift else None
        execute('INSERT INTO spot_finds (spot_id, voter, challenge_id, grant_id, created_at) VALUES (%s, %s, %s, %s, %s)',
                (spot['id'], voter, c['id'], given['id'] if given else None, now()), conn)
        prize = None
        total = scalar('SELECT COUNT(*) FROM spots WHERE challenge_id = %s AND active = 1', (c['id'],), conn)
        mine = scalar('SELECT COUNT(*) FROM spot_finds f JOIN spots s ON s.id = f.spot_id'
                      ' WHERE f.challenge_id = %s AND f.voter = %s AND s.active = 1', (c['id'], voter), conn)
        prize_gift = gift_find(c['prize_gift_id'])
        if prize_gift and prize_gift['active'] and mine >= total and not scalar(
                'SELECT COUNT(*) FROM gift_grants WHERE prize_of = %s AND voter = %s', (c['id'], voter), conn):
            prize = grant(voter, prize_gift, 'prize', None, c['id'], prize_of=c['id'], conn=conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    g.pop('hunt_running', None)
    return {'spot': spot, 'challenge': c, 'grant': given, 'prize': prize, 'found': int(mine), 'total': int(total)}


# ---------- The player's gifts ----------

def inventory(voter):
    """Gifts the player has (not revoked), newest first."""
    return query('SELECT * FROM gift_grants WHERE voter = %s AND revoked_at IS NULL ORDER BY id DESC', (voter,))


def titles(voter):
    return list(dict.fromkeys(r['name'] for r in inventory(voter) if r['kind'] == 'title'))


def set_title(voter, name):
    """The player picks which of their titles to wear (or none)."""
    if name and name not in titles(voter):
        return False
    from .career import _ensure
    _ensure(voter)
    execute('UPDATE players SET title = %s, updated_at = %s WHERE voter = %s', (name or None, now(), voter))
    return True


def gift_xp(voter):
    return int(scalar('SELECT COALESCE(SUM(xp), 0) FROM gift_grants WHERE voter = %s AND revoked_at IS NULL', (voter,)))


def revoke(grant_id):
    """Takes a gift back: its XP stops counting, a title it gave is taken off."""
    r = grant_find(grant_id)
    if not r or r['revoked_at']:
        return None
    execute('UPDATE gift_grants SET revoked_at = %s WHERE id = %s', (now(), grant_id))
    if r['kind'] == 'title':
        execute('UPDATE players SET title = NULL WHERE voter = %s AND title = %s AND NOT EXISTS'
                ' (SELECT 1 FROM gift_grants WHERE voter = %s AND kind = %s AND name = %s AND revoked_at IS NULL)',
                (r['voter'], r['name'], r['voter'], 'title', r['name']))
    return r


def public_grant(r):
    """A grant as the game client and the site's JavaScript see it."""
    if not r:
        return None
    kind = GIFT_KINDS.get(r['kind'], {'name': r['kind'], 'icon': 'gift'})
    return {'id': int(r['id']), 'kind': r['kind'], 'kind_name': kind['name'], 'name': r['name'], 'icon': r['icon'],
            'xp': int(r['xp']), 'text': r['text'], 'link': r['link'], 'code': r['code'], 'source': r['source'],
            'code_missing': r['kind'] == 'code' and not r['code'],
            'created_at': r['created_at'].isoformat(sep=' ') if hasattr(r['created_at'], 'isoformat') else r['created_at']}


# ---------- The team's side ----------

GIFT_FIELDS = ('kind', 'name', 'icon', 'xp', 'text', 'link', 'needs_account', 'active')


def gift_save(values, gift_id=None):
    ts = now()
    params = [values[f] for f in GIFT_FIELDS]
    if gift_id:
        execute('UPDATE gifts SET ' + ', '.join(f + ' = %s' for f in GIFT_FIELDS) + ', updated_at = %s WHERE id = %s',
                (*params, ts, gift_id))
        return gift_id
    return insert('INSERT INTO gifts (' + ', '.join(GIFT_FIELDS) + ', created_at, updated_at) VALUES ('
                  + ', '.join(['%s'] * len(GIFT_FIELDS)) + ', %s, %s)', (*params, ts, ts))


def codes_add(gift_id, codes):
    """Adds codes to a gift's pool (duplicates are skipped); returns how many were added."""
    added = 0
    for code in codes:
        added += execute('INSERT IGNORE INTO gift_codes (gift_id, code) VALUES (%s, %s)', (gift_id, code))
    return added


def codes_of(gift_id):
    return query('SELECT c.code, c.grant_id, r.voter, r.created_at FROM gift_codes c LEFT JOIN gift_grants r ON r.id = c.grant_id'
                 ' WHERE c.gift_id = %s ORDER BY c.grant_id IS NULL, c.id', (gift_id,))


def codes_remove_free(gift_id):
    return execute('DELETE FROM gift_codes WHERE gift_id = %s AND grant_id IS NULL', (gift_id,))


CHALLENGE_FIELDS = ('title', 'intro', 'status', 'starts_at', 'ends_at', 'banner', 'prize_gift_id')


def challenge_save(values, challenge_id=None):
    ts = now()
    params = [values[f] for f in CHALLENGE_FIELDS]
    if challenge_id:
        execute('UPDATE challenges SET ' + ', '.join(f + ' = %s' for f in CHALLENGE_FIELDS) + ', updated_at = %s WHERE id = %s',
                (*params, ts, challenge_id))
        return challenge_id
    return insert('INSERT INTO challenges (' + ', '.join(CHALLENGE_FIELDS) + ', created_at, updated_at) VALUES ('
                  + ', '.join(['%s'] * len(CHALLENGE_FIELDS)) + ', %s, %s)', (*params, ts, ts))


SPOT_FIELDS = ('label', 'page', 'path', 'icon', 'size', 'visibility', 'hint', 'gift_id', 'max_finds', 'active')


def spot_save(values, challenge_id=None, spot_id=None):
    ts = now()
    params = [values[f] for f in SPOT_FIELDS]
    if spot_id:
        execute('UPDATE spots SET ' + ', '.join(f + ' = %s' for f in SPOT_FIELDS) + ', updated_at = %s WHERE id = %s',
                (*params, ts, spot_id))
        return spot_id
    return insert('INSERT INTO spots (challenge_id, ' + ', '.join(SPOT_FIELDS) + ', created_at, updated_at) VALUES (%s, '
                  + ', '.join(['%s'] * len(SPOT_FIELDS)) + ', %s, %s)', (challenge_id, *params, ts, ts))


def spot_place(spot_id, page, path, selector, x, y):
    execute('UPDATE spots SET page = %s, path = %s, selector = %s, x = %s, y = %s, updated_at = %s WHERE id = %s',
            (page, path, selector, x, y, now(), spot_id))


def finds_of(challenge_id, limit=200):
    return query('SELECT f.*, s.label, s.page, r.name AS gift_name, r.code, r.revoked_at, u.display_name, u.login'
                 ' FROM spot_finds f JOIN spots s ON s.id = f.spot_id LEFT JOIN gift_grants r ON r.id = f.grant_id'
                 ' LEFT JOIN players p ON p.voter = f.voter LEFT JOIN users u ON u.id = p.user_id'
                 ' WHERE f.challenge_id = %s ORDER BY f.created_at DESC LIMIT %s', (challenge_id, limit))


def challenge_totals(challenge_id):
    return query_one('SELECT COUNT(*) AS finds, COUNT(DISTINCT voter) AS finders,'
                     ' (SELECT COUNT(*) FROM gift_grants WHERE challenge_id = %s AND revoked_at IS NULL) AS gifts,'
                     ' (SELECT COUNT(*) FROM gift_grants WHERE prize_of = %s AND revoked_at IS NULL) AS prizes'
                     ' FROM spot_finds WHERE challenge_id = %s', (challenge_id, challenge_id, challenge_id))


def preview_spots(challenge_id):
    """For the team's «посмотреть» mode: every placed spot of a hunt, whatever its state."""
    return [{'id': int(s['id']), 'selector': s['selector'], 'x': float(s['x']), 'y': float(s['y']), 'size': int(s['size']),
             'svg': icon_html(s['icon']), 'label': s['label'] or 'Тайник %d' % s['id'], 'page': s['page'], 'path': s['path']}
            for s in spots_of(challenge_id) if s['selector'] and not s['page'].startswith(UNITY)]


def dumps(value):
    """JSON for a <script type="application/json"> block: safe inside HTML."""
    return json.dumps(value, ensure_ascii=False, default=str).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
