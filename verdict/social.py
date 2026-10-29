"""Players together: public profiles, friends, communities with their own rules, ratings.

Everything here belongs to accounts (users.id), never to the secret player id; an account's progress is the player
linked to it (players.user_id). Ratings are computed from the votes like the rest of the career.
"""
import hmac
import re
import secrets
from datetime import datetime, time, timedelta

from . import career
from .catalog import ACHIEVEMENTS, SOCIAL
from .db import execute, insert, now, query, query_one, scalar

MONTHS = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
TRANSLIT = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
                    ['a', 'b', 'v', 'g', 'd', 'e', 'e', 'zh', 'z', 'i', 'y', 'k', 'l', 'm', 'n', 'o', 'p', 'r', 's', 't',
                     'u', 'f', 'kh', 'ts', 'ch', 'sh', 'shch', '', 'y', '', 'e', 'yu', 'ya']))


def _in(ids):
    return ', '.join(['%s'] * len(ids))


# ---------- Accounts ----------

def user_by_login(login):
    return query_one('SELECT u.id, u.login, u.display_name, u.role, u.created_at, u.bio, u.visibility, u.in_ratings, p.voter'
                     ' FROM users u LEFT JOIN players p ON p.user_id = u.id WHERE u.login = %s', (login,))


def save_profile(user_id, bio, visibility, in_ratings):
    execute('UPDATE users SET bio = %s, visibility = %s, in_ratings = %s WHERE id = %s',
            (bio, visibility if visibility in SOCIAL['visibility'] else 'public', 1 if in_ratings else 0, user_id))


# ---------- Friends ----------

def relation(me, other):
    """self | friends | sent (me asked) | received (they asked) | None."""
    if not me or not other:
        return None
    if me == other:
        return 'self'
    rows = {(r['user_id'], r['status']) for r in query(
        'SELECT user_id, status FROM friendships WHERE (user_id = %s AND friend_id = %s) OR (user_id = %s AND friend_id = %s)',
        (me, other, other, me))}
    if (me, 'accepted') in rows or (other, 'accepted') in rows:
        return 'friends'
    if (me, 'requested') in rows:
        return 'sent'
    if (other, 'requested') in rows:
        return 'received'
    return None


def befriend(me, other):
    """Asks to be friends — or accepts, when the other already asked. Returns what happened."""
    r = relation(me, other)
    if r in ('self', 'friends', 'sent'):
        return r
    if r == 'received':
        accept(me, other)
        return 'accepted'
    ts = now()
    execute("INSERT IGNORE INTO friendships (user_id, friend_id, status, created_at, updated_at) VALUES (%s, %s, 'requested', %s, %s)",
            (me, other, ts, ts))
    return 'requested'


def accept(me, other):
    ts = now()
    if not execute("UPDATE friendships SET status = 'accepted', updated_at = %s WHERE user_id = %s AND friend_id = %s"
                   " AND status = 'requested'", (ts, other, me)):
        return False
    execute("INSERT INTO friendships (user_id, friend_id, status, created_at, updated_at) VALUES (%s, %s, 'accepted', %s, %s)"
            " ON DUPLICATE KEY UPDATE status = 'accepted', updated_at = VALUES(updated_at)", (me, other, ts, ts))
    return True


def decline(me, other):
    return execute("DELETE FROM friendships WHERE user_id = %s AND friend_id = %s AND status = 'requested'", (other, me))


def cancel(me, other):
    return execute("DELETE FROM friendships WHERE user_id = %s AND friend_id = %s AND status = 'requested'", (me, other))


def unfriend(me, other):
    return execute('DELETE FROM friendships WHERE (user_id = %s AND friend_id = %s) OR (user_id = %s AND friend_id = %s)',
                   (me, other, other, me))


def friend_ids(user_id):
    return [int(r['friend_id']) for r in query("SELECT friend_id FROM friendships WHERE user_id = %s AND status = 'accepted'",
                                               (user_id,))]


def requests_in(user_id):
    return query("SELECT u.id, u.login, u.display_name, f.created_at FROM friendships f JOIN users u ON u.id = f.user_id"
                 " WHERE f.friend_id = %s AND f.status = 'requested' ORDER BY f.created_at DESC", (user_id,))


def requests_out(user_id):
    return query("SELECT u.id, u.login, u.display_name, f.created_at FROM friendships f JOIN users u ON u.id = f.friend_id"
                 " WHERE f.user_id = %s AND f.status = 'requested' ORDER BY f.created_at DESC", (user_id,))


def friend_votes(user_id, situation_id):
    """How the player's friends judged this case (friends who keep their profile private are left out)."""
    return query("SELECT u.login, u.display_name, v.option_key FROM friendships f"
                 " JOIN users u ON u.id = f.friend_id AND u.visibility <> 'private'"
                 " JOIN players p ON p.user_id = u.id JOIN votes v ON v.voter = p.voter AND v.situation_id = %s"
                 " WHERE f.user_id = %s AND f.status = 'accepted' ORDER BY u.display_name", (situation_id, user_id))


# ---------- Ratings ----------

def season(day=None):
    """The current season: a calendar month (UTC). Returns (first day, first day of the next month)."""
    d = day or career.today()
    start = d.replace(day=1)
    return start, (start + timedelta(days=32)).replace(day=1)


def days_left(day=None):
    """Days until the season ends (the last day counts)."""
    return (season(day)[1] - (day or career.today())).days


def season_name(day=None):
    start, _ = season(day)
    return '%s %d' % (MONTHS[start.month - 1], start.year)


def _stats(user_ids=None, start=None, end=None, rated_only=True):
    """Per account with a player: verdicts on cases in play, right and all majority guesses, cases of the day and gift
    XP — all time, or for [start, end) by when a case was judged first."""
    if start:
        a, b = datetime.combine(start, time.min), datetime.combine(end, time.min)
        votes = ("SELECT v.voter, COUNT(*) AS n, COALESCE(SUM(v.guess_correct = 1), 0) AS g,"
                 " COALESCE(SUM(v.guess_correct IS NOT NULL), 0) AS guesses, COALESCE(SUM(d.sid IS NOT NULL), 0) AS daily"
                 " FROM votes v JOIN situations s ON s.id = v.situation_id AND s.status = 'approved'"
                 " LEFT JOIN (SELECT CAST(meta_value AS UNSIGNED) AS sid, STR_TO_DATE(SUBSTRING(meta_key, 7), '%%Y-%%m-%%d') AS day"
                 "            FROM meta WHERE meta_key >= %s AND meta_key < %s) d"
                 "   ON d.sid = v.situation_id AND DATE(COALESCE(v.first_at, v.created_at)) = d.day"
                 " WHERE COALESCE(v.first_at, v.created_at) >= %s AND COALESCE(v.first_at, v.created_at) < %s GROUP BY v.voter")
        gifts = 'SELECT voter, SUM(xp) AS xp FROM gift_grants WHERE revoked_at IS NULL AND created_at >= %s AND created_at < %s GROUP BY voter'
        params = ['daily:' + start.isoformat(), 'daily:' + end.isoformat(), a, b, a, b]
    else:
        votes = ("SELECT v.voter, COUNT(*) AS n, COALESCE(SUM(v.guess_correct = 1), 0) AS g,"
                 " COALESCE(SUM(v.guess_correct IS NOT NULL), 0) AS guesses, 0 AS daily"
                 " FROM votes v JOIN situations s ON s.id = v.situation_id AND s.status = 'approved' GROUP BY v.voter")
        gifts = 'SELECT voter, SUM(xp) AS xp FROM gift_grants WHERE revoked_at IS NULL GROUP BY voter'
        params = []
    sql = ('SELECT u.id AS user_id, u.login, u.display_name, u.visibility, p.voter, p.title, p.streak, p.last_day, p.daily_done,'
           ' COALESCE(v.n, 0) AS verdicts, COALESCE(v.g, 0) AS right_guesses, COALESCE(v.guesses, 0) AS guesses,'
           ' COALESCE(v.daily, 0) AS daily, COALESCE(x.xp, 0) AS gift_xp'
           ' FROM users u JOIN players p ON p.user_id = u.id'
           ' LEFT JOIN (' + votes + ') v ON v.voter = p.voter LEFT JOIN (' + gifts + ') x ON x.voter = p.voter')
    where = ['u.in_ratings = 1 AND p.blocked = 0'] if rated_only else []
    if user_ids is not None:
        if not user_ids:
            return []
        where.append('u.id IN (%s)' % _in(user_ids))
        params += list(user_ids)
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    return query(sql, params)


def _xp(r, season_row=False):
    daily = int(r['daily']) if season_row else int(r['daily_done'] or 0)
    return career.xp_total(r['verdicts'], r['right_guesses'], daily, r['gift_xp'])


def _streak(r):
    return int(r['streak'] or 0) if r['last_day'] and r['last_day'] >= career.today() - timedelta(days=1) else 0


def accounts(user_ids):
    """Career cards of these accounts (whether or not they appear in ratings): XP, rank, title, streak."""
    out = []
    for r in _stats(user_ids, rated_only=False):
        xp = _xp(r)
        out.append({'user_id': int(r['user_id']), 'login': r['login'], 'display_name': r['display_name'], 'title': r['title'],
                    'xp': xp, 'rank': career.rank_of(xp), 'streak': _streak(r), 'verdicts': int(r['verdicts']),
                    'last_day': r['last_day']})
    found = {a['user_id'] for a in out}
    missing = [i for i in user_ids if i not in found]  # signed up, never played
    if missing:
        for u in query('SELECT id, login, display_name FROM users WHERE id IN (%s)' % _in(missing), missing):
            out.append({'user_id': int(u['id']), 'login': u['login'], 'display_name': u['display_name'], 'title': None,
                        'xp': 0, 'rank': career.rank_of(0), 'streak': 0, 'verdicts': 0, 'last_day': None})
    return sorted(out, key=lambda a: (-a['xp'], a['display_name'].lower()))


def board(kind='season', user_ids=None):
    """A rating: rows best first with place (ties share it), the career rank and the value of this board. Only
    accounts that agreed to be rated and have something to show."""
    rows = _stats(user_ids)
    season_xp = {}
    if kind == 'season':
        start, end = season()
        season_xp = {int(r['user_id']): _xp(r, True) for r in _stats(user_ids, start, end)}
    out = []
    for r in rows:
        xp = _xp(r)
        note = ''
        if kind == 'season':
            value = season_xp.get(int(r['user_id']), 0)
        elif kind == 'all':
            value = xp
        elif kind == 'accuracy':
            guesses = int(r['guesses'])
            if guesses < SOCIAL['min_guesses']:
                continue
            value = round(int(r['right_guesses']) / guesses * 100)
            note = '%d из %d' % (int(r['right_guesses']), guesses)
        else:
            value = _streak(r)
        if value <= 0:
            continue
        out.append({'user_id': int(r['user_id']), 'login': r['login'], 'display_name': r['display_name'], 'title': r['title'],
                    'xp': xp, 'rank': career.rank_of(xp), 'value': value, 'note': note, 'verdicts': int(r['verdicts'])})
    out.sort(key=lambda r: (-r['value'], -r['xp'], r['user_id']))
    place, last = 0, None
    for i, r in enumerate(out, 1):
        if r['value'] != last:
            place, last = i, r['value']
        r['place'] = place
    return out


# ---------- Communities ----------

def slugify(name):
    s = ''.join(TRANSLIT.get(ch, ch) for ch in name.lower())
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')[:40].strip('-') or 'community'
    base, n = s, 2
    while scalar('SELECT COUNT(*) FROM communities WHERE slug = %s', (s,)):
        s, n = '%s-%d' % (base, n), n + 1
    return s


_COMMUNITY = ("SELECT c.*, u.display_name AS owner_name, u.login AS owner_login,"
              " (SELECT COUNT(*) FROM community_members m WHERE m.community_id = c.id AND m.status = 'active') AS members"
              " FROM communities c JOIN users u ON u.id = c.owner_id")


def community_by_slug(slug):
    return query_one(_COMMUNITY + ' WHERE c.slug = %s', (slug,))


def community_by_id(community_id):
    return query_one(_COMMUNITY + ' WHERE c.id = %s', (community_id,))


def communities_list(q='', user_id=None):
    """Every community with its member count and the viewer's membership; the biggest first."""
    sql = ("SELECT c.*, (SELECT COUNT(*) FROM community_members m WHERE m.community_id = c.id AND m.status = 'active') AS members,"
           " me.role AS my_role, me.status AS my_status FROM communities c"
           " LEFT JOIN community_members me ON me.community_id = c.id AND me.user_id = %s")
    params = [user_id or 0]
    if q:
        sql += ' WHERE c.name LIKE %s OR c.description LIKE %s'
        params += ['%' + q + '%', '%' + q + '%']
    return query(sql + ' ORDER BY members DESC, c.id', params)


def owned_count(user_id):
    return int(scalar('SELECT COUNT(*) FROM communities WHERE owner_id = %s', (user_id,)))


def community_create(owner_id, v):
    ts = now()
    cid = insert('INSERT INTO communities (slug, name, description, rules, access, invite_code, icon, hue, owner_id, created_at,'
                 ' updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
                 (slugify(v['name']), v['name'], v['description'], v['rules'], v['access'], secrets.token_urlsafe(12),
                  v['icon'], v['hue'], owner_id, ts, ts))
    execute("INSERT INTO community_members (community_id, user_id, role, status, joined_at) VALUES (%s, %s, 'owner', 'active', %s)",
            (cid, owner_id, ts))
    return cid


def community_update(community_id, v):
    execute('UPDATE communities SET name = %s, description = %s, rules = %s, access = %s, icon = %s, hue = %s, updated_at = %s'
            ' WHERE id = %s', (v['name'], v['description'], v['rules'], v['access'], v['icon'], v['hue'], now(), community_id))


def regenerate_code(community_id):
    execute('UPDATE communities SET invite_code = %s WHERE id = %s', (secrets.token_urlsafe(12), community_id))


def community_delete(community_id):
    execute('DELETE FROM communities WHERE id = %s', (community_id,))


def membership(community_id, user_id):
    if not user_id:
        return None
    return query_one('SELECT * FROM community_members WHERE community_id = %s AND user_id = %s', (community_id, user_id))


def can_manage(m):
    return bool(m) and m['status'] == 'active' and m['role'] in ('owner', 'moderator')


def join(c, user_id, code=''):
    """joined | requested | already | pending | need_code. A valid invite link lets anyone straight in."""
    m = membership(c['id'], user_id)
    if m:
        return 'already' if m['status'] == 'active' else 'pending'
    invited = bool(code) and hmac.compare_digest(str(code), c['invite_code'])
    if c['access'] == 'invite' and not invited:
        return 'need_code'
    status = 'requested' if c['access'] == 'request' and not invited else 'active'
    execute("INSERT INTO community_members (community_id, user_id, role, status, joined_at) VALUES (%s, %s, 'member', %s, %s)",
            (c['id'], user_id, status, now()))
    return 'joined' if status == 'active' else 'requested'


def leave(c, user_id):
    """The founder can't leave their own community (they can delete it)."""
    return execute("DELETE FROM community_members WHERE community_id = %s AND user_id = %s AND role <> 'owner'", (c['id'], user_id))


def approve(c, user_id):
    return execute("UPDATE community_members SET status = 'active', joined_at = %s WHERE community_id = %s AND user_id = %s"
                   " AND status = 'requested'", (now(), c['id'], user_id))


def remove_member(c, user_id, by_owner):
    """Moderators remove members (and decline requests); only the founder removes moderators."""
    sql = "DELETE FROM community_members WHERE community_id = %s AND user_id = %s AND role <> 'owner'"
    if not by_owner:
        sql += " AND role = 'member'"
    return execute(sql, (c['id'], user_id))


def set_role(c, user_id, role):
    return execute("UPDATE community_members SET role = %s WHERE community_id = %s AND user_id = %s AND role <> 'owner'"
                   " AND status = 'active'", (role, c['id'], user_id))


def members(community_id):
    return query("SELECT u.id, u.login, u.display_name, m.role, m.status, m.joined_at FROM community_members m"
                 " JOIN users u ON u.id = m.user_id WHERE m.community_id = %s"
                 " ORDER BY FIELD(m.role, 'owner', 'moderator', 'member'), m.joined_at", (community_id,))


def member_ids(community_id):
    return [int(r['user_id']) for r in query("SELECT user_id FROM community_members WHERE community_id = %s AND status = 'active'",
                                             (community_id,))]


def user_communities(user_id):
    if not user_id:
        return []
    return query("SELECT c.*, m.role FROM community_members m JOIN communities c ON c.id = m.community_id"
                 " WHERE m.user_id = %s AND m.status = 'active' ORDER BY c.name", (user_id,))


# ---------- Reports and barred players ----------

REPORT_TARGETS = ('user', 'community', 'situation')


def barred(user_id):
    """The team took this player out of hunts, ratings and social actions (admin → player → «Отстранить»)."""
    return bool(scalar('SELECT blocked FROM players WHERE user_id = %s', (user_id,)))


def report(target_type, target_id, reason, text, reporter_id, reporter_voter):
    """A report to the team. One open report per reporter and target: a repeat only returns False."""
    if scalar("SELECT COUNT(*) FROM reports WHERE target_type = %s AND target_id = %s AND reporter_id = %s AND status = 'open'",
              (target_type, target_id, reporter_id)):
        return False
    insert('INSERT INTO reports (target_type, target_id, reason, text, reporter_id, reporter_voter, created_at)'
           ' VALUES (%s, %s, %s, %s, %s, %s, %s)', (target_type, target_id, reason, text[:500], reporter_id, reporter_voter, now()))
    return True


def reports_list(status='open'):
    """Reports with what they point at (name and address) and who sent them, newest first."""
    rows = query("SELECT r.*, u.login AS reporter_login, u.display_name AS reporter_name FROM reports r"
                 " LEFT JOIN users u ON u.id = r.reporter_id WHERE r.status = %s ORDER BY r.created_at DESC LIMIT 200", (status,))
    for r in rows:
        if r['target_type'] == 'user':
            t = query_one('SELECT u.login, u.display_name, p.voter FROM users u LEFT JOIN players p ON p.user_id = u.id'
                          ' WHERE u.id = %s', (r['target_id'],))
            r['target'] = {'name': t['display_name'], 'login': t['login'], 'voter': t['voter']} if t else None
        elif r['target_type'] == 'community':
            t = query_one('SELECT slug, name FROM communities WHERE id = %s', (r['target_id'],))
            r['target'] = {'name': t['name'], 'slug': t['slug']} if t else None
        else:
            t = query_one('SELECT id, title, status FROM situations WHERE id = %s', (r['target_id'],))
            r['target'] = {'name': t['title'], 'id': t['id'], 'status': t['status']} if t else None
    return rows


def report_close(report_id, status, by_user_id):
    return execute("UPDATE reports SET status = %s, resolved_at = %s, resolved_by = %s WHERE id = %s AND status = 'open'",
                   (status, now(), by_user_id, report_id))


def open_reports_count():
    return int(scalar("SELECT COUNT(*) FROM reports WHERE status = 'open'"))


# ---------- Public profile ----------

def can_see(user, rel):
    return user['visibility'] == 'public' or rel == 'self' or (user['visibility'] == 'friends' and rel == 'friends')


def profile(user, viewer_id):
    """What a viewer may see of an account: its career, style, achievements, trophies (not codes or messages),
    communities and season place — or only the name, when the profile is closed to this viewer."""
    rel = relation(viewer_id, user['id'])
    out = {'user': user, 'relation': rel, 'visible': can_see(user, rel), 'friends': len(friend_ids(user['id']))}
    if not out['visible']:
        return out
    voter = user['voter']
    if voter:
        from .judge import judge_profile
        jp = judge_profile(voter)
        p = career.player(voter)
        unlocked = set(career._keys(p['achievements']))
        out['summary'] = career.summary(voter)
        out['judge'] = jp
        out['achievements'] = [{'key': k, **a} for k, a in ACHIEVEMENTS.items() if k in unlocked]
        out['trophies'] = query("SELECT kind, name, icon, text, created_at FROM gift_grants WHERE voter = %s AND revoked_at IS NULL"
                                " AND kind IN ('badge', 'title') ORDER BY id DESC", (voter,))
    else:
        out['summary'] = {'xp': 0, 'rank': career.rank_of(0), 'streak': 0, 'best_streak': 0, 'daily_done': 0, 'verdicts': 0,
                          'title': None}
        out['judge'], out['achievements'], out['trophies'] = None, [], []
    mine = {c['id'] for c in user_communities(viewer_id)} if viewer_id else set()
    out['communities'] = [c for c in user_communities(user['id']) if c['access'] != 'invite' or c['id'] in mine]
    place = next((r for r in board('season') if r['user_id'] == user['id']), None) if user['in_ratings'] else None
    out['place'] = place['place'] if place else None
    return out
