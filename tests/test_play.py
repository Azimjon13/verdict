"""Playing: Быстрый суд with majority guesses, the full case, world meters, vote remapping, the judge profile."""
import re

import pytest


def fresh_case(db, exclude=()):
    """An approved case nobody has voted on yet."""
    rows = db.rows("SELECT s.id FROM situations s LEFT JOIN votes v ON v.situation_id = s.id"
                   " WHERE s.status = 'approved' GROUP BY s.id HAVING COUNT(v.id) = 0 ORDER BY s.id")
    return next(r['id'] for r in rows if r['id'] not in exclude)


def test_quick_mode(new_browser, db):
    sid = fresh_case(db)
    p = new_browser()
    p.get('/quick')
    assert re.search(r'data-quick data-situation="\d+"', p.html)
    assert 'data-comic' in p.html and 'cm-panel cm-cast' in p.html and 'cm-panel cm-evidence' in p.html
    assert 'data-step="1"' in p.html and 'data-step="2" hidden' in p.html
    assert 'btn-play" href="/quick"' in p.html

    status, first = new_browser().vote(sid, 'A', 'B')
    assert status == 200 and first['ok'] and first['quick']['correct'] is None and 'Вы первый судья' in first['html']
    new_browser().vote(sid, 'A', 'A')
    new_browser().vote(sid, 'B', '')

    winner = new_browser()
    _, win = winner.vote(sid, 'C', 'A')
    assert win['quick']['correct'] == 1 and win['quick']['stats']['score'] == 1 and 'Вы угадали большинство' in win['html']
    assert 'ваша догадка' in win['html'] and 'ваш выбор' in win['html']
    _, miss = new_browser().vote(sid, 'A', 'B')
    assert miss['quick']['correct'] == 0 and 'Не угадали' in miss['html'] and 'Большинство выбрало' in miss['html']
    assert 'Вы решили как большинство' in miss['html']
    _, skip = new_browser().vote(sid, 'B', '')
    assert skip['ok'] and skip['quick']['correct'] is None and 'Вы не угадывали' in skip['html']

    new_browser().vote(sid, 'B', '')  # A=3, B=3 now: a tie
    _, tie = new_browser().vote(sid, 'D', 'B')
    assert tie['quick']['correct'] == 1

    rows = db.rows('SELECT mode, guess_key, guess_correct, duration_ms FROM votes WHERE situation_id = %s ORDER BY id', (sid,))
    assert len(rows) == 8 and all(r['mode'] == 'quick' for r in rows) and rows[0]['duration_ms'] == 12000
    assert [r['guess_key'] for r in rows] == ['B', 'A', None, 'A', 'B', None, None, 'B']

    # Streak: the winner guesses right again on another case.
    sid2 = fresh_case(db, exclude=(sid,))
    new_browser().vote(sid2, 'A', '')
    _, again = winner.vote(sid2, 'B', 'A')
    assert again['quick']['stats'] == {'score': 2, 'guesses': 2, 'streak': 2}
    winner.get('/quick')
    assert 'Угадано <b>2</b> из 2' in winner.html and 'серия 2' in winner.html
    assert 'data-situation="%d"' % sid not in winner.html
    winner.get('/quick/%d' % sid)
    assert 'data-quick data-situation="%d" hidden' % sid in winner.html and 'Вы угадали большинство' in winner.html

    # A full-case re-vote keeps the earlier guess.
    winner.vote(sid, 'D', mode='full', ms=5000)
    row = db.one('SELECT option_key, guess_key, guess_correct, mode, duration_ms FROM votes WHERE situation_id = %s AND voter = %s',
                 (sid, winner.cookie('verdict_vid')))
    assert row == {'option_key': 'D', 'guess_key': 'A', 'guess_correct': 1, 'mode': 'full', 'duration_ms': 5000}

    _, bad = new_browser().vote(sid2, 'A', 'Z')
    assert bad['ok'] and bad['quick']['correct'] is None


def test_votes_on_cases_not_in_play(new_browser, db):
    pending = db.value("SELECT id FROM situations WHERE status = 'pending' LIMIT 1")
    p = new_browser()
    assert p.get('/quick/%d' % pending).headers['Location'] == '/case/%d' % pending
    p.get('/case/%d' % pending)  # quick mode redirects here, so take the token from the case page
    r = p.post('/api/vote', {'_csrf': p.csrf(), 'situation_id': pending, 'option': 'A', 'mode': 'quick'})
    assert r.status_code == 422 and r.get_json()['error'] == 'Это дело ещё не в игре.'
    status, data = p.vote(pending, 'A', mode='full')
    assert status == 200 and data['preview'] and 'Режим предпросмотра' in data['html']
    assert db.value('SELECT COUNT(*) FROM votes WHERE situation_id = %s', (pending,)) == 0
    assert p.get('/quick/999999').headers['Location'] == '/quick'


def test_vote_validation(browser):
    browser.get('/case/2')
    token = browser.csrf()
    assert browser.client.get('/api/vote').status_code == 405
    assert browser.client.post('/api/vote', data={'situation_id': 2, 'option': 'A'}).status_code == 419
    assert browser.client.post('/api/vote', data={'_csrf': token, 'situation_id': 999999, 'option': 'A'}).status_code == 404
    r = browser.client.post('/api/vote', data={'_csrf': token, 'situation_id': 2, 'option': 'Q'})
    assert r.status_code == 422 and r.get_json()['error'] == 'Выберите один из вариантов решения.'
    r = browser.client.post('/api/vote', data={'_csrf': token, 'situation_id': 2, 'option': 'other', 'reasoning': 'кратко'})
    assert r.status_code == 422
    r = browser.client.post('/api/vote', data={'situation_id': 2, 'option': 'A'}, headers={'X-CSRF-Token': token})
    assert r.status_code == 200


def test_full_case_result_and_world(browser, db):
    sid = fresh_case(db)
    status, data = browser.vote(sid, 'B', mode='full', reasoning='Потому что так честнее для всех жителей')
    assert status == 200 and not data['preview'] and data['quick'] is None
    assert 'Ваше обоснование' in data['html'] and 'Как решили другие' in data['html']
    effects = db.data(sid)['decisions'][1].get('effects') or {}
    assert data['world']['deltas'] == {k: v * 5 for k, v in effects.items()}
    assert data['world']['count'] == 1 and data['world']['word'] == 'вердикт'
    assert all(v == 50 + effects.get(k, 0) * 5 for k, v in data['world']['metrics'].items())
    browser.get('/case/%d' % sid)
    assert 'id="verdict" data-situation="%d" hidden' % sid in browser.html and 'Пересмотреть дело' in browser.html

    r = browser.form('/api/world', {'back': '/play'}, page='/play')
    assert r.headers['Location'] == '/play'
    browser.get('/play')
    assert 'Мир начат заново' in browser.html and '<b data-world-count>0</b>' in browser.html


# ---------- Editing a case that already has votes ----------

def test_votes_follow_their_decisions(new_browser, db):
    sid = 1  # «Три ампулы»: decisions A–F stored without uids (legacy data)
    data = db.data(sid)
    assert 'uid' not in data['decisions'][0]
    plan = [('A', 'B'), ('B', 'C'), ('C', 'D'), ('D', 'B'), ('E', 'F'), ('F', 'A')]
    db.rows('DELETE FROM votes WHERE situation_id = %s', (sid,))
    voters = []
    for opt, guess in plan:
        p = new_browser()
        p.vote(sid, opt, guess)
        voters.append(p)
    new_browser().vote(sid, 'other', mode='full', reasoning='Созвать общий совет поселения')

    def state():
        return [(r['option_key'], r['guess_key']) for r in
                db.rows('SELECT option_key, guess_key FROM votes WHERE situation_id = %s ORDER BY id', (sid,))]
    assert len(state()) == 7

    team = new_browser()
    team.login()
    team.get('/create/%d' % sid)
    uids = re.findall(r'name="decisions\[\d+\]\[uid\]" value="([^"]*)"', team.html)
    assert uids == ['kA', 'kB', 'kC', 'kD', 'kE', 'kF']
    assert team.html.count('class="rep-votes"') == 6 and team.html.count('data-votes="1"') == 6

    def post_edit(rows):
        d = db.data(sid)
        return team.form('/create/%d' % sid, {
            'intent': 'submit', 'category': 'survival', 'type': 'private', 'title': db.value('SELECT title FROM situations WHERE id = %s', (sid,)),
            'world': d['world'], 'story': d['story'], 'participants': d['participants'], 'facts': d['facts'], 'unknowns': d['unknowns'],
            'hidden': d['hidden'], 'ambiguity': d['ambiguity'], 'continuation_possible': 'yes',
            'continuation_text': d['continuation']['text'], 'notes': d['notes'], 'decisions': rows})

    def row(d, uid):
        return {'uid': uid, **{k: d.get(k, '') for k in ('text', 'why', 'immediate', 'longterm', 'characters', 'world')},
                'effects': d.get('effects') or {}}

    dec = {d['key']: d for d in data['decisions']}
    rows = [row(dec['A'], 'kA'), {**row(dec['C'], 'kC'), 'text': 'C — переписанный текст'}, row(dec['D'], 'kD'),
            row(dec['E'], 'kE'), row(dec['F'], 'kF'), {'uid': '', 'text': 'Новый вариант G'}]
    r = post_edit(rows)
    assert r.headers['Location'] == '/view/%d' % sid
    team.get('/view/%d' % sid)
    assert any(re.search(r'перенесены вместе с ними \(4\).*Удалено голосов за убранные варианты: 1', t) for t in team.toasts())
    want = [('A', None), ('B', 'C'), ('C', None), ('D', 'E'), ('E', 'A'), ('other', None)]
    assert state() == want

    voters[2].get('/case/%d' % sid)
    assert 'C — переписанный текст <em>ваш выбор</em>' in voters[2].html

    saved = db.data(sid)
    uids = [d['uid'] for d in saved['decisions']]
    assert len(uids) == 6 and uids[5].startswith('n')
    post_edit([row(d, d['uid']) for d in saved['decisions']])
    assert state() == want
    team.get('/view/%d' % sid)
    assert not any('перенесены' in t or 'Удалено' in t for t in team.toasts())

    rows = [row(d, d['uid']) for d in saved['decisions']]
    rows[0], rows[1] = rows[1], rows[0]
    post_edit(rows)
    assert state() == [('B', None), ('A', 'C'), ('C', None), ('D', 'E'), ('E', 'B'), ('other', None)]

    post_edit([row(d, 'kA') for d in saved['decisions'][:4]])
    uids = [d['uid'] for d in db.data(sid)['decisions']]
    assert len(set(uids)) == len(uids)


# ---------- Judge profile ----------

@pytest.fixture(scope='module')
def cases(db):
    return {r['id']: __import__('json').loads(r['data'])['decisions']
            for r in db.rows("SELECT id, data FROM situations WHERE status = 'approved' ORDER BY id")}


def pick(cases, sid, score):
    best = cases[sid][0]
    for d in cases[sid]:
        if score(d.get('effects') or {}) > score(best.get('effects') or {}):
            best = d
    return best['key']


def trust(fx):
    return int(fx.get('trust', 0))


def order(fx):
    return int(fx.get('authority', 0)) + int(fx.get('stability', 0))


def test_judge_profile(new_browser, cases, db):
    ids = list(cases)
    p = new_browser()
    p.get('/judge')
    assert 'Профиль откроется после 5 вердиктов' in p.html and 'Осталось 5 вердиктов' in p.html

    _, d = p.vote(ids[0], 'other', mode='quick', ms=20000, reasoning='Собрать общий совет и решить вместе')
    assert 'Откроется через 5 вердиктов' in d['html']
    for k in range(1, 5):
        _, d = p.vote(ids[k], pick(cases, ids[k], trust), ms=20000)
    assert 'Откроется через 1 вердикт' in d['html']
    _, d = p.vote(ids[5], pick(cases, ids[5], trust), ms=20000)
    assert 'Профиль судьи открыт!' in d['html'] and 'Вы — «Милосердный судья»' in d['html']
    _, d = p.vote(ids[6], pick(cases, ids[6], trust), ms=20000)
    assert 'Ваш профиль судьи' in d['html'] and 'открыт!' not in d['html']

    p.get('/judge')
    assert '<h2>Милосердный судья</h2>' in p.html
    assert re.search(r'Доверие</span>\s*<span class="jd-track">\s*<span class="jd-zero"></span>\s*<span class="jd-bar up"', p.html)
    assert 'Решает быстро' in p.html and 'Предлагает свои решения' in p.html
    assert 'Показать таблицей' in p.html and p.html.count('<th scope="row">') == 5
    assert 'data-share-url="/judge?a=mercy"' in p.html

    q = new_browser()
    for k in range(10, 16):
        _, d = q.vote(ids[k], pick(cases, ids[k], order), ms=150000)
    assert '«Страж порядка»' in d['html']
    changed = False
    for k in range(16, 34):
        _, d = q.vote(ids[k], pick(cases, ids[k], trust), ms=150000)
        if 'Ваш стиль изменился' in d['html']:
            changed = True
            break
    assert changed
    q.get('/judge')
    assert 'Взвешивает долго' in q.html

    # Three more players make 5 profiles (census line); they all disagree with p on a case nobody else judged.
    bold = next(i for i in reversed(ids) if not db.value('SELECT COUNT(*) FROM votes WHERE situation_id = %s', (i,)))
    p.vote(bold, pick(cases, bold, trust))
    contrary = next(d['key'] for d in cases[bold] if d['key'] != pick(cases, bold, trust))
    for n in range(3):
        r = new_browser()
        r.vote(bold, contrary)
        for k in range(20, 24):
            r.vote(ids[k], cases[ids[k]][n % len(cases[ids[k]])]['key'])
    p.get('/judge')
    assert re.search(r'Так судят \d+% игроков', p.html)
    assert 'Самое смелое решение' in p.html and re.search(r'никто из \d+ игроков не выбрал то же, что вы', p.html)

    s = new_browser()
    s.get('/judge?a=wise')
    assert 'Вам прислали профиль судьи' in s.html and '«Мудрый правитель»' in s.html and 'Узнать, какой судья вы' in s.html
    s.get('/judge?a=hacker')
    assert 'Вам прислали' not in s.html

    _, d = p.vote(ids[40], pick(cases, ids[40], trust), mode='full')
    assert 'judge-teaser' in d['html']
    p.get('/quick')
    assert 'class="quick-judge" href="/judge"' in p.html


def test_archetype_rules():
    from verdict.judge import judge_archetype, judge_leans

    def leans(**values):
        return {m: {'lean': values.get(m, 0.0), 'relevant': 5, 'more': 0, 'less': 0}
                for m in ('reputation', 'authority', 'stability', 'resources', 'trust')}
    assert judge_archetype(leans()) == 'balanced'
    assert judge_archetype(leans(authority=0.6, stability=0.6, trust=0.5)) == 'wise'
    assert judge_archetype(leans(authority=0.6, stability=0.6, trust=-0.5)) == 'order'
    assert judge_archetype(leans(authority=-0.4, stability=-0.4, trust=0.6)) == 'mercy'
    assert judge_archetype(leans(authority=-0.6, stability=-0.6, trust=0.3)) == 'reformer'
    assert judge_archetype(leans(authority=-0.5, stability=-0.5, trust=-0.5)) == 'fire'
    assert judge_archetype(leans(trust=-0.5)) == 'stern'
    assert judge_archetype(leans(resources=0.8)) == 'pragmatic'
    assert judge_archetype(leans(resources=-0.8)) == 'generous'
    assert judge_archetype(leans(reputation=0.8)) == 'diplomat'
    assert judge_archetype(leans(reputation=-0.8)) == 'maverick'
    # Rank, not mean: one outlier option doesn't move a middle choice.
    out = judge_leans([{'chosen': {'trust': 1}, 'options': [{'trust': 0}, {'trust': 1}, {'trust': 3}]}])
    assert out['trust'] == {'more': 0, 'less': 0, 'relevant': 1, 'lean': 0.0}
