"""The installable app: manifest with real icons, the service worker at the root, and an offline page with nothing
personal in it."""
import json
import struct
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / 'assets'


def png_size(path):
    head = path.read_bytes()[:24]
    assert head[:8] == b'\x89PNG\r\n\x1a\n'
    return struct.unpack('>II', head[16:24])


def test_manifest_and_icons(browser):
    r = browser.client.get('/assets/manifest.webmanifest')
    assert r.status_code == 200 and r.headers['Content-Type'].startswith('application/manifest+json')
    m = json.loads(r.get_data(as_text=True))
    assert m['start_url'].startswith('/') and m['scope'] == '/' and m['display'] == 'standalone' and m['lang'] == 'ru'
    sizes = {}
    for icon in m['icons'] + [i for s in m['shortcuts'] for i in s['icons']]:
        file = ASSETS / icon['src'].removeprefix('/assets/')
        w, h = png_size(file)
        assert '%dx%d' % (w, h) == icon['sizes'], icon
        sizes.setdefault(icon.get('purpose', 'any'), set()).add(w)
    assert {192, 512} <= sizes['any'] and 512 in sizes['maskable']
    assert png_size(ASSETS / 'img' / 'apple-touch-icon.png') == (180, 180)
    browser.get('/')
    assert '<link rel="manifest" href="/assets/manifest.webmanifest' in browser.html and 'apple-touch-icon' in browser.html


def test_service_worker_and_offline_page(browser, new_browser):
    r = browser.client.get('/sw.js')
    js = r.get_data(as_text=True)
    assert r.status_code == 200 and r.headers['Content-Type'].startswith('application/javascript')
    assert r.headers['Cache-Control'] == 'no-cache'
    assert 'const VERSION = "' in js and "const OFFLINE = '/offline'" in js and "request.mode === 'navigate'" in js
    team = new_browser()
    team.login()
    page = team.client.get('/offline').get_data(as_text=True)
    assert 'Нет связи' in page and 'Команда VERDICT' not in page and 'user-chip' not in page
    assert 'https://' not in page and '<link' not in page  # works with nothing else loaded
