"""Deleting an account at its owner's request (the profile page on the website, «Удалить аккаунт» in the app) or by
the team (admin → player, for someone who can't sign in any more).

Goes: the account, its sign-ins (sessions, game-client tokens), its player's verdicts and career (experience, streak,
achievements, the world, gifts, finds, campaign runs, activity), friendships, community memberships, comments and
the support it gave to others' comments, notifications, Telegram, password-reset links, drafts.
Stays, without the name: cases the account wrote that are in the game or on review (they are the game's content now),
its place on the boards of closed seasons («Удалённый судья»), reports it sent (the team may still need them).
A community it founded passes to a moderator, or else to its longest-standing member; one with nobody else in it goes.

The team's accounts can't be deleted this way: another member of the team removes them, so the site never loses its
last team account by accident.
"""
import json

from .db import db, execute, query, query_one
from . import notify
from .players import delete_player

GONE = 'Удалённый судья'


def can_erase(user):
    """None when the account may be deleted, else why not."""
    if not user:
        return 'Аккаунт не найден.'
    if user['role'] == 'admin':
        return 'Аккаунт команды так удалить нельзя: его удаляет другой участник команды на странице «Команда».'
    return None


def _hand_over(user_id):
    for c in query('SELECT id, name, slug FROM communities WHERE owner_id = %s', (user_id,)):
        heir = query_one("SELECT user_id FROM community_members WHERE community_id = %s AND user_id <> %s"
                         " AND status = 'active' ORDER BY FIELD(role, 'moderator', 'member'), joined_at LIMIT 1",
                         (c['id'], user_id))
        if not heir:
            continue  # nobody else in it: it goes with the account (ON DELETE CASCADE)
        execute('UPDATE communities SET owner_id = %s WHERE id = %s', (heir['user_id'], c['id']))
        execute("UPDATE community_members SET role = 'owner' WHERE community_id = %s AND user_id = %s",
                (c['id'], heir['user_id']))
        notify.send(heir['user_id'], 'community_role',
                    'Основатель сообщества «%s» удалил аккаунт — теперь сообщество ведёте вы.' % c['name'], '/c/%s' % c['slug'])


def _season_boards(user_id):
    for row in query('SELECT season, board FROM seasons'):
        board = json.loads(row['board'] or '[]')
        mine = [r for r in board if r.get('user_id') == user_id]
        if not mine:
            continue
        for r in mine:
            r.update(user_id=None, login=None, display_name=GONE, title=None)
        execute('UPDATE seasons SET board = %s WHERE season = %s', (json.dumps(board, ensure_ascii=False), row['season']))


def _mentions(user):
    """Others' notifications that name this account: its friend requests, the requests it accepted, its requests to
    join a community. Found through the friendships and memberships it had, so a namesake's stay."""
    uid, name = int(user['id']), user['display_name']
    execute("DELETE n FROM notifications n JOIN friendships f ON f.user_id = %s AND f.friend_id = n.user_id"
            " WHERE n.kind = 'friend_request' AND n.text = %s", (uid, name + ' хочет добавить вас в друзья.'))
    execute("DELETE FROM notifications WHERE kind = 'friend_accepted' AND link = %s", ('/u/%s' % user['login'],))
    execute("DELETE n FROM notifications n JOIN community_members m ON m.user_id = %s"
            " JOIN communities c ON c.id = m.community_id"
            " WHERE n.kind = 'community_request' AND n.text = CONCAT(%s, ' просится в «', c.name, '».')", (uid, name))


def erase_account(user_id):
    """Deletes the account and what belongs to it (see the module's note). Returns the deleted login, or None."""
    user = query_one('SELECT * FROM users WHERE id = %s', (user_id,))
    if can_erase(user):
        return None
    conn = db()
    conn.begin()  # all of it or nothing: every statement below runs on this connection
    try:
        voters = [r['voter'] for r in query('SELECT voter FROM players WHERE user_id = %s', (user_id,))]
        _hand_over(user_id)
        _season_boards(user_id)
        _mentions(user)
        # the support it gave leaves the counters of others' comments (the likes themselves go with the account)
        execute('UPDATE comments c JOIN comment_likes l ON l.comment_id = c.id SET c.likes = IF(c.likes > 0, c.likes - 1, 0)'
                ' WHERE l.user_id = %s', (user_id,))
        execute("DELETE FROM situations WHERE user_id = %s AND status = 'draft'", (user_id,))
        execute("UPDATE situations SET author = '' WHERE user_id = %s", (user_id,))  # the signature goes; the case stays
        execute('UPDATE reports SET reporter_id = NULL WHERE reporter_id = %s', (user_id,))
        execute('DELETE FROM sessions WHERE user_id = %s', (user_id,))
        execute('DELETE FROM auth_failures WHERE login = %s', (user['login'].lower(),))
        for voter in voters:
            delete_player(voter)
        # api_tokens, friendships, community_members, notifications, comments, comment_likes, telegram_*,
        # password_resets go by ON DELETE CASCADE; situations in the game keep no author (ON DELETE SET NULL)
        execute('DELETE FROM users WHERE id = %s', (user_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return user['login']
