"""Players together: ratings, public profiles, friends, communities."""
from flask import request, url_for

from .. import career, notify, seasons, social
from ..auth import current_user_id, is_admin
from ..catalog import SOCIAL
from ..repository import input_str
from ..web import csrf_valid, flash, page, redirect, require_login


def _page(template, title, tab, http_status=200, **ctx):
    return page(template, http_status, title=title, active='ratings', body_class='page-social', bg='calm', tab=tab, **ctx)


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _missing(title):
    return page('error.html', 404, title=title, active='ratings', body_class='page-case', bg='calm')


# ---------- Ratings ----------

def ratings():
    kind = request.args.get('board', 'season')
    kind = kind if kind in SOCIAL['boards'] else 'season'
    scope = request.args.get('scope', 'all')
    uid = current_user_id()
    community, ids = None, None
    if scope == 'friends':
        gate = require_login(url_for('ratings', board=kind, scope='friends'), 'Войдите, чтобы увидеть рейтинг друзей.')
        if gate:
            return gate
        ids = [uid] + social.friend_ids(uid)
    elif scope.startswith('c:'):
        community = social.community_by_slug(scope[2:])
        ids = social.member_ids(community['id']) if community else None
        scope = scope if community else 'all'
    else:
        scope = 'all'
    rows = social.board(kind, ids)
    my_row = next((r for r in rows if r['user_id'] == uid), None) if uid else None
    return _page('ratings.html', 'Рейтинг', 'ratings', rows=rows[:100], total=len(rows), my_row=my_row, kind=kind, scope=scope,
                 community=community, my_communities=social.user_communities(uid), season_name=social.season_name(),
                 days_left=social.days_left())


# ---------- Seasons ----------

def _ranked(rows):
    """Rows of a stored board, with the career rank they had when the season closed."""
    return [{**r, 'rank': career.rank_of(int(r['xp']))} for r in rows]


def seasons_page():
    past = seasons.past()
    for s in past:
        s['board'] = _ranked(s['board'])
    return _page('seasons.html', 'Сезоны', 'seasons', past=past, trophies=seasons.trophies(),
                 season_name=seasons.display_name(), days_left=social.days_left())


def season_page(key):
    s = seasons.get(key)
    if not s:
        return _missing('Сезон не найден')
    s['board'] = _ranked(s['board'])
    uid = current_user_id()
    my_row = next((r for r in s['board'] if r['user_id'] == uid), None) if uid else None
    return _page('season.html', 'Сезон «%s»' % s['name'], 'seasons', s=s, my_row=my_row)


# ---------- Notifications ----------

def notifications_page():
    gate = require_login(url_for('notifications'), 'Войдите, чтобы увидеть уведомления.')
    if gate:
        return gate
    uid = current_user_id()
    items = notify.latest(uid)
    notify.mark_read(uid)  # seen now; the list still shows which ones were new
    from ..repository import situation_find
    from ..web import voter_id
    d = career.daily(voter_id())
    daily_case = situation_find(d['id']) if d['id'] and not d['judged'] else None
    return page('notifications.html', title='Уведомления', active='', body_class='page-social', bg='calm', items=items,
                daily_case=daily_case, daily=d)


# ---------- Profiles and friends ----------

FRIEND_MESSAGES = {
    'requested': ('success', 'Заявка в друзья отправлена.'),
    'accepted': ('success', 'Теперь вы друзья.'),
    'sent': ('success', 'Заявка уже отправлена — ждём ответа.'),
    'friends': ('success', 'Вы уже друзья.'),
    'self': ('error', 'Это вы.'),
}


def _friend_action(uid, other_id, act):
    if act == 'add' and social.barred(uid):
        kind, text = 'error', 'Команда ограничила вам общение с другими игроками.'
    elif act == 'add':
        kind, text = FRIEND_MESSAGES[social.befriend(uid, other_id)]
    elif act == 'accept':
        ok = social.accept(uid, other_id)
        kind, text = ('success', 'Теперь вы друзья.') if ok else ('error', 'Заявки уже нет.')
    elif act == 'decline':
        social.decline(uid, other_id)
        kind, text = 'success', 'Заявка отклонена.'
    elif act == 'cancel':
        social.cancel(uid, other_id)
        kind, text = 'success', 'Заявка отозвана.'
    elif act == 'remove':
        social.unfriend(uid, other_id)
        kind, text = 'success', 'Игрок удалён из друзей.'
    else:
        kind, text = 'error', 'Неизвестное действие.'
    flash(kind, text)


def profile(login):
    user = social.user_by_login(login)
    if not user:
        return _missing('Игрок не найден')
    uid = current_user_id()
    if request.method == 'POST':
        gate = require_login(url_for('profile', login=login), 'Войдите, чтобы добавлять друзей.')
        if gate:
            return gate
        if csrf_valid():
            _friend_action(uid, int(user['id']), request.form.get('action', ''))
        else:
            flash('error', 'Сессия устарела. Попробуйте ещё раз.')
        return redirect(url_for('profile', login=login))
    data = social.profile(user, uid)
    desc = ('%s · %d XP' % (data['summary']['rank']['name'], data['summary']['xp'])) if data['visible'] else ''
    return _page('profile.html', user['display_name'], 'profile', p=data, share_url=url_for('profile', login=login, _external=True),
                 og_desc=('Судья VERDICT: ' + desc + ('. ' + user['bio'] if user['bio'] and data['visible'] else '')) if desc else None)


def friends():
    gate = require_login(url_for('friends'), 'Войдите, чтобы добавлять друзей.')
    if gate:
        return gate
    uid = current_user_id()
    if request.method == 'POST':
        if not csrf_valid():
            flash('error', 'Сессия устарела. Попробуйте ещё раз.')
        elif request.form.get('action') == 'add':
            login = input_str(request.form.get('login', ''), 40).lstrip('@')
            other = social.user_by_login(login) if login else None
            if not other:
                flash('error', 'Игрок с логином «%s» не найден.' % login if login else 'Введите логин друга.')
            else:
                _friend_action(uid, int(other['id']), 'add')
        else:
            _friend_action(uid, _int(request.form.get('user_id')), request.form.get('action', ''))
        return redirect(url_for('friends'))
    return _page('friends.html', 'Друзья', 'friends', friends=social.accounts(social.friend_ids(uid)),
                 incoming=social.requests_in(uid), outgoing=social.requests_out(uid))


def report():
    """A player reports a profile, a community or a case to the team."""
    from ..catalog import REPORT_REASONS
    from ..web import safe_back, voter_id
    back = safe_back(request.form.get('back', '')) or url_for('index')
    gate = require_login(back, 'Войдите, чтобы отправить жалобу.')
    if gate:
        return gate
    kind = request.form.get('target_type', '')
    reason = request.form.get('reason', '')
    if not csrf_valid() or kind not in social.REPORT_TARGETS or reason not in REPORT_REASONS:
        flash('error', 'Не удалось отправить жалобу. Попробуйте ещё раз.')
    elif social.report(kind, _int(request.form.get('target_id')), reason, input_str(request.form.get('text', ''), 500),
                       current_user_id(), voter_id()):
        flash('success', 'Спасибо! Команда посмотрит жалобу.')
    else:
        flash('success', 'Вы уже пожаловались — команда посмотрит.')
    return redirect(back)


# ---------- Communities ----------

def _community_values():
    v = {
        'name': input_str(request.form.get('name', ''), 80),
        'description': input_str(request.form.get('description', ''), 500),
        'rules': input_str(request.form.get('rules', ''), 3000),
        'access': request.form.get('access', 'open'),
        'icon': request.form.get('icon', 'users'),
        'hue': _int(request.form.get('hue')),
    }
    errors = {}
    if not 3 <= len(v['name']) <= 80:
        errors['name'] = 'Название: от 3 до 80 символов.'
    if v['access'] not in SOCIAL['access']:
        v['access'] = 'open'
    if v['icon'] not in SOCIAL['community_icons']:
        v['icon'] = 'users'
    if v['hue'] not in SOCIAL['community_hues']:
        v['hue'] = SOCIAL['community_hues'][0]
    return v, errors


def communities():
    uid = current_user_id()
    errors, values = {}, {'name': '', 'description': '', 'rules': '', 'access': 'open', 'icon': 'users',
                          'hue': SOCIAL['community_hues'][0]}
    if request.method == 'POST':
        gate = require_login(url_for('communities'), 'Войдите, чтобы создать сообщество.')
        if gate:
            return gate
        if not csrf_valid():
            flash('error', 'Сессия устарела. Попробуйте ещё раз.')
            return redirect(url_for('communities'))
        values, errors = _community_values()
        if social.barred(uid):
            errors['name'] = 'Команда ограничила вам создание сообществ.'
        if not errors and social.owned_count(uid) >= SOCIAL['max_owned']:
            errors['name'] = 'У вас уже %d сообществ — это предел.' % SOCIAL['max_owned']
        if not errors:
            c = social.community_by_id(social.community_create(uid, values))
            flash('success', 'Сообщество «%s» создано. Пригласите участников — ссылка-приглашение на его странице.' % c['name'])
            return redirect(url_for('community', slug=c['slug']))
    q = input_str(request.args.get('q', ''), 80)
    items = social.communities_list(q, uid)
    return _page('communities.html', 'Сообщества', 'communities', items=items, q=q, values=values, errors=errors,
                 mine=[c for c in items if c['my_status'] == 'active'], can_create=bool(uid))


JOIN_MESSAGES = {
    'joined': ('success', 'Добро пожаловать в сообщество!'),
    'requested': ('success', 'Заявка отправлена. Основатель или модератор её рассмотрит.'),
    'already': ('success', 'Вы уже в сообществе.'),
    'pending': ('success', 'Ваша заявка ещё ждёт одобрения.'),
    'need_code': ('error', 'В это сообщество вступают только по ссылке-приглашению.'),
}


def community(slug):
    c = social.community_by_slug(slug)
    if not c:
        return _missing('Сообщество не найдено')
    uid = current_user_id()
    m = social.membership(c['id'], uid)
    manage, owner = social.can_manage(m), bool(m) and m['role'] == 'owner' and m['status'] == 'active'
    errors = {}
    if request.method == 'POST':
        gate = require_login(url_for('community', slug=slug), 'Войдите, чтобы вступить в сообщество.')
        if gate:
            return gate
        if not csrf_valid():
            flash('error', 'Сессия устарела. Попробуйте ещё раз.')
            return redirect(url_for('community', slug=slug))
        act = request.form.get('action', '')
        target = _int(request.form.get('user_id'))
        if act == 'join' and social.barred(uid):
            flash('error', 'Команда ограничила вам вступление в сообщества.')
        elif act == 'join':
            if c['rules'].strip() and not request.form.get('accept_rules'):
                flash('error', 'Чтобы вступить, примите правила сообщества.')
            else:
                flash(*JOIN_MESSAGES[social.join(c, uid, request.form.get('code', ''))])
        elif act == 'leave':
            flash(*(('success', 'Вы вышли из сообщества.') if social.leave(c, uid)
                    else ('error', 'Основатель не может выйти — передайте сообщество или удалите его.')))
        elif act == 'approve' and manage:
            social.approve(c, target)
            flash('success', 'Заявка одобрена.')
        elif act in ('decline', 'remove') and manage:
            ok = social.remove_member(c, target, owner)
            flash(*(('success', 'Готово.') if ok else ('error', 'Модератора может убрать только основатель.')))
        elif act in ('promote', 'demote') and owner:
            social.set_role(c, target, 'moderator' if act == 'promote' else 'member')
            flash('success', 'Роль изменена.')
        elif act == 'save' and owner:
            values, errors = _community_values()
            if not errors:
                social.community_update(c['id'], values)
                flash('success', 'Сообщество сохранено.')
                return redirect(url_for('community', slug=slug))
            c = {**c, **values}
        elif act == 'regen' and owner:
            social.regenerate_code(c['id'])
            flash('success', 'Создана новая ссылка-приглашение. Старая больше не работает.')
        elif act == 'delete' and (owner or is_admin()):
            social.community_delete(c['id'])
            flash('success', 'Сообщество «%s» удалено.' % c['name'])
            return redirect(url_for('communities'))
        else:
            flash('error', 'Это действие вам недоступно.')
        if not errors:
            return redirect(url_for('community', slug=slug))
    kind = request.args.get('board', 'season')
    kind = kind if kind in SOCIAL['boards'] else 'season'
    people = social.members(c['id'])
    return _page('community.html', c['name'], 'communities', http_status=422 if errors else 200, c=c, m=m, manage=manage,
                 og_desc=c['description'] or 'Сообщество судей в игре VERDICT.',
                 owner=owner, errors=errors, kind=kind, rows=social.board(kind, social.member_ids(c['id'])),
                 active_members=[p for p in people if p['status'] == 'active'],
                 requests=[p for p in people if p['status'] == 'requested'] if manage else [],
                 invite=request.args.get('invite', ''), season_name=social.season_name(),
                 invite_url=url_for('community', slug=slug, invite=c['invite_code'], _external=True) if manage else None)
