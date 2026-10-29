"""Text and HTML helpers shared by views, templates and the comic engine."""
import itertools
import math
import re
import zlib
from datetime import date, datetime

import regex
from markupsafe import Markup, escape

from .catalog import CATEGORIES, LEVELS
from .icons import ICONS


def esc(value):
    """HTML-escaped text as a plain str, for code that builds HTML by concatenation."""
    return str(escape('' if value is None else value))


def paragraphs(text):
    """Text with paragraphs: a blank line starts a paragraph, a single newline becomes <br>."""
    text = (text or '').strip()
    if not text:
        return Markup('')
    parts = re.split(r'(?:\r\n|\r|\n){2,}', text)
    return Markup(''.join('<p>' + _nl2br(p.strip()) + '</p>' for p in parts))


def _nl2br(text):
    return re.sub(r'\r\n|\r|\n', lambda m: '<br />' + m.group(0), esc(text))


def nl2br(text):
    return Markup(_nl2br(text))


# Python-side HTML builders work on plain str and wrap the result in Markup once:
# str + Markup would escape the str (Markup.__radd__), so they use icon_html(), not icon().

def icon_html(name, cls=''):
    body = ICONS.get(name, ICONS['circle'])
    classes = ('icon ' + cls).strip()
    return ('<svg class="' + esc(classes) + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"'
            ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' + body + '</svg>')


def icon(name, cls=''):
    return Markup(icon_html(name, cls))


def option_icon(name, hue=None):
    """Icon for an item of the neon dropdown: <option{{ option_icon('crown', 45) }}>."""
    return Markup(' data-icon="' + esc(icon_html(name)) + '"' + (' data-hue="%d"' % hue if hue is not None else ''))


_logo_ids = itertools.count(1)


def logo_svg(cls='logo'):
    gid = 'logo-grad-%d' % next(_logo_ids)
    return Markup(
        '<svg class="' + esc(cls) + '" viewBox="0 0 32 32" fill="none" aria-hidden="true">'
        '<defs><linearGradient id="' + gid + '" x1="4" y1="2" x2="28" y2="30" gradientUnits="userSpaceOnUse">'
        '<stop offset="0" stop-color="#2be4ff"/><stop offset="1" stop-color="#8b5cf6"/></linearGradient></defs>'
        '<path d="M16 2.5 27.7 9.25v13.5L16 29.5 4.3 22.75V9.25Z" stroke="url(#' + gid + ')" stroke-width="1.6"/>'
        '<path d="M10.5 10.5 16 21l5.5-10.5" stroke="#fff" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/>'
        '<circle cx="16" cy="25" r="1.4" fill="#2be4ff"/></svg>')


# ---------- Text ----------

_WORD = regex.compile(r"[\p{L}\p{N}]+(?:['’\-][\p{L}\p{N}]+)*")


def word_count(text):
    return len(_WORD.findall(text or ''))


def plural(n, one, few, many):
    n = abs(int(n)) % 100
    n1 = n % 10
    if 10 < n < 20:
        return many
    if 1 < n1 < 5:
        return few
    if n1 == 1:
        return one
    return many


def excerpt(text, length=160):
    text = re.sub(r'\s+', ' ', text or '').strip()
    if len(text) <= length:
        return text
    cut = text[:length]
    space = cut.rfind(' ')
    if space > length * 0.6:
        cut = cut[:space]
    return cut.rstrip(' ,.;:—-') + '…'


def format_duration(ms):
    """95000 → «1 мин 35 с», 42000 → «42 с»."""
    sec = int(round_half_up(ms / 1000))
    return '%d мин %d с' % (sec // 60, sec % 60) if sec >= 60 else '%d с' % sec


def format_left(seconds):
    """Time left: 200000 → «2 дн 7 ч», 7300 → «2 ч 1 мин», 300 → «5 мин»."""
    seconds = max(0, int(seconds or 0))
    d, h, m = seconds // 86400, seconds % 86400 // 3600, seconds % 3600 // 60
    if d:
        return '%d дн %d ч' % (d, h)
    if h:
        return '%d ч %d мин' % (h, m)
    return '%d мин' % max(1, m)


def format_datetime(value):
    """28.10.2026 14:05 (UTC, as stored)."""
    if not value:
        return ''
    if not isinstance(value, datetime):
        try:
            value = datetime.strptime(str(value)[:19], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return ''
    return value.strftime('%d.%m.%Y %H:%M')


def nice_ticks(top, count=3):
    """Axis ticks from 0 to a round number at or above top: 37 → [0, 20, 40], 0 → [0, 1]."""
    top = max(1, int(top or 0))
    step = 1
    while step * (count - 1) < top:
        for k in (2, 2.5, 2):
            if step * (count - 1) >= top:
                break
            step = int(step * k)
    return [step * i for i in range(count)]


def compact(n):
    """1284 → «1 284», 12900 → «12,9 тыс.», 4200000 → «4,2 млн»."""
    n = int(n or 0)
    if abs(n) >= 1000000:
        return ('%.1f' % (n / 1000000)).rstrip('0').rstrip('.').replace('.', ',') + ' млн'
    if abs(n) >= 10000:
        return ('%.1f' % (n / 1000)).rstrip('0').rstrip('.').replace('.', ',') + ' тыс.'
    return '{:,}'.format(n).replace(',', ' ')


def format_date(value):
    if not value:
        return ''
    if isinstance(value, date):  # a datetime is a date too
        return value.strftime('%d.%m.%Y')
    try:
        return datetime.strptime(str(value)[:19], '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')
    except ValueError:
        return ''


def case_number(case_id):
    return '№ %04d' % int(case_id)


def initials(name):
    name = re.sub(r'[«»"„“]', '', name or '').strip()
    parts = name.split()
    if not parts:
        return '?'
    out = parts[0][:1].upper()
    if len(parts) > 1:
        out += parts[1][:1].upper()
    return out


def name_hue(name):
    """Stable avatar hue for a name (same value as PHP crc32($name) % 360)."""
    return zlib.crc32((name or '').encode('utf-8')) % 360


def category_style(category):
    return '--h:%d' % CATEGORIES.get(category, {}).get('hue', 190)


def round_half_up(x):
    """PHP round(): halves go away from zero (Python's round() goes to even)."""
    return math.floor(x + 0.5) if x >= 0 else -math.floor(-x + 0.5)


def pct(part, total):
    return int(round_half_up(part / total * 100)) if total else 0


def fnum(x):
    """A number for SVG attributes, printed the way PHP prints floats (1.0 → 1, 0.8299999 → 0.83)."""
    return '%.14g' % x


# ---------- Game ----------

def controversy(counts, options):
    """Controversy index: normalised entropy of the vote split (0–100).
    0 — everyone chose the same, 100 — votes split evenly between all options."""
    total = sum(counts.values())
    if total < 2 or options < 2:
        return {'value': None, 'label': 'Мало данных', 'level': 'none'}
    h = 0.0
    for c in counts.values():
        if c > 0:
            p = c / total
            h -= p * math.log(p)
    value = int(round_half_up(min(1, h / math.log(options)) * 100))
    if value >= 70:
        return {'value': value, 'label': 'Жаркий спор', 'level': 'hot'}
    if value >= 50:
        return {'value': value, 'label': 'Разногласия', 'level': 'high'}
    if value >= 25:
        return {'value': value, 'label': 'Есть сомнения', 'level': 'mid'}
    return {'value': value, 'label': 'Единодушие', 'level': 'low'}


def case_controversy(s, counts):
    return controversy(counts, max(2, len(s['decisions'])))


def level_chip(level, cls='chip-sm'):
    """Badge for how far a situation is filled in (see LEVELS and repository.situation_level)."""
    if level < 1:
        return Markup('<span class="chip ' + cls + ' chip-level lvl-0" title="Ещё не готова даже идея">' + icon_html('edit') + 'Набросок</span>')
    lv = LEVELS[level]
    return Markup('<span class="chip %s chip-level lvl-%d" title="Уровень %d из 3: %s">' % (cls, level, level, esc(lv['desc']))
                  + icon_html(lv['icon']) + 'Ур. %d · %s</span>' % (level, esc(lv['name'])))


_STATUS_CONFIRM = {
    'approved': ('Добавить в игру', 'Ситуация «%s» появится в архиве дел, и игроки смогут выносить по ней вердикты.', 'В игру', 'success'),
    'rejected': ('Отклонить ситуацию', 'Ситуация «%s» будет отклонена и не попадёт в игру. Решение можно изменить позже.', 'Отклонить', 'danger'),
    'pending': ('Вернуть на отбор', 'Ситуация «%s» вернётся на отбор и пропадёт из архива дел, пока её снова не одобрят.', 'Вернуть', 'warn'),
}


def status_confirm_attrs(to, title):
    """data-attributes of the confirmation modal for a status change."""
    heading, message, ok, tone = _STATUS_CONFIRM.get(to, _STATUS_CONFIRM['pending'])
    return Markup(' data-confirm="%s" data-confirm-title="%s" data-confirm-ok="%s" data-confirm-tone="%s"'
                  % (esc(message % title), esc(heading), esc(ok), tone))


def signed(v, step=1):
    """+15 / −10 style number for effect chips."""
    v = int(v) * step
    return '+%d' % v if v > 0 else str(v)
