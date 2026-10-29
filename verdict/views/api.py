"""JSON endpoints used by the site's own JavaScript (vote, world reset) and the team's export."""
from datetime import datetime, timezone

from flask import make_response, render_template, request, url_for

from .. import career, hunt
from ..auth import can_view_situation, is_admin, is_logged_in
from ..helpers import plural
from ..judge import judge_event, judge_profile
from ..repository import (input_str, majority_keys, next_case, quick_stats, situation_decision, situation_find,
                          situations_list, vote_counts, vote_counts_for, vote_save)
from ..web import csrf_valid, flash, json_response, redirect, safe_back, voter_id


def cast_vote(s, voter, key, reasoning, quick, guess, duration):
    """Saves a verdict (cases in play only) and updates the player's career. Returns what the result screens need;
    for a preview (case not in play) nothing is saved and profile/career are None. Shared with /api/v1."""
    decision = None if key == 'other' else situation_decision(s, key)
    preview = s['status'] != 'approved'
    # The majority guess (Быстрый суд) is compared with the other players' votes BEFORE this verdict.
    guess = guess if guess and situation_decision(s, guess) else None
    majority = majority_keys(s['id'], voter) if quick else []
    guess_correct = int(guess in majority) if guess is not None and majority else None
    profile = record = None
    if not preview:
        before = career.snapshot(voter)
        vote_save(s['id'], voter, key, reasoning, mode='quick' if quick else 'full',
                  duration_ms=min(duration, 3600000) if duration > 0 else None,
                  guess_key=guess if quick else None, guess_correct=guess_correct if quick else None)
        profile = judge_profile(voter)
        record = career.record_verdict(voter, s['id'], before, profile)
    return {'decision': decision, 'preview': preview, 'guess': guess, 'majority': majority, 'correct': guess_correct,
            'profile': profile, 'career': record}


def vote_error(s, key, reasoning, quick):
    """Why a vote can't be accepted, as (message, status) — or None."""
    if key != 'other' and not situation_decision(s, key):
        return 'Выберите один из вариантов решения.', 422
    if key == 'other' and len(reasoning) < 10:
        return 'Опишите своё решение — хотя бы одно предложение.', 422
    if quick and s['status'] != 'approved':
        return 'Это дело ещё не в игре.', 422
    return None


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def vote():
    if request.method != 'POST':
        return json_response({'ok': False, 'error': 'Метод не поддерживается.'}, 405)
    if not csrf_valid():
        return json_response({'ok': False, 'error': 'Сессия устарела. Обновите страницу и попробуйте снова.'}, 419)

    s = situation_find(_int(request.form.get('situation_id')))
    if not s or not can_view_situation(s):
        return json_response({'ok': False, 'error': 'Дело не найдено.'}, 404)

    key = input_str(request.form.get('option', ''), 10)
    reasoning = input_str(request.form.get('reasoning', ''), 1000)
    quick = request.form.get('mode', '') == 'quick'
    problem = vote_error(s, key, reasoning, quick)
    if problem:
        return json_response({'ok': False, 'error': problem[0]}, problem[1])

    voter = voter_id()
    v = cast_vote(s, voter, key, reasoning, quick, input_str(request.form.get('guess', ''), 10), _int(request.form.get('duration_ms')))

    # Judge profile: after a verdict, say whether it opened or the style changed.
    judge_info = None if v['preview'] else {'profile': v['profile'], 'event': judge_event(v['profile'])}

    counts = vote_counts_for(s['id'])
    if quick:
        html = render_template('partials/quick_result.html', s=s, choice=key, guess=v['guess'], majority=v['majority'],
                               correct=v['correct'], counts=counts, stats=quick_stats(voter), judge_info=judge_info,
                               career_info=v['career'])
    else:
        html = render_template('partials/result.html', s=s, choice=key, reasoning=reasoning, counts=counts,
                               preview=v['preview'], next=None if v['preview'] else next_case(s['id'], voter),
                               fresh=True, judge_info=judge_info, career_info=v['career'])

    w = v['career']['world'] if v['career'] else career.world(voter)
    count = w['count']
    return json_response({
        'ok': True,
        'html': html,
        'preview': v['preview'],
        'quick': {'correct': v['correct'], 'stats': quick_stats(voter)} if quick else None,
        'world': {
            'metrics': w['metrics'],
            'deltas': w.get('deltas', {}),
            'count': count,
            'word': plural(count, 'вердикт', 'вердикта', 'вердиктов'),
        },
    })


def hunt_claim():
    """A player clicked a hidden spot: the gift it holds, the hunt's progress, the main prize if that was the last one."""
    if request.method != 'POST':
        return json_response({'ok': False, 'error': 'Метод не поддерживается.'}, 405)
    if not csrf_valid():
        return json_response({'ok': False, 'error': 'Сессия устарела. Обновите страницу и попробуйте снова.'}, 419)
    voter = voter_id()
    before = career.summary(voter)
    try:
        res = hunt.claim(voter, _int(request.form.get('spot')), is_logged_in(), check_token=request.form.get('token', ''))
    except hunt.HuntError as e:
        back = safe_back(request.form.get('back', '')) or url_for('index')
        status = {'gone': 410, 'found': 409, 'empty': 409, 'account': 401, 'blocked': 403, 'token': 403}.get(e.code, 400)
        return json_response({'ok': False, 'code': e.code, 'error': e.message,
                              'login': url_for('login', back=back), 'register': url_for('register', back=back)}, status)
    after = career.summary(voter)
    html = render_template('partials/hunt_found.html', res=res, before=before, after=after)
    return json_response({'ok': True, 'html': html, 'hunt': int(res['challenge']['id']), 'spot': int(res['spot']['id']),
                          'gift': res['grant']['name'] if res['grant'] else None, 'found': res['found'], 'total': res['total']})


def world_reset():
    back = safe_back(request.form.get('back', '')) or url_for('play')
    if request.method != 'POST' or not csrf_valid():
        flash('error', 'Не удалось выполнить действие. Обновите страницу и попробуйте снова.')
        return redirect(back)
    career.reset_world(voter_id())
    flash('success', 'Мир начат заново. Все показатели вернулись к исходным значениям.')
    return redirect(back)


def export():
    """Situations as JSON for the game client (team only).
      /api/export?id=3        — one situation (any status)
      /api/export             — all approved
      /api/export?status=all  — all"""
    if not is_admin():
        return json_response({'ok': False, 'error': 'Доступно только команде.'}, 403)
    counts = vote_counts()

    def pack(s):
        return {**s, 'votes': counts.get(s['id'], {})}

    sid = _int(request.args.get('id'))
    if sid > 0:
        s = situation_find(sid)
        if not s:
            return json_response({'ok': False, 'error': 'Ситуация не найдена.'}, 404)
        items = [pack(s)]
        filename = 'verdict-situation-%d.json' % sid
    else:
        status = None if request.args.get('status') == 'all' else 'approved'
        items = [pack(s) for s in situations_list(status=status, order='old')]
        filename = 'verdict-situations-%s.json' % datetime.now(timezone.utc).strftime('%Y%m%d')

    import json
    body = json.dumps({'exported_at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'count': len(items),
                       'situations': items}, ensure_ascii=False, indent=4)
    response = make_response(body)
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    response.headers['Content-Disposition'] = 'attachment; filename="%s"' % filename
    return response
