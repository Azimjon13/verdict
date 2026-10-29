"""Seasons. The season rating is a calendar month (UTC); a month closes by itself on the first visit after it ends.
Closing keeps the final board (the first SEASONS['keep'] places, for «Прошлые сезоны»), gives the top places a
trophy (catalog `seasons.trophies`: a badge or title with XP — one per player and season, whatever happens twice)
and tells every placed account where it finished.

Trophy XP counts in the career but not in the next season, so last month's winners don't start ahead."""
import json
from datetime import date, timedelta

from . import career, notify, social
from .catalog import SEASONS
from .db import db, execute, now, query, query_one, scalar

_checked = None  # the month this process last looked at: one database look per process and month


def key_of(day):
    return '%04d-%02d' % (day.year, day.month)


def start_of(key):
    year, month = (int(x) for x in key.split('-'))
    return date(year, month, 1)


def next_month(day):
    return (day.replace(day=1) + timedelta(days=32)).replace(day=1)


def valid_key(key):
    try:
        return key_of(start_of(key)) == key
    except (ValueError, AttributeError):
        return False


def display_name(day=None):
    """«Октябрь 2026» — a season's name as a name (social.season_name is lower case, for the middle of a sentence)."""
    name = social.season_name(day)
    return name[:1].upper() + name[1:]


def since(conn=None):
    """The first season that closes: the month this version first ran (older months had no ratings to win)."""
    execute('INSERT IGNORE INTO meta (meta_key, meta_value) VALUES (%s, %s)', ('seasons_since', key_of(career.today())), conn)
    return scalar("SELECT meta_value FROM meta WHERE meta_key = 'seasons_since'", (), conn)


def close_due(today=None):
    """Closes every finished season that isn't closed yet; returns their keys."""
    global _checked
    today = today or career.today()
    current = key_of(today)
    if _checked == current:
        return []
    month, closed = start_of(since()), []
    while key_of(month) < current:
        if not scalar('SELECT COUNT(*) FROM seasons WHERE season = %s', (key_of(month),)) and close(month):
            closed.append(key_of(month))
        month = next_month(month)
    _checked = current
    return closed


def trophy_for(place):
    return next((t for t in SEASONS['trophies'] if t['from'] <= place <= t['to']), None)


def close(first_day):
    """Closes the season of this month: keeps the board, gives trophies, tells the players. False when another
    process (or an earlier call) closed it already."""
    key, name = key_of(first_day), display_name(first_day)
    rows = social.board('season', day=first_day)
    board = [{'place': r['place'], 'user_id': r['user_id'], 'login': r['login'], 'display_name': r['display_name'],
              'value': r['value'], 'xp': r['xp'], 'rank': r['rank']['key'], 'title': r['title']} for r in rows]
    conn = db()
    conn.begin()
    try:
        claimed = execute('INSERT IGNORE INTO seasons (season, name, closed_at, players, board) VALUES (%s, %s, %s, %s, %s)',
                          (key, name, now(), len(rows), json.dumps(board[:SEASONS['keep']], ensure_ascii=False)), conn)
        if claimed != 1:
            conn.rollback()
            return False
        link = '/seasons/%s' % key
        for r in rows:
            trophy = trophy_for(r['place'])
            voter = scalar('SELECT voter FROM players WHERE user_id = %s ORDER BY updated_at DESC LIMIT 1', (r['user_id'],), conn)
            if trophy and voter:
                fill = {'season': name, 'place': r['place'], 'value': r['value']}
                title = trophy['name'].format(**fill)
                execute('INSERT IGNORE INTO gift_grants (voter, gift_id, source, season, kind, name, icon, xp, text, link, note,'
                        ' created_at) VALUES (%s, NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
                        (voter, 'season', key, trophy['kind'], title[:120], trophy['icon'], int(trophy['xp']),
                         trophy['text'].format(**fill), link, 'Сезон %s, %d место' % (key, r['place']), now()), conn)
                if trophy['kind'] == 'title':
                    execute('UPDATE players SET title = %s, updated_at = %s WHERE voter = %s', (title[:120], now(), voter), conn)
                notify.send(r['user_id'], 'season', 'Сезон «%s» закрыт: вы на %d месте. Трофей «%s», +%d XP.'
                            % (name, r['place'], title, int(trophy['xp'])), link, conn)
            else:
                notify.send(r['user_id'], 'season', 'Сезон «%s» закрыт: вы на %d месте из %d.' % (name, r['place'], len(rows)),
                            link, conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return True


def _season(row, top=None):
    board = json.loads(row['board'] or '[]')
    return {'key': row['season'], 'name': row['name'], 'closed_at': row['closed_at'], 'players': int(row['players']),
            'board': board[:top] if top else board}


def past(limit=24):
    """Closed seasons, latest first, each with its podium."""
    return [_season(r, 3) for r in query('SELECT * FROM seasons ORDER BY season DESC LIMIT %s', (limit,))]


def get(key):
    row = query_one('SELECT * FROM seasons WHERE season = %s', (key,)) if valid_key(key) else None
    return _season(row) if row else None


def trophies():
    """What the top places of the current season will get: [{from, to, kind, icon, xp, name}] with names filled in."""
    name = display_name()
    return [{**t, 'name': t['name'].format(season=name, place=t['from'], value=0)} for t in SEASONS['trophies']]
