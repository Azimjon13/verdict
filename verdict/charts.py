"""Shapes for the dashboard's charts (templates/admin/_charts.html): bar heights, axis ticks, which bars get a
direct label. The charts are HTML and CSS, so text stays readable at any width; colors are the two slots validated
for the dark panel (s1 #0f9fbf, s2 #9b6cf6)."""
from .helpers import nice_ticks, plural


def _scale(values, count=3):
    top = max(values, default=0)
    ticks = nice_ticks(top, count)
    return top, ticks, ticks[-1] or 1


def columns(points, unit, every=5, from_start=False):
    """One series. points — [(label, value)]; unit — (one, few, many) for the tooltip. Axis labels every `every`
    bars, counted from the last one (today) or from the first. Direct labels only on the highest bar and the last
    one: the axis and the tooltip carry the rest."""
    values = [int(v) for _, v in points]
    top, ticks, scale = _scale(values)
    last = len(points) - 1
    bars = []
    for i, (label, v) in enumerate(points):
        v = int(v)
        shown = (i if from_start else last - i) % every == 0
        bars.append({'label': label, 'value': v, 'h': v / scale * 100, 'axis': label if shown else '',
                     'tip': '%d %s' % (v, plural(v, *unit)), 'direct': v > 0 and (i == last or v == top)})
    return {'bars': bars, 'ticks': [{'value': t, 'p': t / scale * 100} for t in ticks], 'empty': top == 0, 'n': len(points)}


def stacked(points, names, unit, every=5):
    """Two series stacked per day. points — [(label, a, b)] where a is the lower segment (slot 1), b the upper (slot 2)."""
    totals = [int(a) + int(b) for _, a, b in points]
    top, ticks, scale = _scale(totals)
    last = len(points) - 1
    bars = []
    for i, (label, a, b) in enumerate(points):
        a, b = int(a), int(b)
        segments = [s for s in ({'series': 's2', 'name': names[1], 'value': b, 'h': b / scale * 100},
                                {'series': 's1', 'name': names[0], 'value': a, 'h': a / scale * 100}) if s['value'] > 0]
        bars.append({'label': label, 'total': a + b, 'segments': segments, 'axis': label if (last - i) % every == 0 else '',
                     'tip': '%d %s · %s %d · %s %d' % (a + b, plural(a + b, *unit), names[0].lower(), a, names[1].lower(), b),
                     'direct': a + b > 0 and (i == last or a + b == top), 'h': (a + b) / scale * 100})
    return {'bars': bars, 'ticks': [{'value': t, 'p': t / scale * 100} for t in ticks], 'empty': top == 0,
            'n': len(points), 'names': names}


def hbars(rows, unit=None):
    """Horizontal bars: rows — [{'label', 'value', 'icon'?, 'note'?}], longest bar = the largest value."""
    top = max((int(r['value']) for r in rows), default=0)
    out = []
    for r in rows:
        v = int(r['value'])
        out.append({**r, 'value': v, 'f': v / top if top else 0,
                    'tip': '%d %s' % (v, plural(v, *unit)) if unit else str(v)})
    return {'rows': out, 'empty': top == 0}
