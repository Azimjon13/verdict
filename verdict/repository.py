"""Situations and votes: storage, form input and validation."""
import json
import random
import re
import secrets

from .catalog import CATEGORIES, CHECKLIST, IDEA_MIN_WORDS, MAX_DECISIONS, METRICS, SITUATION_TYPES, WORLD_NAMES
from .db import db, execute, insert, now, query, query_one, scalar
from .helpers import word_count


def situation_blank():
    """An empty situation with the structure of the template."""
    return {
        'category': '',
        'type': 'private',
        'title': '',
        'author': '',
        'world': {'setting': '', 'place': '', 'era': '', 'circumstances': ''},
        'story': '',
        'participants': [],
        'facts': [],
        'unknowns': [],
        'witnesses': [],
        'decisions': [],
        'hidden': '',
        'ambiguity': {'conflict': '', 'for_one': '', 'for_other': '', 'divide': ''},
        'continuation': {'possible': False, 'text': ''},
        'notes': '',
        'checklist': [],
    }


def situation_hydrate(row):
    try:
        data = json.loads(row['data'] or 'null')
    except ValueError:
        data = None
    s = situation_blank()
    if isinstance(data, dict):
        s.update(data)
    s['world'] = {**{'setting': '', 'place': '', 'era': '', 'circumstances': ''}, **(s['world'] or {})}
    s['id'] = int(row['id'])
    s['category'] = str(row['category'])
    s['type'] = str(row['type'])
    s['title'] = str(row['title'])
    s['author'] = str(row['author'])
    s['user_id'] = int(row['user_id']) if row.get('user_id') is not None else None
    s['status'] = str(row['status'])
    s['created_at'] = str(row['created_at'])
    s['updated_at'] = str(row['updated_at'])
    s['decisions'] = decisions_with_uids(s['decisions'])
    return s


def decisions_with_uids(decisions):
    """Each decision has a permanent uid: the letter (A, B, …) is only a position and changes when the case is
    edited, while votes store the letter — so on save they are moved by uid (votes_remap). Decisions saved
    before uids existed get one derived from their letter, which is stable until the first edit."""
    out = []
    for k, d in enumerate(decisions or []):
        if isinstance(d, dict) and not d.get('uid'):
            d = {**d, 'uid': 'k' + str(d.get('key') or chr(65 + k))}
        out.append(d)
    return out


def situation_payload(s):
    blank = situation_blank()
    return {k: s.get(k, v) for k, v in blank.items()}


def _json(s):
    return json.dumps(situation_payload(s), ensure_ascii=False)


def situation_find(situation_id):
    row = query_one('SELECT * FROM situations WHERE id = %s', (situation_id,))
    return situation_hydrate(row) if row else None


def situations_list(status=None, category=None, type=None, user_id=None, order='new'):
    where, params = [], []
    for field, value in (('status', status), ('category', category), ('type', type), ('user_id', user_id)):
        if value:
            where.append(field + ' = %s')
            params.append(value)
    sql = ('SELECT * FROM situations' + (' WHERE ' + ' AND '.join(where) if where else '')
           + ' ORDER BY id ' + ('ASC' if order == 'old' else 'DESC'))
    return [situation_hydrate(r) for r in query(sql, params)]


def situation_insert(s, status, user_id=None, conn=None):
    ts = now()
    return insert('INSERT INTO situations (category, type, title, author, user_id, status, data, created_at, updated_at)'
                  ' VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)',
                  (s['category'], s['type'], s['title'], s.get('author') or '', user_id, status, _json(s), ts, ts), conn)


def situation_update(situation_id, s, status=None):
    """status — the new status (e.g. draft → pending); None keeps the current one.
    Votes and guesses follow their decisions if a decision's letter changed.
    Returns {'moved': votes moved, 'deleted': votes deleted with removed decisions}."""
    conn = db()
    conn.begin()
    try:
        old = scalar('SELECT data FROM situations WHERE id = %s FOR UPDATE', (situation_id,), conn)
        try:
            old_data = json.loads(old or 'null')
        except ValueError:
            old_data = None
        old_decisions = decisions_with_uids(old_data.get('decisions') if isinstance(old_data, dict) and isinstance(old_data.get('decisions'), list) else [])
        execute('UPDATE situations SET category = %s, type = %s, title = %s, author = %s, status = COALESCE(%s, status),'
                ' data = %s, updated_at = %s WHERE id = %s',
                (s['category'], s['type'], s['title'], s.get('author') or '', status, _json(s), now(), situation_id), conn)
        result = votes_remap(conn, situation_id, old_decisions, s['decisions'])
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise


def votes_remap(conn, situation_id, old_decisions, new_decisions):
    """Moves votes and Быстрый суд guesses from the old decision letters to the new ones (by uid).
    Votes for removed decisions are deleted; a guess on them is cleared, but a point already earned stays."""
    new_key_by_uid = {d.get('uid', ''): d['key'] for d in new_decisions}
    changes = {}
    for j, d in enumerate(old_decisions):
        old_key = str(d.get('key') or chr(65 + j))
        new_key = new_key_by_uid.get(d.get('uid', ''))
        if new_key != old_key:
            changes[old_key] = new_key
    if not changes:
        return {'moved': 0, 'deleted': 0}

    # First «park» the changing letters under «~» so that swaps (A↔B) don't mix.
    for col in ('option_key', 'guess_key'):
        for old_key in changes:
            execute("UPDATE votes SET {0} = CONCAT('~', {0}) WHERE situation_id = %s AND {0} = %s".format(col),
                    (situation_id, old_key), conn)
    moved = deleted = 0
    for old_key, new_key in changes.items():
        parked = '~' + old_key
        if new_key is None:
            deleted += execute('DELETE FROM votes WHERE situation_id = %s AND option_key = %s', (situation_id, parked), conn)
            execute('UPDATE votes SET guess_key = NULL WHERE situation_id = %s AND guess_key = %s', (situation_id, parked), conn)
        else:
            moved += execute('UPDATE votes SET option_key = %s WHERE situation_id = %s AND option_key = %s',
                             (new_key, situation_id, parked), conn)
            execute('UPDATE votes SET guess_key = %s WHERE situation_id = %s AND guess_key = %s', (new_key, situation_id, parked), conn)
    return {'moved': moved, 'deleted': deleted}


def situation_set_status(situation_id, status):
    execute('UPDATE situations SET status = %s, updated_at = %s WHERE id = %s', (status, now(), situation_id))


def situation_delete(situation_id):
    execute('DELETE FROM votes WHERE situation_id = %s', (situation_id,))
    execute('DELETE FROM situations WHERE id = %s', (situation_id,))


def situation_decision(s, key):
    for d in s['decisions']:
        if d.get('key', '') == key:
            return d
    return None


def decision_has_consequences(d):
    return ''.join(str(d.get(f) or '') for f in ('immediate', 'longterm', 'characters', 'world')).strip() != ''


# ---------- Votes ----------

def vote_counts():
    """{situation_id: {option_key: count}}"""
    out = {}
    for r in query('SELECT situation_id, option_key, COUNT(*) AS n FROM votes GROUP BY situation_id, option_key'):
        out.setdefault(int(r['situation_id']), {})[r['option_key']] = int(r['n'])
    return out


def vote_counts_for(situation_id):
    return {r['option_key']: int(r['n']) for r in
            query('SELECT option_key, COUNT(*) AS n FROM votes WHERE situation_id = %s GROUP BY option_key', (situation_id,))}


def votes_of_voter(voter):
    """{situation_id: option_key} for one player."""
    return {int(r['situation_id']): r['option_key'] for r in
            query('SELECT situation_id, option_key FROM votes WHERE voter = %s', (voter,))}


def vote_find(situation_id, voter):
    return query_one('SELECT * FROM votes WHERE situation_id = %s AND voter = %s', (situation_id, voter))


def vote_save(situation_id, voter, key, reasoning, mode='full', duration_ms=None, guess_key=None, guess_correct=None):
    """A repeated vote in the full case doesn't erase an earlier Быстрый суд guess."""
    ts = now()
    mode = 'quick' if mode == 'quick' else 'full'
    execute('INSERT INTO votes (situation_id, option_key, reasoning, guess_key, guess_correct, mode, duration_ms, voter, created_at,'
            ' first_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'
            ' ON DUPLICATE KEY UPDATE option_key = %s, reasoning = %s, mode = %s, duration_ms = %s, created_at = %s,'
            ' guess_key = IF(%s IS NULL, guess_key, %s), guess_correct = IF(%s IS NULL, guess_correct, %s)',
            (situation_id, key, reasoning, guess_key, guess_correct, mode, duration_ms, voter, ts, ts,
             key, reasoning, mode, duration_ms, ts,
             guess_key, guess_key, guess_key, guess_correct))


def majority_keys(situation_id, voter):
    """Options chosen by the majority of OTHER players (before this vote). Empty — nobody to compare with.
    On a tie every leading option counts as the majority."""
    counts = vote_counts_for(situation_id)
    mine = vote_find(situation_id, voter)
    if mine and mine['option_key'] in counts:
        counts[mine['option_key']] -= 1
    counts = {k: n for k, n in counts.items() if n}
    if not counts:
        return []
    top = max(counts.values())
    return [k for k, n in counts.items() if n == top]


def quick_stats(voter):
    """Быстрый суд score: majority guessed, guesses made, current streak of right guesses."""
    results = [int(r['guess_correct']) for r in
               query('SELECT guess_correct FROM votes WHERE voter = %s AND guess_correct IS NOT NULL'
                     ' ORDER BY created_at DESC, id DESC', (voter,))]
    streak = 0
    for r in results:
        if r != 1:
            break
        streak += 1
    return {'score': sum(results), 'guesses': len(results), 'streak': streak}


def open_cases(voter, except_id=0):
    """Approved cases the player hasn't judged yet."""
    done = votes_of_voter(voter)
    return [s for s in situations_list(status='approved') if s['id'] not in done and s['id'] != except_id]


def random_open_case(voter, except_id=0):
    found = open_cases(voter, except_id)
    return random.choice(found) if found else None


def vote_duration_stats(situation_id):
    """Average time to decide on a case (ms) and how many votes measured it."""
    r = query_one('SELECT AVG(duration_ms) AS avg_ms, COUNT(duration_ms) AS n FROM votes'
                  ' WHERE situation_id = %s AND duration_ms IS NOT NULL', (situation_id,))
    from .helpers import round_half_up
    return {'avg_ms': int(round_half_up(float(r['avg_ms']))) if r['n'] else None, 'n': int(r['n'])}


def stats_overview():
    counts = {'pending': 0, 'approved': 0, 'rejected': 0}
    for r in query('SELECT status, COUNT(*) AS n FROM situations GROUP BY status'):
        counts[r['status']] = int(r['n'])
    counts['total'] = counts['pending'] + counts['approved'] + counts['rejected']
    counts['votes'] = int(scalar('SELECT COUNT(*) FROM votes'))
    counts['players'] = int(scalar('SELECT COUNT(DISTINCT voter) FROM votes'))
    return counts


def next_case(current_id, voter):
    """The next unjudged case for the player: the first one after this, else any."""
    done = votes_of_voter(voter)
    after = first = None
    for s in situations_list(status='approved', order='old'):
        if s['id'] == current_id or s['id'] in done:
            continue
        if after is None and s['id'] > current_id:
            after = s
        if first is None:
            first = s
    return after or first


# ---------- Form input ----------

def input_str(value, max_len=2000):
    if isinstance(value, (dict, list)) or value is None:
        return ''
    value = str(value).replace('\r\n', '\n').strip()
    return value[:max_len]


def _rows(value):
    """A PHP-style form array (dict with index keys, or list) as a list of its values in order."""
    if isinstance(value, dict):
        return list(value.values())
    return value if isinstance(value, list) else []


def input_rows(rows, fields, max_rows, max_len=2000):
    out = []
    for row in _rows(rows):
        if not isinstance(row, dict):
            continue
        clean = {f: input_str(row.get(f, ''), max_len) for f in fields}
        if not ''.join(clean.values()):
            continue
        out.append(clean)
        if len(out) >= max_rows:
            break
    return out


def input_list(rows, max_rows, max_len=1000):
    out = []
    for row in _rows(rows):
        v = input_str(row, max_len)
        if v:
            out.append(v)
        if len(out) >= max_rows:
            break
    return out


def _int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


_UID = re.compile(r'^[A-Za-z0-9]{1,16}$')


def situation_from_input(form):
    """A situation from the nested creator form (see forms.parse_nested)."""
    s = situation_blank()
    s['category'] = input_str(form.get('category', ''), 40)
    s['type'] = input_str(form.get('type', ''), 20)
    s['title'] = input_str(form.get('title', ''), 120)
    s['author'] = input_str(form.get('author', ''), 80)

    w = form.get('world') if isinstance(form.get('world'), dict) else {}
    setting = input_str(w.get('setting', ''), 80)
    s['world'] = {
        'setting': setting if setting in WORLD_NAMES else '',
        'place': input_str(w.get('place', ''), 160),
        'era': input_str(w.get('era', ''), 160),
        'circumstances': input_str(w.get('circumstances', ''), 2000),
    }

    s['story'] = input_str(form.get('story', ''), 6000)
    s['participants'] = input_rows(form.get('participants'), ['name', 'age', 'role', 'relations', 'description'], 12, 600)
    s['facts'] = input_list(form.get('facts'), 20)
    s['unknowns'] = input_list(form.get('unknowns'), 20)
    s['witnesses'] = [] if s['type'] == 'private' else input_rows(form.get('witnesses'), ['name', 'claim', 'trust', 'interest'], 8, 1000)

    decisions = []
    seen_uids = set()
    for d in _rows(form.get('decisions')):
        if not isinstance(d, dict):
            continue
        row = {
            'text': input_str(d.get('text', ''), 300),
            'why': input_str(d.get('why', ''), 1000),
            'immediate': input_str(d.get('immediate', ''), 1000),
            'longterm': input_str(d.get('longterm', ''), 1000),
            'characters': input_str(d.get('characters', ''), 1000),
            'world': input_str(d.get('world', ''), 1000),
        }
        if not ''.join(row.values()):
            continue
        raw = d.get('effects') if isinstance(d.get('effects'), dict) else {}
        effects = {}
        for m in METRICS:
            v = _int(raw.get(m, 0))
            if v != 0:
                effects[m] = max(-3, min(3, v))
        row['effects'] = effects
        row['key'] = chr(65 + len(decisions))
        # The permanent uid comes from the form; new rows and forged ones get a fresh one.
        uid = input_str(d.get('uid', ''), 16)
        if not _UID.match(uid) or uid in seen_uids:
            uid = 'n' + secrets.token_hex(4)
        seen_uids.add(uid)
        row['uid'] = uid
        decisions.append(row)
        if len(decisions) >= MAX_DECISIONS:
            break
    s['decisions'] = decisions

    s['hidden'] = input_str(form.get('hidden', ''), 4000)

    a = form.get('ambiguity') if isinstance(form.get('ambiguity'), dict) else {}
    s['ambiguity'] = {
        'conflict': input_str(a.get('conflict', ''), 600),
        'for_one': input_str(a.get('for_one', ''), 1000),
        'for_other': input_str(a.get('for_other', ''), 1000),
        'divide': input_str(a.get('divide', ''), 1000),
    }
    s['continuation'] = {
        'possible': form.get('continuation_possible', '') == 'yes',
        'text': input_str(form.get('continuation_text', ''), 2000),
    }
    s['notes'] = input_str(form.get('notes', ''), 4000)

    checks = []
    for c in _rows(form.get('checklist')):
        c = _int(c)
        if 0 <= c < len(CHECKLIST) and c not in checks:
            checks.append(c)
    s['checklist'] = checks
    return s


def situation_validate(s):
    """Validation errors: key — field anchor, value — message."""
    e = {}
    if s['author'] == '':
        e['author'] = 'Укажите имя или ник автора — это нужно для учёта вклада.'
    if s['category'] not in CATEGORIES:
        e['category'] = 'Выберите категорию.'
    if s['type'] not in SITUATION_TYPES:
        e['type'] = 'Выберите тип ситуации.'
    if s['title'] == '':
        e['title'] = 'Укажите название ситуации.'
    if s['world']['place'] == '':
        e['world_place'] = 'Укажите, где происходит ситуация.'
    if s['world']['circumstances'] == '':
        e['world_circumstances'] = 'Опишите обстоятельства мира.'
    if word_count(s['story']) < 40:
        e['story'] = 'Опишите ситуацию подробнее: минимум 40 слов (рекомендуется 100–250).'
    if not s['participants']:
        e['participants'] = 'Добавьте хотя бы одного участника.'
    elif any(p.get('name', '') == '' for p in s['participants']):
        e['participants'] = 'У каждого участника должно быть имя.'
    if not s['facts']:
        e['facts'] = 'Укажите хотя бы один факт, известный игроку.'
    if s['type'] in ('witness', 'public'):
        n = len(s['witnesses'])
        if n < 1:
            e['witnesses'] = 'Для этого типа ситуации нужен хотя бы один свидетель.'
        elif s['type'] == 'witness' and n > 5:
            e['witnesses'] = 'В ситуации со свидетелями — от 1 до 5 свидетелей.'
        elif any(w.get('name', '') == '' or w.get('claim', '') == '' for w in s['witnesses']):
            e['witnesses'] = 'У каждого свидетеля должно быть имя и показания.'
    with_text = 0
    for d in s['decisions']:
        if d.get('text', '') == '':
            e['decisions'] = 'У каждого варианта должна быть формулировка решения.'
            break
        with_text += 1
    if 'decisions' not in e and with_text < 4:
        e['decisions'] = 'Предложите минимум 4 варианта решения.'
    if s['ambiguity']['conflict'] == '':
        e['ambiguity'] = 'Опишите главный конфликт — почему здесь нет очевидного ответа.'
    return e


def situation_level(s):
    """Which fill level is reached (0 — not even «Идея»). create.js checks the same rules.
      1 Идея:  category, title, story of IDEA_MIN_WORDS+ words, 2+ decisions;
      2 Дело:  everything situation_validate requires (the minimum to submit);
      3 Досье: consequences and world effects for 2+ decisions, hidden info, arguments for both sides."""
    decisions = [d for d in s['decisions'] if d.get('text', '') != '']
    idea = (s['category'] in CATEGORIES and s['title'] != ''
            and word_count(s['story']) >= IDEA_MIN_WORDS and len(decisions) >= 2)
    if not idea:
        return 0
    if situation_validate({**s, 'author': s.get('author') or 'x'}):  # the author's signature isn't part of the level
        return 1
    with_consequences = sum(1 for d in s['decisions'] if decision_has_consequences(d))
    with_effects = sum(1 for d in s['decisions'] if d.get('effects'))
    dossier = (with_consequences >= 2 and with_effects >= 2 and s['hidden'].strip() != ''
               and s['ambiguity']['for_one'] != '' and s['ambiguity']['for_other'] != '')
    return 3 if dossier else 2


def situation_validate_draft(s):
    """A draft can be saved at any stage — it only needs a title."""
    return {'title': 'Дайте черновику название — по нему вы найдёте его в профиле.'} if s['title'] == '' else {}


def situation_form_defaults(author=''):
    """Form defaults: 3 participants, 3 facts, 3 witnesses, 3 decisions."""
    s = situation_blank()
    s['author'] = author
    return situation_form_pad(s)


def situation_form_pad(s):
    def pad(rows, n, blank):
        rows = list(rows)
        while len(rows) < n:
            rows.append(dict(blank) if isinstance(blank, dict) else blank)
        return rows

    s = dict(s)
    s['participants'] = pad(s['participants'], 3, {'name': '', 'age': '', 'role': '', 'relations': '', 'description': ''})
    s['facts'] = pad(s['facts'], 3, '')
    s['unknowns'] = pad(s['unknowns'], 1, '')
    s['witnesses'] = pad(s['witnesses'], 3, {'name': '', 'claim': '', 'trust': '', 'interest': ''})
    # «Идея» needs 2–3 options; at the «Дело» level the form adds rows up to 4 by itself.
    s['decisions'] = pad(s['decisions'], 3, {'text': '', 'why': '', 'immediate': '', 'longterm': '',
                                             'characters': '', 'world': '', 'effects': {}})
    return s
