"""Story campaigns: the list and the page of a campaign (intro → chapter → what the verdict led to → … → ending)."""
from flask import request, url_for

from .. import campaigns
from ..repository import vote_counts_for
from ..web import csrf_valid, flash, page, redirect, voter_id


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def campaigns_page():
    return page('campaigns.html', title='Кампании', active='play', body_class='page-campaigns', bg='high',
                items=campaigns.overview(voter_id()))


def campaign_page(key):
    c = campaigns.get(key)
    if not c or not campaigns.available(c):
        return page('error.html', 404, title='Кампания не найдена', active='play', body_class='page-case', bg='calm')
    voter = voter_id()
    if request.method == 'POST':
        if not csrf_valid():
            flash('error', 'Сессия устарела. Попробуйте ещё раз.')
            return redirect(url_for('campaign', key=key))
        act = request.form.get('action', '')
        st = campaigns.state(voter, c)
        if act == 'start' and (not st['run'] or st['finished']):
            campaigns.start(voter, c)
            return redirect(url_for('campaign', key=key))
        if act == 'choose':
            ch = st['chapter']
            st, problem = campaigns.choose(voter, c, request.form.get('option', ''), _int(request.form.get('duration_ms')))
            if problem:
                flash('error', problem)
                return redirect(url_for('campaign', key=key))
            return redirect(url_for('campaign', key=key, after=ch['key']) + '#result')
        return redirect(url_for('campaign', key=key))

    st = campaigns.state(voter, c)
    ctx = {'c': c, 'st': st, 'chapters': [{'ch': ch, 's': campaigns.chapter_case(ch)} for ch in c['chapters']]}
    after = request.args.get('after', '')
    done = {x['chapter']: x for x in st['choices']}
    if st['run'] and after in done:
        i = next(i for i, ch in enumerate(c['chapters']) if ch['key'] == after)
        s = ctx['chapters'][i]['s']
        ctx['result'] = {'index': i, 's': s, 'choice': done[after]['option'], 'adopted': done[after].get('adopted'),
                         'delta': st['steps'][i] if i < len(st['steps']) else {}, 'counts': vote_counts_for(s['id'])}
    elif st['run'] and not st['finished'] and st['index'] < len(c['chapters']):
        i = st['index']
        ctx['play'] = {'index': i, 's': ctx['chapters'][i]['s'], 'bridges': campaigns.bridges(c, i, st['choices'])}
    if st['finished']:
        shares, finished = campaigns.ending_shares(c)
        ctx['shares'], ctx['finished_total'] = shares, finished
    return page('campaign.html', title=c['title'], active='play', body_class='page-campaign', bg='calm',
                scripts=['comic.js'], og_desc=c['teaser'], **ctx)
