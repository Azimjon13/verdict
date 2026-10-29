"""Notifications for accounts — the bell in the header and GET /api/v1/notifications. Sent where things happen (a
friend request, an answer, a community request or role, a case approved or rejected, a gift from the team, a season
trophy, a closed report) and kept for KEEP_DAYS. Anonymous players get none: they have no place to be told later."""
from datetime import datetime, timedelta, timezone

from .db import execute, now, query, scalar

# kind → icon in the list
KINDS = {
    'friend_request': 'users',
    'friend_accepted': 'heart-whole',
    'community_request': 'users',
    'community_joined': 'check-circle',
    'community_role': 'shield',
    'case_approved': 'check-circle',
    'case_rejected': 'x',
    'gift': 'gift',
    'season': 'trophy',
    'report': 'flag',
}
KEEP_DAYS = 90
PAGE = 50


def send(user_id, kind, text, link='', conn=None):
    """Tells the account something. Does nothing without an account."""
    if not user_id:
        return
    execute('INSERT INTO notifications (user_id, kind, text, link, created_at) VALUES (%s, %s, %s, %s, %s)',
            (int(user_id), kind if kind in KINDS else 'gift', text[:255], (link or '')[:255], now()), conn)


def send_to_player(voter, kind, text, link='', conn=None):
    """The same for a player id: reaches the account that player belongs to, if any."""
    send(scalar('SELECT user_id FROM players WHERE voter = %s', (voter,), conn), kind, text, link, conn)


def unread(user_id):
    if not user_id:
        return 0
    return int(scalar('SELECT COUNT(*) FROM notifications WHERE user_id = %s AND read_at IS NULL', (user_id,)))


def latest(user_id, limit=PAGE):
    """Newest first, with an icon each. Old ones are dropped on the way."""
    since = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).strftime('%Y-%m-%d %H:%M:%S')
    execute('DELETE FROM notifications WHERE user_id = %s AND created_at < %s', (user_id, since))
    rows = query('SELECT id, kind, text, link, created_at, read_at FROM notifications WHERE user_id = %s'
                 ' ORDER BY id DESC LIMIT %s', (user_id, int(limit)))
    for r in rows:
        r['icon'] = KINDS.get(r['kind'], 'bell')
    return rows


def mark_read(user_id, ids=None):
    """All of the account's notifications, or only these ids. Returns how many changed."""
    if ids is not None:
        ids = [int(i) for i in ids if str(i).isdigit()][:200]
        if not ids:
            return 0
        return execute('UPDATE notifications SET read_at = %%s WHERE user_id = %%s AND read_at IS NULL AND id IN (%s)'
                       % ', '.join(['%s'] * len(ids)), (now(), user_id, *ids))
    return execute('UPDATE notifications SET read_at = %s WHERE user_id = %s AND read_at IS NULL', (now(), user_id))


def public(row):
    """For the game API."""
    return {'id': int(row['id']), 'kind': row['kind'], 'icon': row['icon'], 'text': row['text'], 'link': row['link'],
            'created_at': row['created_at'].strftime('%Y-%m-%dT%H:%M:%SZ'), 'read': row['read_at'] is not None}
