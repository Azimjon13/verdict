"""Story campaigns: a chain of cases where the earlier verdicts carry into the next case (a short «what your verdict
led to» before each chapter) and decide the ending. Content: content/campaigns/*.json. The first chapter may be a case
of the archive (by title) — a player who already judged it there continues from that verdict; the other chapters are
cases of their own, kept in the database with status 'campaign' so they don't show in the archive.

A campaign has its own small world: the meters start at 50 and move with each chapter's choice, like the player's world.
"""
import json

from .catalog import CONTENT, METRIC_STEP, METRICS, XP
from .db import execute, insert, now, query, query_one, scalar

TEAM = 'Команда VERDICT'


def _load():
    items = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((CONTENT / 'campaigns').glob('*.json'))]
    return sorted(items, key=lambda c: (c.get('order', 99), c['key']))


CAMPAIGNS = _load()
BY_KEY = {c['key']: c for c in CAMPAIGNS}


def get(key):
    return BY_KEY.get(key)


def chapter_title(ch):
    return ch['title'] if 'title' in ch else ch['case']['title']


def seed(conn, admin_id):
    """Puts each campaign's own chapters into the database once (a mark in meta per campaign)."""
    from .repository import situation_insert
    for c in CAMPAIGNS:
        if scalar('SELECT COUNT(*) FROM meta WHERE meta_key = %s', ('campaign:' + c['key'],), conn):
            continue
        for ch in c['chapters']:
            if 'case' in ch and not scalar('SELECT COUNT(*) FROM situations WHERE title = %s', (ch['case']['title'],), conn):
                situation_insert(ch['case'], 'campaign', admin_id, conn)
        execute('INSERT IGNORE INTO meta (meta_key, meta_value) VALUES (%s, %s)', ('campaign:' + c['key'], now()), conn)


def pending(conn):
    return any(not scalar('SELECT COUNT(*) FROM meta WHERE meta_key = %s', ('campaign:' + c['key'],), conn) for c in CAMPAIGNS)


# ---------- Chapters and cases ----------

def chapter_case(ch):
    """The situation of a chapter: an archive case in play, or the campaign's own case."""
    from .repository import situation_find
    status = 'approved' if 'title' in ch else 'campaign'
    sid = scalar("SELECT id FROM situations WHERE title = %s ORDER BY status = %s DESC, id LIMIT 1", (chapter_title(ch), status))
    return situation_find(int(sid)) if sid else None


def available(c):
    return all(chapter_case(ch) for ch in c['chapters'])


def campaign_of_case(situation_id):
    """The campaign that starts with this archive case (its continuation), or None."""
    for c in CAMPAIGNS:
        first = c['chapters'][0]
        if 'title' in first:
            s = chapter_case(first)
            if s and s['id'] == situation_id:
                return c
    return None


# ---------- Runs ----------

def _choices(run):
    try:
        value = json.loads(run['choices'] or '[]')
    except ValueError:
        return []
    return value if isinstance(value, list) else []


def run_of(voter, key):
    """The player's latest run of this campaign, or None."""
    return query_one('SELECT * FROM campaign_runs WHERE voter = %s AND campaign = %s ORDER BY run DESC LIMIT 1', (voter, key))


def start(voter, c):
    """A new run. On the first run, a verdict already given in the archive on the first chapter is taken as its choice."""
    last = run_of(voter, c['key'])
    number = int(last['run']) + 1 if last else 1
    choices = []
    first = c['chapters'][0]
    if number == 1 and 'title' in first:
        s = chapter_case(first)
        v = query_one('SELECT option_key FROM votes WHERE situation_id = %s AND voter = %s', (s['id'], voter)) if s else None
        if v and v['option_key'] != 'other':
            choices.append({'chapter': first['key'], 'option': v['option_key'], 'adopted': True})
    insert('INSERT INTO campaign_runs (voter, campaign, run, choices, started_at) VALUES (%s, %s, %s, %s, %s)',
           (voter, c['key'], number, json.dumps(choices), now()))
    return run_of(voter, c['key'])


def meters(c, choices):
    """The campaign's own world after these choices: every meter starts at 50."""
    m = {k: 50 for k in METRICS}
    steps = []
    for ch, pick in zip(c['chapters'], choices):
        s = chapter_case(ch)
        d = next((x for x in (s['decisions'] if s else []) if x['key'] == pick['option']), None)
        delta = {}
        for k, v in ((d or {}).get('effects') or {}).items():
            if k in m and v:
                before = m[k]
                m[k] = max(0, min(100, m[k] + int(v) * METRIC_STEP))
                delta[k] = m[k] - before
        steps.append(delta)
    return m, steps


def ending_for(c, m, choices):
    picked = {x['chapter']: x['option'] for x in choices}
    for e in c['endings']:
        w = e.get('when', {})
        if (all(m[k] >= v for k, v in w.get('min', {}).items()) and all(m[k] <= v for k, v in w.get('max', {}).items())
                and all(picked.get(k) in v for k, v in w.get('chose', {}).items())):
            return e
    return c['endings'][-1]


def bridges(c, index, choices):
    """What the earlier verdicts led to, told before chapter `index`: [{'from': chapter title, 'text'}]."""
    ch = c['chapters'][index]
    picked = {x['chapter']: x['option'] for x in choices}
    out = []
    for prev in c['chapters'][:index]:
        texts = ch.get('after', {}).get(prev['key'])
        if not texts or prev['key'] not in picked:
            continue
        text = texts.get(picked[prev['key']]) or (texts.get('*') if prev is c['chapters'][index - 1] else None)
        if text:
            out.append({'from': chapter_title(prev), 'text': text})
    return out


def state(voter, c):
    """Where the player is: run, choices, the current chapter (None when finished), the meters, the ending."""
    run = run_of(voter, c['key'])
    if not run:
        return {'run': None, 'choices': [], 'index': 0, 'chapter': None, 'finished': False, 'ending': None,
                'meters': {k: 50 for k in METRICS}, 'steps': [], 'total': len(c['chapters'])}
    choices = _choices(run)
    m, steps = meters(c, choices)
    index = len(choices)
    finished = index >= len(c['chapters'])
    ending = None
    if finished:
        ending = next((e for e in c['endings'] if e['key'] == run['ending']), None) or ending_for(c, m, choices)
    return {'run': run, 'choices': choices, 'index': index, 'chapter': None if finished else c['chapters'][index],
            'finished': finished, 'ending': ending, 'meters': m, 'steps': steps, 'total': len(c['chapters'])}


def choose(voter, c, option, duration_ms=0):
    """The player's verdict in the current chapter. Returns (state, error). The vote counts in the case's split the
    first time only; a replay changes the run, not the player's verdict."""
    from .views.api import cast_vote
    st = state(voter, c)
    if not st['run'] or st['finished']:
        return st, 'Эта кампания не ждёт вердикта.'
    ch = st['chapter']
    s = chapter_case(ch)
    if not s or not any(d['key'] == option for d in s['decisions']):
        return st, 'Выберите один из вариантов.'
    if not scalar('SELECT COUNT(*) FROM votes WHERE situation_id = %s AND voter = %s', (s['id'], voter)):
        if s['status'] == 'approved':
            cast_vote(s, voter, option, '', False, None, duration_ms)  # an archive case: XP, streak, world as usual
        else:
            from .repository import vote_save
            vote_save(s['id'], voter, option, '', mode='full', duration_ms=duration_ms or None)
    choices = st['choices'] + [{'chapter': ch['key'], 'option': option}]
    ending = None
    if len(choices) >= len(c['chapters']):
        m, _ = meters(c, choices)
        ending = ending_for(c, m, choices)
    execute('UPDATE campaign_runs SET choices = %s, ending = %s, finished_at = %s WHERE id = %s',
            (json.dumps(choices), ending['key'] if ending else None, now() if ending else None, st['run']['id']))
    if ending:
        reward(voter, c, ending)
    return state(voter, c), None


def reward(voter, c, ending):
    """The first time a campaign is finished: a trophy with XP (it shows on the judge page and the public profile)."""
    note = 'campaign:' + c['key']
    if scalar('SELECT COUNT(*) FROM gift_grants WHERE voter = %s AND source = %s AND note = %s', (voter, 'campaign', note)):
        return None
    from .career import _ensure
    _ensure(voter)
    return insert("INSERT INTO gift_grants (voter, source, kind, name, icon, xp, text, note, created_at)"
                  " VALUES (%s, 'campaign', 'badge', %s, %s, %s, %s, %s, %s)",
                  (voter, 'Кампания «%s»' % c['title'], c['icon'], XP['campaign'], 'Концовка: «%s».' % ending['title'], note, now()))


def ending_shares(c):
    """How the players' first runs ended: {ending key: share 0..1}, and how many finished."""
    rows = query('SELECT ending, COUNT(*) AS n FROM campaign_runs WHERE campaign = %s AND run = 1 AND ending IS NOT NULL'
                 ' GROUP BY ending', (c['key'],))
    total = sum(int(r['n']) for r in rows)
    return {r['ending']: int(r['n']) / total for r in rows}, total


def overview(voter):
    """Every campaign with the player's progress, for the list page."""
    out = []
    for c in CAMPAIGNS:
        st = state(voter, c) if voter else None
        out.append({'c': c, 'state': st, 'available': available(c)})
    return out
