"""Builds upload packages into dist/:

  dist/verdict-python/             the Python site, unpacked — upload its contents to the app root
  dist/verdict-python.zip          the same as one zip
  dist/verdict-python-no-js.zip    without assets/js/*.js, for hosts whose virus scanner flags the zip
                                   (then upload assets/js/ separately)
  dist/verdict-php.zip             the old PHP site, same rules as before (only with --php)
  dist/verdict-php-no-js.zip

Usage:  python scripts/build_dist.py [--php]
Files sit at the top level of each zip — extract them straight into the application folder.
"""
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / 'dist'

PYTHON_FILES = ['passenger_wsgi.py', 'run.py', 'requirements.txt', 'config.example.json', 'README.md', 'database/schema.sql',
                'docs/API.md', 'docs/ARCHITECTURE.md', 'docs/.htaccess', 'database/.htaccess']
PYTHON_DIRS = ['verdict', 'content', 'assets']
SKIP_PARTS = {'__pycache__', '.pytest_cache'}


def python_files():
    out = []
    for rel in PYTHON_FILES:
        if (ROOT / rel).is_file():
            out.append(rel)
    for d in PYTHON_DIRS:
        for p in sorted((ROOT / d).rglob('*')):
            if p.is_file() and not SKIP_PARTS & set(p.parts) and p.suffix not in ('.pyc', '.php'):
                out.append(p.relative_to(ROOT).as_posix())
    return out


def php_files():
    """The PHP site as uploaded before: no dev router, docs, source documents, archives or database/."""
    out = []
    skip_dirs = {'.venv', 'dist', 'tests', 'scripts', 'verdict', 'content', '.git', '__pycache__', '.pytest_cache', 'database'}
    for p in sorted(ROOT.rglob('*')):
        rel = p.relative_to(ROOT)
        if not p.is_file() or skip_dirs & set(rel.parts[:1]) or SKIP_PARTS & set(rel.parts):
            continue
        name = rel.as_posix()
        if name in ('router.php', 'README.md') or p.suffix.lower() in ('.docx', '.zip', '.py', '.pyc', '.md', '.txt', '.json'):
            continue
        if rel.parts[0] == 'assets' or p.suffix == '.php' or name in ('.htaccess',) or rel.parts[0] in ('includes', 'api'):
            out.append(name)
    return out


def write_zip(name, files, no_js=False):
    path = DIST / name
    path.unlink(missing_ok=True)
    n = 0
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            if no_js and rel.endswith('.js'):
                continue
            # Built on Windows every file would be stored as 0666 (writable by anyone on the server): store 0644.
            info = zipfile.ZipInfo.from_file(ROOT / rel, rel)
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, (ROOT / rel).read_bytes())
            n += 1
    print('%-30s %3d files  %7.1f KB' % (name, n, path.stat().st_size / 1024))


def main():
    DIST.mkdir(exist_ok=True)
    files = python_files()
    tree = DIST / 'verdict-python'
    shutil.rmtree(tree, ignore_errors=True)
    for rel in files:
        (tree / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, tree / rel)
    print('%-30s %3d files' % ('verdict-python/', len(files)))
    write_zip('verdict-python.zip', files)
    write_zip('verdict-python-no-js.zip', files, no_js=True)
    if '--php' in sys.argv:
        php = php_files()
        write_zip('verdict-php.zip', php)
        write_zip('verdict-php-no-js.zip', php, no_js=True)


if __name__ == '__main__':
    main()
