<?php
declare(strict_types=1);

defined('APP_ROOT') || exit;

/*
 * Режим комикса: дело показывается кадрами — мир, сюжет по абзацам, кто есть кто, улики, свидетели.
 * Всё рисуется из данных ситуации: фон по типу мира, портреты по имени/возрасту/роли,
 * реплики в «кавычках» становятся репликами персонажей. Никакого нового контента авторам писать не нужно.
 */

/** Должности и звания перед именем: «Посол Тенгиз», «Доктор Нара» — тот же человек, по слову его не ищем. */
const COMIC_TITLES = ['принц', 'принцесса', 'король', 'королева', 'царь', 'царица', 'царевич', 'царевна', 'хан', 'мэр', 'доктор',
    'капитан', 'командир', 'инспектор', 'аудитор', 'старпом', 'бригадир', 'начальник', 'мастер', 'купец', 'старейшина',
    'верховный', 'судья', 'юрист', 'директор', 'инженер', 'техник', 'медик', 'лекарь', 'жрец', 'жрица', 'прорицатель', 'нотариус',
    'управляющий', 'соседка', 'сосед', 'старик', 'старуха', 'граф', 'барон', 'раб', 'сторож', 'стражник', 'носильщик',
    'прокурор', 'защитник', 'боцман', 'пришелец', 'копия', 'глава', 'председатель', 'учитель', 'бывший', 'хозяин', 'хозяйка',
    'торговец', 'торговка', 'охранник', 'офицер', 'посол', 'сотник', 'лодочник', 'охотник', 'ткачиха', 'распорядитель',
    'ветеран', 'землекоп', 'меняла', 'почтальон', 'бард', 'генетик', 'пекарь', 'пекарка', 'служанка', 'юный', 'ныряльщик',
    'проводница', 'капеллан', 'биолог', 'знахарь', 'кухарка', 'архивариус', 'рыбак', 'кузнец', 'мельник', 'матрос', 'юнга',
    'пилот', 'арбитр', 'кади', 'шахтёр', 'смотритель', 'хранитель', 'хранительница', 'советник', 'канцлер', 'генерал',
    'солдат', 'монах', 'учёный', 'ученик', 'подмастерье', 'губернатор', 'комендант', 'наместник', 'старый', 'старая',
    'молодой', 'мастерица', 'лекарка', 'целитель', 'писарь', 'караванщик', 'проводник'];

/** Родство перед именем: «Дочь Палси», «Мать братьев» — это ДРУГОЙ человек, связанный с названным. */
const COMIC_KIN = ['мать', 'отец', 'сестра', 'брат', 'сын', 'дочь', 'жена', 'муж', 'вдова', 'вдовец', 'внук', 'внучка',
    'тётя', 'дядя', 'бабушка', 'дедушка', 'учитель', 'друг', 'подруга', 'невеста', 'жених'];

/** Слова в начале фразы, которые пропускаем при поиске говорящего. */
const COMIC_SKIP = ['сам', 'сама', 'сами', 'а', 'и', 'но', 'тогда', 'теперь', 'тут', 'вот', 'даже', 'только', 'уже', 'потом', 'затем', 'однако'];

/** Строчные слова-подлежащие: «семья Ото требует», «сыновья отвечают» — говорит не Ото. */
const COMIC_GROUPS = ['семья', 'люди', 'толпа', 'совет', 'город', 'сыновья', 'дочери', 'дети', 'жители', 'соседи', 'народ',
    'стража', 'компания', 'корпорация', 'гильдия', 'защитник', 'старейшины', 'моряки', 'колонисты', 'кто-то', 'одни', 'другие', 'все'];

/** Женские имена на согласную и мужские на -а/-я, которые иначе угадываются неверно. */
const COMIC_FEMALE_NAMES = ['ингрид', 'мэйв', 'агнес', 'рут', 'эстер', 'ирэн', 'нелл', 'ило', 'кармен', 'нинон', 'айнур', 'мерит', 'хемет-нет'];
const COMIC_MALE_A_NAMES = ['илья', 'никита', 'фома', 'лука', 'кузьма', 'добрыня', 'неба', 'сила', 'миха'];

/** Глаголы, которыми обычно вводят реплику: «— спросил Бранн», «— говорит она». */
const COMIC_SAY = 'говорит|сказал|сказала|спросил|спросила|отвечает|ответил|ответила|добавляет|добавил|добавила|шепчет|шепнул|шепнула|кричит|крикнул|крикнула|повторяет|требует|просит';

function comic_lower(string $s): string
{
    return mb_strtolower($s);
}

/** Основа слова для поиска склонённых форм: «Ирма» → «Ирм» (найдёт «Ирмы», «Ирму»). */
function comic_stem(string $word): string
{
    $len = mb_strlen($word);
    if ($len >= 4 && preg_match('/[аяоеиыуюэьй]$/u', comic_lower($word))) {
        return mb_substr($word, 0, $len - 1);
    }
    return $word;
}

/** Слова имени без должностей и родства: «Начальник спасателей Ирвен» → [Ирвен], «Дочь Палси» → [Палси]. */
function comic_name_words(string $name): array
{
    preg_match_all('/\p{Lu}[\p{L}\-]+/u', (string)preg_replace('/,.*$/u', '', $name), $m);
    return array_values(array_filter($m[0], static fn(string $w): bool =>
        !in_array(comic_lower($w), COMIC_TITLES, true) && !in_array(comic_lower($w), COMIC_KIN, true)));
}

/** Регулярное выражение, которое находит слова имени в тексте в любом падеже. */
function comic_words_regex(array $words): ?string
{
    $parts = array_map(static fn(string $w): string => mb_strlen($w) < 3
        ? preg_quote($w, '/') . '(?:а|у|ом|е)?'
        : preg_quote(comic_stem($w), '/') . '\p{L}{0,3}', $words);
    return $parts ? '/(?<![\p{L}])(?:' . implode('|', $parts) . ')(?![\p{L}])/u' : null;
}

function comic_age(array $p): int
{
    return preg_match('/\d+/', (string)($p['age'] ?? ''), $m) ? (int)$m[0] : 35;
}

function comic_is_female(array $p): bool
{
    $role = comic_lower((string)($p['role'] ?? ''));
    $name = (string)($p['name'] ?? '');
    $first = comic_lower(array_key_exists('first', $p) ? (string)$p['first'] : (comic_name_words($name)[0] ?? ''));
    if ($first !== '' && in_array($first, COMIC_FEMALE_NAMES, true)) {
        return true;
    }
    $both = $role . ' ' . comic_lower($name);
    if (preg_match('/(?<!\p{L})(вдова|мать|сестра|жена|дочь|служанка|царевна|невеста|соседка|хозяйка|королева|царица|принцесса|кухарка|прачка|травница|старуха|девушка|покупательница|пассажирка|хранительница|сирота|торговка|ткачиха|жрица|пекарка|проводница|мастерица|лекарка|инженерка)(?!\p{L})/u', $both)) {
        return true;
    }
    if (preg_match('/(?<!\p{L})(отец|муж|сын|брат|старик|царь|король|принц|хан|юноша|мальчик|жених|вдовец|дед)(?!\p{L})/u', $both)) {
        return false;
    }
    // «Умершая», «Выжившая», «обвиняемая» — женский род (родительный падеж женского — на -ой, не на -ая).
    if (preg_match('/\p{L}{3,}(ая|яя)(?!\p{L})/u', $role)) {
        return true;
    }
    // Дальше решает имя: прилагательные в должностях («Капитан городской стражи») рода человека не выдают.
    if ($first === '') {
        return false;
    }
    return (bool)preg_match('/[ая]$/u', $first) && !in_array($first, COMIC_MALE_A_NAMES, true);
}

/**
 * Портрет персонажа в стиле комикса — детерминированный: один и тот же человек выглядит одинаково везде.
 * Возвращает внутренности <symbol> (viewBox 0 0 120 140).
 */
function comic_avatar_body(array $p): string
{
    $name = (string)($p['name'] ?? '?');
    $role = comic_lower((string)($p['role'] ?? ''));
    $h = crc32($name);
    $age = comic_age($p);
    $female = comic_is_female($p);
    $hue = name_hue($name);
    $kid = $age < 16;
    $old = $age >= 60;

    $skin = ['#f2c9a8', '#e3b08a', '#c98d66', '#9a6442'][$h % 4];
    $hair = $age >= 70 ? '#e8e9ef' : ($old ? '#b8bcc8' : ['#1f1b22', '#3d2b20', '#5b3a22', '#8b5a2b', '#c4934c', '#2a2d3a'][($h >> 3) % 6]);
    $cloth = "hsl($hue 55% 40%)";
    $clothDark = "hsl($hue 55% 28%)";
    $o = 'stroke="#0a0e1c" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"';

    $headY = $kid ? 66 : 60;
    $svg = '';
    // Длинные волосы сзади.
    $long = $female && ($h >> 5) % 3 !== 0;
    if ($long) {
        $svg .= '<path d="M27 ' . ($headY) . ' C24 ' . ($headY - 36) . ' 44 ' . ($headY - 44) . ' 60 ' . ($headY - 44) . ' C78 ' . ($headY - 44) . ' 97 ' . ($headY - 36) . ' 93 ' . $headY . ' L99 112 C86 120 34 120 21 112 Z" fill="' . $hair . '" ' . $o . '/>';
    }
    // Плечи и одежда.
    $svg .= '<path d="M8 140 C12 104 34 93 60 93 C86 93 108 104 112 140 Z" fill="' . $cloth . '" ' . $o . '/>';
    $svg .= '<path d="M44 96 L60 116 L76 96" fill="none" stroke="' . $clothDark . '" stroke-width="5" stroke-linecap="round"/>';
    $svg .= '<rect x="51" y="' . ($headY + 22) . '" width="18" height="16" fill="' . $skin . '" ' . $o . '/>';
    // Голова.
    $svg .= '<ellipse cx="60" cy="' . $headY . '" rx="' . ($kid ? 29 : 28) . '" ry="' . ($kid ? 30 : 33) . '" fill="' . $skin . '" ' . $o . '/>';
    // Уши.
    $svg .= '<ellipse cx="32" cy="' . ($headY + 4) . '" rx="5" ry="8" fill="' . $skin . '" ' . $o . '/><ellipse cx="88" cy="' . ($headY + 4) . '" rx="5" ry="8" fill="' . $skin . '" ' . $o . '/>';
    // Глаза.
    $eyeR = $kid ? 4.6 : 3.6;
    foreach ([49, 71] as $x) {
        $svg .= '<ellipse cx="' . $x . '" cy="' . ($headY + 2) . '" rx="' . $eyeR . '" ry="' . ($eyeR + 0.8) . '" fill="#141826"/>'
            . '<circle cx="' . ($x + 1.3) . '" cy="' . ($headY + 0.5) . '" r="1.3" fill="#fff"/>';
    }
    // Брови: у старших — тяжелее.
    $bw = $old ? 3.6 : 3;
    $svg .= '<path d="M42 ' . ($headY - 8) . ' Q49 ' . ($headY - 12) . ' 55 ' . ($headY - 8) . '" fill="none" stroke="' . ($old ? '#8a8d99' : '#1b1720') . '" stroke-width="' . $bw . '" stroke-linecap="round"/>'
        . '<path d="M65 ' . ($headY - 8) . ' Q71 ' . ($headY - 12) . ' 78 ' . ($headY - 8) . '" fill="none" stroke="' . ($old ? '#8a8d99' : '#1b1720') . '" stroke-width="' . $bw . '" stroke-linecap="round"/>';
    // Нос и рот.
    $svg .= '<path d="M60 ' . ($headY + 6) . ' Q57 ' . ($headY + 13) . ' 61 ' . ($headY + 14) . '" fill="none" stroke="#0a0e1c" stroke-width="2.2" stroke-linecap="round"/>';
    $svg .= '<path d="M52 ' . ($headY + 21) . ' Q60 ' . ($headY + 24) . ' 68 ' . ($headY + 21) . '" fill="none" stroke="#0a0e1c" stroke-width="2.6" stroke-linecap="round"/>';
    if ($old) {
        $svg .= '<path d="M38 ' . ($headY + 6) . ' l5 3 M82 ' . ($headY + 6) . ' l-5 3 M50 ' . ($headY + 16) . ' q-3 5 0 9 M70 ' . ($headY + 16) . ' q3 5 0 9" fill="none" stroke="#0a0e1c" stroke-opacity=".35" stroke-width="1.8" stroke-linecap="round"/>';
    }
    // Борода у части взрослых мужчин.
    if (!$female && !$kid && $age >= 28 && ($h >> 7) % 3 === 0) {
        $svg .= '<path d="M34 ' . ($headY + 6) . ' C36 ' . ($headY + 36) . ' 84 ' . ($headY + 36) . ' 86 ' . ($headY + 6) . ' C80 ' . ($headY + 22) . ' 70 ' . ($headY + 18) . ' 60 ' . ($headY + 19) . ' C50 ' . ($headY + 18) . ' 40 ' . ($headY + 22) . ' 34 ' . ($headY + 6) . ' Z" fill="' . $hair . '" ' . $o . '/>'
            . '<path d="M53 ' . ($headY + 23) . ' Q60 ' . ($headY + 26) . ' 67 ' . ($headY + 23) . '" fill="none" stroke="#0a0e1c" stroke-width="2.4" stroke-linecap="round"/>';
    }
    // Волосы спереди.
    $style = ($h >> 9) % 3;
    if ($old && !$female && $style === 0) {
        $svg .= '<path d="M32 ' . ($headY - 2) . ' C30 ' . ($headY - 18) . ' 38 ' . ($headY - 22) . ' 42 ' . ($headY - 20) . ' M88 ' . ($headY - 2) . ' C90 ' . ($headY - 18) . ' 82 ' . ($headY - 22) . ' 78 ' . ($headY - 20) . '" fill="none" stroke="' . $hair . '" stroke-width="7" stroke-linecap="round"/>';
    } elseif ($female) {
        $svg .= '<path d="M31 ' . ($headY - 2) . ' C30 ' . ($headY - 34) . ' 52 ' . ($headY - 40) . ' 64 ' . ($headY - 36) . ' C80 ' . ($headY - 34) . ' 92 ' . ($headY - 22) . ' 89 ' . ($headY - 2) . ' C80 ' . ($headY - 18) . ' 66 ' . ($headY - 22) . ' 52 ' . ($headY - 16) . ' C44 ' . ($headY - 12) . ' 36 ' . ($headY - 8) . ' 31 ' . ($headY - 2) . ' Z" fill="' . $hair . '" ' . $o . '/>';
        if (!$long) { // пучок
            $svg .= '<circle cx="60" cy="' . ($headY - 40) . '" r="11" fill="' . $hair . '" ' . $o . '/>';
        }
    } elseif ($style === 1) {
        $svg .= '<path d="M31 ' . ($headY - 4) . ' C28 ' . ($headY - 34) . ' 48 ' . ($headY - 40) . ' 62 ' . ($headY - 38) . ' C80 ' . ($headY - 37) . ' 93 ' . ($headY - 26) . ' 89 ' . ($headY - 4) . ' C86 ' . ($headY - 16) . ' 74 ' . ($headY - 22) . ' 64 ' . ($headY - 20) . ' L58 ' . ($headY - 12) . ' L54 ' . ($headY - 20) . ' C44 ' . ($headY - 20) . ' 35 ' . ($headY - 14) . ' 31 ' . ($headY - 4) . ' Z" fill="' . $hair . '" ' . $o . '/>';
    } else {
        $svg .= '<path d="M30 ' . ($headY - 2) . ' C27 ' . ($headY - 36) . ' 46 ' . ($headY - 42) . ' 60 ' . ($headY - 42) . ' C76 ' . ($headY - 42) . ' 94 ' . ($headY - 34) . ' 90 ' . ($headY - 2) . ' C84 ' . ($headY - 16) . ' 74 ' . ($headY - 24) . ' 60 ' . ($headY - 24) . ' C46 ' . ($headY - 24) . ' 36 ' . ($headY - 16) . ' 30 ' . ($headY - 2) . ' Z" fill="' . $hair . '" ' . $o . '/>';
    }
    // Атрибуты роли.
    if (preg_match('/(?<!\p{L})(царь|царица|король|королева|хан|ханша|царевна|царевич|принц|принцесса|правитель|правительница|наместник)(?!\p{L})/u', $role . ' ' . comic_lower($name))) {
        $y = $headY - 44;
        $svg .= '<path d="M40 ' . ($y + 14) . ' L42 ' . $y . ' L51 ' . ($y + 8) . ' L60 ' . ($y - 4) . ' L69 ' . ($y + 8) . ' L78 ' . $y . ' L80 ' . ($y + 14) . ' Z" fill="#ffc94a" ' . $o . '/>'
            . '<circle cx="60" cy="' . ($y + 7) . '" r="2.6" fill="#ff4d6d"/>';
    } elseif (preg_match('/(?<!\p{L})(доктор|врач|медик|инженер|учён|нотариус|учитель|аудитор|архивариус|инспектор|юрист|биолог|арбитр)/u', $role . ' ' . comic_lower($name))) {
        $svg .= '<g fill="rgba(170,230,255,.25)" stroke="#0a0e1c" stroke-width="2.6"><circle cx="49" cy="' . ($headY + 2) . '" r="9"/><circle cx="71" cy="' . ($headY + 2) . '" r="9"/></g>'
            . '<path d="M58 ' . ($headY + 1) . ' h4" stroke="#0a0e1c" stroke-width="2.6"/>';
    } elseif (preg_match('/(?<!\p{L})(капитан|стражник|стража|охран|носильщик|матрос|юнга|боцман|солдат|пилот|старпом|офицер)/u', $role)) {
        $y = $headY - 30;
        $svg .= '<path d="M30 ' . ($y + 10) . ' C32 ' . ($y - 8) . ' 88 ' . ($y - 8) . ' 90 ' . ($y + 10) . ' Z" fill="' . $clothDark . '" ' . $o . '/>'
            . '<path d="M26 ' . ($y + 10) . ' H96" stroke="#0a0e1c" stroke-width="5" stroke-linecap="round"/>';
    }
    return $svg;
}

/** Персонажи дела: участники и свидетели (без повторов), с цветом и поиском имени в тексте. */
function comic_cast(array $s): array
{
    $cast = [];
    foreach ([['participants', false], ['witnesses', true]] as [$field, $isWitness]) {
        foreach ($s[$field] ?? [] as $p) {
            $name = trim((string)($p['name'] ?? ''));
            if ($name === '') {
                continue;
            }
            $short = trim((string)preg_replace('/\s*\(.*?\)|,.*$/u', '', $name));
            $words = comic_name_words($name);
            $firstRaw = comic_lower((string)(preg_split('/[\s,]+/u', $short)[0] ?? ''));
            // Свидетель, который уже есть среди участников: то же имя или та же первая часть имени
            // («Ирвен» = «Начальник спасателей Ирвен», «Посол Тенгиз» = «Тенгиз»). «Дочь Палси» — другой человек.
            $same = null;
            if (!in_array($firstRaw, COMIC_KIN, true)) {
                foreach ($cast as $i => $c) {
                    if (comic_lower($c['short']) === comic_lower($short)
                        || ($words && $c['words'] && comic_lower(comic_stem($c['words'][0])) === comic_lower(comic_stem($words[0])))) {
                        $same = $i;
                        break;
                    }
                }
            }
            if ($same !== null) {
                if ($isWitness) {
                    $cast[$same]['claim'] = (string)($p['claim'] ?? '');
                    $cast[$same]['trust'] = (string)($p['trust'] ?? '');
                }
                continue;
            }
            // Главное слово роли: «Глава службы безопасности» → «глав», «Королевский прокурор» → «прокурор».
            $roleWords = preg_split('/[\s,.()«»]+/u', comic_lower((string)($p['role'] ?? '')), -1, PREG_SPLIT_NO_EMPTY);
            $head = $roleWords[0] ?? '';
            if (preg_match('/(ый|ий|ой|ая|яя|ое)$/u', $head) && isset($roleWords[1])) {
                $head = $roleWords[1];
            }
            $cast[] = [
                'name'      => $name,
                'short'     => $short,
                'words'     => $words,
                'age'       => (string)($p['age'] ?? ''),
                'role'      => $isWitness ? 'Свидетель' : (string)($p['role'] ?? ''),
                'relations' => (string)($p['relations'] ?? ''),
                'hue'       => name_hue($name),
                'roleHead'  => mb_strlen($head) >= 3 ? comic_stem($head) : '',
                'witness'   => $isWitness,
                'claim'     => $isWitness ? (string)($p['claim'] ?? '') : '',
                'trust'     => $isWitness ? (string)($p['trust'] ?? '') : '',
                'avatar'    => ['name' => $name, 'age' => $p['age'] ?? '', 'role' => ($p['role'] ?? '') . ($isWitness ? ' ' . $name : '')],
            ];
        }
    }
    // Слова имени, которые на самом деле — чужое главное имя («Раб Демида Ксанф»), не ищем:
    // иначе упоминание Демида подсветится как Ксанф.
    // Имя принадлежит тому, у кого оно стоит первым, а при совпадении — тому, кто в списке раньше.
    $primary = [];
    foreach ($cast as $i => $c) {
        if ($c['words']) {
            $primary[comic_lower(comic_stem($c['words'][0]))] ??= $i;
        }
    }
    foreach ($cast as $i => &$c) {
        $own = array_values(array_filter($c['words'], static function (string $w) use ($primary, $i): bool {
            $owner = $primary[comic_lower(comic_stem($w))] ?? $i;
            return $owner === $i;
        }));
        $c['regex'] = comic_words_regex($own);
        // Пол угадываем по своему имени: «Учитель Эльмера» — не «Эльмера».
        $c['avatar']['first'] = $own[0] ?? '';
    }
    unset($c);
    return $cast;
}

/** Кто упомянут в тексте последним — для «говорит она», «Он отвечает:». */
function comic_last_mention(string $text, array $cast): ?int
{
    $best = null;
    $bestPos = -1;
    foreach ($cast as $i => $c) {
        if ($c['regex'] && preg_match_all($c['regex'], $text, $m, PREG_OFFSET_CAPTURE)) {
            $pos = end($m[0])[1];
            if ($pos > $bestPos) {
                [$best, $bestPos] = [$i, $pos];
            }
        }
    }
    return $best;
}

/**
 * Кто говорит. Смотрим на первое слово фразы с заглавной буквы (строчные «перед броском» пропускаем):
 * имя персонажа, его должность («Глава», «Прокурор», «Вдова») или местоимение «Он/Она» — тогда тот,
 * кто упомянут последним. Любое другое слово («Защитник Лейлы») — говорящий не из списка персонажей.
 */
function comic_find_speaker(string $phrase, array $cast, string $context): ?int
{
    $words = preg_split('/[\s,:;—–]+/u', trim($phrase), -1, PREG_SPLIT_NO_EMPTY);
    $byRole = static function (string $lw) use ($cast): ?int {
        foreach ($cast as $i => $c) {
            if ($c['roleHead'] !== '' && str_starts_with($lw, $c['roleHead'])) {
                return $i;
            }
        }
        return null;
    };
    foreach ($words as $w) {
        // trim() режет байты, а «…«»» многобайтные — их байт 0x80 совпадает с концом буквы «р». Только регуляркой.
        $w = (string)preg_replace('/^[.!?…«»"()]+|[.!?…«»"()]+$/u', '', $w);
        $lw = comic_lower($w);
        if ($w === '' || in_array($lw, COMIC_SKIP, true)) {
            continue;
        }
        if (in_array($lw, ['он', 'она'], true)) {
            return comic_last_mention($context, $cast);
        }
        foreach ($cast as $i => $c) {
            if ($c['regex'] && preg_match($c['regex'], $w)) {
                return $i;
            }
        }
        if (in_array($lw, COMIC_GROUPS, true)) {
            return null; // «Компания отвечает», «семья Ото требует» — говорит не отдельный персонаж
        }
        if (!preg_match('/^\p{Lu}/u', $w)) {
            // «мать Кири требует»: подлежащее — само слово родства; ищем, чья это роль.
            if (in_array($lw, COMIC_KIN, true)) {
                return $byRole($lw);
            }
            continue; // прочие строчные слова («перед броском») — не подлежащее
        }
        return $byRole($lw);
    }
    return null;
}

/** Текст с подсвеченными именами персонажей (цветом их портрета). */
function comic_highlight(string $text, array $cast): string
{
    $html = e($text);
    foreach ($cast as $c) {
        if (!$c['regex']) {
            continue;
        }
        $html = preg_replace_callback($c['regex'], static fn(array $m): string =>
            '<b class="cm-name" style="--ah:' . $c['hue'] . '">' . $m[0] . '</b>', $html);
    }
    return $html;
}

/** Кто упомянут в тексте (для кадра). */
function comic_present(string $text, array $cast): array
{
    $out = [];
    foreach ($cast as $i => $c) {
        if ($c['regex'] && preg_match($c['regex'], $text)) {
            $out[] = $i;
        }
    }
    return $out;
}

/**
 * Абзац → последовательность подписей и реплик. $prior — текст истории до этого абзаца (для «он/она»).
 * Реплика — «кавычки» от четырёх слов, после двоеточия или перед «— сказал …»; короткие «Щит», «верный яд» — просто текст.
 */
function comic_segments(string $para, array $cast, string $prior = ''): array
{
    $segments = [];
    $speakers = [];
    $pos = 0;
    preg_match_all('/«([^«»]+)»/u', $para, $m, PREG_OFFSET_CAPTURE);
    foreach ($m[0] as $k => [$full, $offset]) {
        $quote = $m[1][$k][0];
        $before = substr($para, $pos, $offset - $pos);
        $after = substr($para, $offset + strlen($full));
        $sayTag = '/^[,.?!]?\s*[—–]\s*((?:' . COMIC_SAY . ')\s+[^.!?…,]{1,40})[.!?…,]?/u';
        $isSpeech = count(preg_split('/\s+/u', trim($quote))) >= 4
            || preg_match('/:\s*$/u', $before) || preg_match($sayTag, $after);
        if (!$isSpeech) {
            continue;
        }
        $context = $prior . substr($para, 0, $offset);
        // «Двадцать минут, — говорит она, — и он скажет всё»: автора реплики убираем из пузыря.
        $inner = null;
        $quote = (string)preg_replace_callback('/,?\s*[—–]\s*(?:' . COMIC_SAY . ')\s+(\p{L}+)([,.]?)\s*[—–]\s*/u',
            static function (array $mm) use (&$inner): string {
                $inner = $mm[1];
                return $mm[2] === '.' ? '. ' : ', ';
            }, $quote);
        // Фраза, в которой стоит реплика: от конца предыдущего предложения.
        $parts = preg_split('/(?<=[.!?…»])\s+/u', $before);
        $lead = (string)end($parts);
        $who = comic_find_speaker($lead, $cast, $context);
        $tag = '';
        if (preg_match($sayTag, $after, $t)) {
            $tag = trim($t[1]);
            $who ??= comic_find_speaker((string)preg_replace('/^\p{L}+\s+/u', '', $tag), $cast, $context); // «— спросил Бранн»
            $after = substr($after, strlen($t[0]));
        }
        if ($who === null && $inner !== null) {
            $who = comic_find_speaker($inner, $cast, $context);
        }
        if (trim($before) !== '') {
            $segments[] = ['type' => 'caption', 'text' => ltrim(trim($before), '.,;:!? ')];
        }
        $segments[] = ['type' => 'speech', 'who' => $who, 'text' => $quote, 'tag' => $tag];
        if ($who !== null) {
            $speakers[] = $who;
        }
        $pos = strlen($para) - strlen($after);
    }
    $rest = trim(substr($para, $pos));
    if ($rest !== '' && !preg_match('/^[.!?…,]+$/u', $rest)) {
        $segments[] = ['type' => 'caption', 'text' => ltrim($rest, '.,; ')];
    }
    return [$segments, array_values(array_unique($speakers))];
}


/**
 * Кадры комикса. $full — с кадрами «Кто есть кто», «Улики» и «Свидетели» (быстрый суд);
 * без него — только мир и сюжет (страница дела, где остальное есть в досье).
 */
function comic_panels(array $s, array $cast, bool $full): array
{
    $panels = [];
    $story = trim((string)$s['story']);
    $role = '';
    if (preg_match('/^Вы\s+[—–-]\s+([^.!?]+)[.!?]\s*/u', $story, $m)) {
        $role = trim($m[1]);
        $story = trim(substr($story, strlen($m[0])));
    }

    $world = $s['world'];
    $panels[] = [
        'kind'    => 'world',
        'title'   => $s['title'],
        'place'   => $world['place'],
        'era'     => $world['era'],
        'text'    => $world['circumstances'],
        'role'    => $role,
        'present' => [],
    ];

    $prior = ''; // текст истории до текущего абзаца — чтобы понять, кто такие «он» и «она»
    foreach (preg_split('/\R{2,}/u', $story) ?: [] as $para) {
        $para = trim($para);
        if ($para === '') {
            continue;
        }
        [$segments, $speakers] = comic_segments($para, $cast, $prior);
        $prior .= $para . "\n";
        // Сначала говорящие, затем остальные упомянутые; не больше четырёх в кадре.
        $present = array_slice(array_values(array_unique(array_merge($speakers, comic_present($para, $cast)))), 0, 4);
        $panels[] = ['kind' => 'story', 'segments' => $segments, 'present' => $present];
    }

    if ($full) {
        $people = array_keys(array_filter($cast, static fn(array $c): bool => !$c['witness']));
        if ($people) {
            $panels[] = ['kind' => 'cast', 'present' => array_slice($people, 0, 5), 'people' => $people];
        }
        if ($s['facts'] || $s['unknowns']) {
            $panels[] = ['kind' => 'evidence', 'facts' => $s['facts'], 'unknowns' => $s['unknowns'], 'present' => []];
        }
        $witnesses = array_keys(array_filter($cast, static fn(array $c): bool => $c['claim'] !== ''));
        if ($witnesses) {
            $panels[] = ['kind' => 'witnesses', 'present' => array_slice($witnesses, 0, 4), 'people' => $witnesses];
        }
        $panels[] = ['kind' => 'decide', 'present' => []];
    }
    return $panels;
}

/* ---------- Фоны миров ---------- */

/** Фоновая сцена для типа мира: слои sc-far / sc-mid / sc-near движутся с разной скоростью. viewBox 0 0 1200 600. */
function comic_scene(string $setting, int $hue): string
{
    $sky = static fn(string $top, string $bottom): string => '<defs><linearGradient id="cm-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="' . $top . '"/><stop offset="1" stop-color="' . $bottom . '"/></linearGradient>'
        . '<radialGradient id="cm-glow" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#fff" stop-opacity=".9"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient></defs>'
        . '<rect width="1200" height="600" fill="url(#cm-sky)"/>';
    $stars = static function (int $n, int $seed, int $maxY = 330): string {
        $out = '<g class="sc-twinkle">';
        for ($i = 0; $i < $n; $i++) {
            $x = ($seed * 37 + $i * 173) % 1200;
            $y = ($seed * 11 + $i * 97) % $maxY;
            $out .= '<circle cx="' . $x . '" cy="' . $y . '" r="' . (1 + $i % 3 * 0.6) . '" fill="#fff" opacity="' . (0.35 + ($i % 5) * 0.12) . '" style="--d:' . ($i % 7) * 0.4 . 's"/>';
        }
        return $out . '</g>';
    };
    $accent = "hsl($hue 95% 62%)";

    switch ($setting) {
        case 'Поселение после апокалипсиса':
            return $sky('#2a1030', '#d9632f')
                . '<circle cx="820" cy="360" r="120" fill="#ffb347" opacity=".85"/><circle cx="820" cy="360" r="190" fill="url(#cm-glow)" opacity=".25"/>'
                . '<g class="sc-far" fill="#4a1d33"><path d="M0 420 L60 420 L60 300 L110 300 L110 340 L150 340 L150 250 L190 262 L205 420 L280 420 L280 330 L330 318 L345 420 L420 420 L430 270 L470 300 L480 230 L520 250 L520 420 L600 420 L620 340 L700 330 L700 420 L760 420 L770 290 L812 300 L820 420 L900 420 L910 330 L960 350 L980 260 L1020 280 L1030 420 L1100 420 L1110 310 L1160 300 L1200 330 L1200 600 L0 600 Z"/></g>'
                . '<g class="sc-mid" fill="#2b0f22"><path d="M0 470 L120 455 L170 380 L210 470 L380 480 L420 410 L440 470 L640 488 L700 430 L740 482 L960 470 L1010 400 L1060 476 L1200 470 L1200 600 L0 600 Z"/>'
                . '<path d="M150 380 L240 330 M240 330 L330 370" stroke="#2b0f22" stroke-width="4" fill="none"/></g>'
                . '<g class="sc-near" fill="#16070f"><path d="M0 540 C200 520 400 560 600 540 C800 520 1000 555 1200 535 L1200 600 L0 600 Z"/></g>'
                . '<g class="sc-dust" fill="#ffcf9a" opacity=".45">' . '<circle cx="100" cy="500" r="2"/><circle cx="400" cy="470" r="1.6"/><circle cx="700" cy="520" r="2.2"/><circle cx="1000" cy="480" r="1.6"/></g>';

        case 'Древнее царство':
            return $sky('#3a1f4f', '#f0a95a')
                . '<circle cx="300" cy="200" r="70" fill="#ffe2a0" opacity=".9"/>'
                . '<g class="sc-far" fill="#7a4a3a"><path d="M760 430 L900 250 L1040 430 Z"/><path d="M960 430 L1060 300 L1160 430 Z" opacity=".8"/></g>'
                . '<g class="sc-mid" fill="#4d2733"><path d="M160 300 L420 230 L680 300 Z"/><rect x="180" y="300" width="480" height="22"/>'
                . implode('', array_map(static fn(int $x): string => '<rect x="' . $x . '" y="322" width="28" height="140"/>', [200, 270, 340, 410, 480, 550, 610]))
                . '<rect x="170" y="460" width="500" height="20"/></g>'
                . '<g class="sc-near" fill="#2a1420"><path d="M0 500 C300 470 600 520 900 495 C1050 485 1150 500 1200 495 L1200 600 L0 600 Z"/>'
                . '<path d="M1010 495 C1000 420 1020 380 1030 360 M1030 360 C990 350 970 370 960 390 M1030 360 C1060 340 1090 350 1100 370 M1030 360 C1000 330 990 320 980 330 M1030 360 C1060 320 1080 320 1090 330" stroke="#2a1420" stroke-width="10" fill="none" stroke-linecap="round"/></g>';

        case 'Средневековое поселение':
            return $sky('#0f1838', '#5a4a8a')
                . $stars(26, 3, 260) . '<circle cx="980" cy="120" r="44" fill="#f4f1d0" opacity=".9"/>'
                . '<g class="sc-far" fill="#252a55"><path d="M0 400 C200 330 380 350 560 380 C760 410 960 320 1200 360 L1200 600 L0 600 Z"/>'
                . '<path d="M820 350 L820 270 L840 270 L840 255 L860 255 L860 270 L880 270 L880 230 L900 215 L920 230 L920 270 L960 270 L960 345 Z"/></g>'
                . '<g class="sc-mid" fill="#171a3a"><path d="M80 470 L80 400 L140 360 L200 400 L200 470 Z M230 470 L230 410 L285 375 L340 410 L340 470 Z M560 470 L560 395 L630 350 L700 395 L700 470 Z"/>'
                . '<rect x="420" y="330" width="40" height="140"/><g class="sc-spin" style="transform-origin:440px 330px"><path d="M440 330 L440 250 L452 250 Z M440 330 L520 330 L520 342 Z M440 330 L440 410 L428 410 Z M440 330 L360 330 L360 318 Z" fill="#2d3363"/></g>'
                . '<rect x="105" y="420" width="14" height="18" fill="#ffd27a"/><rect x="600" y="410" width="14" height="18" fill="#ffd27a"/><rect x="270" y="425" width="12" height="16" fill="#ffd27a"/></g>'
                . '<g class="sc-near" fill="#0b0d22"><path d="M0 500 C250 480 500 520 750 500 C950 485 1100 505 1200 495 L1200 600 L0 600 Z"/></g>';

        case 'Королевство или ханство':
            return $sky('#1a0f3a', '#7a3a7a')
                . $stars(30, 7, 280) . '<path d="M960 90 a50 50 0 1 0 40 80 a40 40 0 1 1 -40 -80 Z" fill="#ffe7a0"/>'
                . '<g class="sc-far" fill="#2c1850"><path d="M0 430 L1200 410 L1200 600 L0 600 Z"/></g>'
                . '<g class="sc-mid" fill="#1d0f38"><rect x="380" y="300" width="440" height="180"/>'
                . '<path d="M520 300 C520 220 680 220 680 300 Z"/><path d="M600 222 L600 196"/><circle cx="600" cy="192" r="6" fill="#ffd27a"/>'
                . '<path d="M410 300 C410 262 470 262 470 300 Z M730 300 C730 262 790 262 790 300 Z"/>'
                . '<rect x="330" y="230" width="30" height="250"/><path d="M330 230 L345 190 L360 230 Z"/><rect x="840" y="230" width="30" height="250"/><path d="M840 230 L855 190 L870 230 Z"/>'
                . '<path d="M570 480 L570 400 C570 370 630 370 630 400 L630 480 Z" fill="#ffcf7a" opacity=".8"/>'
                . '<g class="sc-flag"><path d="M855 190 L855 160 L890 168 L855 178" fill="' . $accent . '"/></g></g>'
                . '<g class="sc-near" fill="#0d0720"><path d="M0 505 L1200 495 L1200 600 L0 600 Z"/><circle class="sc-flicker" cx="200" cy="470" r="8" fill="#ffb347"/><circle class="sc-flicker" cx="1000" cy="470" r="8" fill="#ffb347" style="--d:.6s"/></g>';

        case 'Цивилизация будущего':
            $win = '';
            foreach ([[80, 160, 90], [200, 80, 110], [340, 200, 80], [460, 40, 130], [620, 140, 100], [760, 60, 120], [910, 180, 90], [1040, 100, 120]] as $k => [$x, $y, $w]) {
                $win .= '<rect x="' . $x . '" y="' . $y . '" width="' . $w . '" height="' . (600 - $y) . '" fill="#0c1430" stroke="' . $accent . '" stroke-opacity=".35"/>';
                for ($r = $y + 20; $r < 470; $r += 34) {
                    $win .= '<rect x="' . ($x + 12) . '" y="' . $r . '" width="' . ($w - 24) . '" height="6" fill="' . (($r + $k) % 3 ? '#2be4ff' : '#ff2bd6') . '" opacity="' . (0.15 + (($r * 7 + $k) % 5) * 0.08) . '"/>';
                }
            }
            return $sky('#04040f', '#1a0a3a') . $stars(18, 5, 200)
                . '<g class="sc-far">' . $win . '</g>'
                . '<g class="sc-fly"><rect x="-60" y="150" width="40" height="6" rx="3" fill="#2be4ff"/><rect x="-200" y="230" width="30" height="5" rx="2" fill="#ff2bd6" style="--d:3s"/></g>'
                . '<g class="sc-near"><path d="M0 500 L1200 500 L1200 600 L0 600 Z" fill="#05060f"/><path d="M0 500 L1200 500" stroke="' . $accent . '" stroke-width="3" opacity=".7"/>'
                . '<path d="M0 540 L1200 540 M0 575 L1200 575" stroke="#2be4ff" stroke-opacity=".2"/></g>';

        case 'Космическая колония':
            return $sky('#020208', '#0b1030') . $stars(60, 9, 480)
                . '<g class="sc-far"><circle cx="880" cy="190" r="120" fill="hsl(' . $hue . ' 60% 45%)" opacity=".85"/><circle cx="850" cy="160" r="120" fill="#020208" opacity=".35"/>'
                . '<ellipse cx="880" cy="190" rx="200" ry="34" fill="none" stroke="#c7d2ff" stroke-opacity=".55" stroke-width="5" transform="rotate(-14 880 190)"/></g>'
                . '<g class="sc-mid"><path d="M0 470 C200 440 420 455 600 450 C820 445 1000 430 1200 450 L1200 600 L0 600 Z" fill="#2a2f45"/>'
                . '<path d="M220 452 a90 90 0 0 1 180 0 Z" fill="rgba(160,220,255,.18)" stroke="#9fdcff" stroke-width="3"/><path d="M450 452 a60 60 0 0 1 120 0 Z" fill="rgba(160,220,255,.15)" stroke="#9fdcff" stroke-width="3"/>'
                . '<rect x="300" y="420" width="18" height="30" fill="#ffd27a" opacity=".8"/><path d="M700 450 L700 330 M700 330 L680 350 M700 330 L720 350" stroke="#c7d2ff" stroke-width="4"/><circle class="sc-blink" cx="700" cy="326" r="6" fill="#ff4d6d"/></g>'
                . '<g class="sc-near"><path d="M0 520 C300 505 700 530 1200 512 L1200 600 L0 600 Z" fill="#161a2b"/><circle cx="150" cy="560" r="14" fill="#11141f"/><circle cx="980" cy="555" r="20" fill="#11141f"/></g>';

        case 'Вымышленное племя':
            return $sky('#1d2b55', '#ff9a6a')
                . '<circle cx="600" cy="420" r="90" fill="#ffcf8a" opacity=".9"/>'
                . '<g class="sc-far"><path d="M0 420 L1200 420 L1200 470 L0 470 Z" fill="#3a5a8a"/><path d="M0 430 L1200 430" stroke="#ffcf8a" stroke-opacity=".5" stroke-width="3"/></g>'
                . '<g class="sc-mid" fill="#1f1a2e"><path d="M120 470 L190 370 L260 470 Z M300 470 L360 385 L420 470 Z M820 470 L900 360 L980 470 Z"/>'
                . '<path d="M1060 470 C1050 400 1070 360 1080 340 M1080 340 C1040 330 1020 350 1010 370 M1080 340 C1110 320 1140 330 1150 350 M1080 340 C1060 310 1040 305 1030 315" stroke="#1f1a2e" stroke-width="10" fill="none" stroke-linecap="round"/></g>'
                . '<g class="sc-near"><path d="M0 500 C300 485 900 515 1200 495 L1200 600 L0 600 Z" fill="#120f1d"/>'
                . '<g class="sc-flicker"><path d="M560 500 C555 470 575 455 580 440 C590 460 610 470 600 500 Z" fill="#ff8a3a"/><path d="M570 500 C570 482 582 474 585 465 C592 478 598 485 592 500 Z" fill="#ffd27a"/></g></g>';

        default: // Полностью вымышленное общество и всё остальное
            return $sky('#101a3a', '#3b5f9a') . $stars(14, 4, 200)
                . '<g class="sc-far" fill="#2a3a6a"><path d="M150 300 C150 260 330 260 330 300 L280 360 L200 360 Z"/><rect x="215" y="200" width="20" height="100"/><rect x="250" y="160" width="26" height="140"/>'
                . '<path d="M820 260 C820 220 1040 220 1040 260 L980 330 L880 330 Z"/><rect x="870" y="150" width="24" height="110"/><rect x="920" y="110" width="30" height="150"/><rect x="975" y="170" width="22" height="90"/></g>'
                . '<g class="sc-fly"><ellipse cx="-140" cy="130" rx="70" ry="22" fill="' . $accent . '" opacity=".75"/><rect x="-160" y="150" width="40" height="14" rx="4" fill="#1a2350"/></g>'
                . '<g class="sc-mid" fill="#18224a"><path d="M380 470 L380 260 L420 230 L460 260 L460 470 Z M500 470 L500 300 L560 270 L620 300 L620 470 Z M660 470 L660 220 L700 190 L740 220 L740 470 Z"/>'
                . '<rect x="400" y="300" width="10" height="12" fill="#ffd27a"/><rect x="540" y="330" width="10" height="12" fill="#ffd27a"/><rect x="690" y="260" width="10" height="12" fill="#ffd27a"/></g>'
                . '<g class="sc-near"><path d="M0 500 C300 480 900 520 1200 495 L1200 600 L0 600 Z" fill="#0c1230"/></g>';
    }
}

/** Положения «камеры» для кадров — фон плавно панорамируется между ними. */
function comic_camera(int $i): string
{
    $cams = ['0 0 1', '-4 1.5 1.08', '4 -1 1.14', '-2 2 1.1', '3 1 1.16', '-5 -1 1.12', '2 2.5 1.06'];
    return $cams[$i % count($cams)];
}
