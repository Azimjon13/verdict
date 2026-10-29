"""Judge profile: what kind of judge you are, from your verdicts. Computed from the votes of the anonymous player
id (cookie), so it lives in this browser and needs no account.

The lean on a world meter is not «how much trust did your choice give» but «did your choice give more trust than
the case's other options». So the profile describes you, not the fact that in most cases almost any option raises
trust. Only cases whose options differ on that meter count, so rare meters (resources) weigh as much as common
ones (authority).
"""
from flask import g, session

from .catalog import JUDGE_ARCHETYPES, JUDGE_MIN_RELEVANT, JUDGE_MIN_VERDICTS, JUDGE_NEUTRAL, METRICS
from .db import query
from .repository import quick_stats, vote_counts

__all__ = ['JUDGE_ARCHETYPES', 'JUDGE_MIN_VERDICTS', 'judge_leans', 'judge_archetype', 'judge_profile',
           'judge_archetype_shares', 'judge_event']


def judge_leans(verdicts):
    """Leans per meter. verdicts — [{'chosen': effects of the chosen decision, 'options': [effects of each option]}].

    In every case whose options differ on the meter, the choice gets the rank
    r = (other options that give less − options that give more) / (options − 1) ∈ [−1, 1].
    The lean is the average rank. A random choice averages exactly 0 however the cases are built (a mean over the
    options can't do that: one outlier among the options shifted everyone one way).
    more/less — in how many cases the rank was above/below zero, relevant — how many cases counted."""
    out = {}
    for m in METRICS:
        more = less = relevant = 0
        total = 0.0
        for v in verdicts:
            vals = [int((fx or {}).get(m, 0)) for fx in v['options']]
            if len(vals) < 2 or max(vals) == min(vals):
                continue
            chosen = int((v['chosen'] or {}).get(m, 0))
            lower = sum(1 for x in vals if x < chosen)
            higher = sum(1 for x in vals if x > chosen)
            r = (lower - higher) / (len(vals) - 1)
            relevant += 1
            total += r
            if r > 0:
                more += 1
            elif r < 0:
                less += 1
        out[m] = {'more': more, 'less': less, 'relevant': relevant, 'lean': total / relevant if relevant else 0.0}
    return out


def judge_archetype(leans, neutral=JUDGE_NEUTRAL):
    """The style from the leans. The main axes are order (authority + stability) and trust: in cases they often go
    opposite ways (the strict option raises power and lowers trust), so the style is their combination, not the one
    «strongest» axis. Resources and reputation decide only when stronger than both. Meters with fewer than
    JUDGE_MIN_RELEVANT cases where the player had a choice don't count."""
    def lean(m):
        return float(leans[m]['lean']) if leans.get(m, {}).get('relevant', 0) >= JUDGE_MIN_RELEVANT else 0.0
    order = (lean('authority') + lean('stability')) / 2
    mercy = lean('trust')
    thrift = lean('resources')
    image = lean('reputation')

    core = max(abs(order), abs(mercy))
    side = max(abs(thrift), abs(image))
    if max(core, side) < neutral:
        return 'balanced'
    if side > core:
        if abs(thrift) >= abs(image):
            return 'pragmatic' if thrift > 0 else 'generous'
        return 'diplomat' if image > 0 else 'maverick'
    o = 1 if order >= neutral else (-1 if order <= -neutral else 0)
    t = 1 if mercy >= neutral else (-1 if mercy <= -neutral else 0)
    if o > 0 and t > 0:
        return 'wise'
    if o > 0:
        return 'order'     # order at any price, trust included
    if o < 0 and t > 0:
        return 'mercy' if abs(mercy) >= 0.75 * abs(order) else 'reformer'
    if o < 0 and t < 0:
        return 'fire'
    if o < 0:
        return 'reformer'
    if t > 0:
        return 'mercy'
    return 'stern'         # trust falls and order doesn't grow from it


def effects_map():
    """Decision effects of approved cases: {situation_id: {decision key: effects}}. Once per request."""
    if 'judge_effects' not in g:
        import json
        out = {}
        for r in query("SELECT id, data FROM situations WHERE status = 'approved'"):
            try:
                data = json.loads(r['data'] or 'null')
            except ValueError:
                data = None
            decisions = data.get('decisions') if isinstance(data, dict) and isinstance(data.get('decisions'), list) else []
            for d in decisions:
                if isinstance(d, dict) and 'key' in d:
                    out.setdefault(int(r['id']), {})[d['key']] = d['effects'] if isinstance(d.get('effects'), dict) else {}
        g.judge_effects = out
    return g.judge_effects


def judge_profile(voter):
    """The player's profile: style, leans per meter, agreement with the majority, speed, boldest calls."""
    rows = query("SELECT v.situation_id, v.option_key, v.duration_ms, s.title, s.category"
                 " FROM votes v JOIN situations s ON s.id = v.situation_id"
                 " WHERE v.voter = %s AND s.status = 'approved' ORDER BY v.created_at, v.id", (voter,))
    effects = effects_map()
    counts = vote_counts()

    verdicts = []
    own = 0
    durations = []
    with_majority = compared = 0
    boldest = None
    categories = {}

    for r in rows:
        sid = int(r['situation_id'])
        key = str(r['option_key'])
        categories[r['category']] = categories.get(r['category'], 0) + 1
        if r['duration_ms'] is not None:
            durations.append(int(r['duration_ms']))

        # How the others decided (without this player).
        others = dict(counts.get(sid, {}))
        if key in others:
            others[key] -= 1
        others = {k: n for k, n in others.items() if n}
        total = sum(others.values())
        if total > 0:
            compared += 1
            if others.get(key, 0) == max(others.values()):
                with_majority += 1
            share = others.get(key, 0) / total
            if total >= 3 and (boldest is None or share < boldest['share']):
                boldest = {'id': sid, 'title': str(r['title']), 'share': share, 'others': total}

        if key == 'other':
            own += 1
        elif key in effects.get(sid, {}):
            verdicts.append({'chosen': effects[sid][key], 'options': list(effects[sid].values())})

    leans = judge_leans(verdicts)
    decided = len(verdicts)
    durations.sort()
    top = sorted(categories.items(), key=lambda kv: -kv[1])  # stable: first-seen category wins a tie

    return {
        'verdicts': len(rows),
        'decided': decided,
        'own': own,
        'leans': leans,
        'archetype': judge_archetype(leans) if decided >= JUDGE_MIN_VERDICTS else None,
        'left': max(0, JUDGE_MIN_VERDICTS - decided),
        'with_majority': with_majority,
        'compared': compared,
        'median_ms': durations[len(durations) // 2] if len(durations) >= 3 else None,
        # A «bold» call — no more than a third of the other players agreed with you.
        'boldest': boldest if boldest is not None and boldest['share'] <= 0.34 else None,
        'top_category': top[0][0] if top and top[0][1] >= 3 else None,
        'quick': quick_stats(voter),
    }


def judge_archetype_shares():
    """How styles are spread among players with an open profile: {'players': N, 'shares': {style: share 0..1}}."""
    effects = effects_map()
    by_voter = {}
    for r in query("SELECT voter, situation_id, option_key FROM votes WHERE option_key <> 'other'"):
        sid = int(r['situation_id'])
        if r['option_key'] in effects.get(sid, {}):
            by_voter.setdefault(r['voter'], []).append({'chosen': effects[sid][r['option_key']], 'options': list(effects[sid].values())})
    tally = {}
    players = 0
    for verdicts in by_voter.values():
        if len(verdicts) >= JUDGE_MIN_VERDICTS:
            style = judge_archetype(judge_leans(verdicts))
            tally[style] = tally.get(style, 0) + 1
            players += 1
    return {'players': players, 'shares': {k: n / players for k, n in tally.items()}}


def judge_event(profile):
    """What to tell the player after a verdict: the profile opened, the style changed, or nothing.
    The last style shown is kept in the session."""
    prev = session.get('judge_archetype')
    now = profile['archetype']
    session['judge_archetype'] = now
    if now is None:
        return None
    # «Opened» — only on the verdict that opened the profile (not after an expired session).
    if profile['decided'] == JUDGE_MIN_VERDICTS and prev is None:
        return 'unlocked'
    return 'changed' if prev is not None and prev != now else None
