"""A player's progress follows their account: registering keeps it, signing in on another device brings it there
(and merges what that device did anonymously), signing out leaves the device to a new anonymous player."""
import re


def approved(db):
    return [r['id'] for r in db.rows("SELECT id FROM situations WHERE status = 'approved' ORDER BY id")]


def user_id(db, login):
    return db.value('SELECT id FROM users WHERE login = %s', (login,))


def test_register_keeps_the_progress(new_browser, db):
    b = new_browser()
    b.vote(approved(db)[0], 'A')
    vid = b.cookie('verdict_vid')
    login = b.register()
    assert b.cookie('verdict_vid') == vid
    assert db.value('SELECT user_id FROM players WHERE voter = %s', (vid,)) == user_id(db, login)
    b.get('/judge')
    assert 'Профиль сохранён в аккаунте' in b.html


def test_signing_in_elsewhere_brings_the_progress_and_merges(new_browser, db):
    ids = approved(db)
    home = new_browser()
    home.vote(ids[1], 'A')
    home.vote(ids[2], 'B')
    login = home.register()
    account = home.cookie('verdict_vid')

    phone = new_browser()
    phone.vote(ids[2], 'C')   # judged on both devices: the account's verdict stays
    phone.vote(ids[3], 'A')   # only on the phone: moves to the account
    anon = phone.cookie('verdict_vid')
    phone.login(login, 'password123')
    assert phone.cookie('verdict_vid') == account
    mine = {r['situation_id']: r['option_key'] for r in db.rows('SELECT situation_id, option_key FROM votes WHERE voter = %s', (account,))}
    assert mine[ids[1]] == 'A' and mine[ids[2]] == 'B' and mine[ids[3]] == 'A'
    assert db.value('SELECT COUNT(*) FROM votes WHERE voter = %s', (anon,)) == 0
    assert db.value('SELECT COUNT(*) FROM players WHERE voter = %s', (anon,)) == 0
    phone.get('/judge')
    assert re.search(r'<span class="jd-tile-label">Вердиктов</span><b>3</b>', phone.html)


def test_signing_out_starts_a_new_anonymous_player(new_browser, db):
    b = new_browser()
    b.vote(approved(db)[4], 'A')
    b.register()
    account = b.cookie('verdict_vid')
    b.form('/logout', {}, page='/account')
    fresh = b.cookie('verdict_vid')
    assert fresh and fresh != account
    b.get('/judge')
    assert '<b>0 XP</b>' in b.html
    b.login(db.value('SELECT u.login FROM users u JOIN players p ON p.user_id = u.id WHERE p.voter = %s', (account,)), 'password123')
    assert b.cookie('verdict_vid') == account


def test_two_accounts_on_one_device(new_browser, db):
    first = new_browser()
    login1 = first.register('Первый')
    second = new_browser()
    login2 = second.register('Второй')
    shared = new_browser()
    shared.login(login1, 'password123')
    p1 = shared.cookie('verdict_vid')
    shared.form('/logout', {}, page='/account')
    shared.vote(approved(db)[5], 'A')  # an anonymous verdict between the two sign-ins
    shared.login(login2, 'password123')
    p2 = shared.cookie('verdict_vid')
    assert p1 != p2
    assert db.value('SELECT user_id FROM players WHERE voter = %s', (p1,)) == user_id(db, login1)
    assert db.value('SELECT user_id FROM players WHERE voter = %s', (p2,)) == user_id(db, login2)
    assert db.value('SELECT COUNT(*) FROM votes WHERE voter = %s', (p2,)) == 1  # merged into the second account
