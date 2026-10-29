"""The team's control room: analytics, players, treasure hunts and gifts, the case of the day. Team accounts only."""
import functools
import re
from datetime import datetime, timedelta

from flask import Blueprint, request, url_for

from .. import analytics, career, charts, hunt, players
from ..auth import is_admin, is_logged_in
from ..catalog import GIFT_KINDS, HUNT
from ..db import execute
from ..icons import ICONS
from ..repository import input_str, situation_find, situations_list
from ..web import VOTER_ID, csrf_valid, flash, json_response, page, redirect, safe_back

bp = Blueprint('admin', __name__)

UNITY_PAGE = re.compile(r'^unity:[a-z0-9_\-]{1,40}$')
STAMP = '%Y-%m-%dT%H:%M'


def team_only(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        if not is_logged_in():
            flash('error', 'Войдите в аккаунт команды.')
            return redirect(url_for('login', back=request.full_path.rstrip('?')))
        if not is_admin():
            flash('error', 'Админка доступна только команде.')
            return redirect(url_for('index'))
        if request.method == 'POST' and not csrf_valid():
            if request.is_json:
                return json_response({'ok': False, 'error': 'Сессия устарела. Обновите страницу.'}, 419)
            flash('error', 'Сессия устарела. Попробуйте ещё раз.')
            return redirect(request.path)
        return view(*args, **kwargs)
    return wrapper


def _render(template, title, section, **ctx):
    return page('admin/' + template, title=title + ' — админка', active='admin', body_class='page-admin', bg='calm',
                scripts=['admin.js'], section=section, **ctx)


def _int(value, default=0, low=None, high=None):
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    if low is not None:
        n = max(low, n)
    if high is not None:
        n = min(high, n)
    return n


def _stamp(value):
    """<input type="datetime-local"> → datetime (UTC, as the team entered it) or None."""
    value = input_str(value, 20)
    try:
        return datetime.strptime(value, STAMP) if value else None
    except ValueError:
        return False


def _checkbox(name):
    return 1 if request.form.get(name) else 0


# ---------- Overview ----------

@bp.get('/')
@team_only
def dashboard():
    a = analytics.dashboard()

    def day(d):
        return d.strftime('%d.%m')

    ch = {
        'activity': charts.stacked([(day(r['day']), r['visitors'] - r['new'], r['new']) for r in a['series']],
                                   ('Вернувшиеся', 'Новые'), ('игрок', 'игрока', 'игроков')),
        'verdicts': charts.columns([(day(r['day']), r['verdicts']) for r in a['series']], ('вердикт', 'вердикта', 'вердиктов')),
        'hours': charts.columns([('%02d' % h, v) for h, v in enumerate(a['hours'])], ('вердикт', 'вердикта', 'вердиктов'),
                                every=6, from_start=True),
        'funnel': charts.hbars([{'label': f['label'], 'value': f['value'], 'note': '%d%%' % round(f['share'] * 100)}
                                for f in a['funnel']], ('игрок', 'игрока', 'игроков')),
        'categories': charts.hbars([{**r, 'label': r['name']} for r in a['categories']], ('вердикт', 'вердикта', 'вердиктов')),
        'ranks': charts.hbars([{**r, 'label': r['name'], 'note': 'от %d XP' % r['xp']} for r in a['ranks']],
                              ('игрок', 'игрока', 'игроков')),
        'achievements': charts.hbars([{**r, 'label': r['name']} for r in sorted(a['achievements'], key=lambda r: -r['value'])],
                                     ('игрок', 'игрока', 'игроков')),
    }
    from ..social import open_reports_count
    return _render('dashboard.html', 'Обзор', 'dashboard', a=a, ch=ch, running=hunt.running_challenges(),
                   open_reports=open_reports_count(), default_password=default_password())


def default_password():
    """The first team account (admin) still opens with the password from the setup guide."""
    from ..auth import check_password
    from ..db import scalar
    hashed = scalar("SELECT password_hash FROM users WHERE login = 'admin' AND role = 'admin'")
    return bool(hashed) and check_password('verdict-admin', hashed)


# ---------- Players ----------

@bp.get('/players')
@team_only
def players_page():
    q = input_str(request.args.get('q', ''), 64)
    who = request.args.get('who', 'players')
    who = who if who in ('players', 'accounts', 'blocked', 'all') else 'players'
    sort = request.args.get('sort', 'recent')
    sort = sort if sort in players.SORTS else 'recent'
    pg = _int(request.args.get('page'), 1, 1)
    rows, total = players.players_list(q, who, sort, pg)
    for r in rows:
        r['rank'] = career.rank_of(int(r['xp']))
    return _render('players.html', 'Игроки', 'players', rows=rows, total=total, q=q, who=who, sort=sort, pg=pg,
                   pages=max(1, -(-total // 50)))


@bp.route('/players/<voter>', methods=['GET', 'POST'])
@team_only
def player_page(voter):
    voter = voter.lower()
    if not VOTER_ID.match(voter) or not players.exists(voter):
        flash('error', 'Игрок не найден.')
        return redirect(url_for('admin.players_page'))
    back = url_for('admin.player_page', voter=voter)
    if request.method == 'POST':
        act = request.form.get('action', '')
        if act == 'block':
            players.set_blocked(voter, True)
            flash('success', 'Игрок отстранён от охоты за тайниками.')
        elif act == 'unblock':
            players.set_blocked(voter, False)
            flash('success', 'Игрок снова может искать тайники.')
        elif act == 'reset_world':
            career.reset_world(voter)
            flash('success', 'Мир игрока начат заново.')
        elif act == 'grant':
            gift = hunt.gift_find(_int(request.form.get('gift_id')))
            if not gift:
                flash('error', 'Выберите подарок.')
            else:
                r = hunt.grant(voter, gift, 'admin', note=input_str(request.form.get('note', ''), 255))
                from .. import notify
                notify.send_to_player(voter, 'gift', 'Команда VERDICT прислала вам подарок «%s».' % gift['name'], '/judge#gifts')
                flash('success', 'Подарок «%s» выдан.' % gift['name'] + (' Коды в пуле закончились — код не выдан.'
                                                                       if gift['kind'] == 'code' and not r['code'] else ''))
        elif act == 'revoke':
            r = hunt.revoke(_int(request.form.get('grant_id')))
            flash('success' if r else 'error', ('Подарок «%s» отозван.' % r['name']) if r else 'Подарок уже отозван.')
        elif act == 'password' and info_user(voter):
            import secrets
            from .. import gameauth
            from ..auth import user_set_password
            from ..sessions import revoke_others
            u = info_user(voter)
            new = secrets.token_urlsafe(9)
            user_set_password(u['id'], new)
            revoke_others(u['id'], '')
            gameauth.revoke_user(u['id'])
            flash('success', 'Новый пароль для @%s: %s — передайте его игроку и попросите сменить в профиле. '
                             'Все входы игрока на сайте и в игре завершены.' % (u['login'], new))
        elif act == 'delete':
            players.delete_player(voter)
            flash('success', 'Все игровые данные игрока удалены.')
            return redirect(url_for('admin.players_page'))
        return redirect(back)

    info = players.player_detail(voter)
    from ..judge import judge_profile
    p = judge_profile(voter)
    return _render('player.html', 'Игрок', 'players', voter=voter, info=info, summary=career.summary(voter),
                   profile=p, badges=career.achievements(voter, p)[0], votes=players.player_votes(voter),
                   grants=players.player_grants(voter), finds=players.player_finds(voter),
                   world=career.world(voter), gifts=[x for x in hunt.gifts_all() if x['active']])


def info_user(voter):
    from ..db import query_one
    return query_one('SELECT u.id, u.login FROM players p JOIN users u ON u.id = p.user_id WHERE p.voter = %s', (voter,))


# ---------- Treasure hunts ----------

def _challenge_values():
    v = {
        'title': input_str(request.form.get('title', ''), 120),
        'intro': input_str(request.form.get('intro', ''), 4000),
        'status': request.form.get('status', 'draft'),
        'starts_at': _stamp(request.form.get('starts_at')),
        'ends_at': _stamp(request.form.get('ends_at')),
        'banner': _checkbox('banner'),
        'prize_gift_id': _int(request.form.get('prize_gift_id')) or None,
    }
    errors = {}
    if len(v['title']) < 2:
        errors['title'] = 'Назовите охоту: от 2 до 120 символов.'
    if v['status'] not in hunt.STATUSES:
        v['status'] = 'draft'
    for f in ('starts_at', 'ends_at'):
        if v[f] is False:
            errors[f] = 'Дата в формате ГГГГ-ММ-ДД ЧЧ:ММ.'
            v[f] = None
    if v['starts_at'] and v['ends_at'] and v['ends_at'] <= v['starts_at']:
        errors['ends_at'] = 'Конец охоты должен быть позже начала.'
    if v['prize_gift_id'] and not hunt.gift_find(v['prize_gift_id']):
        v['prize_gift_id'] = None
    return v, errors


@bp.route('/hunts', methods=['GET', 'POST'])
@team_only
def hunts_page():
    errors, values = {}, {'title': '', 'intro': '', 'status': 'draft', 'starts_at': None, 'ends_at': None, 'banner': 1,
                          'prize_gift_id': None}
    if request.method == 'POST':
        values, errors = _challenge_values()
        if not errors:
            cid = hunt.challenge_save(values)
            flash('success', 'Охота «%s» создана. Добавьте тайники и разместите их на страницах.' % values['title'])
            return redirect(url_for('admin.hunt_page', challenge_id=cid))
    items = hunt.challenges_all()
    for c in items:
        c['state'] = hunt.state_of(c)
    return _render('hunts.html', 'Охота за тайниками', 'hunts', items=items, values=values, errors=errors,
                   gifts=hunt.gifts_all(), now=hunt.utcnow())


def _spot_values(current=None):
    page_key = input_str(request.form.get('page', '*'), 60)
    if page_key == 'unity':
        page_key = 'unity:' + re.sub(r'[^a-z0-9_\-]', '', input_str(request.form.get('scene', ''), 40).lower())
    v = {
        'label': input_str(request.form.get('label', ''), 120),
        'page': page_key,
        'path': input_str(request.form.get('path', ''), 255),
        'icon': request.form.get('icon', 'gem'),
        'size': _int(request.form.get('size'), 24, 12, 64),
        'visibility': request.form.get('visibility', 'subtle'),
        'hint': input_str(request.form.get('hint', ''), 255),
        'gift_id': _int(request.form.get('gift_id')) or None,
        'max_finds': _int(request.form.get('max_finds'), 0, 0, 1000000),
        'active': _checkbox('active'),
    }
    errors = {}
    if v['page'] not in hunt.PAGES and not UNITY_PAGE.match(v['page']):
        errors['page'] = 'Выберите страницу сайта или укажите сцену игры (латиница, цифры, - и _).'
    if v['path'] and (not v['path'].startswith('/') or v['path'].startswith('//')):
        errors['path'] = 'Адрес страницы начинается с «/», например /case/12.'
    if v['icon'] not in ICONS:
        v['icon'] = 'gem'
    if v['visibility'] not in HUNT['visibility']:
        v['visibility'] = 'subtle'
    if v['gift_id'] and not hunt.gift_find(v['gift_id']):
        v['gift_id'] = None
    return v, errors


def _blank_spot():
    return {'label': '', 'page': 'index', 'path': '', 'icon': 'gem', 'size': 24, 'visibility': 'subtle', 'hint': '',
            'gift_id': None, 'max_finds': 0, 'active': 1}


@bp.route('/hunts/<int:challenge_id>', methods=['GET', 'POST'])
@team_only
def hunt_page(challenge_id):
    c = hunt.challenge_find(challenge_id)
    if not c:
        flash('error', 'Охота не найдена.')
        return redirect(url_for('admin.hunts_page'))
    errors, spot_errors, spot_values = {}, {}, _blank_spot()
    if request.method == 'POST':
        act = request.form.get('action', 'save')
        if act == 'save':
            values, errors = _challenge_values()
            if not errors:
                hunt.challenge_save(values, challenge_id)
                flash('success', 'Охота сохранена.')
                return redirect(url_for('admin.hunt_page', challenge_id=challenge_id))
            c = {**c, **values}
        elif act in ('start', 'stop'):
            execute('UPDATE challenges SET status = %s WHERE id = %s', ('active' if act == 'start' else 'ended', challenge_id))
            flash('success', 'Охота запущена.' if act == 'start' else 'Охота завершена: тайники исчезли со страниц.')
            return redirect(url_for('admin.hunt_page', challenge_id=challenge_id))
        elif act == 'delete':
            execute('DELETE FROM challenges WHERE id = %s', (challenge_id,))
            flash('success', 'Охота «%s» удалена. Выданные подарки остались у игроков.' % c['title'])
            return redirect(url_for('admin.hunts_page'))
        elif act == 'add_spot':
            spot_values, spot_errors = _spot_values()
            if not spot_errors:
                sid = hunt.spot_save(spot_values, challenge_id)
                flash('success', 'Тайник добавлен. Теперь разместите его на странице.')
                return redirect(url_for('admin.spot_page', spot_id=sid) + '#place')
    spots = hunt.spots_of(challenge_id)
    return _render('hunt.html', c['title'], 'hunts', c=c, state=hunt.state_of(c), errors=errors, spots=spots,
                   spot_values=spot_values, spot_errors=spot_errors, gifts=hunt.gifts_all(), finds=hunt.finds_of(challenge_id),
                   totals=hunt.challenge_totals(challenge_id), now=hunt.utcnow())


@bp.route('/spots/<int:spot_id>', methods=['GET', 'POST'])
@team_only
def spot_page(spot_id):
    s = hunt.spot_find(spot_id)
    if not s:
        flash('error', 'Тайник не найден.')
        return redirect(url_for('admin.hunts_page'))
    c = hunt.challenge_find(s['challenge_id'])
    errors = {}
    if request.method == 'POST':
        act = request.form.get('action', 'save')
        if act == 'delete':
            execute('DELETE FROM spots WHERE id = %s', (spot_id,))
            flash('success', 'Тайник удалён.')
            return redirect(url_for('admin.hunt_page', challenge_id=c['id']))
        if act == 'open':
            url = safe_back(input_str(request.form.get('url', ''), 255))
            if not url or url.startswith(request.script_root + '/admin'):
                flash('error', 'Укажите адрес страницы сайта, например /case/12.')
                return redirect(url_for('admin.spot_page', spot_id=spot_id) + '#place')
            return redirect(url + ('&' if '?' in url else '?') + 'hunt_place=%d' % spot_id)
        values, errors = _spot_values(s)
        x = request.form.get('x')
        if not errors:
            hunt.spot_save(values, spot_id=spot_id)
            if x is not None:  # the exact place, edited by hand
                execute('UPDATE spots SET selector = %s, x = %s, y = %s WHERE id = %s',
                        (input_str(request.form.get('selector', ''), 500), _coord(x), _coord(request.form.get('y')), spot_id))
            flash('success', 'Тайник сохранён.')
            return redirect(url_for('admin.spot_page', spot_id=spot_id))
        s = {**s, **values}
    return _render('spot.html', s['label'] or 'Тайник %d' % spot_id, 'hunts', s=s, c=c, errors=errors,
                   gifts=hunt.gifts_all(), place_url=_default_url(s), finds=[f for f in hunt.finds_of(c['id']) if f['spot_id'] == spot_id])


def _coord(value):
    try:
        return max(0.0, min(100.0, round(float(str(value).replace(',', '.')), 2)))
    except (TypeError, ValueError):
        return 50.0


def _default_url(s):
    """Where the team goes to place the spot: its exact address, or the page of its kind."""
    if s['path']:
        return s['path']
    endpoint = s['page']
    if endpoint in ('quick_case', 'case', 'view'):
        first = next(iter(situations_list(status='approved', order='old')), None)
        return url_for(endpoint, id=first['id']) if first else url_for('index')
    try:
        return url_for(endpoint) if endpoint in hunt.PAGES and endpoint != '*' else url_for('index')
    except Exception:
        return url_for('index')


@bp.post('/spots/<int:spot_id>/place')
@team_only
def spot_place(spot_id):
    """Placement mode on a page posts here: which element, where inside it, on which page."""
    s = hunt.spot_find(spot_id)
    data = request.get_json(silent=True) or {}
    if not s:
        return json_response({'ok': False, 'error': 'Тайник не найден.'}, 404)
    page_key = input_str(data.get('page', ''), 60)
    path = input_str(data.get('path', ''), 255)
    selector = input_str(data.get('selector', ''), 500)
    scope = data.get('scope', 'page')
    if page_key not in hunt.PAGES or page_key == '*' or not selector:
        return json_response({'ok': False, 'error': 'На этой странице тайник разместить нельзя.'}, 422)
    if scope == 'site':
        page_key, path = '*', ''
    elif scope == 'kind':
        path = ''
    elif not path.startswith('/'):
        return json_response({'ok': False, 'error': 'Не удалось определить адрес страницы.'}, 422)
    hunt.spot_place(spot_id, page_key, path, selector, _coord(data.get('x')), _coord(data.get('y')))
    flash('success', 'Тайник размещён. Проверьте, как его видят игроки: «Посмотреть на странице».')
    return json_response({'ok': True, 'back': url_for('admin.spot_page', spot_id=spot_id)})


# ---------- Gifts ----------

def _gift_values():
    v = {
        'kind': request.form.get('kind', 'badge'),
        'name': input_str(request.form.get('name', ''), 120),
        'icon': request.form.get('icon', 'gift'),
        'xp': _int(request.form.get('xp'), 0, 0, 10000),
        'text': input_str(request.form.get('text', ''), 2000),
        'link': input_str(request.form.get('link', ''), 500),
        'needs_account': _checkbox('needs_account'),
        'active': _checkbox('active'),
    }
    errors = {}
    if v['kind'] not in GIFT_KINDS:
        errors['kind'] = 'Выберите вид подарка.'
    if len(v['name']) < 2:
        errors['name'] = 'Название: от 2 до 120 символов.'
    if v['icon'] not in ICONS:
        v['icon'] = 'gift'
    if v['link'] and not re.match(r'^(https?://|/)[^\s<>"]+$', v['link']):
        errors['link'] = 'Ссылка начинается с https:// или с «/».'
    if v['kind'] == 'xp' and v['xp'] <= 0:
        errors['xp'] = 'Сколько опыта даёт подарок?'
    return v, errors


def _codes(text):
    return list(dict.fromkeys(c.strip()[:120] for c in (text or '').splitlines() if c.strip()))


@bp.route('/gifts', methods=['GET', 'POST'])
@team_only
def gifts_page():
    errors, values = {}, {'kind': 'badge', 'name': '', 'icon': 'gift', 'xp': 0, 'text': '', 'link': '', 'needs_account': 0, 'active': 1}
    if request.method == 'POST':
        values, errors = _gift_values()
        if not errors:
            gid = hunt.gift_save(values)
            added = hunt.codes_add(gid, _codes(request.form.get('codes', ''))) if values['kind'] == 'code' else 0
            flash('success', 'Подарок «%s» создан.' % values['name'] + (' Кодов в пуле: %d.' % added if values['kind'] == 'code' else ''))
            return redirect(url_for('admin.gifts_page'))
    return _render('gifts.html', 'Подарки', 'gifts', items=hunt.gifts_all(), values=values, errors=errors)


@bp.route('/gifts/<int:gift_id>', methods=['GET', 'POST'])
@team_only
def gift_page(gift_id):
    gift = hunt.gift_find(gift_id)
    if not gift:
        flash('error', 'Подарок не найден.')
        return redirect(url_for('admin.gifts_page'))
    errors = {}
    if request.method == 'POST':
        act = request.form.get('action', 'save')
        if act == 'delete':
            execute('DELETE FROM gifts WHERE id = %s', (gift_id,))
            flash('success', 'Подарок «%s» удалён. Уже выданные остались у игроков.' % gift['name'])
            return redirect(url_for('admin.gifts_page'))
        if act == 'codes':
            added = hunt.codes_add(gift_id, _codes(request.form.get('codes', '')))
            flash('success', 'Добавлено кодов: %d.' % added)
            return redirect(url_for('admin.gift_page', gift_id=gift_id))
        if act == 'clear_codes':
            flash('success', 'Удалено свободных кодов: %d.' % hunt.codes_remove_free(gift_id))
            return redirect(url_for('admin.gift_page', gift_id=gift_id))
        values, errors = _gift_values()
        if not errors:
            hunt.gift_save(values, gift_id)
            flash('success', 'Подарок сохранён.')
            return redirect(url_for('admin.gift_page', gift_id=gift_id))
        gift = {**gift, **values}
    from ..db import query
    grants = query('SELECT r.*, u.display_name, u.login FROM gift_grants r LEFT JOIN players p ON p.voter = r.voter'
                   ' LEFT JOIN users u ON u.id = p.user_id WHERE r.gift_id = %s ORDER BY r.id DESC LIMIT 200', (gift_id,))
    codes = hunt.codes_of(gift_id)
    preview = {**gift, 'code': next((c['code'] for c in codes if not c['grant_id']), 'ВАШ-КОД') if gift['kind'] == 'code' else None}
    return _render('gift.html', gift['name'], 'gifts', gift=gift, errors=errors, codes=codes, grants=grants, preview=preview)


# ---------- Reports ----------

@bp.route('/reports', methods=['GET', 'POST'])
@team_only
def reports_page():
    from .. import social
    from ..auth import current_user_id
    status = request.args.get('status', 'open')
    status = status if status in ('open', 'resolved', 'dismissed') else 'open'
    if request.method == 'POST':
        act = request.form.get('action', '')
        rid = _int(request.form.get('id'))
        if act == 'block':
            players.set_blocked(input_str(request.form.get('voter', ''), 32), True)
            flash('success', 'Игрок отстранён: охота, рейтинг, друзья и сообщества для него закрыты.')
        elif act == 'delete_community':
            c = social.community_by_id(_int(request.form.get('target_id')))
            if c:
                social.community_delete(c['id'])
                flash('success', 'Сообщество «%s» удалено.' % c['name'])
        elif act == 'unpublish':
            execute("UPDATE situations SET status = 'pending' WHERE id = %s AND status = 'approved'",
                    (_int(request.form.get('target_id')),))
            flash('success', 'Ситуация снята с игры и вернулась на отбор.')
        if act in ('block', 'delete_community', 'unpublish', 'resolve'):
            social.report_close(rid, 'resolved', current_user_id())
            if act == 'resolve':
                flash('success', 'Жалоба закрыта.')
        elif act == 'dismiss':
            social.report_close(rid, 'dismissed', current_user_id())
            flash('success', 'Жалоба отклонена.')
        return redirect(url_for('admin.reports_page'))
    return _render('reports.html', 'Жалобы', 'reports', items=social.reports_list(status), status=status)


# ---------- Communities ----------

@bp.route('/communities', methods=['GET', 'POST'])
@team_only
def communities_page():
    from .. import social
    if request.method == 'POST':
        c = social.community_by_id(_int(request.form.get('id')))
        if c:
            social.community_delete(c['id'])
            flash('success', 'Сообщество «%s» удалено.' % c['name'])
        return redirect(url_for('admin.communities_page'))
    from ..db import query
    items = query("SELECT c.*, u.display_name AS owner_name, u.login AS owner_login,"
                  " (SELECT COUNT(*) FROM community_members m WHERE m.community_id = c.id AND m.status = 'active') AS members,"
                  " (SELECT COUNT(*) FROM community_members m WHERE m.community_id = c.id AND m.status = 'requested') AS requests"
                  " FROM communities c JOIN users u ON u.id = c.owner_id ORDER BY c.id DESC")
    friendships = query("SELECT COUNT(*) AS n FROM friendships WHERE status = 'accepted'")[0]['n'] // 2
    return _render('communities.html', 'Сообщества', 'communities', items=items, friendships=friendships)


# ---------- The game ----------

@bp.route('/game', methods=['GET', 'POST'])
@team_only
def game_page():
    if request.method == 'POST':
        day = request.form.get('day', '')
        sid = _int(request.form.get('situation_id'))
        s = situation_find(sid) if sid else None
        try:
            d = datetime.strptime(day, '%Y-%m-%d').date()
        except ValueError:
            d = None
        if not d or not s or s['status'] != 'approved' or d < career.today():
            flash('error', 'Выберите день (сегодня или позже) и дело в игре.')
        else:
            execute('INSERT INTO meta (meta_key, meta_value) VALUES (%s, %s) ON DUPLICATE KEY UPDATE meta_value = %s',
                    ('daily:' + d.isoformat(), str(sid), str(sid)))
            flash('success', 'Дело дня на %s: «%s».' % (d.strftime('%d.%m'), s['title']))
        return redirect(url_for('admin.game_page'))
    days = []
    for i in range(7):
        d = career.today() + timedelta(days=i)
        sid = career.daily_case_id(d)
        days.append({'day': d, 'case': situation_find(sid) if sid else None})
    from .. import signups
    return _render('game.html', 'Игра', 'game', days=days, cases=situations_list(status='approved', order='old'),
                   seen=signups.seen())
