"""Draws the app icons (assets/img/icon-*.png, apple-touch-icon.png) from the logo, in headless Chrome: a canvas at
each exact size, saved through a small local server. Run it again after changing the logo.

    python scripts/make_icons.py
"""
import base64
import http.server
import json
import shutil
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tests' / 'e2e'))
OUT = ROOT / 'assets' / 'img'
# name: (size in px, logo share of the side — maskable icons keep the logo inside the safe circle)
ICONS = {'icon-192.png': (192, .68), 'icon-512.png': (512, .68), 'icon-maskable-512.png': (512, .5),
         'apple-touch-icon.png': (180, .62)}

PAGE = """<!doctype html><meta charset="utf-8"><body style="margin:0;background:#000">
<script>
const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" fill="none">
  <defs><linearGradient id="g" x1="4" y1="2" x2="28" y2="30" gradientUnits="userSpaceOnUse">
  <stop offset="0" stop-color="#2be4ff"/><stop offset="1" stop-color="#8b5cf6"/></linearGradient></defs>
  <path d="M16 2.5 27.7 9.25v13.5L16 29.5 4.3 22.75V9.25Z" fill="#070a1f" stroke="url(#g)" stroke-width="1.6"/>
  <path d="M10.5 10.5 16 21l5.5-10.5" stroke="#fff" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="16" cy="25" r="1.4" fill="#2be4ff"/></svg>`;
const icons = %s;
const img = new Image();
img.onload = async () => {
  for (const [name, [size, share]] of Object.entries(icons)) {
    const c = document.createElement('canvas');
    c.width = c.height = size;
    const x = c.getContext('2d');
    const bg = x.createRadialGradient(size / 2, size * .42, 0, size / 2, size / 2, size * .75);
    bg.addColorStop(0, '#1a1550'); bg.addColorStop(.55, '#0a0c26'); bg.addColorStop(1, '#03040a');
    x.fillStyle = bg; x.fillRect(0, 0, size, size);
    const s = size * share, o = (size - s) / 2;
    x.shadowColor = 'rgba(43, 228, 255, .55)'; x.shadowBlur = size * .08;
    x.drawImage(img, o, o, s, s);
    await fetch('/save?name=' + name, { method: 'POST', body: c.toDataURL('image/png') });
  }
  await fetch('/done', { method: 'POST' });
};
img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
</script>""" % json.dumps(ICONS)


def main():
    from run import chrome, find_chrome, remove_profile, stop  # the browser-test runner knows how to drive Chrome
    done = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            body = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            data = self.rfile.read(int(self.headers.get('Content-Length') or 0))
            if self.path.startswith('/save?name='):
                name = self.path.split('=', 1)[1]
                if name in ICONS:
                    (OUT / name).write_bytes(base64.b64decode(data.split(b',', 1)[1]))
                    print('%-24s %d bytes' % (name, (OUT / name).stat().st_size))
            elif self.path == '/done':
                done.set()
            self.send_response(204)
            self.end_headers()

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    binary = find_chrome()
    if not binary:
        sys.exit('Chrome not found (set CHROME).')
    profile = tempfile.mkdtemp(prefix='chrome-icons-')
    proc = chrome(binary, 'http://127.0.0.1:%d/' % server.server_port, profile)
    try:
        if not done.wait(30):
            sys.exit('Chrome did not draw the icons in 30 s.')
    finally:
        stop(proc)
        remove_profile(profile)
        server.shutdown()
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == '__main__':
    main()
