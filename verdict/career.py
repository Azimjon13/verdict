"""Judge career: the player's world, the case of the day, days in a row, XP and ranks, world events, achievements.

Whatever the votes can tell is computed from the votes table, so it can't drift from what really happened.
The players table keeps only what votes can't: when the world was started anew, the day streak, how many cases
of the day were judged on their day, and which world events and achievements were already announced.
"""
import json
import random
from datetime import datetime, timedelta, timezone

from flask import g

from .catalog import ACHIEVEMENTS, CATEGORIES, METRIC_STEP, METRICS, RANKS, WORLD_EVENTS, WORLD_LEVELS, XP
from .db import execute, now, query, query_one, scalar
from .judge import effects_map, judge_profile

RECENT_DAILY_DAYS = 30  # a case of the day doesn't come back within this many days, while others are left


def today():
    """Days change at midnight UTC (early morning in Moscow and Tashkent) — the same for every player."""
    return datetime.now(timezone.utc).date()


def seconds_to_next_day():
    t = datetime.now(timezone.utc)
    return int((datetime.combine(t.date() + timedelta(days=1), datetime.min.time(), timezone.utc) - t).total_seconds())


# ---------- The players row ----------

def player(voter):
    row = query_one('SELECT * FROM players WHERE voter = %s', (voter,))
    return row or {'voter': voter, 'user_id': None, 'world_since': None, 'last_day': None, 'streak': 0, 'best_streak': 0,
                   'last_daily': None, 'daily_done': 0, 'events': None, 'achievements': None, 'title': None, 'blocked': 0}


def _ensure(voter):
    ts = now()
    execute('INSERT IGNORE INTO players (voter, created_at, updated_at) VALUES (%s, %s, %s)', (voter, ts, ts))


def _keys(text):
    try:
        value = json.loads(text or '[]')
    except ValueError:
        return []
    return value if isinstance(value, list) else []


def _forget(voter):
    g.pop('career_world', None)


# ---------- The world ----------

def level_of(value):
    if value <= WORLD_LEVELS['zero']:
        return 'zero'
    if value <= WORLD_LEVELS['low']:
        return 'low'
    if value >= WORLD_LEVELS['peak']:
        return 'peak'
    if value >= WORLD_LEVELS['high']:
        return 'high'
    return None


def _implied(meter, level):
    """An event and the milder one it passed through: a meter at 0 has also been «low»."""
    if level == 'zero':
        return [meter + '_low', meter + '_zero']
    if level == 'peak':
        return [meter + '_high', meter + '_peak']
    return [meter + '_' + level] if level else []


def event_info(key):
    meter, level = key.rsplit('_', 1)
    return {'key': key, 'meter': meter, 'level': level, 'tone': 'up' if level in ('high', 'peak') else 'down',
            'icon': METRICS[meter]['icon'], 'meter_name': METRICS[meter]['name'], **WORLD_EVENTS[key]}


def world(voter):
    """The player's world: meters (0–100, start at 50) from every verdict on a case in play since the world was
    last started anew, how many verdicts that is, and the world events active now."""
    cache = g.setdefault('career_world', {})
    if voter in cache:
        return cache[voter]
    p = player(voter)
    sql = ("SELECT v.situation_id, v.option_key FROM votes v JOIN situations s ON s.id = v.situation_id"
           " WHERE v.voter = %s AND s.status = 'approved'")
    params = [voter]
    if p['world_since']:
        sql += ' AND v.created_at > %s'  # a verdict in the same second as the reset belongs to the old world
        params.append(p['world_since'])
    rows = query(sql, params)
    effects = effects_map()
    total = {m: 0 for m in METRICS}
    for r in rows:
        for m, v in (effects.get(int(r['situation_id']), {}).get(r['option_key']) or {}).items():
            if m in total:
                total[m] += int(v)
    metrics = {m: max(0, min(100, 50 + v * METRIC_STEP)) for m, v in total.items()}
    active = [event_info(m + '_' + lv) for m, lv in ((m, level_of(v)) for m, v in metrics.items()) if lv]
    cache[voter] = {'metrics': metrics, 'count': len(rows), 'active': active, 'seen': _keys(p['events'])}
    return cache[voter]


def reset_world(voter):
    """Starts the world anew: meters back to 50, events forgotten. Votes and the career stay."""
    _ensure(voter)
    execute("UPDATE players SET world_since = %s, events = '[]', updated_at = %s WHERE voter = %s", (now(), now(), voter))
    _forget(voter)


# ---------- The case of the day ----------

def daily_case_id(day=None):
    """One case of the day for everyone, kept in meta (daily:YYYY-MM-DD), so it doesn't change within the day.
    Picked among cases in play that weren't the case of the day recently."""
    day = day or today()
    key = 'daily:' + day.isoformat()
    approved = [int(r['id']) for r in query("SELECT id FROM situations WHERE status = 'approved' ORDER BY id")]
    if not approved:
        return None
    stored = scalar('SELECT meta_value FROM meta WHERE meta_key = %s', (key,))
    if stored is not None and int(stored) in approved:
        return int(stored)
    recent_keys = ['daily:' + (day - timedelta(days=i)).isoformat() for i in range(1, RECENT_DAILY_DAYS + 1)]
    recent = {int(r['meta_value']) for r in query('SELECT meta_value FROM meta WHERE meta_key IN (%s)'
                                                  % ', '.join(['%s'] * len(recent_keys)), recent_keys)}
    pool = [i for i in approved if i not in recent] or approved
    pick = random.Random(key).choice(pool)
    if stored is None:
        execute('INSERT IGNORE INTO meta (meta_key, meta_value) VALUES (%s, %s)', (key, str(pick)))
    else:  # yesterday's choice left the game (returned to review, deleted): pick another
        execute('UPDATE meta SET meta_value = %s WHERE meta_key = %s', (str(pick), key))
    return int(scalar('SELECT meta_value FROM meta WHERE meta_key = %s', (key,)))


def daily(voter):
    """Today's case for this player: its id, whether they judged it today (bonus taken) or earlier."""
    sid = daily_case_id()
    p = player(voter)
    judged = bool(sid) and scalar('SELECT COUNT(*) FROM votes WHERE situation_id = %s AND voter = %s', (sid, voter)) > 0
    return {'id': sid, 'judged': judged, 'today': p['last_daily'] == today(), 'seconds_left': seconds_to_next_day(),
            'bonus': XP['daily']}


# ---------- XP, ranks, streak ----------

def stats(voter):
    r = query_one("SELECT COUNT(*) AS n, COALESCE(SUM(v.guess_correct), 0) AS right_guesses,"
                  " COUNT(DISTINCT s.category) AS categories, COALESCE(SUM(v.option_key = 'other'), 0) AS own,"
                  " COALESCE(MAX(v.duration_ms), 0) AS longest"
                  " FROM votes v JOIN situations s ON s.id = v.situation_id WHERE v.voter = %s AND s.status = 'approved'",
                  (voter,))
    out = {k: int(v) for k, v in r.items()}
    out['gift_xp'] = int(scalar('SELECT COALESCE(SUM(xp), 0) FROM gift_grants WHERE voter = %s AND revoked_at IS NULL', (voter,)))
    return out


def xp_total(verdicts, right_guesses, daily, gift_xp):
    """The XP formula — the only one: verdicts on cases in play, right guesses of the majority, cases of the day judged
    on their day, plus XP from gifts (treasure hunts, campaign endings, the team). xp_sql is the same in SQL."""
    return (int(verdicts or 0) * XP['verdict'] + int(right_guesses or 0) * XP['guess'] + int(daily or 0) * XP['daily']
            + int(gift_xp or 0))


def xp_sql(verdicts, right_guesses, daily, gift_xp):
    """xp_total as an SQL expression over these columns (NULL counts as 0), for sorting and counting in the database."""
    return 'COALESCE(%s, 0) * %d + COALESCE(%s, 0) * %d + COALESCE(%s, 0) * %d + COALESCE(%s, 0)' % (
        verdicts, int(XP['verdict']), right_guesses, int(XP['guess']), daily, int(XP['daily']), gift_xp)


def xp_of(st, p):
    """A player's XP from stats() and the players row."""
    return xp_total(st['n'], st['right_guesses'], p['daily_done'], st.get('gift_xp', 0))


def rank_of(xp):
    """The rank for this much XP and the way to the next one (progress 0..1; next is None at the top)."""
    level = max(i for i, r in enumerate(RANKS) if xp >= r['xp'])
    cur = RANKS[level]
    nxt = RANKS[level + 1] if level + 1 < len(RANKS) else None
    progress = 1.0 if nxt is None else (xp - cur['xp']) / (nxt['xp'] - cur['xp'])
    return {**cur, 'level': level + 1, 'levels': len(RANKS), 'progress': progress,
            'next': {k: nxt[k] for k in ('key', 'name', 'xp')} if nxt else None, 'to_next': nxt['xp'] - xp if nxt else 0}


def streak_now(p):
    """Days in a row with a verdict; it is still alive today if the last verdict was yesterday."""
    last = p['last_day']
    return int(p['streak']) if last and last >= today() - timedelta(days=1) else 0


def summary(voter):
    """What the header of a page shows: XP, rank, streak."""
    p = player(voter)
    st = stats(voter)
    xp = xp_of(st, p)
    return {'xp': xp, 'rank': rank_of(xp), 'streak': streak_now(p), 'best_streak': int(p['best_streak']),
            'daily_done': int(p['daily_done']), 'verdicts': st['n'], 'title': p.get('title')}


# ---------- Achievements ----------

def _best_guess_run(voter):
    best = run = 0
    for r in query('SELECT guess_correct FROM votes WHERE voter = %s AND guess_correct IS NOT NULL ORDER BY created_at, id', (voter,)):
        run = run + 1 if int(r['guess_correct']) == 1 else 0
        best = max(best, run)
    return best


def _earned(voter, p, st, profile):
    approved = query("SELECT COUNT(*) AS n, COUNT(DISTINCT category) AS c FROM situations WHERE status = 'approved'")[0]
    checks = {
        'first': st['n'] >= 1,
        'ten': st['n'] >= 10,
        'archive': int(approved['n']) >= 10 and st['n'] >= int(approved['n']),
        'categories': st['categories'] >= min(len(CATEGORIES), int(approved['c'])) > 0,
        'intuition': _best_guess_run(voter) >= 3,
        'bold': profile['boldest'] is not None,
        'own': st['own'] >= 1,
        'style': profile['archetype'] is not None,
        'daily': int(p['daily_done']) >= 1,
        'streak3': int(p['best_streak']) >= 3,
        'streak7': int(p['best_streak']) >= 7,
        'world': bool(_keys(p['events'])),
        'thinker': st['longest'] >= 120000,
    }
    return {k for k, ok in checks.items() if ok}


def achievements(voter, profile=None, p=None, st=None):
    """Every achievement with an `unlocked` flag, and the keys unlocked just now. Unlocked ones are stored,
    so they stay even if a case later leaves the game."""
    p = p or player(voter)
    st = st or stats(voter)
    profile = profile or judge_profile(voter)
    stored = set(_keys(p['achievements']))
    new = _earned(voter, p, st, profile) - stored
    if new:
        _ensure(voter)
        keys = [k for k in ACHIEVEMENTS if k in stored | new]
        execute('UPDATE players SET achievements = %s, updated_at = %s WHERE voter = %s', (json.dumps(keys), now(), voter))
    have = stored | new
    return [{'key': k, **a, 'unlocked': k in have} for k, a in ACHIEVEMENTS.items()], [k for k in ACHIEVEMENTS if k in new]


# ---------- After a verdict ----------

def snapshot(voter):
    """Taken before a vote is saved, to tell afterwards what the verdict changed."""
    p = player(voter)
    xp = xp_of(stats(voter), p)
    return {'xp': xp, 'rank': rank_of(xp)['key'], 'metrics': dict(world(voter)['metrics'])}


def record_verdict(voter, situation_id, before, profile=None):
    """Updates the streak, the case of the day and world events after a saved verdict; returns what to tell the
    player: XP gained, rank (and whether it went up), streak, new world events, new achievements, the world."""
    _ensure(voter)
    p = player(voter)
    day = today()
    streak, best, streak_up = int(p['streak']), int(p['best_streak']), False
    if p['last_day'] != day:
        streak = streak + 1 if p['last_day'] == day - timedelta(days=1) else 1
        best = max(best, streak)
        streak_up = True
    daily_now = situation_id == daily_case_id(day) and p['last_daily'] != day
    execute('UPDATE players SET last_day = %s, streak = %s, best_streak = %s, last_daily = %s, daily_done = daily_done + %s,'
            ' updated_at = %s WHERE voter = %s',
            (day, streak, best, day if daily_now else p['last_daily'], 1 if daily_now else 0, now(), voter))

    _forget(voter)
    w = world(voter)
    seen = set(w['seen'])
    new_events = []
    for e in w['active']:
        implied = _implied(e['meter'], e['level'])
        if not set(implied) <= seen:
            new_events.append(e)  # the deepest level is the one announced
            seen.update(implied)
    if new_events:
        execute('UPDATE players SET events = %s WHERE voter = %s', (json.dumps(sorted(seen)), voter))
        _forget(voter)
        w = world(voter)

    p = player(voter)
    st = stats(voter)
    xp = xp_of(st, p)
    rank = rank_of(xp)
    _, new_keys = achievements(voter, profile, p, st)
    return {
        'xp': xp,
        'xp_gained': xp - before['xp'],
        'rank': rank,
        'rank_up': rank['key'] != before['rank'],
        'streak': streak,
        'streak_up': streak_up,
        'daily': daily_now,
        'events': new_events,
        'achievements': [{'key': k, **ACHIEVEMENTS[k]} for k in new_keys],
        'world': {
            'metrics': w['metrics'],
            'deltas': {m: w['metrics'][m] - before['metrics'][m] for m in METRICS if w['metrics'][m] != before['metrics'][m]},
            'count': w['count'],
            'active': w['active'],
        },
    }
