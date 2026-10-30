"""All URLs in one place. Old PHP addresses (case.php?id=3 …) redirect to the new ones."""
from flask import abort, redirect, request, url_for

from .views import accounts, admin, api, api_v1, authoring, campaigns, pages, social, talk

ROUTES = [
    # rule                       endpoint       view                     methods
    ('/',                        'index',       pages.index,             ['GET']),
    ('/quick',                   'quick',       pages.quick,             ['GET']),
    ('/quick/<int:id>',          'quick_case',  pages.quick,             ['GET']),
    ('/play',                    'play',        pages.play,              ['GET']),
    ('/case/<int:id>',           'case',        pages.case,              ['GET']),
    ('/talk/<int:id>',           'talk',        talk.talk_page,          ['GET', 'POST']),
    ('/judge',                   'judge',       pages.judge_page,        ['GET']),
    ('/judge/title',             'judge_title', pages.judge_title,       ['POST']),
    ('/brief',                   'brief',       pages.brief,             ['GET']),
    ('/campaigns',               'campaigns',   campaigns.campaigns_page, ['GET']),
    ('/campaign/<key>',          'campaign',    campaigns.campaign_page, ['GET', 'POST']),
    ('/ratings',                 'ratings',     social.ratings,          ['GET']),
    ('/seasons',                 'seasons',     social.seasons_page,     ['GET']),
    ('/seasons/<key>',           'season',      social.season_page,      ['GET']),
    ('/notifications',           'notifications', social.notifications_page, ['GET']),
    ('/u/<login>',               'profile',     social.profile,          ['GET', 'POST']),
    ('/friends',                 'friends',     social.friends,          ['GET', 'POST']),
    ('/communities',             'communities', social.communities,      ['GET', 'POST']),
    ('/c/<slug>',                'community',   social.community,        ['GET', 'POST']),
    ('/report',                  'report',      social.report,           ['POST']),
    ('/create',                  'create',      authoring.create,        ['GET', 'POST']),
    ('/create/<int:id>',         'edit',        authoring.create,        ['GET', 'POST']),
    ('/library',                 'library',     authoring.library,       ['GET']),
    ('/view/<int:id>',           'view',        authoring.view,          ['GET']),
    ('/action',                  'action',      authoring.action,        ['GET', 'POST']),
    ('/login',                   'login',       accounts.login,          ['GET', 'POST']),
    ('/register',                'register',    accounts.register,       ['GET', 'POST']),
    ('/forgot',                  'forgot',      accounts.forgot,         ['GET', 'POST']),
    ('/reset/<token>',           'reset',       accounts.reset,          ['GET', 'POST']),
    ('/logout',                  'logout',      accounts.logout,         ['GET', 'POST']),
    ('/account',                 'account',     accounts.account,        ['GET', 'POST']),
    ('/users',                   'users',       accounts.users,          ['GET', 'POST']),
    # JSON for the site's own JavaScript
    ('/api/vote',                'api_vote',    api.vote,                ['GET', 'POST']),
    ('/api/world',               'api_world',   api.world_reset,         ['GET', 'POST']),
    ('/api/hunt',                'api_hunt',    api.hunt_claim,          ['POST']),
    ('/api/export',              'api_export',  api.export,              ['GET']),
    ('/health',                  'health',      api.health,              ['GET', 'HEAD']),
    ('/cron/<key>',              'cron',        api.cron,                ['GET', 'POST']),
    ('/telegram/hook',           'telegram_hook', api.telegram_hook,     ['POST']),
    ('/sw.js',                   'service_worker', pages.service_worker, ['GET']),
    ('/offline',                 'offline',     pages.offline,           ['GET']),
]

# PHP page → (endpoint, query parameter that becomes the <int:id> part, endpoint when that parameter is set)
LEGACY = {
    'index': ('index', None, None),
    'quick': ('quick', 'id', 'quick_case'),
    'play': ('play', None, None),
    'case': ('play', 'id', 'case'),
    'judge': ('judge', None, None),
    'brief': ('brief', None, None),
    'create': ('create', 'edit', 'edit'),
    'library': ('library', None, None),
    'view': ('library', 'id', 'view'),
    'action': ('action', None, None),
    'login': ('login', None, None),
    'register': ('register', None, None),
    'logout': ('logout', None, None),
    'account': ('account', None, None),
    'users': ('users', None, None),
    'api/vote': ('api_vote', None, None),
    'api/world': ('api_world', None, None),
    'api/export': ('api_export', None, None),
}


def legacy(name):
    """Bookmarks and shared links from the PHP site. POST keeps its method (307)."""
    if name not in LEGACY:
        abort(404)
    endpoint, param, with_param = LEGACY[name]
    args = request.args.to_dict()
    value = args.pop(param, None) if param else None
    if value is not None and value.isdigit() and int(value) > 0:
        target = url_for(with_param, id=int(value), **args)
    else:
        target = url_for(endpoint, **args)
    return redirect(target, 307 if request.method == 'POST' else 301)


def register(app):
    for rule, endpoint, view, methods in ROUTES:
        app.add_url_rule(rule, endpoint, view, methods=methods)
    app.add_url_rule('/<any(index, quick, play, case, judge, brief, create, library, view, action, login, register, '
                     'logout, account, users):name>.php', 'legacy', legacy, methods=['GET', 'POST'])
    app.add_url_rule('/api/<any(vote, world, export):name>.php', 'legacy_api',
                     lambda name: legacy('api/' + name), methods=['GET', 'POST'])
    app.register_blueprint(api_v1.bp, url_prefix='/api/v1')
    app.register_blueprint(admin.bp, url_prefix='/admin')
