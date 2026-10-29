<?php
declare(strict_types=1);

defined('APP_ROOT') || exit;

/*
 * Профиль судьи: какой вы судья — по вашим вердиктам. Считается из таблицы votes для анонимного id игрока
 * (cookie), поэтому живёт в этом браузере и не требует регистрации.
 *
 * Склонность по показателю мира — не «сколько доверия дал ваш выбор», а «давал ли ваш выбор больше доверия,
 * чем другие варианты того же дела». Так профиль говорит о вас, а не о том, что в большинстве дел почти
 * любой вариант поднимает доверие. Считаются только дела, где варианты по этому показателю различаются,
 * поэтому редкие показатели (ресурсы) весят столько же, сколько частые (авторитет).
 */

/** Сколько вердиктов с выбранным вариантом нужно, чтобы профиль открылся. */
const JUDGE_MIN_VERDICTS = 5;

/**
 * Склонность (−1…+1), ниже которой стиль считается взвешенным. Подобрана симуляцией на реальных делах:
 * последовательный стиль (всегда за доверие, всегда за порядок…) даёт по главной оси 0.3–0.9,
 * а у случайного выбора склонности с каждым вердиктом стягиваются к нулю.
 */
const JUDGE_NEUTRAL = 0.25;

/** Сколько дел с выбором по показателю нужно, чтобы склонность по нему учитывалась в стиле. */
const JUDGE_MIN_RELEVANT = 3;

const JUDGE_ARCHETYPES = [
    'order' => [
        'name' => 'Страж порядка', 'icon' => 'shield',
        'desc' => 'Закон для вас один для всех. Вы укрепляете порядок и власть, даже когда это стоит людям доверия.',
        'strength' => 'Ваши решения предсказуемы — на них можно строить.',
        'blind' => 'За правилом легко не заметить человека.',
    ],
    'wise' => [
        'name' => 'Мудрый правитель', 'icon' => 'crown',
        'desc' => 'Вы ищете решения, которые укрепляют порядок и при этом не отталкивают людей. Редкое сочетание.',
        'strength' => 'Умеете совместить строгость и доверие.',
        'blind' => 'Иногда компромисс — это способ не выбирать.',
    ],
    'mercy' => [
        'name' => 'Милосердный судья', 'icon' => 'heart-whole',
        'desc' => 'Вы видите за делом человека и готовы рискнуть порядком ради справедливости к нему.',
        'strength' => 'Люди вам доверяют.',
        'blind' => 'Мягкость легко принять за слабость.',
    ],
    'stern' => [
        'name' => 'Суровый судья', 'icon' => 'gavel',
        'desc' => 'Ваши приговоры строги, и люди это чувствуют: доверие к власти падает, зато нарушать закон боятся.',
        'strength' => 'Вас трудно разжалобить.',
        'blind' => 'Страх — не то же самое, что уважение.',
    ],
    'reformer' => [
        'name' => 'Реформатор', 'icon' => 'sparkles',
        'desc' => 'Вы не держитесь за старый порядок и меняете правила, если они мешают людям.',
        'strength' => 'Видите, где закон устарел.',
        'blind' => 'Сломать проще, чем построить заново.',
    ],
    'fire' => [
        'name' => 'Игрок с огнём', 'icon' => 'flame',
        'desc' => 'Ваши решения раскачивают мир: слабеет и порядок, и доверие. Скучно с вами не бывает.',
        'strength' => 'Не боитесь непопулярных решений.',
        'blind' => 'Мир может не выдержать ещё одного эксперимента.',
    ],
    'pragmatic' => [
        'name' => 'Прагматик', 'icon' => 'box',
        'desc' => 'Вы считаете ресурсы: красивые жесты не накормят поселение, а запасы — накормят.',
        'strength' => 'С вами не пропадёшь в голодный год.',
        'blind' => 'Не всё в мире измеряется запасами.',
    ],
    'generous' => [
        'name' => 'Щедрый покровитель', 'icon' => 'coins',
        'desc' => 'Вы готовы платить из общей казны, лишь бы никто не остался без помощи.',
        'strength' => 'Ваши решения спасают людей здесь и сейчас.',
        'blind' => 'Казна не бездонна.',
    ],
    'diplomat' => [
        'name' => 'Дипломат', 'icon' => 'star',
        'desc' => 'Вы думаете о том, как решение выглядит со стороны: доброе имя для вас — тоже ресурс.',
        'strength' => 'Умеете сохранить лицо в любом споре.',
        'blind' => 'Правильное решение не всегда красиво выглядит.',
    ],
    'maverick' => [
        'name' => 'Неудобный судья', 'icon' => 'target',
        'desc' => 'Вы готовы потерять репутацию ради принципа и не оглядываетесь на чужое мнение.',
        'strength' => 'Вас не сдвинуть общественным мнением.',
        'blind' => 'Принципиальность без союзников мало что меняет.',
    ],
    'balanced' => [
        'name' => 'Взвешенный судья', 'icon' => 'scale',
        'desc' => 'Ваши решения не толкают мир в одну сторону: вы избегаете крайностей и взвешиваете каждое дело заново.',
        'strength' => 'Ваши решения трудно оспорить.',
        'blind' => 'Иногда от судьи ждут смелости.',
    ],
];

/**
 * Склонности по показателям. $verdicts — список ['chosen' => эффекты выбранного решения,
 * 'options' => [эффекты каждого варианта дела]].
 *
 * В каждом деле, где варианты по показателю различаются, выбор получает ранг
 * r = (сколько других вариантов дают меньше − сколько дают больше) / (вариантов − 1) ∈ [−1, 1].
 * Склонность lean — средний ранг. Случайный выбор в среднем даёт ровно 0, как бы ни были устроены дела
 * (среднее по вариантам так не умеет: один «выброс» среди вариантов сдвигал всех в одну сторону).
 * more/less — в скольких делах ранг был выше/ниже нуля, relevant — сколько дел учтено.
 */
function judge_leans(array $verdicts): array
{
    $out = [];
    foreach (array_keys(METRICS) as $m) {
        $more = $less = $relevant = 0;
        $sum = 0.0;
        foreach ($verdicts as $v) {
            $vals = array_map(static fn(array $fx): int => (int)($fx[$m] ?? 0), $v['options']);
            if (count($vals) < 2 || max($vals) === min($vals)) {
                continue;
            }
            $chosen = (int)($v['chosen'][$m] ?? 0);
            $lower = count(array_filter($vals, static fn(int $x): bool => $x < $chosen));
            $higher = count(array_filter($vals, static fn(int $x): bool => $x > $chosen));
            $r = ($lower - $higher) / (count($vals) - 1);
            $relevant++;
            $sum += $r;
            if ($r > 0) {
                $more++;
            } elseif ($r < 0) {
                $less++;
            }
        }
        $out[$m] = ['more' => $more, 'less' => $less, 'relevant' => $relevant, 'lean' => $relevant ? $sum / $relevant : 0.0];
    }
    return $out;
}

/**
 * Стиль по склонностям. Главные оси — порядок (авторитет + стабильность) и доверие: в делах они часто
 * идут в разные стороны (строгий вариант поднимает власть и роняет доверие), поэтому стиль задаёт их
 * сочетание, а не одна «самая сильная» ось. Ресурсы и репутация решают, только если выражены сильнее
 * обеих. Показатели, по которым у игрока меньше JUDGE_MIN_RELEVANT дел с выбором, не учитываются.
 */
function judge_archetype(array $leans, float $neutral = JUDGE_NEUTRAL): string
{
    $lean = static fn(string $m): float => ($leans[$m]['relevant'] ?? 0) >= JUDGE_MIN_RELEVANT ? (float)$leans[$m]['lean'] : 0.0;
    $order = ($lean('authority') + $lean('stability')) / 2;
    $mercy = $lean('trust');
    $thrift = $lean('resources');
    $image = $lean('reputation');

    $core = max(abs($order), abs($mercy));
    $side = max(abs($thrift), abs($image));
    if (max($core, $side) < $neutral) {
        return 'balanced';
    }
    if ($side > $core) {
        if (abs($thrift) >= abs($image)) {
            return $thrift > 0 ? 'pragmatic' : 'generous';
        }
        return $image > 0 ? 'diplomat' : 'maverick';
    }
    $o = $order >= $neutral ? 1 : ($order <= -$neutral ? -1 : 0);
    $t = $mercy >= $neutral ? 1 : ($mercy <= -$neutral ? -1 : 0);
    return match (true) {
        $o > 0 && $t > 0 => 'wise',
        $o > 0           => 'order',     // порядок любой ценой, в том числе ценой доверия
        $o < 0 && $t > 0 => abs($mercy) >= 0.75 * abs($order) ? 'mercy' : 'reformer',
        $o < 0 && $t < 0 => 'fire',
        $o < 0           => 'reformer',
        $t > 0           => 'mercy',
        default          => 'stern',     // доверие падает, а порядок от этого не крепнет
    };
}

/** Эффекты решений одобренных дел: [situation_id => [ключ решения => эффекты]]. Один раз за запрос. */
function judge_effects_map(): array
{
    static $map = null;
    if ($map !== null) {
        return $map;
    }
    $map = [];
    foreach (db()->query("SELECT id, data FROM situations WHERE status = 'approved'") as $r) {
        $data = json_decode((string)$r['data'], true);
        foreach (is_array($data['decisions'] ?? null) ? $data['decisions'] : [] as $d) {
            if (isset($d['key'])) {
                $map[(int)$r['id']][$d['key']] = is_array($d['effects'] ?? null) ? $d['effects'] : [];
            }
        }
    }
    return $map;
}

/** Профиль игрока: стиль, склонности по показателям, совпадение с большинством, скорость, смелые решения. */
function judge_profile(string $voter): array
{
    $st = db()->prepare("SELECT v.situation_id, v.option_key, v.duration_ms, s.title, s.category
        FROM votes v JOIN situations s ON s.id = v.situation_id
        WHERE v.voter = ? AND s.status = 'approved' ORDER BY v.created_at, v.id");
    $st->execute([$voter]);
    $rows = $st->fetchAll();
    $effects = judge_effects_map();
    $counts = vote_counts();

    $verdicts = [];
    $own = 0;
    $durations = [];
    $withMajority = 0;
    $compared = 0;
    $boldest = null;
    $categories = [];

    foreach ($rows as $r) {
        $sid = (int)$r['situation_id'];
        $key = (string)$r['option_key'];
        $categories[$r['category']] = ($categories[$r['category']] ?? 0) + 1;
        if ($r['duration_ms'] !== null) {
            $durations[] = (int)$r['duration_ms'];
        }

        // Как решили остальные (без этого игрока).
        $others = $counts[$sid] ?? [];
        if (isset($others[$key])) {
            $others[$key]--;
        }
        $others = array_filter($others);
        $total = array_sum($others);
        if ($total > 0) {
            $compared++;
            if (($others[$key] ?? 0) === max($others)) {
                $withMajority++;
            }
            $share = ($others[$key] ?? 0) / $total;
            if ($total >= 3 && ($boldest === null || $share < $boldest['share'])) {
                $boldest = ['id' => $sid, 'title' => (string)$r['title'], 'share' => $share, 'others' => $total];
            }
        }

        if ($key === 'other') {
            $own++;
        } elseif (isset($effects[$sid][$key])) {
            $verdicts[] = ['chosen' => $effects[$sid][$key], 'options' => array_values($effects[$sid])];
        }
    }

    $leans = judge_leans($verdicts);
    $decided = count($verdicts);
    sort($durations);
    arsort($categories);

    return [
        'verdicts'      => count($rows),
        'decided'       => $decided,
        'own'           => $own,
        'leans'         => $leans,
        'archetype'     => $decided >= JUDGE_MIN_VERDICTS ? judge_archetype($leans) : null,
        'left'          => max(0, JUDGE_MIN_VERDICTS - $decided),
        'with_majority' => $withMajority,
        'compared'      => $compared,
        'median_ms'     => count($durations) >= 3 ? $durations[intdiv(count($durations), 2)] : null,
        // «Смелое» решение — когда с вами согласились не больше трети остальных игроков.
        'boldest'       => $boldest !== null && $boldest['share'] <= 0.34 ? $boldest : null,
        'top_category'  => $categories && reset($categories) >= 3 ? array_key_first($categories) : null,
        'quick'         => quick_stats($voter),
    ];
}

/** Как распределены стили среди игроков с открытым профилем: ['players' => N, 'shares' => [стиль => доля 0..1]]. */
function judge_archetype_shares(): array
{
    $effects = judge_effects_map();
    $byVoter = [];
    foreach (db()->query("SELECT voter, situation_id, option_key FROM votes WHERE option_key <> 'other'") as $r) {
        $sid = (int)$r['situation_id'];
        if (isset($effects[$sid][$r['option_key']])) {
            $byVoter[$r['voter']][] = ['chosen' => $effects[$sid][$r['option_key']], 'options' => array_values($effects[$sid])];
        }
    }
    $tally = [];
    $players = 0;
    foreach ($byVoter as $verdicts) {
        if (count($verdicts) >= JUDGE_MIN_VERDICTS) {
            $type = judge_archetype(judge_leans($verdicts));
            $tally[$type] = ($tally[$type] ?? 0) + 1;
            $players++;
        }
    }
    return ['players' => $players, 'shares' => array_map(static fn(int $n): float => $n / $players, $tally)];
}

/**
 * Что сказать игроку после вердикта: профиль открылся, стиль изменился или всё как было.
 * Последний показанный стиль хранится в сессии.
 */
function judge_event(array $profile): ?string
{
    $prev = $_SESSION['judge_archetype'] ?? null;
    $now = $profile['archetype'];
    $_SESSION['judge_archetype'] = $now;
    if ($now === null) {
        return null;
    }
    // «Открыт» — только на том вердикте, который открыл профиль (а не после истёкшей сессии).
    if ($profile['decided'] === JUDGE_MIN_VERDICTS && $prev === null) {
        return 'unlocked';
    }
    return $prev !== null && $prev !== $now ? 'changed' : null;
}
