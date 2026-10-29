"""«Дело в кадрах»: a case shown as comic frames — world, story by paragraph, who is who, evidence, witnesses.

Everything is drawn from the situation data: a scene per world type, portraits from name/age/role, and «quoted»
lines become characters' speech bubbles. Authors don't write anything extra.
"""
import zlib

import regex

from .helpers import esc, fnum, name_hue

# Titles before a name: «Посол Тенгиз», «Доктор Нара» — the same person, not searched as a name.
TITLES = {'принц', 'принцесса', 'король', 'королева', 'царь', 'царица', 'царевич', 'царевна', 'хан', 'мэр', 'доктор',
          'капитан', 'командир', 'инспектор', 'аудитор', 'старпом', 'бригадир', 'начальник', 'мастер', 'купец', 'старейшина',
          'верховный', 'судья', 'юрист', 'директор', 'инженер', 'техник', 'медик', 'лекарь', 'жрец', 'жрица', 'прорицатель', 'нотариус',
          'управляющий', 'соседка', 'сосед', 'старик', 'старуха', 'граф', 'барон', 'раб', 'сторож', 'стражник', 'носильщик',
          'прокурор', 'защитник', 'боцман', 'пришелец', 'копия', 'глава', 'председатель', 'учитель', 'бывший', 'хозяин', 'хозяйка',
          'торговец', 'торговка', 'охранник', 'офицер', 'посол', 'сотник', 'лодочник', 'охотник', 'ткачиха', 'распорядитель',
          'ветеран', 'землекоп', 'меняла', 'почтальон', 'бард', 'генетик', 'пекарь', 'пекарка', 'служанка', 'юный', 'ныряльщик',
          'проводница', 'капеллан', 'биолог', 'знахарь', 'кухарка', 'архивариус', 'рыбак', 'кузнец', 'мельник', 'матрос', 'юнга',
          'пилот', 'арбитр', 'кади', 'шахтёр', 'смотритель', 'хранитель', 'хранительница', 'советник', 'канцлер', 'генерал',
          'солдат', 'монах', 'учёный', 'ученик', 'подмастерье', 'губернатор', 'комендант', 'наместник', 'старый', 'старая',
          'молодой', 'мастерица', 'лекарка', 'целитель', 'писарь', 'караванщик', 'проводник'}

# Kinship before a name: «Дочь Палси», «Мать братьев» — a DIFFERENT person, related to the one named.
KIN = {'мать', 'отец', 'сестра', 'брат', 'сын', 'дочь', 'жена', 'муж', 'вдова', 'вдовец', 'внук', 'внучка',
       'тётя', 'дядя', 'бабушка', 'дедушка', 'учитель', 'друг', 'подруга', 'невеста', 'жених'}

# Words at the start of a phrase that are skipped when looking for the speaker.
SKIP = {'сам', 'сама', 'сами', 'а', 'и', 'но', 'тогда', 'теперь', 'тут', 'вот', 'даже', 'только', 'уже', 'потом', 'затем', 'однако'}

# Lower-case subjects: «семья Ото требует», «сыновья отвечают» — it's not Ото speaking.
GROUPS = {'семья', 'люди', 'толпа', 'совет', 'город', 'сыновья', 'дочери', 'дети', 'жители', 'соседи', 'народ',
          'стража', 'компания', 'корпорация', 'гильдия', 'защитник', 'старейшины', 'моряки', 'колонисты', 'кто-то', 'одни', 'другие', 'все'}

# Female names ending in a consonant and male names in -а/-я, which would otherwise be guessed wrong.
FEMALE_NAMES = {'ингрид', 'мэйв', 'агнес', 'рут', 'эстер', 'ирэн', 'нелл', 'ило', 'кармен', 'нинон', 'айнур', 'мерит', 'хемет-нет'}
MALE_A_NAMES = {'илья', 'никита', 'фома', 'лука', 'кузьма', 'добрыня', 'неба', 'сила', 'миха'}

# Verbs that usually introduce a line: «— спросил Бранн», «— говорит она».
SAY = ('говорит|сказал|сказала|спросил|спросила|отвечает|ответил|ответила|добавляет|добавил|добавила|шепчет|шепнул|шепнула'
       '|кричит|крикнул|крикнула|повторяет|требует|просит')

_ENDING = regex.compile(r'[аяоеиыуюэьй]$')
_CAPWORD = regex.compile(r'\p{Lu}[\p{L}\-]+')
_SAY_TAG = regex.compile(r'^[,.?!]?\s*[—–]\s*((?:' + SAY + r')\s+[^.!?…,]{1,40})[.!?…,]?')
_INNER_TAG = regex.compile(r',?\s*[—–]\s*(?:' + SAY + r')\s+(\p{L}+)([,.]?)\s*[—–]\s*')
_FEMALE_WORDS = regex.compile(r'(?<!\p{L})(вдова|мать|сестра|жена|дочь|служанка|царевна|невеста|соседка|хозяйка|королева|царица|принцесса|кухарка|прачка|травница|старуха|девушка|покупательница|пассажирка|хранительница|сирота|торговка|ткачиха|жрица|пекарка|проводница|мастерица|лекарка|инженерка)(?!\p{L})')
_MALE_WORDS = regex.compile(r'(?<!\p{L})(отец|муж|сын|брат|старик|царь|король|принц|хан|юноша|мальчик|жених|вдовец|дед)(?!\p{L})')
_ROYAL = regex.compile(r'(?<!\p{L})(царь|царица|король|королева|хан|ханша|царевна|царевич|принц|принцесса|правитель|правительница|наместник)(?!\p{L})')
_SCHOLAR = regex.compile(r'(?<!\p{L})(доктор|врач|медик|инженер|учён|нотариус|учитель|аудитор|архивариус|инспектор|юрист|биолог|арбитр)')
_GUARD = regex.compile(r'(?<!\p{L})(капитан|стражник|стража|охран|носильщик|матрос|юнга|боцман|солдат|пилот|старпом|офицер)')
_PARAS = regex.compile(r'(?:\r\n|\r|\n){2,}')


def stem(word):
    """Word stem for finding declined forms: «Ирма» → «Ирм» (finds «Ирмы», «Ирму»)."""
    if len(word) >= 4 and _ENDING.search(word.lower()):
        return word[:-1]
    return word


def name_words(name):
    """Words of a name without titles and kinship: «Начальник спасателей Ирвен» → [Ирвен], «Дочь Палси» → [Палси]."""
    found = _CAPWORD.findall(regex.sub(r',.*$', '', name))
    return [w for w in found if w.lower() not in TITLES and w.lower() not in KIN]


def words_regex(words):
    """A regex that finds the words of a name in any grammatical case."""
    parts = [regex.escape(w) + '(?:а|у|ом|е)?' if len(w) < 3 else regex.escape(stem(w)) + r'\p{L}{0,3}' for w in words]
    return regex.compile(r'(?<![\p{L}])(?:' + '|'.join(parts) + r')(?![\p{L}])') if parts else None


def age_of(p):
    m = regex.search(r'\d+', str(p.get('age') or ''))
    return int(m.group(0)) if m else 35


def is_female(p):
    role = str(p.get('role') or '').lower()
    name = str(p.get('name') or '')
    if 'first' in p:
        first = str(p['first']).lower()
    else:
        words = name_words(name)
        first = words[0].lower() if words else ''
    if first and first in FEMALE_NAMES:
        return True
    both = role + ' ' + name.lower()
    if _FEMALE_WORDS.search(both):
        return True
    if _MALE_WORDS.search(both):
        return False
    # «Умершая», «Выжившая», «обвиняемая» — feminine (feminine genitive ends in -ой, not -ая).
    if regex.search(r'\p{L}{3,}(ая|яя)(?!\p{L})', role):
        return True
    # Then the name decides: adjectives in job titles («Капитан городской стражи») don't tell the gender.
    if not first:
        return False
    return bool(regex.search(r'[ая]$', first)) and first not in MALE_A_NAMES


def avatar_body(p):
    """A comic-style portrait, deterministic: the same person looks the same everywhere.
    Returns the inside of a <symbol> (viewBox 0 0 120 140)."""
    name = str(p.get('name') or '?')
    role = str(p.get('role') or '').lower()
    h = zlib.crc32(name.encode('utf-8'))
    age = age_of(p)
    female = is_female(p)
    hue = name_hue(name)
    kid = age < 16
    old = age >= 60

    skin = ['#f2c9a8', '#e3b08a', '#c98d66', '#9a6442'][h % 4]
    hair = '#e8e9ef' if age >= 70 else ('#b8bcc8' if old else ['#1f1b22', '#3d2b20', '#5b3a22', '#8b5a2b', '#c4934c', '#2a2d3a'][(h >> 3) % 6])
    cloth = 'hsl(%d 55%% 40%%)' % hue
    cloth_dark = 'hsl(%d 55%% 28%%)' % hue
    o = 'stroke="#0a0e1c" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"'
    y = 66 if kid else 60
    n = lambda v: fnum(v)

    svg = ''
    # Long hair behind.
    long_hair = female and (h >> 5) % 3 != 0
    if long_hair:
        svg += ('<path d="M27 %d C24 %d 44 %d 60 %d C78 %d 97 %d 93 %d L99 112 C86 120 34 120 21 112 Z" fill="%s" %s/>'
                % (y, y - 36, y - 44, y - 44, y - 44, y - 36, y, hair, o))
    # Shoulders and clothes.
    svg += '<path d="M8 140 C12 104 34 93 60 93 C86 93 108 104 112 140 Z" fill="' + cloth + '" ' + o + '/>'
    svg += '<path d="M44 96 L60 116 L76 96" fill="none" stroke="' + cloth_dark + '" stroke-width="5" stroke-linecap="round"/>'
    svg += '<rect x="51" y="%d" width="18" height="16" fill="%s" %s/>' % (y + 22, skin, o)
    # Head.
    svg += '<ellipse cx="60" cy="%d" rx="%d" ry="%d" fill="%s" %s/>' % (y, 29 if kid else 28, 30 if kid else 33, skin, o)
    # Ears.
    svg += ('<ellipse cx="32" cy="%d" rx="5" ry="8" fill="%s" %s/><ellipse cx="88" cy="%d" rx="5" ry="8" fill="%s" %s/>'
            % (y + 4, skin, o, y + 4, skin, o))
    # Eyes.
    eye_r = 4.6 if kid else 3.6
    for x in (49, 71):
        svg += ('<ellipse cx="%d" cy="%d" rx="%s" ry="%s" fill="#141826"/><circle cx="%s" cy="%s" r="1.3" fill="#fff"/>'
                % (x, y + 2, n(eye_r), n(eye_r + 0.8), n(x + 1.3), n(y + 0.5)))
    # Brows: heavier for the old.
    bw = n(3.6 if old else 3)
    brow = '#8a8d99' if old else '#1b1720'
    svg += ('<path d="M42 %d Q49 %d 55 %d" fill="none" stroke="%s" stroke-width="%s" stroke-linecap="round"/>'
            '<path d="M65 %d Q71 %d 78 %d" fill="none" stroke="%s" stroke-width="%s" stroke-linecap="round"/>'
            % (y - 8, y - 12, y - 8, brow, bw, y - 8, y - 12, y - 8, brow, bw))
    # Nose and mouth.
    svg += '<path d="M60 %d Q57 %d 61 %d" fill="none" stroke="#0a0e1c" stroke-width="2.2" stroke-linecap="round"/>' % (y + 6, y + 13, y + 14)
    svg += '<path d="M52 %d Q60 %d 68 %d" fill="none" stroke="#0a0e1c" stroke-width="2.6" stroke-linecap="round"/>' % (y + 21, y + 24, y + 21)
    if old:
        svg += ('<path d="M38 %d l5 3 M82 %d l-5 3 M50 %d q-3 5 0 9 M70 %d q3 5 0 9" fill="none" stroke="#0a0e1c" stroke-opacity=".35" stroke-width="1.8" stroke-linecap="round"/>'
                % (y + 6, y + 6, y + 16, y + 16))
    # A beard for some adult men.
    if not female and not kid and age >= 28 and (h >> 7) % 3 == 0:
        svg += ('<path d="M34 %d C36 %d 84 %d 86 %d C80 %d 70 %d 60 %d C50 %d 40 %d 34 %d Z" fill="%s" %s/>'
                '<path d="M53 %d Q60 %d 67 %d" fill="none" stroke="#0a0e1c" stroke-width="2.4" stroke-linecap="round"/>'
                % (y + 6, y + 36, y + 36, y + 6, y + 22, y + 18, y + 19, y + 18, y + 22, y + 6, hair, o, y + 23, y + 26, y + 23))
    # Hair in front.
    style = (h >> 9) % 3
    if old and not female and style == 0:
        svg += ('<path d="M32 %d C30 %d 38 %d 42 %d M88 %d C90 %d 82 %d 78 %d" fill="none" stroke="%s" stroke-width="7" stroke-linecap="round"/>'
                % (y - 2, y - 18, y - 22, y - 20, y - 2, y - 18, y - 22, y - 20, hair))
    elif female:
        svg += ('<path d="M31 %d C30 %d 52 %d 64 %d C80 %d 92 %d 89 %d C80 %d 66 %d 52 %d C44 %d 36 %d 31 %d Z" fill="%s" %s/>'
                % (y - 2, y - 34, y - 40, y - 36, y - 34, y - 22, y - 2, y - 18, y - 22, y - 16, y - 12, y - 8, y - 2, hair, o))
        if not long_hair:  # a bun
            svg += '<circle cx="60" cy="%d" r="11" fill="%s" %s/>' % (y - 40, hair, o)
    elif style == 1:
        svg += ('<path d="M31 %d C28 %d 48 %d 62 %d C80 %d 93 %d 89 %d C86 %d 74 %d 64 %d L58 %d L54 %d C44 %d 35 %d 31 %d Z" fill="%s" %s/>'
                % (y - 4, y - 34, y - 40, y - 38, y - 37, y - 26, y - 4, y - 16, y - 22, y - 20, y - 12, y - 20, y - 20, y - 14, y - 4, hair, o))
    else:
        svg += ('<path d="M30 %d C27 %d 46 %d 60 %d C76 %d 94 %d 90 %d C84 %d 74 %d 60 %d C46 %d 36 %d 30 %d Z" fill="%s" %s/>'
                % (y - 2, y - 36, y - 42, y - 42, y - 42, y - 34, y - 2, y - 16, y - 24, y - 24, y - 24, y - 16, y - 2, hair, o))
    # Role attributes.
    if _ROYAL.search(role + ' ' + name.lower()):
        c = y - 44
        svg += ('<path d="M40 %d L42 %d L51 %d L60 %d L69 %d L78 %d L80 %d Z" fill="#ffc94a" %s/><circle cx="60" cy="%d" r="2.6" fill="#ff4d6d"/>'
                % (c + 14, c, c + 8, c - 4, c + 8, c, c + 14, o, c + 7))
    elif _SCHOLAR.search(role + ' ' + name.lower()):
        svg += ('<g fill="rgba(170,230,255,.25)" stroke="#0a0e1c" stroke-width="2.6"><circle cx="49" cy="%d" r="9"/><circle cx="71" cy="%d" r="9"/></g>'
                '<path d="M58 %d h4" stroke="#0a0e1c" stroke-width="2.6"/>' % (y + 2, y + 2, y + 1))
    elif _GUARD.search(role):
        c = y - 30
        svg += ('<path d="M30 %d C32 %d 88 %d 90 %d Z" fill="%s" %s/><path d="M26 %d H96" stroke="#0a0e1c" stroke-width="5" stroke-linecap="round"/>'
                % (c + 10, c - 8, c - 8, c + 10, cloth_dark, o, c + 10))
    return svg


def cast_of(s):
    """The case's characters: participants and witnesses (no repeats), with colour and a name search."""
    cast = []
    for field, is_witness in (('participants', False), ('witnesses', True)):
        for p in s.get(field) or []:
            name = str(p.get('name') or '').strip()
            if not name:
                continue
            short = regex.sub(r'\s*\(.*?\)|,.*$', '', name).strip()
            words = name_words(name)
            first_raw = regex.split(r'[\s,]+', short)[0].lower()
            # A witness who is already a participant: the same name or the same first name word
            # («Ирвен» = «Начальник спасателей Ирвен», «Посол Тенгиз» = «Тенгиз»). «Дочь Палси» is someone else.
            same = None
            if first_raw not in KIN:
                for i, c in enumerate(cast):
                    if (c['short'].lower() == short.lower()
                            or (words and c['words'] and stem(c['words'][0]).lower() == stem(words[0]).lower())):
                        same = i
                        break
            if same is not None:
                if is_witness:
                    cast[same]['claim'] = str(p.get('claim') or '')
                    cast[same]['trust'] = str(p.get('trust') or '')
                continue
            # The main word of the role: «Глава службы безопасности» → «глав», «Королевский прокурор» → «прокурор».
            role_words = [w for w in regex.split(r'[\s,.()«»]+', str(p.get('role') or '').lower()) if w]
            head = role_words[0] if role_words else ''
            if regex.search(r'(ый|ий|ой|ая|яя|ое)$', head) and len(role_words) > 1:
                head = role_words[1]
            cast.append({
                'name': name,
                'short': short,
                'words': words,
                'age': str(p.get('age') or ''),
                'role': 'Свидетель' if is_witness else str(p.get('role') or ''),
                'relations': str(p.get('relations') or ''),
                'hue': name_hue(name),
                'roleHead': stem(head) if len(head) >= 3 else '',
                'witness': is_witness,
                'claim': str(p.get('claim') or '') if is_witness else '',
                'trust': str(p.get('trust') or '') if is_witness else '',
                'avatar': {'name': name, 'age': p.get('age') or '', 'role': str(p.get('role') or '') + (' ' + name if is_witness else '')},
            })
    # Name words that are really someone else's main name («Раб Демида Ксанф») aren't searched — otherwise a
    # mention of Демид would light up as Ксанф. A name belongs to whoever has it first, on a tie to the earlier one.
    primary = {}
    for i, c in enumerate(cast):
        if c['words']:
            primary.setdefault(stem(c['words'][0]).lower(), i)
    for i, c in enumerate(cast):
        own = [w for w in c['words'] if primary.get(stem(w).lower(), i) == i]
        c['regex'] = words_regex(own)
        # Gender is guessed from the person's own name: «Учитель Эльмера» is not «Эльмера».
        c['avatar']['first'] = own[0] if own else ''
    return cast


def last_mention(text, cast):
    """Who was mentioned last in the text — for «говорит она», «Он отвечает:»."""
    best, best_pos = None, -1
    for i, c in enumerate(cast):
        if c['regex']:
            found = list(c['regex'].finditer(text))
            if found and found[-1].start() > best_pos:
                best, best_pos = i, found[-1].start()
    return best


def find_speaker(phrase, cast, context):
    """Who speaks. Looks at the first capitalised word of the phrase (lower-case words like «перед броском» are
    skipped): a character's name, their role («Глава», «Прокурор», «Вдова») or «Он/Она» — then whoever was
    mentioned last. Any other word («Защитник Лейлы») means a speaker who isn't among the characters."""
    words = [w for w in regex.split(r'[\s,:;—–]+', phrase.strip()) if w]

    def by_role(lw):
        for i, c in enumerate(cast):
            if c['roleHead'] and lw.startswith(c['roleHead']):
                return i
        return None

    for w in words:
        w = regex.sub(r'^[.!?…«»"()]+|[.!?…«»"()]+$', '', w)
        lw = w.lower()
        if not w or lw in SKIP:
            continue
        if lw in ('он', 'она'):
            return last_mention(context, cast)
        for i, c in enumerate(cast):
            if c['regex'] and c['regex'].search(w):
                return i
        if lw in GROUPS:
            return None  # «Компания отвечает», «семья Ото требует» — not a single character speaking
        if not regex.match(r'\p{Lu}', w):
            # «мать Кири требует»: the subject is the kinship word itself; find whose role it is.
            if lw in KIN:
                return by_role(lw)
            continue  # other lower-case words («перед броском») aren't the subject
        return by_role(lw)
    return None


def highlight(text, cast):
    """Text with the characters' names coloured like their portraits (returns HTML)."""
    html = esc(text)
    for c in cast:
        if c['regex']:
            html = c['regex'].sub(lambda m, hue=c['hue']: '<b class="cm-name" style="--ah:%d">%s</b>' % (hue, m.group(0)), html)
    return html


def present_in(text, cast):
    """Who is mentioned in the text (for the frame)."""
    return [i for i, c in enumerate(cast) if c['regex'] and c['regex'].search(text)]


def segments_of(para, cast, prior=''):
    """A paragraph → a sequence of captions and speech. prior — the story text before this paragraph (for «он/она»).
    Speech is «a quote» of four words or more, after a colon or before «— сказал …»; short «Щит», «верный яд» stay text."""
    segments, speakers = [], []
    pos = 0
    for m in regex.finditer(r'«([^«»]+)»', para):
        full, offset = m.group(0), m.start()
        quote = m.group(1)
        before = para[pos:offset]
        after = para[offset + len(full):]
        is_speech = (len(quote.split()) >= 4 or regex.search(r':\s*$', before) or _SAY_TAG.search(after))
        if not is_speech:
            continue
        context = prior + para[:offset]
        # «Двадцать минут, — говорит она, — и он скажет всё»: the speaker tag is removed from the bubble.
        inner = []

        def drop_tag(mm):
            inner.append(mm.group(1))
            return '. ' if mm.group(2) == '.' else ', '
        quote = _INNER_TAG.sub(drop_tag, quote)
        # The sentence the quote stands in: from the end of the previous sentence.
        lead = regex.split(r'(?<=[.!?…»])\s+', before)[-1]
        who = find_speaker(lead, cast, context)
        tag = ''
        t = _SAY_TAG.search(after)
        if t:
            tag = t.group(1).strip()
            if who is None:
                who = find_speaker(regex.sub(r'^\p{L}+\s+', '', tag), cast, context)  # «— спросил Бранн»
            after = after[len(t.group(0)):]
        if who is None and inner:
            who = find_speaker(inner[-1], cast, context)
        if before.strip():
            segments.append({'type': 'caption', 'text': before.strip().lstrip('.,;:!? ')})
        segments.append({'type': 'speech', 'who': who, 'text': quote, 'tag': tag})
        if who is not None:
            speakers.append(who)
        pos = len(para) - len(after)
    rest = para[pos:].strip()
    if rest and not regex.match(r'^[.!?…,]+$', rest):
        segments.append({'type': 'caption', 'text': rest.lstrip('.,; ')})
    return segments, list(dict.fromkeys(speakers))


def panels_of(s, cast, full):
    """Comic frames. full — with «Кто есть кто», «Что известно», witnesses and «Ваш вердикт» frames (Быстрый суд);
    without it — only the world and the story (the case page, where the rest is in the dossier)."""
    panels = []
    story = str(s.get('story') or '').strip()
    role = ''
    m = regex.match(r'^Вы\s+[—–-]\s+([^.!?]+)[.!?]\s*', story)
    if m:
        role = m.group(1).strip()
        story = story[len(m.group(0)):].strip()

    world = s['world']
    panels.append({'kind': 'world', 'title': s['title'], 'place': world['place'], 'era': world['era'],
                   'text': world['circumstances'], 'role': role, 'present': []})

    prior = ''  # the story before the current paragraph — to know who «он» and «она» are
    for para in _PARAS.split(story):
        para = para.strip()
        if not para:
            continue
        segments, speakers = segments_of(para, cast, prior)
        prior += para + '\n'
        # Speakers first, then the others mentioned; at most four in a frame.
        present = list(dict.fromkeys(speakers + present_in(para, cast)))[:4]
        panels.append({'kind': 'story', 'segments': segments, 'present': present})

    if full:
        people = [i for i, c in enumerate(cast) if not c['witness']]
        if people:
            panels.append({'kind': 'cast', 'present': people[:5], 'people': people})
        if s['facts'] or s['unknowns']:
            panels.append({'kind': 'evidence', 'facts': s['facts'], 'unknowns': s['unknowns'], 'present': []})
        witnesses = [i for i, c in enumerate(cast) if c['claim'] != '']
        if witnesses:
            panels.append({'kind': 'witnesses', 'present': witnesses[:4], 'people': witnesses})
        panels.append({'kind': 'decide', 'present': []})
    return panels


# ---------- World scenes ----------

def _sky(top, bottom):
    return ('<defs><linearGradient id="cm-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="' + top + '"/><stop offset="1" stop-color="' + bottom + '"/></linearGradient>'
            '<radialGradient id="cm-glow" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#fff" stop-opacity=".9"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient></defs>'
            '<rect width="1200" height="600" fill="url(#cm-sky)"/>')


def _stars(n, seed, max_y=330):
    out = '<g class="sc-twinkle">'
    for i in range(n):
        x = (seed * 37 + i * 173) % 1200
        y = (seed * 11 + i * 97) % max_y
        out += ('<circle cx="%d" cy="%d" r="%s" fill="#fff" opacity="%s" style="--d:%ss"/>'
                % (x, y, fnum(1 + i % 3 * 0.6), fnum(0.35 + (i % 5) * 0.12), fnum((i % 7) * 0.4)))
    return out + '</g>'


def scene(setting, hue):
    """Background scene for a world type: layers sc-far / sc-mid / sc-near move at different speeds. viewBox 0 0 1200 600."""
    accent = 'hsl(%d 95%% 62%%)' % hue

    if setting == 'Поселение после апокалипсиса':
        return (_sky('#2a1030', '#d9632f')
                + '<circle cx="820" cy="360" r="120" fill="#ffb347" opacity=".85"/><circle cx="820" cy="360" r="190" fill="url(#cm-glow)" opacity=".25"/>'
                '<g class="sc-far" fill="#4a1d33"><path d="M0 420 L60 420 L60 300 L110 300 L110 340 L150 340 L150 250 L190 262 L205 420 L280 420 L280 330 L330 318 L345 420 L420 420 L430 270 L470 300 L480 230 L520 250 L520 420 L600 420 L620 340 L700 330 L700 420 L760 420 L770 290 L812 300 L820 420 L900 420 L910 330 L960 350 L980 260 L1020 280 L1030 420 L1100 420 L1110 310 L1160 300 L1200 330 L1200 600 L0 600 Z"/></g>'
                '<g class="sc-mid" fill="#2b0f22"><path d="M0 470 L120 455 L170 380 L210 470 L380 480 L420 410 L440 470 L640 488 L700 430 L740 482 L960 470 L1010 400 L1060 476 L1200 470 L1200 600 L0 600 Z"/>'
                '<path d="M150 380 L240 330 M240 330 L330 370" stroke="#2b0f22" stroke-width="4" fill="none"/></g>'
                '<g class="sc-near" fill="#16070f"><path d="M0 540 C200 520 400 560 600 540 C800 520 1000 555 1200 535 L1200 600 L0 600 Z"/></g>'
                '<g class="sc-dust" fill="#ffcf9a" opacity=".45"><circle cx="100" cy="500" r="2"/><circle cx="400" cy="470" r="1.6"/><circle cx="700" cy="520" r="2.2"/><circle cx="1000" cy="480" r="1.6"/></g>')

    if setting == 'Древнее царство':
        return (_sky('#3a1f4f', '#f0a95a')
                + '<circle cx="300" cy="200" r="70" fill="#ffe2a0" opacity=".9"/>'
                '<g class="sc-far" fill="#7a4a3a"><path d="M760 430 L900 250 L1040 430 Z"/><path d="M960 430 L1060 300 L1160 430 Z" opacity=".8"/></g>'
                '<g class="sc-mid" fill="#4d2733"><path d="M160 300 L420 230 L680 300 Z"/><rect x="180" y="300" width="480" height="22"/>'
                + ''.join('<rect x="%d" y="322" width="28" height="140"/>' % x for x in (200, 270, 340, 410, 480, 550, 610))
                + '<rect x="170" y="460" width="500" height="20"/></g>'
                '<g class="sc-near" fill="#2a1420"><path d="M0 500 C300 470 600 520 900 495 C1050 485 1150 500 1200 495 L1200 600 L0 600 Z"/>'
                '<path d="M1010 495 C1000 420 1020 380 1030 360 M1030 360 C990 350 970 370 960 390 M1030 360 C1060 340 1090 350 1100 370 M1030 360 C1000 330 990 320 980 330 M1030 360 C1060 320 1080 320 1090 330" stroke="#2a1420" stroke-width="10" fill="none" stroke-linecap="round"/></g>')

    if setting == 'Средневековое поселение':
        return (_sky('#0f1838', '#5a4a8a')
                + _stars(26, 3, 260) + '<circle cx="980" cy="120" r="44" fill="#f4f1d0" opacity=".9"/>'
                '<g class="sc-far" fill="#252a55"><path d="M0 400 C200 330 380 350 560 380 C760 410 960 320 1200 360 L1200 600 L0 600 Z"/>'
                '<path d="M820 350 L820 270 L840 270 L840 255 L860 255 L860 270 L880 270 L880 230 L900 215 L920 230 L920 270 L960 270 L960 345 Z"/></g>'
                '<g class="sc-mid" fill="#171a3a"><path d="M80 470 L80 400 L140 360 L200 400 L200 470 Z M230 470 L230 410 L285 375 L340 410 L340 470 Z M560 470 L560 395 L630 350 L700 395 L700 470 Z"/>'
                '<rect x="420" y="330" width="40" height="140"/><g class="sc-spin" style="transform-origin:440px 330px"><path d="M440 330 L440 250 L452 250 Z M440 330 L520 330 L520 342 Z M440 330 L440 410 L428 410 Z M440 330 L360 330 L360 318 Z" fill="#2d3363"/></g>'
                '<rect x="105" y="420" width="14" height="18" fill="#ffd27a"/><rect x="600" y="410" width="14" height="18" fill="#ffd27a"/><rect x="270" y="425" width="12" height="16" fill="#ffd27a"/></g>'
                '<g class="sc-near" fill="#0b0d22"><path d="M0 500 C250 480 500 520 750 500 C950 485 1100 505 1200 495 L1200 600 L0 600 Z"/></g>')

    if setting == 'Королевство или ханство':
        return (_sky('#1a0f3a', '#7a3a7a')
                + _stars(30, 7, 280) + '<path d="M960 90 a50 50 0 1 0 40 80 a40 40 0 1 1 -40 -80 Z" fill="#ffe7a0"/>'
                '<g class="sc-far" fill="#2c1850"><path d="M0 430 L1200 410 L1200 600 L0 600 Z"/></g>'
                '<g class="sc-mid" fill="#1d0f38"><rect x="380" y="300" width="440" height="180"/>'
                '<path d="M520 300 C520 220 680 220 680 300 Z"/><path d="M600 222 L600 196"/><circle cx="600" cy="192" r="6" fill="#ffd27a"/>'
                '<path d="M410 300 C410 262 470 262 470 300 Z M730 300 C730 262 790 262 790 300 Z"/>'
                '<rect x="330" y="230" width="30" height="250"/><path d="M330 230 L345 190 L360 230 Z"/><rect x="840" y="230" width="30" height="250"/><path d="M840 230 L855 190 L870 230 Z"/>'
                '<path d="M570 480 L570 400 C570 370 630 370 630 400 L630 480 Z" fill="#ffcf7a" opacity=".8"/>'
                '<g class="sc-flag"><path d="M855 190 L855 160 L890 168 L855 178" fill="' + accent + '"/></g></g>'
                '<g class="sc-near" fill="#0d0720"><path d="M0 505 L1200 495 L1200 600 L0 600 Z"/><circle class="sc-flicker" cx="200" cy="470" r="8" fill="#ffb347"/><circle class="sc-flicker" cx="1000" cy="470" r="8" fill="#ffb347" style="--d:.6s"/></g>')

    if setting == 'Цивилизация будущего':
        win = ''
        for k, (x, y, w) in enumerate([(80, 160, 90), (200, 80, 110), (340, 200, 80), (460, 40, 130), (620, 140, 100), (760, 60, 120), (910, 180, 90), (1040, 100, 120)]):
            win += '<rect x="%d" y="%d" width="%d" height="%d" fill="#0c1430" stroke="%s" stroke-opacity=".35"/>' % (x, y, w, 600 - y, accent)
            for r in range(y + 20, 470, 34):
                win += ('<rect x="%d" y="%d" width="%d" height="6" fill="%s" opacity="%s"/>'
                        % (x + 12, r, w - 24, '#2be4ff' if (r + k) % 3 else '#ff2bd6', fnum(0.15 + ((r * 7 + k) % 5) * 0.08)))
        return (_sky('#04040f', '#1a0a3a') + _stars(18, 5, 200)
                + '<g class="sc-far">' + win + '</g>'
                '<g class="sc-fly"><rect x="-60" y="150" width="40" height="6" rx="3" fill="#2be4ff"/><rect x="-200" y="230" width="30" height="5" rx="2" fill="#ff2bd6" style="--d:3s"/></g>'
                '<g class="sc-near"><path d="M0 500 L1200 500 L1200 600 L0 600 Z" fill="#05060f"/><path d="M0 500 L1200 500" stroke="' + accent + '" stroke-width="3" opacity=".7"/>'
                '<path d="M0 540 L1200 540 M0 575 L1200 575" stroke="#2be4ff" stroke-opacity=".2"/></g>')

    if setting == 'Космическая колония':
        return (_sky('#020208', '#0b1030') + _stars(60, 9, 480)
                + '<g class="sc-far"><circle cx="880" cy="190" r="120" fill="hsl(%d 60%% 45%%)" opacity=".85"/><circle cx="850" cy="160" r="120" fill="#020208" opacity=".35"/>' % hue
                + '<ellipse cx="880" cy="190" rx="200" ry="34" fill="none" stroke="#c7d2ff" stroke-opacity=".55" stroke-width="5" transform="rotate(-14 880 190)"/></g>'
                '<g class="sc-mid"><path d="M0 470 C200 440 420 455 600 450 C820 445 1000 430 1200 450 L1200 600 L0 600 Z" fill="#2a2f45"/>'
                '<path d="M220 452 a90 90 0 0 1 180 0 Z" fill="rgba(160,220,255,.18)" stroke="#9fdcff" stroke-width="3"/><path d="M450 452 a60 60 0 0 1 120 0 Z" fill="rgba(160,220,255,.15)" stroke="#9fdcff" stroke-width="3"/>'
                '<rect x="300" y="420" width="18" height="30" fill="#ffd27a" opacity=".8"/><path d="M700 450 L700 330 M700 330 L680 350 M700 330 L720 350" stroke="#c7d2ff" stroke-width="4"/><circle class="sc-blink" cx="700" cy="326" r="6" fill="#ff4d6d"/></g>'
                '<g class="sc-near"><path d="M0 520 C300 505 700 530 1200 512 L1200 600 L0 600 Z" fill="#161a2b"/><circle cx="150" cy="560" r="14" fill="#11141f"/><circle cx="980" cy="555" r="20" fill="#11141f"/></g>')

    if setting == 'Вымышленное племя':
        return (_sky('#1d2b55', '#ff9a6a')
                + '<circle cx="600" cy="420" r="90" fill="#ffcf8a" opacity=".9"/>'
                '<g class="sc-far"><path d="M0 420 L1200 420 L1200 470 L0 470 Z" fill="#3a5a8a"/><path d="M0 430 L1200 430" stroke="#ffcf8a" stroke-opacity=".5" stroke-width="3"/></g>'
                '<g class="sc-mid" fill="#1f1a2e"><path d="M120 470 L190 370 L260 470 Z M300 470 L360 385 L420 470 Z M820 470 L900 360 L980 470 Z"/>'
                '<path d="M1060 470 C1050 400 1070 360 1080 340 M1080 340 C1040 330 1020 350 1010 370 M1080 340 C1110 320 1140 330 1150 350 M1080 340 C1060 310 1040 305 1030 315" stroke="#1f1a2e" stroke-width="10" fill="none" stroke-linecap="round"/></g>'
                '<g class="sc-near"><path d="M0 500 C300 485 900 515 1200 495 L1200 600 L0 600 Z" fill="#120f1d"/>'
                '<g class="sc-flicker"><path d="M560 500 C555 470 575 455 580 440 C590 460 610 470 600 500 Z" fill="#ff8a3a"/><path d="M570 500 C570 482 582 474 585 465 C592 478 598 485 592 500 Z" fill="#ffd27a"/></g></g>')

    # «Полностью вымышленное общество» and anything else
    return (_sky('#101a3a', '#3b5f9a') + _stars(14, 4, 200)
            + '<g class="sc-far" fill="#2a3a6a"><path d="M150 300 C150 260 330 260 330 300 L280 360 L200 360 Z"/><rect x="215" y="200" width="20" height="100"/><rect x="250" y="160" width="26" height="140"/>'
            '<path d="M820 260 C820 220 1040 220 1040 260 L980 330 L880 330 Z"/><rect x="870" y="150" width="24" height="110"/><rect x="920" y="110" width="30" height="150"/><rect x="975" y="170" width="22" height="90"/></g>'
            '<g class="sc-fly"><ellipse cx="-140" cy="130" rx="70" ry="22" fill="' + accent + '" opacity=".75"/><rect x="-160" y="150" width="40" height="14" rx="4" fill="#1a2350"/></g>'
            '<g class="sc-mid" fill="#18224a"><path d="M380 470 L380 260 L420 230 L460 260 L460 470 Z M500 470 L500 300 L560 270 L620 300 L620 470 Z M660 470 L660 220 L700 190 L740 220 L740 470 Z"/>'
            '<rect x="400" y="300" width="10" height="12" fill="#ffd27a"/><rect x="540" y="330" width="10" height="12" fill="#ffd27a"/><rect x="690" y="260" width="10" height="12" fill="#ffd27a"/></g>'
            '<g class="sc-near"><path d="M0 500 C300 480 900 520 1200 495 L1200 600 L0 600 Z" fill="#0c1230"/></g>')


_CAMS = ['0 0 1', '-4 1.5 1.08', '4 -1 1.14', '-2 2 1.1', '3 1 1.16', '-5 -1 1.12', '2 2.5 1.06']


def camera(i):
    """«Camera» positions per frame — the background pans smoothly between them."""
    return _CAMS[i % len(_CAMS)]


def cast_public(cast):
    """The cast without compiled regexes — for JSON (game clients)."""
    return [{k: v for k, v in c.items() if k not in ('regex', 'words', 'roleHead')} for c in cast]
