"""Game-client API (Unity, mobile, anything that speaks HTTP + JSON). See docs/API.md.

The player is identified by the X-Voter-Id header: 32 lowercase hex characters the client generates once and
keeps (in Unity: Guid.NewGuid().ToString("N")). No cookies are read, so the API is open to any origin (CORS *).
Votes from the API and from the website share one table, so the vote split and the judge profile are common.
"""
import re

from flask import Blueprint, g, request

from .. import career, gameauth, hunt, players, social
from ..catalog import JUDGE_ARCHETYPES, METRICS, SOCIAL, public as catalog_public
from ..comic import cast_of, cast_public, panels_of
from ..helpers import case_controversy, excerpt
from ..judge import judge_profile
from ..repository import (decision_has_consequences, input_str, next_case, open_cases, quick_stats, situation_find,
                          situations_list, vote_counts, vote_counts_for, vote_find, votes_of_voter)
from .api import cast_vote, vote_error

bp = Blueprint('api_v1', __name__)

VOTER = re.compile(r'^[a-f0-9]{32}$')
VERSION = 1


@bp.after_request
def cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Voter-Id, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Max-Age'] = '86400'
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.before_request
def preflight():
    if request.method == 'OPTIONS':
        return '', 204


def error(message, status):
    return {'ok': False, 'error': message}, status


def account():
    """The account signed in from the game client (Authorization: Bearer <token>), or None."""
    if 'api_account' not in g:
        h = request.headers.get('Authorization', '')
        g.api_account = gameauth.user_for(h[7:].strip()) if h[:7].lower() == 'bearer ' else None
    return g.api_account


def header_voter():
    vid = request.headers.get('X-Voter-Id', '').strip().lower()
    return vid if VOTER.match(vid) else None


def voter():
    """The player: the signed-in account's player, else the X-Voter-Id the client keeps."""
    user = account()
    if user:
        return players.attach(int(user['id']), header_voter())
    return header_voter()


def need_account():
    return error('Нужен вход: заголовок Authorization: Bearer <token> из POST /api/v1/auth/login.', 401)


def need_voter():
    return error('Нужен заголовок X-Voter-Id: 32 шестнадцатеричных символа (например, Guid без дефисов).', 400)


# ---------- Shapes ----------

def case_summary(s, counts, mine=None):
    c = counts.get(s['id'], {})
    contro = case_controversy(s, c)
    return {
        'id': s['id'],
        'title': s['title'],
        'category': s['category'],
        'type': s['type'],
        'setting': s['world']['setting'],
        'place': s['world']['place'],
        'era': s['world']['era'],
        'teaser': excerpt(s['story'], 170),
        'decisions': len(s['decisions']),
        'votes': sum(c.values()),
        'controversy': contro['value'],
        'my_verdict': (mine or {}).get(s['id']),
    }


def case_full(s, vid=None):
    """What a player sees before the verdict: no consequences, hidden info or author notes."""
    cast = cast_of(s)
    out = {
        'id': s['id'],
        'title': s['title'],
        'category': s['category'],
        'type': s['type'],
        'author': s['author'],
        'world': s['world'],
        'story': s['story'],
        'participants': s['participants'],
        'facts': s['facts'],
        'unknowns': s['unknowns'],
        'witnesses': s['witnesses'],
        'decisions': [{'key': d['key'], 'text': d['text']} for d in s['decisions']],
        'allows_own_decision': True,
        'comic': {'cast': cast_public(cast), 'panels': panels_of(s, cast, True)},
        'my_vote': None,
    }
    if vid:
        mine = vote_find(s['id'], vid)
        if mine:
            out['my_vote'] = {'option': mine['option_key'], 'guess': mine['guess_key'],
                              'guess_correct': None if mine['guess_correct'] is None else bool(mine['guess_correct'])}
    return out


def outcome(s, choice, counts):
    """After the verdict: consequences, the split, the arguments."""
    decisions = []
    total = sum(counts.values())
    for d in s['decisions']:
        decisions.append({
            'key': d['key'], 'text': d['text'], 'why': d.get('why', ''),
            'votes': counts.get(d['key'], 0),
            'share': counts.get(d['key'], 0) / total if total else 0,
        })
    chosen = next((d for d in s['decisions'] if d['key'] == choice), None)
    return {
        'choice': choice,
        'consequences': {f: chosen.get(f, '') for f in ('immediate', 'longterm', 'characters', 'world')}
        if chosen and decision_has_consequences(chosen) else None,
        'effects': {m: int(v) for m, v in ((chosen or {}).get('effects') or {}).items() if m in METRICS and v},
        'decisions': decisions,
        'other_votes': counts.get('other', 0),
        'total_votes': total,
        'controversy': case_controversy(s, counts),
        'ambiguity': s['ambiguity'],
        'continuation': bool(s['continuation'].get('possible')),
    }


def profile_out(vid, p=None):
    p = p or judge_profile(vid)
    style = p['archetype']
    return {
        **{k: p[k] for k in ('verdicts', 'decided', 'own', 'left', 'with_majority', 'compared', 'median_ms', 'top_category', 'quick')},
        'archetype': {'key': style, **JUDGE_ARCHETYPES[style]} if style else None,
        'leans': p['leans'],
        'boldest': p['boldest'],
    }


def career_out(vid, p=None):
    summary = career.summary(vid)
    badges, _ = career.achievements(vid, p)
    return {**{k: summary[k] for k in ('xp', 'rank', 'streak', 'best_streak', 'daily_done', 'title')}, 'achievements': badges}


def world_out(vid):
    w = career.world(vid)
    return {'metrics': w['metrics'], 'count': w['count'], 'active': w['active']}


# ---------- Endpoints ----------

@bp.get('/')
def index():
    return {
        'ok': True, 'name': 'VERDICT', 'version': VERSION,
        'endpoints': {
            'GET /api/v1/catalog': 'categories, world types, meters, levels, judge styles',
            'GET /api/v1/cases': 'cases in play (X-Voter-Id optional: adds my_verdict)',
            'GET /api/v1/cases/<id>': 'one case with comic frames (X-Voter-Id optional: adds my_vote)',
            'GET /api/v1/quick/next': 'a random case the player has not judged (X-Voter-Id required)',
            'POST /api/v1/cases/<id>/verdict': '{option, reasoning?, guess?, mode?, duration_ms?} (X-Voter-Id required)',
            'GET /api/v1/profile': 'judge profile, Быстрый суд score and career (X-Voter-Id required)',
            'GET /api/v1/daily': 'the case of the day, the same for every player (X-Voter-Id optional)',
            'GET /api/v1/world': "the player's world: meters and active world events (X-Voter-Id required)",
            'POST /api/v1/world/reset': 'start the world anew; verdicts and career stay (X-Voter-Id required)',
            'GET /api/v1/hunt': 'running treasure hunts, progress and the spots of the game client (X-Voter-Id required)',
            'POST /api/v1/hunt/spots/<id>/claim': 'the player found a spot: the gift (X-Voter-Id required)',
            'GET /api/v1/gifts': "the player's gifts (X-Voter-Id required)",
            'GET /api/v1/ratings?board=season|all|accuracy|streak[&community=<slug>]': 'ratings of players with an account',
            'GET /api/v1/users/<login>': 'a public profile (as much as its owner shows to everyone)',
            'GET /api/v1/communities': 'communities: name, rules, access, members',
            'GET /api/v1/communities/<slug>': 'one community with its members and rating',
            'POST /api/v1/auth/register, /auth/login': '{login, password[, display_name, device]} → token, voter_id',
            'POST /api/v1/auth/logout': 'forgets this device (Authorization: Bearer <token>)',
            'GET /api/v1/me, POST /api/v1/me/profile': 'the signed-in account (Bearer)',
            'GET /api/v1/friends, POST /api/v1/friends {login}': 'friends and requests (Bearer)',
            'POST /api/v1/friends/<login>/accept|decline|cancel|remove': 'answer or end a friendship (Bearer)',
            'POST /api/v1/communities/<slug>/join|leave': '{accept_rules, code?} (Bearer)',
            'GET /api/v1/campaigns': 'story campaigns and the player\'s progress (X-Voter-Id optional)',
            'GET /api/v1/campaigns/<key>': 'a campaign: what earlier verdicts led to, the current chapter, the ending',
            'POST /api/v1/campaigns/<key>/start, /choose {option}': 'start (or replay) a campaign; judge the chapter',
        },
    }


@bp.get('/catalog')
def catalog():
    return {'ok': True, **catalog_public()}


@bp.get('/cases')
def cases():
    vid = voter()
    counts = vote_counts()
    mine = votes_of_voter(vid) if vid else {}
    items = [case_summary(s, counts, mine) for s in situations_list(status='approved', order='old')]
    return {'ok': True, 'count': len(items), 'cases': items}


@bp.get('/cases/<int:case_id>')
def case(case_id):
    s = situation_find(case_id)
    if not s or s['status'] != 'approved':
        return error('Дело не найдено.', 404)
    return {'ok': True, 'case': case_full(s, voter())}


@bp.get('/quick/next')
def quick_next():
    vid = voter()
    if not vid:
        return need_voter()
    try:
        exclude = int(request.args.get('except', 0))
    except ValueError:
        exclude = 0
    found = open_cases(vid, exclude)
    if not found:
        return {'ok': True, 'case': None, 'done': True, 'stats': quick_stats(vid)}
    import random
    return {'ok': True, 'case': case_full(random.choice(found), vid), 'done': False, 'remaining': len(found),
            'stats': quick_stats(vid)}


@bp.post('/cases/<int:case_id>/verdict')
def verdict(case_id):
    vid = voter()
    if not vid:
        return need_voter()
    s = situation_find(case_id)
    if not s or s['status'] != 'approved':
        return error('Дело не найдено.', 404)
    data = request.get_json(silent=True) if request.is_json else request.form
    data = data if isinstance(data, dict) or hasattr(data, 'get') else {}
    key = input_str(data.get('option', ''), 10)
    reasoning = input_str(data.get('reasoning', ''), 1000)
    quick = data.get('mode', 'full') == 'quick'
    problem = vote_error(s, key, reasoning, quick)
    if problem:
        return error(*problem)
    try:
        duration = int(data.get('duration_ms') or 0)
    except (TypeError, ValueError):
        duration = 0
    v = cast_vote(s, vid, key, reasoning, quick, input_str(data.get('guess', ''), 10), duration)
    nxt = next_case(s['id'], vid)
    return {
        'ok': True,
        'result': outcome(s, key, vote_counts_for(s['id'])),
        'guess': {'key': v['guess'], 'majority': v['majority'],
                  'correct': None if v['correct'] is None else bool(v['correct'])} if quick else None,
        'stats': quick_stats(vid),
        'profile': profile_out(vid, v['profile']),
        'career': v['career'],
        'next_case_id': nxt['id'] if nxt else None,
        'friends': [{'login': f['login'], 'display_name': f['display_name'], 'option': f['option_key']}
                    for f in social.friend_votes(int(account()['id']), s['id'])] if account() else None,
    }


@bp.get('/profile')
def profile():
    vid = voter()
    if not vid:
        return need_voter()
    p = judge_profile(vid)
    return {'ok': True, 'profile': profile_out(vid, p), 'career': career_out(vid, p)}


@bp.get('/daily')
def daily():
    vid = voter()
    d = career.daily(vid or '0' * 32)
    s = situation_find(d['id']) if d['id'] else None
    return {'ok': True, 'case': case_full(s, vid) if s else None, 'judged': d['judged'] if vid else None,
            'bonus_taken': d['today'] if vid else None, 'bonus_xp': d['bonus'], 'seconds_left': d['seconds_left']}


@bp.get('/world')
def world():
    vid = voter()
    if not vid:
        return need_voter()
    return {'ok': True, 'world': world_out(vid)}


@bp.post('/world/reset')
def world_reset():
    vid = voter()
    if not vid:
        return need_voter()
    career.reset_world(vid)
    return {'ok': True, 'world': world_out(vid)}


def hunts_out(vid):
    out = []
    for h in hunt.progress(vid):
        item = {k: h[k] for k in ('id', 'title', 'intro', 'total', 'found', 'seconds_left', 'prize', 'prize_taken')}
        item['ends_at'] = h['ends_at'].isoformat(sep=' ') if h['ends_at'] else None
        item['spots'] = [{k: x[k] for k in ('id', 'found', 'hint', 'page', 'gift', 'empty')} for x in h['spots']]
        out.append(item)
    return out


@bp.get('/hunt')
def hunt_state():
    vid = voter()
    if not vid:
        return need_voter()
    return {'ok': True, 'hunts': hunts_out(vid), 'spots': hunt.unity_spots(vid)}


@bp.post('/hunt/spots/<int:spot_id>/claim')
def hunt_claim(spot_id):
    vid = voter()
    if not vid:
        return need_voter()
    spot = hunt.spot_find(spot_id)
    if not spot or not spot['page'].startswith(hunt.UNITY):
        return error('Тайник не найден.', 404)  # spots on the website are found on the website
    try:
        res = hunt.claim(vid, spot_id, players.user_of_voter(vid) is not None)
    except hunt.HuntError as e:
        status = {'gone': 410, 'found': 409, 'empty': 409, 'account': 401, 'blocked': 403}.get(e.code, 400)
        return {'ok': False, 'code': e.code, 'error': e.message}, status
    return {'ok': True, 'gift': hunt.public_grant(res['grant']), 'prize': hunt.public_grant(res['prize']),
            'found': res['found'], 'total': res['total'], 'career': career_out(vid)}


@bp.get('/gifts')
def gifts():
    vid = voter()
    if not vid:
        return need_voter()
    return {'ok': True, 'gifts': [hunt.public_grant(r) for r in hunt.inventory(vid)], 'title': career.player(vid).get('title')}


def rating_rows(rows, limit=100):
    return [{k: r[k] for k in ('place', 'login', 'display_name', 'title', 'value', 'note', 'xp')}
            | {'rank': {k: r['rank'][k] for k in ('key', 'name', 'icon', 'level')}} for r in rows[:limit]]


def community_out(c):
    return {k: c[k] for k in ('slug', 'name', 'description', 'rules', 'access', 'icon', 'hue', 'members')} | {
        'owner': {'login': c['owner_login'], 'display_name': c['owner_name']} if 'owner_login' in c else None,
        'created_at': c['created_at'].isoformat(sep=' ')}


@bp.get('/ratings')
def ratings():
    kind = request.args.get('board', 'season')
    kind = kind if kind in SOCIAL['boards'] else 'season'
    ids = None
    slug = request.args.get('community', '')
    if slug:
        c = social.community_by_slug(slug)
        if not c:
            return error('Сообщество не найдено.', 404)
        ids = social.member_ids(c['id'])
    if request.args.get('scope') == 'friends':
        if not account():
            return need_account()
        ids = [int(account()['id'])] + social.friend_ids(int(account()['id']))
    rows = social.board(kind, ids)
    return {'ok': True, 'board': kind, 'season': social.season_name(), 'days_left': social.days_left(), 'total': len(rows),
            'rows': rating_rows(rows)}


@bp.get('/users/<login>')
def user_profile(login):
    user = social.user_by_login(login)
    if not user:
        return error('Игрок не найден.', 404)
    p = social.profile(user, None)
    out = {'login': user['login'], 'display_name': user['display_name'], 'visible': p['visible'], 'friends': p['friends']}
    if p['visible']:
        s = p['summary']
        style = (p['judge'] or {}).get('archetype')
        out |= {'bio': user['bio'], 'xp': s['xp'], 'title': s['title'], 'streak': s['streak'], 'best_streak': s['best_streak'],
                'verdicts': s['verdicts'], 'daily_done': s['daily_done'], 'season_place': p['place'],
                'rank': {k: s['rank'][k] for k in ('key', 'name', 'icon', 'level', 'progress')},
                'style': {'key': style, **JUDGE_ARCHETYPES[style]} if style else None,
                'achievements': [a['key'] for a in p['achievements']],
                'trophies': [{'kind': t['kind'], 'name': t['name'], 'icon': t['icon']} for t in p['trophies']],
                'communities': [{'slug': c['slug'], 'name': c['name'], 'role': c['role']} for c in p['communities']]}
    return {'ok': True, 'user': out}


@bp.get('/communities')
def communities():
    return {'ok': True, 'communities': [community_out(c) for c in social.communities_list()]}


@bp.get('/communities/<slug>')
def community(slug):
    c = social.community_by_slug(slug)
    if not c:
        return error('Сообщество не найдено.', 404)
    people = [{'login': p['login'], 'display_name': p['display_name'], 'role': p['role']}
              for p in social.members(c['id']) if p['status'] == 'active']
    return {'ok': True, 'community': community_out(c) | {'people': people},
            'rating': rating_rows(social.board('season', social.member_ids(c['id'])))}


# ---------- Story campaigns ----------

def campaign_out(c, vid, with_chapter=False):
    from .. import campaigns
    st = campaigns.state(vid, c) if vid else None
    out = {'key': c['key'], 'title': c['title'], 'teaser': c['teaser'], 'intro': c['intro'], 'icon': c['icon'],
           'category': c['category'], 'chapters': [campaigns.chapter_title(ch) for ch in c['chapters']]}
    if st:
        out['progress'] = {'started': bool(st['run']), 'run': int(st['run']['run']) if st['run'] else 0,
                           'chapter_index': st['index'], 'finished': st['finished'], 'meters': st['meters'],
                           'choices': [{'chapter': x['chapter'], 'option': x['option']} for x in st['choices']],
                           'ending': {k: st['ending'][k] for k in ('key', 'title', 'icon', 'tone', 'text')} if st['ending'] else None}
        if with_chapter and st['run'] and not st['finished']:
            s = campaigns.chapter_case(st['chapter'])
            out['chapter'] = {'index': st['index'], 'bridges': campaigns.bridges(c, st['index'], st['choices']),
                              'case': case_full(s, vid) | {'allows_own_decision': False}}
    return out


@bp.get('/campaigns')
def campaigns_list():
    from .. import campaigns
    vid = voter()
    return {'ok': True, 'campaigns': [campaign_out(c, vid) for c in campaigns.CAMPAIGNS if campaigns.available(c)]}


@bp.get('/campaigns/<key>')
def campaign_state(key):
    from .. import campaigns
    c = campaigns.get(key)
    if not c or not campaigns.available(c):
        return error('Кампания не найдена.', 404)
    return {'ok': True, 'campaign': campaign_out(c, voter(), True)}


@bp.post('/campaigns/<key>/<action>')
def campaign_act(key, action):
    from .. import campaigns
    vid = voter()
    if not vid:
        return need_voter()
    c = campaigns.get(key)
    if not c or not campaigns.available(c) or action not in ('start', 'choose'):
        return error('Кампания не найдена.', 404)
    if action == 'start':
        st = campaigns.state(vid, c)
        if st['run'] and not st['finished']:
            return error('Кампания уже идёт — сначала доиграйте её.', 409)
        campaigns.start(vid, c)
        return {'ok': True, 'campaign': campaign_out(c, vid, True)}
    d = body()
    before = campaigns.state(vid, c)
    st, problem = campaigns.choose(vid, c, input_str(d.get('option', ''), 10), int(d.get('duration_ms') or 0))
    if problem:
        return error(problem, 422)
    i = before['index']
    s = campaigns.chapter_case(c['chapters'][i])
    chosen = next(x for x in s['decisions'] if x['key'] == st['choices'][i]['option'])
    return {'ok': True, 'result': {'chapter_index': i, 'option': chosen['key'], 'immediate': chosen.get('immediate', ''),
                                   'longterm': chosen.get('longterm', ''), 'meters_delta': st['steps'][i]},
            'campaign': campaign_out(c, vid, True)}


# ---------- Sign-in from the game client ----------

def body():
    data = request.get_json(silent=True) if request.is_json else request.form
    return data if isinstance(data, dict) or hasattr(data, 'get') else {}


def session_out(user, token=None):
    vid = players.attach(int(user['id']), header_voter())
    out = {'ok': True, 'voter_id': vid, 'user': {'id': int(user['id']), 'login': user['login'],
                                                'display_name': user['display_name']}}
    if token:
        out['token'] = token
    return out


@bp.post('/auth/register')
def auth_register():
    from ..auth import registration_validate, user_create, user_find
    import pymysql
    d = body()
    login = input_str(d.get('login', ''), 40)
    name = input_str(d.get('display_name', ''), 80)
    password = str(d.get('password', ''))
    errors = registration_validate(login, name, password, password)
    if errors:
        return {'ok': False, 'error': next(iter(errors.values())), 'errors': errors}, 422
    try:
        uid = user_create(login, name, password)
    except pymysql.err.IntegrityError:
        return error('Такой логин уже занят.', 422)
    user = user_find(uid)
    return session_out(user, gameauth.issue(uid, input_str(d.get('device', ''), 60)))


@bp.post('/auth/login')
def auth_login():
    import time
    from ..auth import auth_attempt
    d = body()
    login = input_str(d.get('login', ''), 40)
    if gameauth.locked(login):
        return error('Слишком много неудачных попыток. Попробуйте через 15 минут.', 429)
    user = auth_attempt(login, str(d.get('password', ''))) if login else None
    if not user:
        gameauth.failed(login)
        time.sleep(0.3)
        return error('Неверный логин или пароль.', 401)
    return session_out(user, gameauth.issue(int(user['id']), input_str(d.get('device', ''), 60)))


@bp.post('/auth/logout')
def auth_logout():
    h = request.headers.get('Authorization', '')
    if h[:7].lower() != 'bearer ' or not gameauth.revoke(h[7:].strip()):
        return need_account()
    return {'ok': True}


@bp.get('/me')
def me():
    user = account()
    if not user:
        return need_account()
    out = session_out(user)
    uid = int(user['id'])
    out['user'] |= {'bio': user['bio'], 'visibility': user['visibility'], 'in_ratings': bool(user['in_ratings'])}
    out['career'] = career_out(out['voter_id'])
    out['communities'] = [{'slug': c['slug'], 'name': c['name'], 'role': c['role']} for c in social.user_communities(uid)]
    out['friend_requests'] = len(social.requests_in(uid))
    return out


@bp.post('/me/profile')
def me_profile():
    user = account()
    if not user:
        return need_account()
    d = body()
    social.save_profile(int(user['id']), input_str(d.get('bio', user['bio']), 280), d.get('visibility', user['visibility']),
                        bool(d.get('in_ratings', user['in_ratings'])))
    return {'ok': True}


def people_out(rows):
    return [{'login': r['login'], 'display_name': r['display_name']} for r in rows]


def card(a):
    return {'login': a['login'], 'display_name': a['display_name'], 'title': a['title'], 'xp': a['xp'], 'streak': a['streak'],
            'rank': {k: a['rank'][k] for k in ('key', 'name', 'icon', 'level')}}


@bp.get('/friends')
def friends():
    user = account()
    if not user:
        return need_account()
    uid = int(user['id'])
    return {'ok': True, 'friends': [card(a) for a in social.accounts(social.friend_ids(uid))],
            'incoming': people_out(social.requests_in(uid)), 'outgoing': people_out(social.requests_out(uid))}


@bp.post('/friends')
def friends_add():
    user = account()
    if not user:
        return need_account()
    other = social.user_by_login(input_str(body().get('login', ''), 40).lstrip('@'))
    if not other:
        return error('Игрок не найден.', 404)
    result = social.befriend(int(user['id']), int(other['id']))
    return {'ok': result != 'self', 'result': result}


@bp.post('/friends/<login>/<action>')
def friends_action(login, action):
    user = account()
    if not user:
        return need_account()
    other = social.user_by_login(login)
    if not other or action not in ('accept', 'decline', 'cancel', 'remove'):
        return error('Не найдено.', 404)
    fn = {'accept': social.accept, 'decline': social.decline, 'cancel': social.cancel, 'remove': social.unfriend}[action]
    return {'ok': bool(fn(int(user['id']), int(other['id'])))}


@bp.post('/communities/<slug>/join')
def community_join(slug):
    user = account()
    if not user:
        return need_account()
    c = social.community_by_slug(slug)
    if not c:
        return error('Сообщество не найдено.', 404)
    d = body()
    if c['rules'].strip() and not d.get('accept_rules'):
        return error('Чтобы вступить, примите правила сообщества (accept_rules: true).', 422)
    result = social.join(c, int(user['id']), str(d.get('code', '')))
    return {'ok': result != 'need_code', 'result': result}, (200 if result != 'need_code' else 403)


@bp.post('/communities/<slug>/leave')
def community_leave(slug):
    user = account()
    if not user:
        return need_account()
    c = social.community_by_slug(slug)
    if not c:
        return error('Сообщество не найдено.', 404)
    return {'ok': bool(social.leave(c, int(user['id'])))}


@bp.app_errorhandler(405)
def not_allowed(_e):
    if request.path.startswith('/api/'):
        return error('Метод не поддерживается.', 405)
    return 'Method Not Allowed', 405
