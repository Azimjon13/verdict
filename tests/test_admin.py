"""The team's control room: analytics, players, the case of the day; activity tracking behind the numbers."""
import re
import secrets
from datetime import timedelta

import pytest


@pytest.fixture
def team(new_browser):
    b = new_browser()
    b.login()
    return b


def visit(b, url='/'):
    b.get(url)
    b.get(url)  # the first view sets the cookie; activity counts from the second, like a real browser
    return b.cookie('verdict_vid')


def approved(db):
    return [r['id'] for r in db.rows("SELECT id FROM situations WHERE status = 'approved' ORDER BY id")]


def test_activity_is_counted_per_day(new_browser, db, app):
    from verdict.career import today
    b = new_browser()
    b.get('/')
    vid = b.cookie('verdict_vid')
    assert db.value('SELECT COUNT(*) FROM player_days WHERE voter = %s', (vid,)) == 0  # a hit without a cookie is not a visit
    b.get('/play')
    b.get('/judge')
    row = db.one('SELECT day, hits FROM player_days WHERE voter = %s', (vid,))
    assert row['day'] == today() and row['hits'] == 2
    b.get('/assets/css/style.css')
    assert db.value('SELECT hits FROM player_days WHERE voter = %s', (vid,)) == 2  # assets don't count
    me = {'X-Voter-Id': secrets.token_hex(16)}
    app.test_client().get('/api/v1/cases', headers=me)
    assert db.value('SELECT hits FROM player_days WHERE voter = %s', (me['X-Voter-Id'],)) == 1  # the game client counts too


def test_dashboard(team, new_browser, db, app):
    p = new_browser()
    visit(p)
    ids = approved(db)
    for sid in ids[:3]:
        p.vote(sid, 'A')
    team.get('/admin/')
    assert team.html.count('class="panel kpi') >= 6 and 'Активные игроки по дням' in team.html
    assert 'class="vz-col"' in team.html and 'data-tip="' in team.html and 'class="vz-table"' in team.html
    from verdict import analytics
    with app.test_request_context():
        k = analytics.kpis()
        today = db.value('SELECT COUNT(*) FROM votes WHERE created_at >= UTC_DATE()')
        assert k['verdicts_today'] == today and k['active_today'] >= 1 and k['players'] >= 1
        series = analytics.daily_series(30)
        assert len(series) == 30 and series[-1]['verdicts'] == today
        steps = analytics.funnel()
        assert steps[0]['label'] == 'Зашли на сайт' and steps[0]['value'] >= steps[1]['value'] >= 1
        assert sum(analytics.by_hour(30)) >= 3
        assert sum(r['value'] for r in analytics.by_rank()) == k['players']
        r = analytics.retention(30)
        assert set(r) == {'d1', 'd1_base', 'd7', 'd7_base'}


def test_retention_counts_finished_windows_only(app, db):
    """Only these players first came more than a day ago (everyone else in the test database came today)."""
    from verdict import analytics
    from verdict.career import today
    t = today()
    a, b, c = (secrets.token_hex(16) for _ in range(3))
    rows = [(a, t - timedelta(days=9)), (a, t - timedelta(days=8)),   # back the next day
            (b, t - timedelta(days=9)), (b, t - timedelta(days=4)),   # back within the week, not the next day
            (c, t)]                                                   # came today: too early to tell
    for voter, day in rows:
        db.rows('INSERT INTO player_days (voter, day, hits) VALUES (%s, %s, 1)', (voter, day))
    try:
        with app.test_request_context():
            r = analytics.retention(10)
        assert r == {'d1': 0.5, 'd1_base': 2, 'd7': 1.0, 'd7_base': 2}
    finally:
        db.rows('DELETE FROM player_days WHERE voter IN (%s, %s, %s)', (a, b, c))


def test_players_list_search_and_detail(team, new_browser, db):
    p = new_browser()
    vid = visit(p)
    sid = approved(db)[0]
    p.vote(sid, 'B')
    team.get('/admin/players')
    assert vid in team.html and 'Аноним' in team.html
    team.get('/admin/players?q=' + vid[:8])
    assert team.html.count('class="player-cell"') == 1
    author = new_browser()
    login = author.register('Судья Тест')
    visit(author)
    author.vote(approved(db)[1], 'A')
    team.get('/admin/players?q=' + login)
    assert 'Судья Тест' in team.html and '@' + login in team.html
    team.get('/admin/players?who=accounts')
    assert 'Судья Тест' in team.html
    team.get('/admin/players/%s' % vid)
    assert 'Последние вердикты' in team.html and db.value('SELECT title FROM situations WHERE id = %s', (sid,)) in team.html
    day = db.value('SELECT day FROM player_days WHERE voter = %s', (vid,)).strftime('%d.%m.%Y')
    assert 'с %s по %s' % (day, day) in team.html  # activity dates are plain dates
    assert team.get('/admin/players/' + 'f' * 32).status_code == 302
    assert team.get('/admin/players/not-a-player').status_code == 302


def test_reset_and_delete_a_player(team, new_browser, db):
    p = new_browser()
    vid = visit(p)
    p.vote(approved(db)[2], 'A')
    team.form('/admin/players/%s' % vid, {'action': 'reset_world'})
    assert db.value('SELECT world_since FROM players WHERE voter = %s', (vid,)) is not None
    team.form('/admin/players/%s' % vid, {'action': 'delete'})
    for table in ('votes', 'players', 'player_days'):
        assert db.value('SELECT COUNT(*) FROM %s WHERE voter = %%s' % table, (vid,)) == 0, table


def test_case_of_the_day_by_hand(team, db, app):
    from verdict import career
    ids = approved(db)
    with app.test_request_context():
        tomorrow = career.today() + timedelta(days=1)
        yesterday = career.today() - timedelta(days=1)
    team.form('/admin/game', {'day': tomorrow.isoformat(), 'situation_id': str(ids[5])})
    with app.test_request_context():
        assert career.daily_case_id(tomorrow) == ids[5]
    team.get('/admin/game')
    assert 'Дело дня на %s' % tomorrow.strftime('%d.%m') in team.html
    team.form('/admin/game', {'day': yesterday.isoformat(), 'situation_id': str(ids[6])})
    team.get('/admin/game')
    assert 'Выберите день (сегодня или позже)' in team.html
    assert re.search(r'name="day" value="%s"' % tomorrow.isoformat(), team.html)
