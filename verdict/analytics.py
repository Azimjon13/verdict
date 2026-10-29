"""Numbers for the team's dashboard. Everything is computed from what the game already stores: votes, activity by
day (player_days), the players table, hunts and gifts. Days are UTC, like the case of the day."""
import json
from datetime import datetime, time, timedelta

from .career import rank_of, today
from .catalog import ACHIEVEMENTS, CATEGORIES, JUDGE_MIN_VERDICTS, RANKS, XP
from .db import query, query_one, scalar
from .helpers import case_controversy
from .repository import situations_list, vote_counts


def _start(day):
    return datetime.combine(day, time.min)


def _days(n):
    t = today()
    return [t - timedelta(days=i) for i in range(n - 1, -1, -1)]


def kpis():
    t = today()
    d7, d30 = t - timedelta(days=6), t - timedelta(days=29)
    first = '(SELECT voter, MIN(day) AS f FROM player_days GROUP BY voter) t'
    approved = "JOIN situations s ON s.id = v.situation_id AND s.status = 'approved'"
    return {
        'players': int(scalar('SELECT COUNT(DISTINCT v.voter) FROM votes v ' + approved)),
        'visitors': int(scalar('SELECT COUNT(DISTINCT voter) FROM player_days')),
        'accounts': int(scalar('SELECT COUNT(*) FROM players WHERE user_id IS NOT NULL')),
        'active_today': int(scalar('SELECT COUNT(*) FROM player_days WHERE day = %s', (t,))),
        'active_7': int(scalar('SELECT COUNT(DISTINCT voter) FROM player_days WHERE day >= %s', (d7,))),
        'active_30': int(scalar('SELECT COUNT(DISTINCT voter) FROM player_days WHERE day >= %s', (d30,))),
        'new_7': int(scalar('SELECT COUNT(*) FROM ' + first + ' WHERE t.f >= %s', (d7,))),
        'verdicts_today': int(scalar('SELECT COUNT(*) FROM votes WHERE created_at >= %s', (_start(t),))),
        'verdicts_7': int(scalar('SELECT COUNT(*) FROM votes WHERE created_at >= %s', (_start(d7),))),
        'verdicts': int(scalar('SELECT COUNT(*) FROM votes v ' + approved)),
        'in_play': int(scalar("SELECT COUNT(*) FROM situations WHERE status = 'approved'")),
        'pending': int(scalar("SELECT COUNT(*) FROM situations WHERE status = 'pending'")),
    }


def daily_series(n=30):
    """Per day for the last n days: visitors, new visitors, verdicts, players who gave a verdict."""
    days = _days(n)
    since = days[0]
    visitors = {r['day']: int(r['c']) for r in query('SELECT day, COUNT(*) AS c FROM player_days WHERE day >= %s GROUP BY day', (since,))}
    new = {r['f']: int(r['c']) for r in query('SELECT f, COUNT(*) AS c FROM (SELECT voter, MIN(day) AS f FROM player_days GROUP BY voter) t'
                                               ' WHERE f >= %s GROUP BY f', (since,))}
    verdicts, judges = {}, {}
    for r in query('SELECT DATE(created_at) AS d, COUNT(*) AS c, COUNT(DISTINCT voter) AS p FROM votes WHERE created_at >= %s'
                   ' GROUP BY DATE(created_at)', (_start(since),)):
        verdicts[r['d']], judges[r['d']] = int(r['c']), int(r['p'])
    return [{'day': d, 'visitors': visitors.get(d, 0), 'new': new.get(d, 0), 'verdicts': verdicts.get(d, 0),
             'judges': judges.get(d, 0)} for d in days]


def retention(n=30):
    """Of the players who first came in the last n days: the share back the next day (D1) and within a week (D7).
    Only cohorts whose window is over count, so a player who came today doesn't pull D1 down."""
    t = today()
    rows = query('SELECT t.voter, t.f, MAX(d.day = t.f + INTERVAL 1 DAY) AS d1,'
                 ' MAX(d.day > t.f AND d.day <= t.f + INTERVAL 7 DAY) AS d7'
                 ' FROM (SELECT voter, MIN(day) AS f FROM player_days GROUP BY voter) t'
                 ' JOIN player_days d ON d.voter = t.voter WHERE t.f >= %s GROUP BY t.voter, t.f', (t - timedelta(days=n),))
    c1 = [r for r in rows if r['f'] <= t - timedelta(days=1)]
    c7 = [r for r in rows if r['f'] <= t - timedelta(days=7)]
    return {
        'd1': sum(int(r['d1'] or 0) for r in c1) / len(c1) if c1 else None, 'd1_base': len(c1),
        'd7': sum(int(r['d7'] or 0) for r in c7) / len(c7) if c7 else None, 'd7_base': len(c7),
    }


def funnel():
    """From a visit to a regular: how many players reached each step (all time)."""
    r = query_one("SELECT COUNT(*) AS visitors, COALESCE(SUM(n >= 1), 0) AS v1, COALESCE(SUM(n >= 5), 0) AS v5,"
                  " COALESCE(SUM(n >= 10), 0) AS v10, COALESCE(SUM(n >= %s), 0) AS style, COALESCE(SUM(days >= 2), 0) AS returned"
                  " FROM (SELECT a.voter, COALESCE(v.n, 0) AS n, COALESCE(d.days, 0) AS days"
                  "       FROM (SELECT voter FROM player_days UNION SELECT voter FROM votes) a"
                  "       LEFT JOIN (SELECT voter, COUNT(*) AS n FROM votes GROUP BY voter) v ON v.voter = a.voter"
                  "       LEFT JOIN (SELECT voter, COUNT(*) AS days FROM player_days GROUP BY voter) d ON d.voter = a.voter) x",
                  (JUDGE_MIN_VERDICTS,))
    accounts = int(scalar('SELECT COUNT(*) FROM players WHERE user_id IS NOT NULL'))
    steps = [
        ('Зашли на сайт', int(r['visitors'])),
        ('Вынесли первый вердикт', int(r['v1'])),
        ('Вернулись в другой день', int(r['returned'])),
        ('5 вердиктов', int(r['v5'])),
        ('Открыли стиль судьи (%d)' % JUDGE_MIN_VERDICTS, int(r['style'])),
        ('10 вердиктов', int(r['v10'])),
        ('Завели аккаунт', accounts),
    ]
    top = steps[0][1] or 1
    return [{'label': label, 'value': v, 'share': v / top} for label, v in steps]


def modes(n=30):
    """Быстрый суд vs the full case file over the last n days: verdicts and the median time to decide."""
    since = _start(today() - timedelta(days=n - 1))
    out = {}
    for mode in ('quick', 'full'):
        count = int(scalar('SELECT COUNT(*) FROM votes WHERE mode = %s AND created_at >= %s', (mode, since)))
        timed = int(scalar('SELECT COUNT(*) FROM votes WHERE mode = %s AND created_at >= %s AND duration_ms IS NOT NULL', (mode, since)))
        median = scalar('SELECT duration_ms FROM votes WHERE mode = %s AND created_at >= %s AND duration_ms IS NOT NULL'
                        ' ORDER BY duration_ms LIMIT 1 OFFSET %s', (mode, since, timed // 2)) if timed else None
        out[mode] = {'verdicts': count, 'median_ms': int(median) if median is not None else None}
    return out


def by_hour(n=30):
    """Verdicts by hour of the day (UTC) over the last n days — when people play."""
    hours = {int(r['h']): int(r['c']) for r in query('SELECT HOUR(created_at) AS h, COUNT(*) AS c FROM votes WHERE created_at >= %s'
                                                     ' GROUP BY HOUR(created_at)', (_start(today() - timedelta(days=n - 1)),))}
    return [hours.get(h, 0) for h in range(24)]


def by_category():
    counts = {r['category']: int(r['c']) for r in query("SELECT s.category, COUNT(*) AS c FROM votes v JOIN situations s"
                                                        " ON s.id = v.situation_id AND s.status = 'approved' GROUP BY s.category")}
    return sorted(({'key': k, 'name': c['name'], 'icon': c['icon'], 'value': counts.get(k, 0)} for k, c in CATEGORIES.items()),
                  key=lambda r: -r['value'])


def by_rank():
    rows = query("SELECT COALESCE(v.n, 0) * %s + COALESCE(v.g, 0) * %s + COALESCE(p.daily_done, 0) * %s + COALESCE(x.xp, 0) AS xp"
                 " FROM (SELECT v.voter, COUNT(*) AS n, COALESCE(SUM(v.guess_correct), 0) AS g FROM votes v"
                 "       JOIN situations s ON s.id = v.situation_id AND s.status = 'approved' GROUP BY v.voter) v"
                 " LEFT JOIN players p ON p.voter = v.voter"
                 " LEFT JOIN (SELECT voter, SUM(xp) AS xp FROM gift_grants WHERE revoked_at IS NULL GROUP BY voter) x ON x.voter = v.voter",
                 (XP['verdict'], XP['guess'], XP['daily']))
    counts = {r['key']: 0 for r in RANKS}
    for r in rows:
        counts[rank_of(int(r['xp']))['key']] += 1
    return [{'key': r['key'], 'name': r['name'], 'icon': r['icon'], 'xp': r['xp'], 'value': counts[r['key']]} for r in RANKS]


def by_achievement():
    counts = {k: 0 for k in ACHIEVEMENTS}
    for r in query("SELECT achievements FROM players WHERE achievements IS NOT NULL AND achievements <> '[]'"):
        try:
            keys = json.loads(r['achievements'])
        except ValueError:
            continue
        for k in keys if isinstance(keys, list) else []:
            if k in counts:
                counts[k] += 1
    return [{'key': k, 'name': a['name'], 'icon': a['icon'], 'value': counts[k]} for k, a in ACHIEVEMENTS.items()]


def cases_table():
    """Cases in play by verdicts: the most played, the most divisive, and the ones nobody reaches."""
    counts = vote_counts()
    rows = []
    for s in situations_list(status='approved', order='old'):
        c = counts.get(s['id'], {})
        rows.append({'id': s['id'], 'title': s['title'], 'category': s['category'], 'votes': sum(c.values()),
                     'controversy': case_controversy(s, c)['value']})
    top = sorted(rows, key=lambda r: (-r['votes'], r['id']))[:8]
    divisive = sorted((r for r in rows if r['controversy'] is not None and r['votes'] >= 3),
                      key=lambda r: (-r['controversy'], -r['votes']))[:5]
    quiet = sorted(rows, key=lambda r: (r['votes'], r['id']))[:5]
    return {'top': top, 'divisive': divisive, 'quiet': quiet}


def daily_cases(n=14):
    """The case of the day for the last n days and how many judged it on its day."""
    out = []
    for d in reversed(_days(n)):
        sid = scalar('SELECT meta_value FROM meta WHERE meta_key = %s', ('daily:' + d.isoformat(),))
        if sid is None:
            continue
        row = query_one('SELECT id, title FROM situations WHERE id = %s', (int(sid),))
        judged = int(scalar('SELECT COUNT(*) FROM votes WHERE situation_id = %s AND created_at >= %s AND created_at < %s',
                            (int(sid), _start(d), _start(d + timedelta(days=1)))))
        out.append({'day': d, 'id': int(sid), 'title': row['title'] if row else 'Дело удалено', 'judged': judged})
    return out


def hunt_overview():
    """Hunts that are on (or were): spots, finds, finders, gifts out; gift pools that are running dry."""
    hunts = query('SELECT c.id, c.title, c.status, c.starts_at, c.ends_at,'
                  ' (SELECT COUNT(*) FROM spots s WHERE s.challenge_id = c.id AND s.active = 1) AS spots,'
                  ' (SELECT COUNT(*) FROM spot_finds f WHERE f.challenge_id = c.id) AS finds,'
                  ' (SELECT COUNT(DISTINCT f.voter) FROM spot_finds f WHERE f.challenge_id = c.id) AS finders,'
                  ' (SELECT COUNT(*) FROM gift_grants r WHERE r.challenge_id = c.id AND r.prize_of IS NOT NULL) AS prizes'
                  " FROM challenges c WHERE c.status <> 'draft' ORDER BY c.id DESC LIMIT 5")
    pools = query("SELECT * FROM (SELECT g.id, g.name, (SELECT COUNT(*) FROM gift_codes c WHERE c.gift_id = g.id AND c.grant_id IS NULL)"
                  " AS free FROM gifts g WHERE g.kind = 'code' AND g.active = 1) t WHERE t.free < 5 ORDER BY t.free")
    return {'hunts': hunts, 'low_pools': pools,
            'granted': int(scalar('SELECT COUNT(*) FROM gift_grants WHERE revoked_at IS NULL')),
            'finds_today': int(scalar('SELECT COUNT(*) FROM spot_finds WHERE created_at >= %s', (_start(today()),)))}


def dashboard():
    return {
        'kpis': kpis(), 'series': daily_series(30), 'retention': retention(30), 'funnel': funnel(), 'modes': modes(30),
        'hours': by_hour(30), 'categories': by_category(), 'ranks': by_rank(), 'achievements': by_achievement(),
        'cases': cases_table(), 'daily': daily_cases(14), 'hunt': hunt_overview(),
    }
