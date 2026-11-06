"""For GitHub Actions: turns what failed into error annotations on the run. Annotations can be read without signing
in to GitHub (the run's logs can't), so a failure is visible to anyone looking at the commit.

    python scripts/ci_annotate.py pytest.xml     pytest's JUnit XML: one annotation per failing test, with its message
                                                 and the end of its traceback
    python scripts/ci_annotate.py e2e.log        a browser-test log: its FAIL lines
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_LINES = 30


def data(text):
    return text.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')


def prop(text):
    return data(text).replace(':', '%3A').replace(',', '%2C')


def error(title, message):
    print('::error title=%s::%s' % (prop(title)[:250], data(message)[:6000]))


def from_junit(path):
    count = 0
    for case in ET.parse(path).iter('testcase'):
        for kind in ('failure', 'error'):
            el = case.find(kind)
            if el is None:
                continue
            count += 1
            lines = ((el.get('message') or '') + '\n' + (el.text or '')).strip().splitlines()
            if len(lines) > MAX_LINES:  # the message, then the end of the traceback (where the assertion is)
                lines = lines[:6] + ['…'] + lines[-(MAX_LINES - 7):]
            error('%s %s::%s' % (kind, case.get('classname', ''), case.get('name', '')), '\n'.join(lines))
    return count


def from_log(path):
    fails = [line.strip() for line in Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
             if line.lstrip().startswith(('FAIL ', 'Traceback', 'Error'))]
    for line in fails[:20]:
        error('browser test', line)
    return len(fails)


def main(path):
    if not Path(path).is_file():
        error('ci_annotate', 'no report at %s: the step failed before writing it' % path)
        return
    count = from_junit(path) if path.endswith('.xml') else from_log(path)
    print('%d failure(s) annotated from %s' % (count, path))


if __name__ == '__main__':
    main(sys.argv[1])
