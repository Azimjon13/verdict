"""VERDICT — decision & judgment game. Flask application factory."""
import secrets

from flask import Flask, request
from markupsafe import Markup

from . import catalog, config, helpers
from .db import DatabaseUnavailable, close_db
from .sessions import DbSessionInterface

ASSETS = config.ROOT / 'assets'


def create_app(overrides=None):
    cfg = config.load(overrides)
    import mimetypes
    mimetypes.add_type('application/manifest+json', '.webmanifest')
    app = Flask(__name__, static_folder=str(ASSETS), static_url_path='/assets')
    app.config['VERDICT'] = cfg
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 7 * 24 * 3600  # asset URLs carry ?v=<mtime>
    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
    app.secret_key = cfg['secret_key'] or secrets.token_hex(32)
    app.json.ensure_ascii = False
    app.json.sort_keys = False
    app.session_interface = DbSessionInterface(cfg['session_lifetime'])
    app.teardown_appcontext(close_db)

    _template_globals(app)

    from . import routes
    routes.register(app)

    @app.before_request
    def close_seasons():
        """The first visit after a month ends closes its season (trophies, the final board)."""
        if request.endpoint == 'static':
            return
        from . import seasons
        try:
            seasons.close_due()
        except DatabaseUnavailable:
            pass
        except Exception:  # a failed close must not take the page down; the next process or month tries again
            app.logger.exception('closing the season failed')

    @app.after_request
    def headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'same-origin')
        if request.endpoint != 'static':
            # Pages carry the visitor's own session, CSRF token and progress: a shared cache in front of the site
            # (nginx / Engintron on cPanel) must not keep them and hand them to someone else.
            response.headers.setdefault('Cache-Control', 'private, no-cache')
        from .web import remember_voter
        if response.status_code < 500:
            try:
                from .players import track_request
                track_request(request.endpoint)
            except DatabaseUnavailable:
                pass
        return remember_voter(response)

    @app.errorhandler(404)
    def not_found(_e):
        if request.path.startswith('/api/'):
            return {'ok': False, 'error': 'Не найдено.'}, 404
        from .web import page
        return page('error.html', 404, title='Страница не найдена', active='', body_class='page-case', bg='calm')

    @app.errorhandler(DatabaseUnavailable)
    def db_down(e):
        return _db_fail(app, e)

    @app.errorhandler(500)
    def server_error(e):
        original = getattr(e, 'original_exception', None)
        if isinstance(original, DatabaseUnavailable):
            return _db_fail(app, original)
        if request.path.startswith('/api/'):
            return {'ok': False, 'error': 'Ошибка сервера. Попробуйте ещё раз.'}, 500
        return ('<!doctype html><meta charset="utf-8"><title>Ошибка — VERDICT</title>'
                '<p style="font:16px system-ui;padding:24px">Что-то пошло не так. Обновите страницу.</p>'), 500

    return app


def _template_globals(app):
    from . import auth, campaigns, career, comic, hunt, judge, notify, repository, talk, web
    from .forms import field_error

    def asset(path):
        file = ASSETS / path
        version = int(file.stat().st_mtime) if file.is_file() else 1
        from flask import url_for
        return url_for('static', filename=path, v=version)

    def csrf_field():
        return Markup('<input type="hidden" name="_csrf" value="%s">' % helpers.esc(web.csrf_token()))

    app.jinja_env.globals.update(
        # catalog
        CATEGORIES=catalog.CATEGORIES, SITUATION_TYPES=catalog.SITUATION_TYPES, METRICS=catalog.METRICS,
        METRIC_STEP=catalog.METRIC_STEP, WORLDS=catalog.WORLDS, CHECKLIST=catalog.CHECKLIST, LEVELS=catalog.LEVELS,
        IDEA_MIN_WORDS=catalog.IDEA_MIN_WORDS, MAX_DECISIONS=catalog.MAX_DECISIONS, STATUSES=catalog.STATUSES,
        ROLES=catalog.ROLES, ROADMAP=catalog.ROADMAP, JUDGE_ARCHETYPES=catalog.JUDGE_ARCHETYPES,
        JUDGE_MIN_VERDICTS=catalog.JUDGE_MIN_VERDICTS, PASSWORD_MIN=auth.PASSWORD_MIN,
        # html + text
        icon=helpers.icon, option_icon=helpers.option_icon, logo_svg=helpers.logo_svg, asset=asset,
        paragraphs=helpers.paragraphs, nl2br=helpers.nl2br, word_count=helpers.word_count, plural=helpers.plural,
        excerpt=helpers.excerpt, format_duration=helpers.format_duration, format_date=helpers.format_date,
        format_left=helpers.format_left, format_datetime=helpers.format_datetime, nice_ticks=helpers.nice_ticks,
        compact=helpers.compact,
        case_number=helpers.case_number, initials=helpers.initials, name_hue=helpers.name_hue,
        category_style=helpers.category_style, controversy=helpers.controversy, case_controversy=helpers.case_controversy,
        level_chip=helpers.level_chip, status_confirm_attrs=helpers.status_confirm_attrs, signed=helpers.signed,
        pct=helpers.pct, round_half_up=helpers.round_half_up, field_error=field_error,
        # request
        csrf_token=web.csrf_token, csrf_field=csrf_field, take_flashes=web.take_flashes,
        take_autosave_clear=web.take_autosave_clear,
        player_world=lambda: career.world(web.voter_id()), career_summary=lambda: career.summary(web.voter_id()),
        daily_info=lambda: career.daily(web.voter_id()), RANKS=catalog.RANKS, XP=catalog.XP,
        hunt_for_page=_hunt_for_page, hunt_tools=_hunt_tools, hunt_json=hunt.dumps, GIFT_KINDS=catalog.GIFT_KINDS,
        HUNT=catalog.HUNT, HUNT_PAGES=hunt.PAGES, HUNT_STATUSES=hunt.STATUSES, SOCIAL=catalog.SOCIAL,
        ACHIEVEMENTS=catalog.ACHIEVEMENTS, REPORT_REASONS=catalog.REPORT_REASONS,
        friend_votes_for=_friend_votes_for, campaign_of=campaigns.campaign_of_case,
        notifications_unread=lambda: notify.unread(auth.current_user_id()),
        talk_preview=lambda sid: talk.preview(sid, auth.current_user_id()),
        current_user=auth.current_user, is_admin=auth.is_admin, is_logged_in=auth.is_logged_in,
        owns_situation=auth.owns_situation, can_edit_situation=auth.can_edit_situation, can_see_hidden=auth.can_see_hidden,
        # game
        situation_level=repository.situation_level, situation_decision=repository.situation_decision,
        decision_has_consequences=repository.decision_has_consequences,
        decision_text=lambda s, key: (repository.situation_decision(s, key) or {}).get('text', 'Другое решение'),
        comic_cast=comic.cast_of, comic_panels=comic.panels_of, comic_avatar=comic.avatar_body, comic_scene=comic.scene,
        comic_camera=comic.camera, comic_highlight=lambda text, cast: Markup(comic.highlight(text, cast)),
        judge=judge,
    )
    @app.context_processor
    def year():
        from datetime import date
        return {'year': date.today().year}

    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True


def _friend_votes_for(situation_id):
    """How the signed-in player's friends judged this case (for the result screens)."""
    from . import auth, social
    uid = auth.current_user_id()
    return social.friend_votes(uid, situation_id) if uid else []


def _hunt_for_page():
    """Hidden spots and the hunt banner for the page being rendered (not on the team's pages)."""
    from . import hunt, web
    endpoint = request.endpoint or ''
    if endpoint.startswith('admin') or request.args.get('hunt_place') or request.args.get('hunt_preview'):
        return None
    return hunt.for_page(web.voter_id(), endpoint, request.path)


def _hunt_tools():
    """For the team: placement mode (?hunt_place=<spot>) or a preview of a hunt's spots (?hunt_preview=<hunt>)."""
    from flask import url_for
    from . import auth, hunt, web
    if not auth.is_admin():
        return None
    endpoint = request.endpoint or ''
    place = request.args.get('hunt_place', '')
    preview = request.args.get('hunt_preview', '')
    if place.isdigit():
        spot = hunt.spot_find(int(place))
        if not spot:
            return None
        return {'mode': 'place', 'page': endpoint, 'path': request.path, 'page_name': hunt.PAGES.get(endpoint, endpoint),
                'with_id': endpoint in hunt.PAGES_WITH_ID, 'allowed': endpoint in hunt.PAGES,
                'spot': {'id': int(spot['id']), 'label': spot['label'] or 'Тайник %d' % spot['id'],
                         'svg': helpers.icon_html(spot['icon']), 'size': int(spot['size'])},
                'save': url_for('admin.spot_place', spot_id=spot['id']), 'back': url_for('admin.spot_page', spot_id=spot['id']),
                'csrf': web.csrf_token(),
                'others': [x for x in hunt.preview_spots(spot['challenge_id'])
                           if x['id'] != spot['id'] and hunt.matches(x, endpoint, request.path)]}
    if preview.isdigit():
        c = hunt.challenge_find(int(preview))
        if not c:
            return None
        return {'mode': 'preview', 'title': c['title'], 'back': url_for('admin.hunt_page', challenge_id=c['id']),
                'others': [x for x in hunt.preview_spots(c['id']) if hunt.matches(x, endpoint, request.path)]}
    return None


def _db_fail(app, e):
    """A clear page instead of a crash when MySQL is unreachable."""
    c = app.config['VERDICT']['db']
    if request.path.startswith('/api/') or request.path == '/health':
        return {'ok': False, 'error': 'База данных недоступна.'}, 503
    where = helpers.esc('%s@%s:%s / %s' % (c['user'], c['host'], c['port'], c['name']))
    html = ('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>База данных недоступна — VERDICT</title><style>'
            'body{margin:0;min-height:100vh;display:grid;place-items:center;background:#03050b;color:#e8edff;font:16px/1.6 system-ui,sans-serif;padding:16px}'
            '.box{max-width:620px;border:1px solid rgba(255,77,109,.4);border-radius:16px;padding:28px;background:rgba(20,10,20,.6)}'
            'h1{font-size:20px;margin:0 0 12px;color:#ff8fa5}code{background:rgba(255,255,255,.06);padding:2px 6px;border-radius:4px;font-size:14px}'
            'li{margin:6px 0}small{color:#95a0c3}</style></head><body><div class="box">'
            '<h1>Не удалось подключиться к MySQL</h1>'
            '<p>Сайт пытался подключиться как <code>' + where + '</code>.</p><ol>'
            '<li>Убедитесь, что MySQL запущен.</li>'
            '<li>Проверьте хост, порт, логин и пароль: переменные окружения <code>VERDICT_DB_*</code> или файл <code>config.json</code>.</li>'
            '<li>Если у пользователя нет права создавать базы, создайте базу и импортируйте <code>database/schema.sql</code>.</li>'
            '</ol><p><small>Ошибка: ' + helpers.esc(str(e)) + '</small></p></div></body></html>')
    return html, 503

