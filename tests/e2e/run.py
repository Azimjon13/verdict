"""Browser tests: the real pages in headless Chrome, driven by the scripts in tests/e2e/scenarios/.

    python tests/e2e/run.py                  every scenario
    python tests/e2e/run.py hunt quick       some of them
    python tests/e2e/run.py --shots shots/   screenshots of the main pages at desktop and phone width
    python tests/e2e/run.py --serve          keep the test site open on http://127.0.0.1:8099 to look around

The site runs in this process on a fresh database: the server and credentials come from the same VERDICT_TEST_DB_*
variables as pytest, the database is VERDICT_E2E_DB_NAME (default verdict_e2e) and it is DROPPED and rebuilt. It is
filled with a running hunt, a hunt being prepared, a player with a judge profile and a month of made-up activity.

Each scenario gets its own Chrome profile (so a fresh anonymous player) and opens its start page with ?__script=<name>.
A small layer in front of the site then adds the scenario's script to every HTML page and offers helpers:
/__as?vid=..&to=.. (become a player), /__login?to=.. (sign in as the team), /__report (the script's results),
/__phone?src=..&w=390 (a page in a phone-wide frame: headless Chrome on Windows won't go below ~500 px).
A script keeps its state in sessionStorage across pages and posts PASS/FAIL lines when done.
Chrome is found automatically; set CHROME to use another Chromium-based browser.
"""
import argparse
import json
import logging
import os
import random
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from html import escape as html_escape
from pathlib import Path
from urllib.parse import parse_qs, quote

import pymysql
from werkzeug.http import parse_cookie
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from verdict import create_app  # noqa: E402

HERE = Path(__file__).resolve().parent
SCENARIOS_DIR = HERE / 'scenarios'
DB = {
    'host': os.environ.get('VERDICT_TEST_DB_HOST', '127.0.0.1'),
    'port': int(os.environ.get('VERDICT_TEST_DB_PORT', 3306)),
    'user': os.environ.get('VERDICT_TEST_DB_USER', 'root'),
    'password': os.environ.get('VERDICT_TEST_DB_PASSWORD', ''),
    'name': os.environ.get('VERDICT_E2E_DB_NAME', 'verdict_e2e'),
}
ADMIN = ('admin', 'verdict-admin')

# name: (start page, seconds it may take). {judge} and {place_spot} come from the seed.
SCENARIOS = {
    'play': ('/play', 30),
    'judge': ('/__as?vid={judge}&to=/judge', 30),
    'quick': ('/quick', 40),
    'juice': ('/quick', 40),
    'comic': ('/quick/5', 40),
    'vote': ('/case/3', 40),
    'create': ('/register', 50),
    'remove': ('/login?back=/create/1', 50),
    'hunt': ('/', 45),
    'place': ('/__login?to=%2F%3Fhunt_place%3D{place_spot}', 45),
    'phone': ('/__login?to=%2F__phone%3Fw%3D360', 90),
}
# name: (page, signed in as the team). Taken at 1280 and 390 px wide.
SHOTS = [
    ('home', '/', False), ('quick', '/quick', False), ('case', '/case/3', False), ('play', '/play', False),
    ('judge', '/__as?vid={judge}&to=/judge', False), ('ratings', '/ratings', False), ('campaigns', '/campaigns', False),
    ('admin', '/admin/', True), ('admin-players', '/admin/players', True), ('admin-hunt', '/admin/hunts/{hunt}', True),
]


# ---------- the site ----------

def build_site():
    conn = pymysql.connect(host=DB['host'], port=DB['port'], user=DB['user'], password=DB['password'])
    with conn.cursor() as cur:
        cur.execute('DROP DATABASE IF EXISTS `%s`' % DB['name'])
    conn.close()
    app = create_app({'db': DB, 'admin_password': ADMIN[1], 'secret_key': 'e2e', 'min_signup_seconds': 0})
    app.test_client().get('/')  # builds the database
    return app, seed(app)


def seed(app):
    """The running hunt «Неделя тайников» (made through the admin forms, as the team would), a hunt in preparation
    for the placement scenario, a player with enough verdicts for a judge profile, and 30 days of made-up players."""
    c = app.test_client()
    csrf = _sign_in(c, *ADMIN)
    db = pymysql.connect(host=DB['host'], port=DB['port'], user=DB['user'], password=DB['password'], database=DB['name'],
                         charset='utf8mb4', autocommit=True, cursorclass=pymysql.cursors.DictCursor)

    def q(sql, params=()):
        with db.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())

    def post(url, data):
        r = c.post(url, data={'_csrf': csrf, **data})
        assert r.status_code in (200, 302), (url, r.status_code)

    def place(spot_id, page, selector, x, y, scope='kind'):
        r = c.post('/admin/spots/%d/place' % spot_id, json={'page': page, 'path': '/', 'selector': selector, 'x': x, 'y': y,
                                                             'scope': scope}, headers={'X-CSRF-Token': csrf})
        assert r.get_json()['ok'], r.get_json()

    def add_spot(hunt_id, label, gift, hint, visibility):
        post('/admin/hunts/%d' % hunt_id, {'action': 'add_spot', 'label': label, 'page': 'index', 'path': '', 'gift_id': str(gift or ''),
                                           'hint': hint, 'icon': 'gem', 'size': '24', 'visibility': visibility,
                                           'max_finds': '0', 'active': '1'})
        return q('SELECT id FROM spots WHERE challenge_id = %s AND label = %s', (hunt_id, label))[0]['id']

    post('/admin/gifts', {'kind': 'xp', 'name': '+50 XP за зоркость', 'icon': 'zap', 'xp': '50',
                          'text': 'Опыт за внимательность: так держать!', 'active': '1'})
    post('/admin/gifts', {'kind': 'code', 'name': 'Код на футболку VERDICT', 'icon': 'ticket', 'xp': '10',
                          'text': 'Покажите код на стенде VERDICT и заберите футболку.',
                          'codes': 'TEE-7Q2K\nTEE-M4XA\nTEE-9PLD', 'active': '1'})
    post('/admin/gifts', {'kind': 'title', 'name': 'Искатель тайников', 'icon': 'crown', 'xp': '25',
                          'text': 'Титул за все тайники охоты.', 'active': '1'})
    gifts = {r['name']: r['id'] for r in q('SELECT id, name FROM gifts')}
    ends = (datetime.now(timezone.utc) + timedelta(days=3, hours=5)).strftime('%Y-%m-%dT%H:%M')
    post('/admin/hunts', {'title': 'Неделя тайников', 'status': 'active', 'starts_at': '', 'ends_at': ends, 'banner': '1',
                          'intro': 'На сайте спрятаны три тайника. Найдите все — получите титул «Искатель тайников».',
                          'prize_gift_id': str(gifts['Искатель тайников'])})
    hunt = q("SELECT id FROM challenges WHERE title = 'Неделя тайников'")[0]['id']
    place(add_spot(hunt, 'Под заголовком главной', gifts['+50 XP за зоркость'], 'Там, где игру называют по имени', 'visible'),
          'index', '.hero h1', 88, 85)
    place(add_spot(hunt, 'В архиве, у фильтров', gifts['Код на футболку VERDICT'], 'Архив дел: присмотритесь к фильтрам', 'subtle'),
          'play', '.filters', 97, 50)
    place(add_spot(hunt, 'У логотипа', None, 'Рядом с тем, что есть на каждой странице', 'subtle'),
          'index', '.site-header .brand', 104, 20, scope='site')

    post('/admin/hunts', {'title': 'Охота к празднику', 'status': 'draft', 'starts_at': '', 'ends_at': '', 'banner': '1',
                          'intro': 'Готовится.', 'prize_gift_id': ''})
    draft = q("SELECT id FROM challenges WHERE title = 'Охота к празднику'")[0]['id']
    place(add_spot(draft, 'Уже на месте', None, 'Под заголовком', 'subtle'), 'index', '.hero h1', 20, 60)
    place_spot = add_spot(draft, 'Новый тайник', None, 'У кнопки', 'subtle')

    cases = {r['id']: [d['key'] for d in json.loads(r['data'])['decisions']]
             for r in q("SELECT id, data FROM situations WHERE status = 'approved' ORDER BY id")}
    rnd = random.Random(7)
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)

    def vote(voter, sid, key, at, mode='quick'):
        q('INSERT IGNORE INTO votes (situation_id, option_key, reasoning, voter, mode, duration_ms, created_at, first_at)'
          ' VALUES (%s, %s, "", %s, %s, %s, %s, %s)', (sid, key, voter, mode, rnd.randint(8000, 160000), at, at))

    judge = secrets.token_hex(16)
    for i, sid in enumerate(list(cases)[:8]):  # case 1 among them: the «remove» scenario needs a decision with votes
        vote(judge, sid, cases[sid][i % len(cases[sid])], now - timedelta(days=2, minutes=i))
    q('INSERT IGNORE INTO player_days (voter, day, hits) VALUES (%s, %s, 5)', (judge, (now - timedelta(days=2)).date()))

    today = now.date()
    for _ in range(90):
        voter = secrets.token_hex(16)
        first = today - timedelta(days=rnd.randint(0, 29))
        days = {first} | {first + timedelta(days=rnd.randint(1, 9)) for _ in range(rnd.choice([0, 0, 1, 2, 4]))}
        for d in sorted(x for x in days if x <= today):
            q('INSERT IGNORE INTO player_days (voter, day, hits) VALUES (%s, %s, %s)', (voter, d, rnd.randint(1, 12)))
            for sid in rnd.sample(list(cases), rnd.randint(0, 4)):
                at = datetime.combine(d, datetime.min.time()) + timedelta(hours=rnd.choice([6, 8, 12, 13, 16, 17, 18, 19]),
                                                                         minutes=rnd.randint(0, 59))
                vote(voter, sid, rnd.choice(cases[sid]), min(at, now), rnd.choice(['quick', 'quick', 'full']))
    db.close()
    return {'hunt': hunt, 'draft_hunt': draft, 'place_spot': place_spot, 'judge': judge}


def _sign_in(client, login, password):
    html = client.get('/login').get_data(as_text=True)
    csrf = re.search(r'name="_csrf" value="([^"]+)"', html).group(1)
    r = client.post('/login', data={'_csrf': csrf, 'login': login, 'password': password, 'back': ''})
    assert r.status_code == 302, 'team sign-in failed'
    return re.search(r'data-csrf="([^"]+)"', client.get('/admin/').get_data(as_text=True)).group(1)


class Harness:
    """WSGI layer in front of the site: adds the scenario script to HTML pages, the test helpers, and collects reports."""

    def __init__(self, app, seed_data):
        self.app = app
        self.seed = seed_data
        self.reports = {}
        self.arrived = threading.Condition()

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        args = {k: v[0] for k, v in parse_qs(environ.get('QUERY_STRING', '')).items()}
        script = re.sub(r'\W', '', args.get('__script') or parse_cookie(environ).get('e2e_script', ''))
        extra = [('Set-Cookie', 'e2e_script=%s; Path=/' % script)] if '__script' in args else []

        if path == '/__e2e.js':
            file = SCENARIOS_DIR / ('%s.js' % script)
            body = ('window.__e2e = %s;\n' % json.dumps({'name': script, 'seed': self.seed})).encode()
            body += file.read_bytes() if script and file.is_file() else b''
            return self._send(start_response, '200 OK', body, 'application/javascript; charset=utf-8', extra)
        if path == '/__as':
            vid = re.sub(r'[^a-f0-9]', '', args.get('vid', ''))
            return self._redirect(start_response, args.get('to'), extra + [('Set-Cookie', 'verdict_vid=%s; Path=/; HttpOnly' % vid)])
        if path == '/__login':
            client = self.app.test_client()
            _sign_in(client, args.get('user', ADMIN[0]), args.get('pass', ADMIN[1]))
            cookies = [('Set-Cookie', '%s=%s; Path=/; HttpOnly' % (name, client.get_cookie(name).value))
                       for name in ('verdict_sid', 'verdict_vid') if client.get_cookie(name)]
            return self._redirect(start_response, args.get('to'), extra + cookies)
        if path == '/__phone':
            width = int(args.get('w', '390')) if args.get('w', '').isdigit() else 390
            src = args.get('src', 'about:blank')
            src = src if src.startswith('/') and not src.startswith('//') else 'about:blank'
            body = ('<!doctype html><html><head><meta charset="utf-8"><title>phone</title><style>html,body{margin:0;'
                    'background:#03050b;height:100%%}iframe{display:block;border:0;width:%dpx;height:100%%}</style></head>'
                    '<body><iframe id="phone" src="%s"></iframe><script src="/__e2e.js"></script></body></html>'
                    % (width, html_escape(src))).encode()
            return self._send(start_response, '200 OK', body, 'text/html; charset=utf-8', extra)
        if path == '/__report':
            size = int(environ.get('CONTENT_LENGTH') or 0)
            text = environ['wsgi.input'].read(size).decode('utf-8', 'replace') if size else ''
            with self.arrived:
                self.reports[script or 'unknown'] = text
                self.arrived.notify_all()
            return self._send(start_response, '204 No Content', b'', 'text/plain', [])

        captured = {}

        def remember(status, headers, exc_info=None):
            captured['status'], captured['headers'] = status, list(headers) + extra
            return lambda data: None

        result = self.app(environ, remember)
        ctype = next((v for k, v in captured['headers'] if k.lower() == 'content-type'), '')
        if not script or not ctype.startswith('text/html'):
            start_response(captured['status'], captured['headers'])
            return result
        try:
            body = b''.join(result)
        finally:
            if hasattr(result, 'close'):
                result.close()
        head, sep, tail = body.rpartition(b'</body>')
        if sep:
            body = head + b'<script src="/__e2e.js"></script></body>' + tail
        headers = [(k, v) for k, v in captured['headers'] if k.lower() != 'content-length']
        start_response(captured['status'], headers + [('Content-Length', str(len(body)))])
        return [body]

    def wait_report(self, name, seconds):
        deadline = time.monotonic() + seconds
        with self.arrived:
            while name not in self.reports and time.monotonic() < deadline:
                self.arrived.wait(max(0.0, deadline - time.monotonic()))
            return self.reports.get(name)

    @staticmethod
    def _send(start_response, status, body, ctype, headers):
        start_response(status, headers + [('Content-Type', ctype), ('Content-Length', str(len(body))), ('Cache-Control', 'no-store')])
        return [body]

    def _redirect(self, start_response, to, headers):
        to = to if to and to.startswith('/') and not to.startswith('//') else '/'
        return self._send(start_response, '302 Found', b'', 'text/plain', headers + [('Location', to)])


def serve(app, port):
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    server = make_server('127.0.0.1', port, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


# ---------- Chrome ----------

def find_chrome():
    if os.environ.get('CHROME'):
        return os.environ['CHROME']
    candidates = []
    if os.name == 'nt':
        for base in (os.environ.get('PROGRAMFILES'), os.environ.get('PROGRAMFILES(X86)'), os.environ.get('LOCALAPPDATA')):
            if base:
                candidates += [Path(base) / 'Google/Chrome/Application/chrome.exe', Path(base) / 'Microsoft/Edge/Application/msedge.exe']
    elif sys.platform == 'darwin':
        candidates.append(Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'))
    found = next((str(p) for p in candidates if p.is_file()), None)
    return found or next(filter(None, map(shutil.which, ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome'))), None)


def chrome(binary, url, profile, extra=(), log=None):
    args = [binary, '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--hide-scrollbars',
            '--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--user-data-dir=%s' % profile, *extra, url]
    if os.environ.get('CI') or (os.name != 'nt' and os.geteuid() == 0):  # CI runners and root can't use Chrome's sandbox
        args.insert(1, '--no-sandbox')
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=log or subprocess.DEVNULL, start_new_session=os.name != 'nt')


def stop(proc):
    """Ends the Chrome this run started, with its helper processes — and nothing else."""
    if proc.poll() is None:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    try:
        proc.wait(10)
    except subprocess.TimeoutExpired:
        pass


def remove_profile(path):
    for _ in range(10):  # Chrome lets go of its files a moment after it ends
        shutil.rmtree(path, ignore_errors=True)
        if not Path(path).exists():
            return
        time.sleep(0.3)


# ---------- the run ----------

def run_scenarios(names, harness, base, binary):
    total = failed = 0
    for name in names:
        start, seconds = SCENARIOS[name]
        url = base + start.format(**harness.seed)
        url += ('&' if '?' in url else '?') + '__script=' + name
        profile = tempfile.mkdtemp(prefix='chrome-e2e-%s-' % name)
        began = time.monotonic()
        with tempfile.TemporaryFile() as log:  # Chrome's own messages, shown when the script never reported
            proc = chrome(binary, url, profile, ['--window-size=1280,900'], log=log)
            try:
                report = harness.wait_report(name, seconds)
            finally:
                stop(proc)
                remove_profile(profile)
            log.seek(0)
            chrome_said = [x for x in log.read().decode('utf-8', 'replace').splitlines() if x.strip()][-6:]
        # one entry per check; the detail in [...] may span lines
        lines = [re.sub(r'\s+', ' ', e).strip() for e in re.split(r'\n(?=(?:PASS|FAIL|ERROR) )', report or '') if e.strip()]
        bad = [line for line in lines if not line.startswith('PASS ')]
        if report is None:
            bad = lines = ['NO REPORT within %d s: the script did not finish (open %s with --serve to see why)' % (seconds, start)]
            bad += ['chrome: ' + x for x in chrome_said]
        elif not lines:
            bad = lines = ['EMPTY REPORT']
        total += len(lines)
        failed += len(bad)
        print('== %s  (%.1f s, %s)' % (name, time.monotonic() - began, 'FAILED' if bad else '%d ok' % len(lines)))
        for line in lines if (bad or VERBOSE) else []:
            print('   ' + line)
        if bad and os.environ.get('GITHUB_ACTIONS'):  # an annotation on the run's page (readable without the log)
            text = '\n'.join(bad[:8]).replace('%', '%25').replace('\r', '').replace('\n', '%0A')
            print('::error title=Browser test «%s» failed::%s' % (name, text))
    print('\n%d scenarios, %d checks, %s' % (len(names), total, 'all passed' if not failed else '%d FAILED' % failed))
    return failed == 0


def take_shots(out, harness, base, binary):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name, page, team in SHOTS:
        page = page.format(**harness.seed)
        for width, height, tag in ((1280, 1400, 'desktop'), (500, 1600, 'phone')):
            shown = page if tag == 'desktop' else '/__phone?src=' + quote(page, safe='')
            if team:
                shown = '/__login?to=' + quote(shown, safe='')
            url = base + shown + ('&' if '?' in shown else '?') + '__script=shot'
            file = out / ('%s-%s.png' % (name, tag))
            profile = tempfile.mkdtemp(prefix='chrome-shot-')
            proc = chrome(binary, url, profile, ['--window-size=%d,%d' % (width, height), '--virtual-time-budget=6000',
                                                 '--screenshot=%s' % file])
            try:
                proc.wait(40)
            except subprocess.TimeoutExpired:
                pass
            stop(proc)
            remove_profile(profile)
            print('%-28s %s' % (file.name, '%d KB' % (file.stat().st_size // 1024) if file.is_file() else 'MISSING'))


VERBOSE = False


def main():
    global VERBOSE
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('names', nargs='*', help='scenarios to run (default: all): ' + ', '.join(SCENARIOS))
    parser.add_argument('--shots', metavar='DIR', help='take screenshots into DIR instead of running scenarios')
    parser.add_argument('--serve', action='store_true', help='only start the seeded test site and wait')
    parser.add_argument('--port', type=int, default=0, help='port for the test site (default: any free one; 8099 with --serve)')
    parser.add_argument('-v', '--verbose', action='store_true', help='print every check, not only failures')
    a = parser.parse_args()
    VERBOSE = a.verbose
    unknown = [n for n in a.names if n not in SCENARIOS]
    if unknown:
        parser.error('unknown scenario: %s' % ', '.join(unknown))
    binary = None if a.serve else find_chrome()
    if not a.serve and not binary:
        sys.exit('Chrome not found: install Chrome or Chromium, or set CHROME to its path.')

    print('Building the test site on %s:%s/%s ...' % (DB['host'], DB['port'], DB['name']), flush=True)
    app, seed_data = build_site()
    harness = Harness(app, seed_data)
    server = serve(harness, a.port or (8099 if a.serve else 0))
    base = 'http://127.0.0.1:%d' % server.server_port
    try:
        if a.serve:
            print('Test site on %s (team: %s / %s). Seed: %s. Ctrl+C to stop.' % (base, ADMIN[0], ADMIN[1], seed_data))
            print('Add ?__script=<name> to a page to run a scenario in your own browser.')
            while True:
                time.sleep(3600)
        if a.shots:
            take_shots(a.shots, harness, base, binary)
            return
        ok = run_scenarios(a.names or list(SCENARIOS), harness, base, binary)
        sys.exit(0 if ok else 1)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
