"""The creator form: PHP-style field names (decisions[0][effects][trust]) and its repeating blocks."""
import re

from markupsafe import Markup

from .catalog import METRICS
from .helpers import esc, icon_html as icon, plural
from .repository import decision_has_consequences

_PART = re.compile(r'\[([^\]]*)\]')


def parse_nested(multidict):
    """Turns flat form keys like `participants[0][name]` and `checklist[]` into nested dicts and lists,
    in the order the browser sent them (like PHP's $_POST)."""
    out = {}
    for key, values in multidict.lists():
        head = key.split('[', 1)[0]
        parts = [head] + _PART.findall(key[len(head):]) if '[' in key else [key]
        for value in values:
            _put(out, parts, value)
    return out


def _put(node, parts, value):
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        if part == '':
            if not isinstance(node, list):
                return
            if last:
                node.append(value)
                return
            node.append({})
            node = node[-1]
            continue
        if not isinstance(node, dict):
            return
        if last:
            node[part] = value
            return
        nxt = parts[i + 1]
        if part not in node or not isinstance(node[part], (dict, list)):
            node[part] = [] if nxt == '' else {}
        node = node[part]


# ---------- Repeating blocks. i — field index (or '__i__' for the <template>), n — number in the list. ----------

def field_error(errors, key):
    if key not in errors:
        return Markup('')
    return Markup('<p class="field-error" role="alert">' + icon('alert') + esc(errors[key]) + '</p>')


def _rep_head(label, n, remove_label):
    return ('<div class="rep-head"><span class="rep-label">' + esc(label) + ' <b class="rep-num">' + (str(n) if n else '') + '</b></span>'
            '<button type="button" class="rep-remove" aria-label="' + esc(remove_label) + '" title="' + esc(remove_label) + '">'
            + icon('x') + '</button></div>')


def render_participant(i, p, n):
    v = lambda k: esc(p.get(k, ''))
    name = 'participants[%s]' % i
    return ('<div class="rep-item person-item">'
            + _rep_head('Участник', n, 'Удалить участника')
            + '<div class="grid grid-3">'
            '<label class="field"><span>Имя</span><input type="text" name="' + name + '[name]" value="' + v('name') + '" maxlength="80" placeholder="Например: Аран"></label>'
            '<label class="field"><span>Возраст</span><input type="text" name="' + name + '[age]" value="' + v('age') + '" maxlength="40" placeholder="41"></label>'
            '<label class="field"><span>Роль</span><input type="text" name="' + name + '[role]" value="' + v('role') + '" maxlength="120" placeholder="Механик водяных насосов"></label>'
            '</div>'
            '<label class="field"><span>Отношение к другим</span><input type="text" name="' + name + '[relations]" value="' + v('relations') + '" maxlength="300" placeholder="Отец Леи, в натянутых отношениях с главой охраны"></label>'
            '<label class="field"><span>Краткое описание</span><textarea name="' + name + '[description]" rows="2" maxlength="600" placeholder="Характер, мотивы, что важно знать игроку">' + v('description') + '</textarea></label>'
            '</div>')


def render_line(field, label, placeholder):
    def render(i, value, n):
        return ('<div class="rep-item line-item">'
                + _rep_head(label, n, 'Удалить')
                + '<textarea name="' + field + '[' + i + ']" rows="2" maxlength="1000" placeholder="' + esc(placeholder) + '" aria-label="' + esc(label) + '">'
                + esc(value if isinstance(value, str) else '') + '</textarea></div>')
    return render


def render_witness(i, w, n):
    v = lambda k: esc(w.get(k, ''))
    name = 'witnesses[%s]' % i
    return ('<div class="rep-item witness-item">'
            + _rep_head('Свидетель', n, 'Удалить свидетеля')
            + '<label class="field"><span>Имя</span><input type="text" name="' + name + '[name]" value="' + v('name') + '" maxlength="120" placeholder="Например: Агафья, травница"></label>'
            '<label class="field"><span>Что он утверждает</span><textarea name="' + name + '[claim]" rows="2" maxlength="1000" placeholder="Показания своими словами">' + v('claim') + '</textarea></label>'
            '<div class="grid grid-2">'
            '<label class="field"><span>Насколько ему можно доверять</span><textarea name="' + name + '[trust]" rows="2" maxlength="1000">' + v('trust') + '</textarea></label>'
            '<label class="field"><span>Есть ли личный интерес</span><textarea name="' + name + '[interest]" rows="2" maxlength="1000">' + v('interest') + '</textarea></label>'
            '</div></div>')


def render_decision(i, d, n):
    v = lambda k: esc(d.get(k, ''))
    name = 'decisions[%s]' % i
    letter = chr(64 + n) if n > 0 else ''
    is_open = ' open' if decision_has_consequences(d) or d.get('effects') else ''

    effects = ''
    for key, m in METRICS.items():
        val = int((d.get('effects') or {}).get(key, 0))
        effects += ('<label class="effect">'
                    '<span class="effect-name">' + icon(m['icon']) + esc(m['name']) + '</span>'
                    '<input type="range" min="-3" max="3" step="1" name="' + name + '[effects][' + key + ']" value="' + str(val) + '">'
                    '<output class="effect-out ' + ('up' if val > 0 else 'down' if val < 0 else '') + '">' + ('+%d' % val if val > 0 else str(val)) + '</output>'
                    '</label>')

    # How many players already chose this option (only when editing a case in play) — remove it with care.
    votes = int(d.get('votes', 0) or 0)
    votes_chip = ''
    if votes > 0:
        votes_chip = ('<span class="rep-votes" title="Столько игроков уже выбрали этот вариант. Голоса останутся за ним, даже если буква сменится.">'
                      + icon('gavel') + str(votes) + ' ' + plural(votes, 'голос', 'голоса', 'голосов') + '</span>')

    return ('<div class="rep-item decision-item"' + (' data-votes="%d"' % votes if votes > 0 else '') + '>'
            '<input type="hidden" name="' + name + '[uid]" value="' + v('uid') + '">'
            '<div class="rep-head"><span class="rep-letter">' + letter + '</span><span class="rep-label">Вариант решения</span>' + votes_chip
            + '<button type="button" class="rep-remove" aria-label="Удалить вариант" title="Удалить вариант">' + icon('x') + '</button></div>'
            '<label class="field"><span>Решение</span><input type="text" name="' + name + '[text]" value="' + v('text') + '" maxlength="300" placeholder="Например: Частично ответственен — понять мотив, но назначить отработку"></label>'
            '<label class="field" data-lvl="2"><span>Почему игрок может выбрать этот вариант</span><textarea name="' + name + '[why]" rows="2" maxlength="1000">' + v('why') + '</textarea></label>'
            '<details class="conseq" data-lvl="3"' + is_open + '><summary>' + icon('zap') + 'Последствия этого решения <small>раздел 8</small>' + icon('chevron-down', 'chev') + '</summary>'
            '<div class="grid grid-2">'
            '<label class="field"><span>Немедленное последствие</span><textarea name="' + name + '[immediate]" rows="2" maxlength="1000">' + v('immediate') + '</textarea></label>'
            '<label class="field"><span>Долгосрочное последствие</span><textarea name="' + name + '[longterm]" rows="2" maxlength="1000">' + v('longterm') + '</textarea></label>'
            '<label class="field"><span>Влияние на персонажей</span><textarea name="' + name + '[characters]" rows="2" maxlength="1000">' + v('characters') + '</textarea></label>'
            '<label class="field"><span>Влияние на общество / мир</span><textarea name="' + name + '[world]" rows="2" maxlength="1000">' + v('world') + '</textarea></label>'
            '</div>'
            '<div class="effects"><p class="effects-title">Влияние на показатели мира <small>от −3 до +3</small></p><div class="effects-grid">' + effects + '</div></div>'
            '</details></div>')


def render_repeater(key, items, render, add_label, min_rows, max_rows):
    """A repeater: the list of items, a <template> for new ones and the «add» button."""
    html = '<div class="repeater" data-repeater="%s" data-min="%d" data-max="%d" data-next="%d">' % (esc(key), min_rows, max_rows, len(items))
    html += '<div class="rep-list">'
    for n, item in enumerate(items):
        html += render(str(n), item, n + 1)
    html += '</div>'
    html += '<template>' + render('__i__', {} if render in (render_participant, render_witness, render_decision) else '', 0) + '</template>'
    html += '<button type="button" class="btn btn-sm btn-ghost rep-add">' + icon('plus') + esc(add_label) + '</button>'
    html += '</div>'
    return Markup(html)
