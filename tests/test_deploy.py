"""What matters on a real host: how MySQL is reached, and that no shared cache keeps a visitor's pages."""
import verdict.db as dbmod


def test_localhost_goes_through_the_socket_like_php(monkeypatch):
    monkeypatch.setattr(dbmod.os.path, 'exists', lambda p: p == '/var/lib/mysql/mysql.sock')
    assert dbmod.address({'host': 'localhost', 'port': 3306, 'socket': ''}) == {'unix_socket': '/var/lib/mysql/mysql.sock'}
    assert dbmod.address({'host': '127.0.0.1', 'port': 3306, 'socket': ''}) == {'host': '127.0.0.1', 'port': 3306}
    assert dbmod.address({'host': 'db.host', 'port': '3307', 'socket': '/srv/my.sock'}) == {'unix_socket': '/srv/my.sock'}
    monkeypatch.setattr(dbmod.os.path, 'exists', lambda p: False)
    assert dbmod.address({'host': 'localhost', 'port': 3306, 'socket': ''}) == {'host': 'localhost', 'port': 3306}


def test_pages_are_private_and_assets_cacheable(browser, app):
    assert browser.get('/').headers['Cache-Control'] == 'private, no-cache'
    assert browser.get('/judge').headers['Cache-Control'] == 'private, no-cache'
    static = browser.client.get('/assets/css/style.css').headers['Cache-Control']
    assert 'private' not in static and 'max-age=604800' in static
    assert app.test_client().get('/api/v1/cases').headers['Cache-Control'] == 'no-store'


def test_code_folders_are_closed_to_the_web():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    for folder in ('verdict', 'content', 'docs', 'database'):
        assert 'Require all denied' in (root / folder / '.htaccess').read_text(encoding='utf-8'), folder
    assert not (root / 'assets' / '.htaccess').exists()


def test_startup_failure_is_reported_on_the_page():
    """passenger_wsgi.py: when the app can't start, the page says why (and startup-error.txt has the details)."""
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    report = root / 'startup-error.txt'
    script = ("import passenger_wsgi as p\n"
              "out = []\n"
              "body = b''.join(p.application({}, lambda status, headers: out.append(status)))\n"
              "print(out[0]); print(body.decode())")
    env = dict(__import__('os').environ, VERDICT_SESSION_LIFETIME='not-a-number')
    try:
        r = subprocess.run([sys.executable, '-c', script], cwd=root, env=env, capture_output=True, text=True, timeout=60)
        assert r.stdout.startswith('500 Internal Server Error'), r.stdout + r.stderr
        assert "ValueError: invalid literal for int() with base 10: 'not-a-number'" in r.stdout
        assert 'Traceback' in report.read_text(encoding='utf-8')
        ok = subprocess.run([sys.executable, '-c', 'import passenger_wsgi as p; print(type(p.application).__name__)'],
                            cwd=root, capture_output=True, text=True, timeout=60)
        assert ok.stdout.strip() == 'Flask' and not report.exists()  # a good start removes the old report
    finally:
        if report.exists():
            report.unlink()
