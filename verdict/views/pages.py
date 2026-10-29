"""Player pages: landing, case archive, Быстрый суд, case file, judge profile, creator brief."""
import random

from flask import request, session, url_for

from .. import career, hunt
from ..auth import can_view_situation, is_admin
from ..catalog import CATEGORIES, JUDGE_ARCHETYPES
from ..comic import cast_of
from ..helpers import case_controversy, excerpt, round_half_up
from ..judge import judge_archetype_shares, judge_profile
from ..repository import (majority_keys, next_case, quick_stats, random_open_case, situation_find, situations_list,
                          stats_overview, vote_counts, vote_counts_for, vote_find, votes_of_voter)
from ..repository import input_str
from ..web import csrf_valid, flash, page, redirect, voter_id


def index():
    stats = stats_overview()
    approved = situations_list(status='approved', order='old')
    counts = vote_counts()

    by_category = {k: 0 for k in CATEGORIES}
    for s in approved:
        if s['category'] in by_category:
            by_category[s['category']] += 1

    # The most controversial case: highest controversy index, then more votes.
    featured, best = None, (-1, -1)
    for s in approved:
        c = counts.get(s['id'], {})
        value = case_controversy(s, c)['value']
        score = (value if value is not None else -1, sum(c.values()))
        if score > best:
            featured, best = s, score
    featured_contro = case_controversy(featured, counts.get(featured['id'], {})) if featured else None

    voter = voter_id()
    daily = career.daily(voter)
    from .. import campaigns
    return page('index.html', campaign_items=[x for x in campaigns.overview(voter) if x['available']], title='', active='home', body_class='page-home', bg='high',
                stats=stats, by_category=by_category, featured=featured, featured_contro=featured_contro,
                daily=daily, daily_case=situation_find(daily['id']) if daily['id'] else None, career=career.summary(voter))


def play():
    situations = situations_list(status='approved', order='old')
    counts = vote_counts()
    mine = votes_of_voter(voter_id())
    present_cats = {s['category'] for s in situations}
    open_cases = [s for s in situations if s['id'] not in mine]
    initial_cat = request.args.get('category', '')
    if initial_cat not in CATEGORIES:
        initial_cat = ''
    return page('play.html', title='Архив дел', active='play', body_class='page-play', bg='high', scripts=['play.js'],
                situations=situations, counts=counts, mine=mine, present_cats=present_cats,
                done=len(situations) - len(open_cases), random_case=random.choice(open_cases) if open_cases else None,
                initial_cat=initial_cat)


def quick(id=0):
    """Быстрый суд: one case on screen, two taps — the verdict and a guess of the majority's choice.
    /quick — the case of the day if the player hasn't judged it, else a random unjudged case;
    /quick/N — this one (if already judged, straight to the result)."""
    voter = voter_id()
    daily = career.daily(voter)
    if id > 0:
        s = situation_find(id)
        if not s or s['status'] != 'approved':
            # Cases not in play open only as the full file (preview for the author and the team).
            return redirect(url_for('case', id=id) if s and can_view_situation(s) else url_for('quick'))
    else:
        s = situation_find(daily['id']) if daily['id'] and not daily['judged'] else None
        s = s or random_open_case(voter)

    approved_ids = {x['id'] for x in situations_list(status='approved')}
    done_count = len(set(votes_of_voter(voter)) & approved_ids)
    stats = quick_stats(voter)
    my_vote = vote_find(s['id'], voter) if s else None
    jp = judge_profile(voter)

    ctx = dict(s=s, done_count=done_count, approved_total=len(approved_ids), stats=stats, my_vote=my_vote, jp=jp,
               daily=daily, is_daily=bool(s) and s['id'] == daily['id'], career=career.summary(voter))
    if s:
        ctx['people'] = [(i, c) for i, c in enumerate(cast_of(s)) if not c['witness']]
        if my_vote:
            ctx['result'] = dict(
                s=s, choice=my_vote['option_key'], guess=my_vote['guess_key'],
                majority=majority_keys(s['id'], voter),
                correct=None if my_vote['guess_correct'] is None else int(my_vote['guess_correct']),
                counts=vote_counts_for(s['id']), stats=stats, judge_info={'profile': jp, 'event': None})
    return page('quick.html', title='Быстрый суд — ' + s['title'] if s else 'Быстрый суд', active='quick',
                og_desc=excerpt(s['story'], 200) if s else None,
                body_class='page-quick', bg='calm', scripts=['comic.js', 'quick.js'], **ctx)


def case(id):
    s = situation_find(id) if id > 0 else None
    if not s or not can_view_situation(s):
        return page('case_missing.html', 404, title='Дело не найдено', active='play', body_class='page-case', bg='calm')

    if s['status'] == 'campaign' and not is_admin():
        return redirect(url_for('campaigns'))
    voter = voter_id()
    preview = s['status'] != 'approved'
    my_vote = None if preview else vote_find(s['id'], voter)
    sections = {'story': 'Ситуация', 'people': 'Участники', 'evidence': 'Улики'}
    if s['witnesses']:
        sections['witnesses'] = 'Свидетели'
    sections['verdict'] = 'Вердикт'

    result = None
    if my_vote:
        result = dict(s=s, choice=my_vote['option_key'], reasoning=my_vote['reasoning'], counts=vote_counts_for(s['id']),
                      preview=False, next=next_case(s['id'], voter), fresh=False,
                      judge_info={'profile': judge_profile(voter), 'event': None})
    return page('case.html', title=s['title'], active='play', body_class='page-case', bg='calm', og_desc=excerpt(s['story'], 200),
                scripts=['comic.js', 'case.js'], s=s, preview=preview, my_vote=my_vote, sections=sections, result=result)


def judge_page():
    """Профиль судьи; /judge?a=<style> — a style card another player shared."""
    voter = voter_id()
    p = judge_profile(voter)
    style = JUDGE_ARCHETYPES[p['archetype']] if p['archetype'] is not None else None
    session['judge_archetype'] = p['archetype']  # already shown — don't announce «opened» after the next verdict
    shared = request.args.get('a')
    shared = shared if shared in JUDGE_ARCHETYPES else None

    majority_pct = int(round_half_up(p['with_majority'] / p['compared'] * 100)) if p['compared'] >= 3 else None
    traits = []
    if majority_pct is not None:
        traits.append(('users', 'Голос большинства') if majority_pct >= 65 else
                      ('flag', 'Особое мнение') if majority_pct <= 35 else ('scale', 'Независимый взгляд'))
    if p['median_ms'] is not None:
        traits.append(('zap', 'Решает быстро') if p['median_ms'] < 30000 else
                      ('hourglass', 'Взвешивает долго') if p['median_ms'] > 120000 else ('clock', 'Обдумывает'))
    if p['own'] > 0:
        traits.append(('sparkles', 'Предлагает свои решения'))
    if p['quick']['guesses'] >= 3 and p['quick']['score'] / p['quick']['guesses'] >= 0.6:
        traits.append(('target', 'Чувствует, как решат другие'))

    return page('judge.html', title='Профиль судьи — ' + style['name'] if style else 'Профиль судьи', active='judge',
                body_class='page-judge', bg='calm', scripts=['judge.js'], p=p, style=style, shared=shared,
                census=judge_archetype_shares(), majority_pct=majority_pct, traits=traits,
                career=career.summary(voter), badges=career.achievements(voter, p)[0], daily=career.daily(voter),
                gifts=hunt.inventory(voter), titles=hunt.titles(voter))


def judge_title():
    """The player picks which of their titles shows under the rank."""
    if request.method == 'POST' and csrf_valid():
        ok = hunt.set_title(voter_id(), input_str(request.form.get('title', ''), 120))
        flash('success' if ok else 'error', 'Титул обновлён.' if ok else 'Такого титула у вас нет.')
    return redirect(url_for('judge') + '#gifts')


def brief():
    # The brief's example is one of the demo cases — link to it if it's in play.
    example_id = next((s['id'] for s in situations_list(status='approved', order='old') if s['title'] == 'Три ампулы'), None)
    toc = {
        'about': 'О проекте',
        'idea': 'Основная идея',
        'formats': 'Форматы ситуаций',
        'cats': 'Категории',
        'contents': 'Что содержит ситуация',
        'good': 'Хорошая ситуация',
        'example': 'Пример',
        'review': 'Отбор и метрики',
        'rewards': 'Участие и вознаграждение',
        'sprint': 'Первый спринт',
    }
    return page('brief.html', title='Бриф для авторов', active='brief', body_class='page-brief', bg='calm',
                example_id=example_id, toc=toc)
