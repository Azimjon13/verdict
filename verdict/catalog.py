"""Game dictionaries from content/catalog.json — the same file a game client (Unity etc.) reads."""
import json

from .config import ROOT

CONTENT = ROOT / 'content'

_data = json.loads((CONTENT / 'catalog.json').read_text(encoding='utf-8'))

CATEGORIES = _data['categories']          # key -> {name, icon, hue, desc}
SITUATION_TYPES = _data['situation_types']  # private | witness | public -> {name, many, icon, target, desc}
METRICS = _data['metrics']                # reputation, authority, stability, resources, trust -> {name, icon}
METRIC_STEP = _data['metric_step']        # one effect point moves a world meter by this much
WORLDS = _data['worlds']                  # [{name, icon}]
WORLD_NAMES = [w['name'] for w in WORLDS]
CHECKLIST = _data['checklist']
LEVELS = {int(k): v for k, v in _data['levels'].items()}  # 1 Идея, 2 Дело, 3 Полное досье
IDEA_MIN_WORDS = _data['idea_min_words']
MAX_DECISIONS = _data['max_decisions']
STATUSES = _data['statuses']              # draft, pending, approved, rejected -> label
ROLES = _data['roles']                    # author, admin -> label
ROADMAP = _data['roadmap']

JUDGE_MIN_VERDICTS = _data['judge']['min_verdicts']
JUDGE_NEUTRAL = _data['judge']['neutral']
JUDGE_MIN_RELEVANT = _data['judge']['min_relevant']
JUDGE_ARCHETYPES = _data['judge']['archetypes']

# Judge career: XP per action, ranks by XP, world events at the edges of a meter, achievements.
XP = _data['xp']                          # verdict, guess (a right majority guess), daily (the case of the day)
RANKS = _data['ranks']                    # [{key, name, icon, xp}] by rising xp
WORLD_LEVELS = _data['world_levels']      # meter values that trigger an event: low, zero, high, peak
WORLD_EVENTS = _data['world_events']      # '<meter>_<level>' -> {name, text}
ACHIEVEMENTS = _data['achievements']      # key -> {name, desc, icon}

# Treasure hunts: what a gift can be, and how a hidden spot may look. The gifts and hunts themselves live in the database.
GIFT_KINDS = _data['gift_kinds']          # xp | badge | title | code | message -> {name, icon, desc}
HUNT = _data['hunt']                      # visibility (faint | subtle | visible -> {name, opacity}), icons, sizes

# Players together: who sees a profile, how a community is joined, roles, rating boards.
SOCIAL = _data['social']
REPORT_REASONS = _data['report_reasons']   # why a player reports a profile, a community or a case


def public():
    """Everything a game client needs to draw cases and profiles (no moderation data)."""
    return {k: v for k, v in _data.items() if k not in ('checklist', 'roles', 'roadmap')}
