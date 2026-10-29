"""The discussion page of a case: /talk/<id>. Readable by those who judged the case (and the team); accounts write,
back, delete their own comments; the team hides or deletes."""
from flask import request, url_for

from .. import social, talk
from ..auth import current_user_id, is_admin
from ..repository import input_str, situation_find
from ..web import csrf_valid, flash, page, redirect, require_login, voter_id


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _scope(uid):
    """all | friends | c:<slug> → (scope, the authors to show or None, the community)."""
    scope = request.values.get('scope', 'all')
    if scope == 'friends' and uid:
        return scope, [uid] + social.friend_ids(uid), None
    if scope.startswith('c:'):
        c = social.community_by_slug(scope[2:])
        if c:
            return scope, social.member_ids(c['id']), c
    return 'all', None, None


def talk_page(id):
    s = situation_find(id)
    if not s or s['status'] != 'approved':
        return page('error.html', 404, title='Дело не найдено', active='', body_class='page-case', bg='calm')
    uid = current_user_id()
    mine = talk.judged(voter_id(), s['id'])
    team = is_admin()
    sort = request.values.get('sort', 'top')
    sort = sort if sort in talk.SORTS else 'top'
    scope, authors, community = _scope(uid)
    here = url_for('talk', id=s['id'], sort=sort, scope=scope if scope != 'all' else None)
    draft, problem = '', ''

    if request.method == 'POST':
        gate = require_login(here, 'Войдите, чтобы участвовать в обсуждении.')
        if gate:
            return gate
        if not csrf_valid():
            flash('error', 'Сессия устарела. Попробуйте ещё раз.')
            return redirect(here)
        act = request.form.get('action', '')
        cid = _int(request.form.get('comment_id'))
        c = talk.find(cid) if cid else None
        if c and int(c['situation_id']) != s['id']:
            c = None
        if act == 'post':
            draft = input_str(request.form.get('text', ''), talk.MAX_LEN + 1)
            try:
                cid = talk.post(s['id'], uid, voter_id(), draft)
            except talk.TalkError as e:
                problem = e.message  # the page again, with the text kept
            else:
                flash('success', 'Ваш комментарий опубликован.')
                return redirect(url_for('talk', id=s['id'], sort='new') + '#c%d' % cid)
        elif act in ('like', 'unlike') and c:
            (talk.like if act == 'like' else talk.unlike)(c['id'], uid)
        elif act == 'delete' and c and int(c['user_id']) == uid:
            talk.delete_own(c['id'], uid)
            flash('success', 'Комментарий удалён.')
        elif act in ('hide', 'show') and c and team:
            talk.set_hidden(c['id'], act == 'hide')
            flash('success', 'Комментарий скрыт, автор узнает об этом.' if act == 'hide' else 'Комментарий снова виден.')
        elif act == 'remove' and c and team:
            talk.remove(c['id'])
            flash('success', 'Комментарий удалён.')
        if not problem:
            return redirect(here + ('#c%d' % c['id'] if c and act in ('like', 'unlike', 'hide', 'show') else ''))

    if mine is None and not team:
        return page('talk.html', title='Обсуждение: %s' % s['title'], active='play', body_class='page-social', bg='calm',
                    s=s, locked=True, total=talk.count(s['id']))
    items = talk.comments(s['id'], uid, sort, authors, team=team)
    return page('talk.html', 422 if problem else 200, title='Обсуждение: %s' % s['title'], active='play',
                body_class='page-social', bg='calm', s=s, locked=False, items=items, total=talk.count(s['id']), mine=mine,
                sort=sort, scope=scope, community=community, my_communities=social.user_communities(uid),
                barred=bool(uid) and social.barred(uid), max_len=talk.MAX_LEN, draft=draft, problem=problem)
