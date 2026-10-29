"""Players as people: activity by day, the link between a player and an account, and the team's view of players.

A player is the anonymous id in the cookie (or X-Voter-Id in the game client). That id is the player's key to
their verdicts, so it is never shown to other players. An account (users) is the public side: once a player
signs in, their progress follows the account to any device. Friends, communities and ratings will hang off
accounts, see docs/ARCHITECTURE.md.
"""
import json
import secrets

from flask import g, request

from .catalog import ACHIEVEMENTS, XP
from .db import execute, now, query, query_one, scalar
from .web import VOTER_ID


# ---------- Activity ----------

def touch(voter):
    """Counts a page view for today. Called once per request, for players whose cookie was already set — a
    browser that keeps cookies — so bots and one-off hits don't inflate the numbers."""
    from .career import today
    execute('INSERT INTO player_days (voter, day, hits) VALUES (%s, %s, 1) ON DUPLICATE KEY UPDATE hits = hits + 1',
            (voter, today()))


# ---------- Accounts ----------

def voter_of_user(user_id):
    return scalar('SELECT voter FROM players WHERE user_id = %s', (user_id,))


def user_of_voter(voter):
    return scalar('SELECT user_id FROM players WHERE voter = %s', (voter,))


def _link(voter, user_id):
    ts = now()
    execute('INSERT INTO players (voter, user_id, created_at, updated_at) VALUES (%s, %s, %s, %s)'
            ' ON DUPLICATE KEY UPDATE user_id = VALUES(user_id), updated_at = VALUES(updated_at)', (voter, user_id, ts, ts))


def switch_voter(vid):
    """The browser continues as this player from the next response on."""
    g.voter = vid
    g.voter_new = True


def on_register(user_id, voter):
    """A new account takes over what the player did on this device so far."""
    if user_of_voter(voter) is None:
        _link(voter, user_id)
    else:  # this device's player already belongs to another account: the new account starts clean
        vid = secrets.token_hex(16)
        _link(vid, user_id)
        switch_voter(vid)


def attach(user_id, voter):
    """Signing in on a device: returns the account's player id. Whatever this device's player did anonymously
    (verdicts, gifts, finds) is merged into the account; a device player of another account is left alone."""
    mine = voter_of_user(user_id)
    owner = user_of_voter(voter) if voter else None
    if mine is None:
        if voter and owner is None:
            _link(voter, user_id)
            return voter
        mine = secrets.token_hex(16)
        _link(mine, user_id)
    elif voter and mine != voter and owner is None:
        merge(voter, mine)
    return mine


def on_login(user_id, voter):
    """After sign-in the browser plays as the account's player (see attach). Returns that player id."""
    mine = attach(user_id, voter)
    if mine != voter:
        switch_voter(mine)
    return mine


def on_logout():
    """A signed-out browser becomes a new anonymous player, so the next person at this device doesn't play
    as the account."""
    switch_voter(secrets.token_hex(16))


def _keys(text):
    try:
        value = json.loads(text or '[]')
    except ValueError:
        return []
    return value if isinstance(value, list) else []


def merge(source, target):
    """Moves an anonymous player's progress into another player (the account's). Where both judged the same case,
    the account's verdict stays."""
    if source == target:
        return
    execute('UPDATE IGNORE votes SET voter = %s WHERE voter = %s', (target, source))
    execute('DELETE FROM votes WHERE voter = %s', (source,))
    execute('UPDATE IGNORE spot_finds SET voter = %s WHERE voter = %s', (target, source))
    execute('DELETE FROM spot_finds WHERE voter = %s', (source,))
    execute('UPDATE IGNORE gift_grants SET voter = %s WHERE voter = %s', (target, source))
    execute('DELETE FROM gift_grants WHERE voter = %s', (source,))  # a second main prize of the same hunt
    execute('INSERT INTO player_days (voter, day, hits) SELECT %s, d.day, d.hits FROM player_days d WHERE d.voter = %s'
            ' ON DUPLICATE KEY UPDATE hits = player_days.hits + d.hits', (target, source))
    execute('DELETE FROM player_days WHERE voter = %s', (source,))

    a = query_one('SELECT * FROM players WHERE voter = %s', (source,))
    if a:
        from .career import _ensure
        _ensure(target)
        b = query_one('SELECT * FROM players WHERE voter = %s', (target,))
        latest = a if a['last_day'] and (not b['last_day'] or a['last_day'] > b['last_day']) else b
        achievements = [k for k in ACHIEVEMENTS if k in set(_keys(a['achievements'])) | set(_keys(b['achievements']))]
        execute('UPDATE players SET last_day = %s, streak = %s, best_streak = %s, last_daily = %s, daily_done = %s,'
                ' achievements = %s, title = COALESCE(title, %s), updated_at = %s WHERE voter = %s',
                (latest['last_day'], latest['streak'], max(int(a['best_streak']), int(b['best_streak'])),
                 max([d for d in (a['last_daily'], b['last_daily']) if d], default=None),
                 int(a['daily_done']) + int(b['daily_done']), json.dumps(achievements), a['title'], now(), target))
        execute('DELETE FROM players WHERE voter = %s', (source,))
    g.pop('career_world', None)


# ---------- The team's view ----------

def _xp_sql():
    return ('COALESCE(v.n, 0) * %d + COALESCE(v.right_guesses, 0) * %d + COALESCE(p.daily_done, 0) * %d + COALESCE(x.xp, 0)'
            % (int(XP['verdict']), int(XP['guess']), int(XP['daily'])))


_BASE = """
    FROM (SELECT voter FROM player_days UNION SELECT voter FROM players) a
    LEFT JOIN players p ON p.voter = a.voter
    LEFT JOIN users u ON u.id = p.user_id
    LEFT JOIN (SELECT v.voter, COUNT(*) AS n, COALESCE(SUM(v.guess_correct), 0) AS right_guesses, MAX(v.created_at) AS last_vote
               FROM votes v JOIN situations s ON s.id = v.situation_id AND s.status = 'approved' GROUP BY v.voter) v ON v.voter = a.voter
    LEFT JOIN (SELECT voter, MIN(day) AS first_day, MAX(day) AS last_day, COUNT(*) AS days, SUM(hits) AS hits
               FROM player_days GROUP BY voter) d ON d.voter = a.voter
    LEFT JOIN (SELECT voter, SUM(xp) AS xp, COUNT(*) AS gifts FROM gift_grants WHERE revoked_at IS NULL GROUP BY voter) x ON x.voter = a.voter
    LEFT JOIN (SELECT voter, COUNT(*) AS finds FROM spot_finds GROUP BY voter) f ON f.voter = a.voter
"""

SORTS = {
    'recent': 'COALESCE(d.last_day, DATE(v.last_vote)) DESC, a.voter',
    'xp': 'xp DESC, a.voter',
    'verdicts': 'verdicts DESC, a.voter',
    'new': 'd.first_day DESC, a.voter',
    'finds': 'finds DESC, a.voter',
}


def players_list(q='', who='players', sort='recent', page=1, per_page=50):
    """Players for the team: who (players — with a verdict, accounts — signed up, blocked, all — every visitor),
    search by id prefix, login or name. Returns (rows, total)."""
    where, params = [], []
    if who == 'players':
        where.append('COALESCE(v.n, 0) > 0')
    elif who == 'accounts':
        where.append('p.user_id IS NOT NULL')
    elif who == 'blocked':
        where.append('p.blocked = 1')
    q = (q or '').strip()
    if q:
        if VOTER_ID.match(q.lower()) or (q.isalnum() and all(ch in '0123456789abcdef' for ch in q.lower()) and len(q) >= 4):
            where.append('a.voter LIKE %s')
            params.append(q.lower() + '%')
        else:
            where.append('(u.login LIKE %s OR u.display_name LIKE %s)')
            params += ['%' + q + '%', '%' + q + '%']
    cond = (' WHERE ' + ' AND '.join(where)) if where else ''
    total = int(scalar('SELECT COUNT(*) ' + _BASE + cond, params))
    page = max(1, int(page))
    rows = query('SELECT a.voter, p.user_id, p.blocked, p.title, p.streak, p.best_streak, p.daily_done, u.login, u.display_name,'
                 ' COALESCE(v.n, 0) AS verdicts, COALESCE(v.right_guesses, 0) AS right_guesses, v.last_vote,'
                 ' d.first_day, d.last_day, COALESCE(d.days, 0) AS days, COALESCE(d.hits, 0) AS hits,'
                 ' COALESCE(x.gifts, 0) AS gifts, COALESCE(f.finds, 0) AS finds, ' + _xp_sql() + ' AS xp '
                 + _BASE + cond + ' ORDER BY ' + SORTS.get(sort, SORTS['recent']) + ' LIMIT %s OFFSET %s',
                 [*params, per_page, (page - 1) * per_page])
    return rows, total


def player_detail(voter):
    row = query_one('SELECT a.voter, p.user_id, p.blocked, p.title, u.login, u.display_name, u.role, u.created_at AS user_since,'
                    ' d.first_day, d.last_day, COALESCE(d.days, 0) AS days, COALESCE(d.hits, 0) AS hits '
                    + _BASE + ' WHERE a.voter = %s', (voter,))
    return row


def player_votes(voter, limit=40):
    return query('SELECT v.situation_id, v.option_key, v.reasoning, v.mode, v.guess_correct, v.duration_ms, v.created_at,'
                 ' s.title, s.status, s.category FROM votes v JOIN situations s ON s.id = v.situation_id'
                 ' WHERE v.voter = %s ORDER BY v.created_at DESC, v.id DESC LIMIT %s', (voter, limit))


def player_finds(voter):
    return query('SELECT f.created_at, s.label, s.page, c.title AS challenge FROM spot_finds f JOIN spots s ON s.id = f.spot_id'
                 ' JOIN challenges c ON c.id = f.challenge_id WHERE f.voter = %s ORDER BY f.created_at DESC', (voter,))


def player_grants(voter):
    return query('SELECT * FROM gift_grants WHERE voter = %s ORDER BY id DESC', (voter,))


def set_blocked(voter, blocked):
    from .career import _ensure
    _ensure(voter)
    execute('UPDATE players SET blocked = %s, updated_at = %s WHERE voter = %s', (1 if blocked else 0, now(), voter))


def delete_player(voter):
    """Removes everything the game knows about a player: verdicts, career, gifts, finds, activity. The account
    (if any) stays — it is a separate thing, managed on the «Команда» page."""
    for table in ('votes', 'spot_finds', 'gift_grants', 'player_days', 'players'):
        execute('DELETE FROM %s WHERE voter = %%s' % table, (voter,))


def exists(voter):
    return bool(scalar('SELECT 1 FROM players WHERE voter = %s UNION SELECT 1 FROM player_days WHERE voter = %s'
                       ' UNION SELECT 1 FROM votes WHERE voter = %s LIMIT 1', (voter, voter, voter)))


def track_request(endpoint):
    """after_request: counts activity for page views and game-client calls (not assets or the team's pages)."""
    if not endpoint or endpoint == 'static' or endpoint.startswith('admin') or request.method == 'OPTIONS':
        return
    if endpoint.startswith('api_v1.'):
        user = g.get('api_account')
        vid = voter_of_user(int(user['id'])) if user else request.headers.get('X-Voter-Id', '').strip().lower()
        if vid and VOTER_ID.match(vid):
            touch(vid)
        return
    if g.get('voter') and not g.get('voter_new'):
        touch(g.voter)
