"""The game-client API (/api/v1): identity by header, no cookies, CORS, no spoilers before the verdict."""
import secrets


def player():
    return {'X-Voter-Id': secrets.token_hex(16)}


def test_index_and_catalog(app):
    c = app.test_client()
    r = c.get('/api/v1/')
    assert r.status_code == 200 and r.get_json()['version'] == 1
    assert r.headers['Access-Control-Allow-Origin'] == '*'
    cat = c.get('/api/v1/catalog').get_json()
    assert set(cat['categories']) >= {'moral', 'crime'} and len(cat['worlds']) == 8
    assert 'mercy' in cat['judge']['archetypes'] and 'checklist' not in cat


def test_preflight(app):
    r = app.test_client().options('/api/v1/cases/1/verdict', headers={'Origin': 'http://localhost:5000',
                                                                      'Access-Control-Request-Method': 'POST'})
    assert r.status_code == 204
    assert 'X-Voter-Id' in r.headers['Access-Control-Allow-Headers']


def test_cases_list_and_case(app, db):
    c = app.test_client()
    data = c.get('/api/v1/cases').get_json()
    assert data['count'] == db.value("SELECT COUNT(*) FROM situations WHERE status = 'approved'")
    assert all(x['my_verdict'] is None for x in data['cases'])
    case = c.get('/api/v1/cases/1').get_json()['case']
    assert case['title'] == 'Три ампулы'
    assert set(case['decisions'][0]) == {'key', 'text'}  # no consequences or effects before the verdict
    assert 'hidden' not in case and 'notes' not in case and 'checklist' not in case
    kinds = [p['kind'] for p in case['comic']['panels']]
    assert kinds[0] == 'world' and kinds[-1] == 'decide' and 'story' in kinds
    assert all('regex' not in x for x in case['comic']['cast'])
    pending = db.value("SELECT id FROM situations WHERE status = 'pending' LIMIT 1")
    assert c.get('/api/v1/cases/%d' % pending).status_code == 404
    assert c.get('/api/v1/cases/999999').status_code == 404


def test_verdict_flow(app, db):
    c = app.test_client()
    me = player()
    assert c.get('/api/v1/quick/next').status_code == 400
    assert c.post('/api/v1/cases/3/verdict', json={'option': 'A'}).status_code == 400
    assert c.post('/api/v1/cases/3/verdict', json={'option': 'Q'}, headers=me).status_code == 422

    nxt = c.get('/api/v1/quick/next', headers=me).get_json()
    assert nxt['case'] and nxt['remaining'] == db.value("SELECT COUNT(*) FROM situations WHERE status = 'approved'") and nxt['stats'] == {'score': 0, 'guesses': 0, 'streak': 0}
    sid = nxt['case']['id']
    key = nxt['case']['decisions'][0]['key']
    r = c.post('/api/v1/cases/%d/verdict' % sid, json={'option': key, 'guess': key, 'mode': 'quick', 'duration_ms': 9000},
               headers=me)
    body = r.get_json()
    assert r.status_code == 200 and body['ok']
    res = body['result']
    assert res['choice'] == key and res['total_votes'] >= 1 and len(res['decisions']) == len(nxt['case']['decisions'])
    assert 'conflict' in res['ambiguity'] and isinstance(res['effects'], dict)
    assert body['guess']['key'] == key and body['profile']['left'] == 4
    row = db.one('SELECT option_key, mode, duration_ms FROM votes WHERE situation_id = %s AND voter = %s', (sid, me['X-Voter-Id']))
    assert row == {'option_key': key, 'mode': 'quick', 'duration_ms': 9000}
    assert 'Set-Cookie' not in r.headers or 'verdict_vid' not in r.headers.get('Set-Cookie', '')

    again = c.get('/api/v1/cases/%d' % sid, headers=me).get_json()['case']
    assert again['my_vote']['option'] == key
    listed = c.get('/api/v1/cases', headers=me).get_json()['cases']
    assert next(x for x in listed if x['id'] == sid)['my_verdict'] == key
    assert c.get('/api/v1/quick/next?except=%d' % sid, headers=me).get_json()['case']['id'] != sid

    r = c.post('/api/v1/cases/%d/verdict' % sid, json={'option': 'other', 'reasoning': 'Собрать совет и решить вместе'}, headers=me)
    assert r.get_json()['result']['consequences'] is None

    for x in listed[:6]:
        c.post('/api/v1/cases/%d/verdict' % x['id'], json={'option': 'A'}, headers=me)
    prof = c.get('/api/v1/profile', headers=me).get_json()['profile']
    assert prof['archetype'] and prof['archetype']['key'] and prof['decided'] >= 5
    assert set(prof['leans']) == {'reputation', 'authority', 'stability', 'resources', 'trust'}


def test_form_encoded_verdict(app):
    r = app.test_client().post('/api/v1/cases/2/verdict', data={'option': 'B'}, headers=player())
    assert r.status_code == 200 and r.get_json()['result']['choice'] == 'B'
