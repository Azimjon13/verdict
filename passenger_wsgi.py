"""Entry point for cPanel «Setup Python App» (Phusion Passenger) and any WSGI server:
    application = verdict.create_app()

If the site can't start (a package missing, a setting wrong), the reason is shown on the page in one line and the
details are written to startup-error.txt next to this file, so it can be fixed without digging through server logs.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ERROR_FILE = os.path.join(HERE, 'startup-error.txt')
sys.path.insert(0, HERE)

try:
    from verdict import create_app

    application = create_app()
    if os.path.exists(ERROR_FILE):
        os.remove(ERROR_FILE)  # started fine: an old report would only mislead
except Exception as exc:  # noqa: BLE001 — anything that stops the start must be reported, not swallowed
    import traceback

    REASON = '%s: %s' % (type(exc).__name__, exc)
    try:
        with open(ERROR_FILE, 'w', encoding='utf-8') as f:
            f.write('Python %s\nApplication folder: %s\n\n%s' % (sys.version, HERE, traceback.format_exc()))
    except OSError:
        pass

    def application(environ, start_response):
        body = ('VERDICT could not start.\n\n%s\n\nPython %s. Details: startup-error.txt in the application folder.\n'
                % (REASON, sys.version.split()[0])).encode('utf-8')
        start_response('500 Internal Server Error', [('Content-Type', 'text/plain; charset=utf-8'),
                                                     ('Content-Length', str(len(body))), ('Cache-Control', 'no-store')])
        return [body]
