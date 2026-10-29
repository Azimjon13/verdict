"""Discussion under a case. Only those who judged the case see it (the arguments give the case away) and only accounts
write: each comment carries the verdict its author had when writing. Others back a comment with «Поддерживаю»; the
author hears of it at 1, 5, 10… backers. The team hides what breaks the rules (the author is told), players report
comments like profiles. A barred player can't write or back; writing is slowed down (GAP_SECONDS, PER_DAY)."""
from datetime import datetime, timedelta, timezone

from . import notify
from .db import execute, insert, now, query, query_one, scalar

MIN_LEN, MAX_LEN = 3, 1000
GAP_SECONDS = 15
PER_DAY = 30
LIKE_MILESTONES = (1, 5, 10, 25, 50, 100)
SORTS = {'top': 'c.likes DESC, c.id DESC', 'new': 'c.id DESC'}


class TalkError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def judged(voter, situation_id):
    """The player's verdict on this case (option key), or None."""
    if not voter:
        return None
    return scalar('SELECT option_key FROM votes WHERE situation_id = %s AND voter = %s', (situation_id, voter))


def count(situation_id):
    return int(scalar("SELECT COUNT(*) FROM comments WHERE situation_id = %s AND status = 'visible'", (situation_id,)))


def _ago(seconds):
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).strftime('%Y-%m-%d %H:%M:%S')


def comments(situation_id, viewer_id=None, sort='top', user_ids=None, team=False, limit=200):
    """Comments with their authors, newest or most backed first. user_ids limits them to some authors (friends, a
    community). The team also sees hidden ones."""
    where, params = ['c.situation_id = %s'], [viewer_id or 0, situation_id]
    if not team:
        where.append("c.status = 'visible'")
    if user_ids is not None:
        if not user_ids:
            return []
        where.append('c.user_id IN (%s)' % ', '.join(['%s'] * len(user_ids)))
        params += list(user_ids)
    rows = query('SELECT c.*, u.login, u.display_name, p.title, (l.user_id IS NOT NULL) AS liked'
                 ' FROM comments c JOIN users u ON u.id = c.user_id'
                 ' LEFT JOIN players p ON p.user_id = c.user_id'
                 ' LEFT JOIN comment_likes l ON l.comment_id = c.id AND l.user_id = %s'
                 ' WHERE ' + ' AND '.join(where) + ' ORDER BY ' + SORTS.get(sort, SORTS['top']) + ' LIMIT %s',
                 params + [int(limit)])
    for r in rows:
        r['liked'] = bool(r['liked'])
        r['mine'] = bool(viewer_id) and int(r['user_id']) == int(viewer_id)
    return rows


def find(comment_id):
    return query_one('SELECT c.*, s.title AS case_title FROM comments c JOIN situations s ON s.id = c.situation_id'
                     ' WHERE c.id = %s', (comment_id,))


def post(situation_id, user_id, voter, text):
    """Writes a comment; returns its id or raises TalkError (judge, blocked, short, long, slow, daily)."""
    from .social import barred
    text = (text or '').replace('\r\n', '\n').strip()
    option = judged(voter, situation_id)
    if option is None:
        raise TalkError('judge', 'Сначала вынесите вердикт по этому делу — потом спорьте.')
    if barred(user_id):
        raise TalkError('blocked', 'Команда закрыла вам обсуждения.')
    if len(text) < MIN_LEN:
        raise TalkError('short', 'Напишите хотя бы пару слов.')
    if len(text) > MAX_LEN:
        raise TalkError('long', 'Слишком длинно: не больше %d символов.' % MAX_LEN)
    if scalar('SELECT COUNT(*) FROM comments WHERE user_id = %s AND created_at > %s', (user_id, _ago(GAP_SECONDS))):
        raise TalkError('slow', 'Не так быстро: подождите несколько секунд.')
    if int(scalar('SELECT COUNT(*) FROM comments WHERE user_id = %s AND created_at > %s', (user_id, _ago(86400)))) >= PER_DAY:
        raise TalkError('daily', 'На сегодня хватит: не больше %d комментариев в день.' % PER_DAY)
    text = '\n'.join(line.rstrip() for line in text.split('\n'))
    while '\n\n\n' in text:
        text = text.replace('\n\n\n', '\n\n')
    return insert('INSERT INTO comments (situation_id, user_id, option_key, text, created_at) VALUES (%s, %s, %s, %s, %s)',
                  (situation_id, user_id, option, text, now()))


def like(comment_id, user_id):
    """Backs a comment (not one's own, not a hidden one, once). Tells the author at the milestones."""
    from .social import barred
    c = find(comment_id)
    if not c or c['status'] != 'visible' or int(c['user_id']) == int(user_id) or barred(user_id):
        return False
    if not execute('INSERT IGNORE INTO comment_likes (comment_id, user_id, created_at) VALUES (%s, %s, %s)',
                   (comment_id, user_id, now())):
        return False
    execute('UPDATE comments SET likes = likes + 1 WHERE id = %s', (comment_id,))
    likes = int(c['likes']) + 1
    if likes in LIKE_MILESTONES:
        notify.send(c['user_id'], 'comment_liked', 'Ваш комментарий к делу «%s» поддержали: %d.' % (c['case_title'], likes),
                    '/talk/%d#c%d' % (c['situation_id'], comment_id))
    return True


def unlike(comment_id, user_id):
    if not execute('DELETE FROM comment_likes WHERE comment_id = %s AND user_id = %s', (comment_id, user_id)):
        return False
    execute('UPDATE comments SET likes = GREATEST(likes, 1) - 1 WHERE id = %s', (comment_id,))
    return True


def delete_own(comment_id, user_id):
    return execute('DELETE FROM comments WHERE id = %s AND user_id = %s', (comment_id, user_id))


def set_hidden(comment_id, hidden):
    """The team hides a comment (the author is told) or shows it again."""
    c = find(comment_id)
    if not c or (c['status'] == 'hidden') == hidden:
        return False
    execute('UPDATE comments SET status = %s WHERE id = %s', ('hidden' if hidden else 'visible', comment_id))
    if hidden:
        notify.send(c['user_id'], 'comment_hidden', 'Команда скрыла ваш комментарий к делу «%s»: он нарушает правила обсуждений.'
                    % c['case_title'], '/talk/%d' % c['situation_id'])
    return True


def remove(comment_id):
    return execute('DELETE FROM comments WHERE id = %s', (comment_id,))


def preview(situation_id, viewer_id=None):
    """For the result screen: how many comments, and the two most backed."""
    return {'count': count(situation_id), 'top': comments(situation_id, viewer_id, 'top', limit=2)}


def recent(status='visible', limit=100):
    """For the team: the latest comments everywhere."""
    return query('SELECT c.*, u.login, u.display_name, s.title AS case_title FROM comments c'
                 ' JOIN users u ON u.id = c.user_id JOIN situations s ON s.id = c.situation_id'
                 ' WHERE c.status = %s ORDER BY c.id DESC LIMIT %s', (status, int(limit)))


def public(row):
    """For the game API."""
    return {'id': int(row['id']), 'case_id': int(row['situation_id']), 'text': row['text'], 'option': row['option_key'],
            'likes': int(row['likes']), 'liked': bool(row.get('liked')), 'mine': bool(row.get('mine')),
            'author': {'login': row['login'], 'display_name': row['display_name'], 'title': row.get('title')},
            'created_at': row['created_at'].strftime('%Y-%m-%dT%H:%M:%SZ')}
