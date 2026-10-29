"""Local development server:  python run.py  →  http://127.0.0.1:8000

Settings come from environment variables (VERDICT_DB_HOST, VERDICT_DB_PORT, VERDICT_DB_NAME, VERDICT_DB_USER,
VERDICT_DB_PASSWORD, VERDICT_ADMIN_PASSWORD, VERDICT_SECRET_KEY) or config.json — see verdict/config.py.
"""
import os

from verdict import create_app

app = create_app()

if __name__ == '__main__':
    app.run(host=os.environ.get('VERDICT_HOST', '127.0.0.1'), port=int(os.environ.get('VERDICT_PORT', 8000)),
            debug=os.environ.get('VERDICT_DEBUG') == '1')
