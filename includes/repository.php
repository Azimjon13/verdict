<?php
declare(strict_types=1);

defined('APP_ROOT') || exit;

/** Пустая ситуация по структуре шаблона. */
function situation_blank(): array
{
    return [
        'category'     => '',
        'type'         => 'private',
        'title'        => '',
        'author'       => '',
        'world'        => ['setting' => '', 'place' => '', 'era' => '', 'circumstances' => ''],
        'story'        => '',
        'participants' => [],
        'facts'        => [],
        'unknowns'     => [],
        'witnesses'    => [],
        'decisions'    => [],
        'hidden'       => '',
        'ambiguity'    => ['conflict' => '', 'for_one' => '', 'for_other' => '', 'divide' => ''],
        'continuation' => ['possible' => false, 'text' => ''],
        'notes'        => '',
        'checklist'    => [],
    ];
}

function situation_hydrate(array $row): array
{
    $data = json_decode((string)$row['data'], true);
    $s = array_replace(situation_blank(), is_array($data) ? $data : []);
    $s['world'] += ['setting' => '', 'place' => '', 'era' => '', 'circumstances' => ''];
    $s['id']         = (int)$row['id'];
    $s['category']   = (string)$row['category'];
    $s['type']       = (string)$row['type'];
    $s['title']      = (string)$row['title'];
    $s['author']     = (string)$row['author'];
    $s['user_id']    = isset($row['user_id']) ? (int)$row['user_id'] : null;
    $s['status']     = (string)$row['status'];
    $s['created_at'] = (string)$row['created_at'];
    $s['updated_at'] = (string)$row['updated_at'];
    $s['decisions'] = decisions_with_uids($s['decisions']);
    return $s;
}

/**
 * У каждого решения есть постоянный uid: буква (A, B, …) — это только позиция и меняется при правке,
 * а голоса привязаны к букве, поэтому при сохранении их переносят по uid (votes_remap).
 * Решениям, сохранённым до появления uid, он выводится из буквы — это стабильно до первой правки.
 */
function decisions_with_uids(array $decisions): array
{
    foreach ($decisions as $k => $d) {
        if (is_array($d) && empty($d['uid'])) {
            $decisions[$k]['uid'] = 'k' . ($d['key'] ?? chr(65 + (int)$k));
        }
    }
    return $decisions;
}

function situation_payload(array $s): array
{
    return array_intersect_key(array_replace(situation_blank(), $s), situation_blank());
}

function situation_find(int $id): ?array
{
    $st = db()->prepare('SELECT * FROM situations WHERE id = ?');
    $st->execute([$id]);
    $row = $st->fetch();
    return $row ? situation_hydrate($row) : null;
}

function situations_list(array $filter = []): array
{
    $where = [];
    $params = [];
    foreach (['status', 'category', 'type', 'user_id'] as $field) {
        if (!empty($filter[$field])) {
            $where[] = "$field = ?";
            $params[] = $filter[$field];
        }
    }
    $sql = 'SELECT * FROM situations'
        . ($where ? ' WHERE ' . implode(' AND ', $where) : '')
        . ' ORDER BY id ' . (($filter['order'] ?? 'new') === 'old' ? 'ASC' : 'DESC');
    $st = db()->prepare($sql);
    $st->execute($params);
    return array_map('situation_hydrate', $st->fetchAll());
}

function situation_insert(PDO $pdo, array $s, string $status, ?int $userId = null): int
{
    $now = date('Y-m-d H:i:s');
    $st = $pdo->prepare('INSERT INTO situations (category, type, title, author, user_id, status, data, created_at, updated_at)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)');
    $st->execute([
        $s['category'], $s['type'], $s['title'], $s['author'] ?? '', $userId, $status,
        json_encode(situation_payload($s), JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE), $now, $now,
    ]);
    return (int)$pdo->lastInsertId();
}

/**
 * $status — новый статус (например, черновик → на отбор); null оставляет текущий.
 * Голоса и догадки переезжают вслед за своими решениями, если у тех сменилась буква.
 * Возвращает ['moved' => перенесено голосов, 'deleted' => удалено голосов за убранные решения].
 */
function situation_update(int $id, array $s, ?string $status = null): array
{
    $pdo = db();
    $pdo->beginTransaction();
    try {
        $old = $pdo->prepare('SELECT data FROM situations WHERE id = ? FOR UPDATE');
        $old->execute([$id]);
        $oldData = json_decode((string)$old->fetchColumn(), true);
        $oldDecisions = decisions_with_uids(is_array($oldData['decisions'] ?? null) ? $oldData['decisions'] : []);

        $st = $pdo->prepare('UPDATE situations SET category = ?, type = ?, title = ?, author = ?, status = COALESCE(?, status), data = ?, updated_at = ? WHERE id = ?');
        $st->execute([
            $s['category'], $s['type'], $s['title'], $s['author'] ?? '', $status,
            json_encode(situation_payload($s), JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE), date('Y-m-d H:i:s'), $id,
        ]);
        $result = votes_remap($pdo, $id, $oldDecisions, $s['decisions']);
        $pdo->commit();
        return $result;
    } catch (Throwable $e) {
        $pdo->rollBack();
        throw $e;
    }
}

/**
 * Переносит голоса и догадки «Быстрого суда» со старых букв решений на новые (по uid).
 * Голоса за удалённые решения удаляются; догадка о них сбрасывается, но заработанное очко остаётся.
 */
function votes_remap(PDO $pdo, int $situationId, array $oldDecisions, array $newDecisions): array
{
    $newKeyByUid = [];
    foreach ($newDecisions as $d) {
        $newKeyByUid[$d['uid'] ?? ''] = $d['key'];
    }
    $changes = [];
    foreach ($oldDecisions as $j => $d) {
        $oldKey = (string)($d['key'] ?? chr(65 + (int)$j));
        $newKey = $newKeyByUid[$d['uid'] ?? ''] ?? null;
        if ($newKey !== $oldKey) {
            $changes[$oldKey] = $newKey;
        }
    }
    if (!$changes) {
        return ['moved' => 0, 'deleted' => 0];
    }

    // Сначала «паркуем» меняющиеся буквы под «~», чтобы перестановки (A↔B) не смешались.
    foreach (['option_key', 'guess_key'] as $col) {
        $park = $pdo->prepare("UPDATE votes SET $col = CONCAT('~', $col) WHERE situation_id = ? AND $col = ?");
        foreach (array_keys($changes) as $oldKey) {
            $park->execute([$situationId, $oldKey]);
        }
    }
    $moved = 0;
    $deleted = 0;
    foreach ($changes as $oldKey => $newKey) {
        $parked = '~' . $oldKey;
        if ($newKey === null) {
            $st = $pdo->prepare('DELETE FROM votes WHERE situation_id = ? AND option_key = ?');
            $st->execute([$situationId, $parked]);
            $deleted += $st->rowCount();
            $pdo->prepare('UPDATE votes SET guess_key = NULL WHERE situation_id = ? AND guess_key = ?')->execute([$situationId, $parked]);
        } else {
            $st = $pdo->prepare('UPDATE votes SET option_key = ? WHERE situation_id = ? AND option_key = ?');
            $st->execute([$newKey, $situationId, $parked]);
            $moved += $st->rowCount();
            $pdo->prepare('UPDATE votes SET guess_key = ? WHERE situation_id = ? AND guess_key = ?')->execute([$newKey, $situationId, $parked]);
        }
    }
    return ['moved' => $moved, 'deleted' => $deleted];
}

function situation_set_status(int $id, string $status): void
{
    db()->prepare('UPDATE situations SET status = ?, updated_at = ? WHERE id = ?')
        ->execute([$status, date('Y-m-d H:i:s'), $id]);
}

function situation_delete(int $id): void
{
    db()->prepare('DELETE FROM votes WHERE situation_id = ?')->execute([$id]);
    db()->prepare('DELETE FROM situations WHERE id = ?')->execute([$id]);
}

function situation_decision(array $s, string $key): ?array
{
    foreach ($s['decisions'] as $d) {
        if (($d['key'] ?? '') === $key) {
            return $d;
        }
    }
    return null;
}

function decision_has_consequences(array $d): bool
{
    return trim(($d['immediate'] ?? '') . ($d['longterm'] ?? '') . ($d['characters'] ?? '') . ($d['world'] ?? '')) !== '';
}

/* ---------- Голоса ---------- */

/** [situation_id => [option_key => count]] */
function vote_counts(): array
{
    $out = [];
    foreach (db()->query('SELECT situation_id, option_key, COUNT(*) AS n FROM votes GROUP BY situation_id, option_key') as $r) {
        $out[(int)$r['situation_id']][$r['option_key']] = (int)$r['n'];
    }
    return $out;
}

function vote_counts_for(int $situationId): array
{
    $st = db()->prepare('SELECT option_key, COUNT(*) AS n FROM votes WHERE situation_id = ? GROUP BY option_key');
    $st->execute([$situationId]);
    $out = [];
    foreach ($st->fetchAll() as $r) {
        $out[$r['option_key']] = (int)$r['n'];
    }
    return $out;
}

/** [situation_id => option_key] для текущего игрока. */
function votes_of_voter(string $voter): array
{
    $st = db()->prepare('SELECT situation_id, option_key FROM votes WHERE voter = ?');
    $st->execute([$voter]);
    $out = [];
    foreach ($st->fetchAll() as $r) {
        $out[(int)$r['situation_id']] = $r['option_key'];
    }
    return $out;
}

function vote_find(int $situationId, string $voter): ?array
{
    $st = db()->prepare('SELECT * FROM votes WHERE situation_id = ? AND voter = ?');
    $st->execute([$situationId, $voter]);
    return $st->fetch() ?: null;
}

/**
 * $extra: mode (full|quick), duration_ms, guess_key, guess_correct.
 * Повторный голос в полном деле не стирает прежнюю догадку из «Быстрого суда».
 */
function vote_save(int $situationId, string $voter, string $key, string $reasoning, array $extra = []): void
{
    $now = date('Y-m-d H:i:s');
    $mode = ($extra['mode'] ?? 'full') === 'quick' ? 'quick' : 'full';
    $duration = $extra['duration_ms'] ?? null;
    $guess = $extra['guess_key'] ?? null;
    $correct = $extra['guess_correct'] ?? null;
    $st = db()->prepare('INSERT INTO votes (situation_id, option_key, reasoning, guess_key, guess_correct, mode, duration_ms, voter, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON DUPLICATE KEY UPDATE option_key = ?, reasoning = ?, mode = ?, duration_ms = ?, created_at = ?,
            guess_key = IF(? IS NULL, guess_key, ?), guess_correct = IF(? IS NULL, guess_correct, ?)');
    $st->execute([
        $situationId, $key, $reasoning, $guess, $correct, $mode, $duration, $voter, $now,
        $key, $reasoning, $mode, $duration, $now,
        $guess, $guess, $guess, $correct,
    ]);
}

/**
 * Варианты, которые выбрало большинство ДРУГИХ игроков (до этого голоса). Пусто — сравнивать не с кем.
 * При ничьей большинство — все лидирующие варианты.
 */
function majority_keys(int $situationId, string $voter): array
{
    $counts = vote_counts_for($situationId);
    $mine = vote_find($situationId, $voter);
    if ($mine && isset($counts[$mine['option_key']])) {
        $counts[$mine['option_key']]--;
    }
    $counts = array_filter($counts);
    if (!$counts) {
        return [];
    }
    $max = max($counts);
    return array_keys(array_filter($counts, static fn(int $n): bool => $n === $max));
}

/** Счёт «Быстрого суда»: угадано большинство, всего догадок, текущая серия угаданных подряд. */
function quick_stats(string $voter): array
{
    $st = db()->prepare('SELECT guess_correct FROM votes WHERE voter = ? AND guess_correct IS NOT NULL ORDER BY created_at DESC, id DESC');
    $st->execute([$voter]);
    $results = array_map('intval', $st->fetchAll(PDO::FETCH_COLUMN));
    $streak = 0;
    foreach ($results as $r) {
        if ($r !== 1) {
            break;
        }
        $streak++;
    }
    return ['score' => array_sum($results), 'guesses' => count($results), 'streak' => $streak];
}

/** Случайное одобренное дело, по которому игрок ещё не выносил вердикт. */
function random_open_case(string $voter, int $exceptId = 0): ?array
{
    $done = votes_of_voter($voter);
    $open = array_values(array_filter(situations_list(['status' => 'approved']),
        static fn(array $s): bool => !isset($done[$s['id']]) && $s['id'] !== $exceptId));
    return $open ? $open[array_rand($open)] : null;
}

/** Среднее время на решение по делу (мс) и сколько голосов его измерили. */
function vote_duration_stats(int $situationId): array
{
    $st = db()->prepare('SELECT AVG(duration_ms) AS avg_ms, COUNT(duration_ms) AS n FROM votes WHERE situation_id = ? AND duration_ms IS NOT NULL');
    $st->execute([$situationId]);
    $r = $st->fetch();
    return ['avg_ms' => $r['n'] ? (int)round((float)$r['avg_ms']) : null, 'n' => (int)$r['n']];
}

function stats_overview(): array
{
    $counts = ['pending' => 0, 'approved' => 0, 'rejected' => 0];
    foreach (db()->query('SELECT status, COUNT(*) AS n FROM situations GROUP BY status') as $r) {
        $counts[$r['status']] = (int)$r['n'];
    }
    $counts['total'] = $counts['pending'] + $counts['approved'] + $counts['rejected'];
    $counts['votes'] = (int)db()->query('SELECT COUNT(*) FROM votes')->fetchColumn();
    $counts['players'] = (int)db()->query('SELECT COUNT(DISTINCT voter) FROM votes')->fetchColumn();
    return $counts;
}

/** Следующее нерассмотренное дело для игрока. */
function next_case(int $currentId, string $voter): ?array
{
    $done = votes_of_voter($voter);
    $after = null;
    $any = null;
    foreach (situations_list(['status' => 'approved', 'order' => 'old']) as $s) {
        if ($s['id'] === $currentId || isset($done[$s['id']])) {
            continue;
        }
        if ($after === null && $s['id'] > $currentId) {
            $after = $s;
        }
        $any ??= $s;
    }
    return $after ?? $any;
}

/* ---------- Ввод из формы ---------- */

function input_str($value, int $max = 2000): string
{
    if (!is_scalar($value)) {
        return '';
    }
    $value = trim(str_replace("\r\n", "\n", mb_scrub((string)$value, 'UTF-8')));
    return mb_substr($value, 0, $max);
}

function input_rows($rows, array $fields, int $maxRows, int $maxLen = 2000): array
{
    if (!is_array($rows)) {
        return [];
    }
    $out = [];
    foreach ($rows as $row) {
        if (!is_array($row)) {
            continue;
        }
        $clean = [];
        foreach ($fields as $f) {
            $clean[$f] = input_str($row[$f] ?? '', $maxLen);
        }
        if (implode('', $clean) === '') {
            continue;
        }
        $out[] = $clean;
        if (count($out) >= $maxRows) {
            break;
        }
    }
    return $out;
}

function input_list($rows, int $maxRows, int $maxLen = 1000): array
{
    if (!is_array($rows)) {
        return [];
    }
    $out = [];
    foreach ($rows as $row) {
        $v = input_str($row, $maxLen);
        if ($v !== '') {
            $out[] = $v;
        }
        if (count($out) >= $maxRows) {
            break;
        }
    }
    return $out;
}

function situation_from_input(array $in): array
{
    $s = situation_blank();
    $s['category'] = input_str($in['category'] ?? '', 40);
    $s['type']     = input_str($in['type'] ?? '', 20);
    $s['title']    = input_str($in['title'] ?? '', 120);
    $s['author']   = input_str($in['author'] ?? '', 80);

    $w = is_array($in['world'] ?? null) ? $in['world'] : [];
    $setting = input_str($w['setting'] ?? '', 80);
    $s['world'] = [
        'setting'       => in_array($setting, array_column(WORLDS, 'name'), true) ? $setting : '',
        'place'         => input_str($w['place'] ?? '', 160),
        'era'           => input_str($w['era'] ?? '', 160),
        'circumstances' => input_str($w['circumstances'] ?? '', 2000),
    ];

    $s['story']        = input_str($in['story'] ?? '', 6000);
    $s['participants'] = input_rows($in['participants'] ?? [], ['name', 'age', 'role', 'relations', 'description'], 12, 600);
    $s['facts']        = input_list($in['facts'] ?? [], 20);
    $s['unknowns']     = input_list($in['unknowns'] ?? [], 20);
    $s['witnesses']    = $s['type'] === 'private'
        ? []
        : input_rows($in['witnesses'] ?? [], ['name', 'claim', 'trust', 'interest'], 8, 1000);

    $decisions = [];
    $seenUids = [];
    foreach (is_array($in['decisions'] ?? null) ? $in['decisions'] : [] as $d) {
        if (!is_array($d)) {
            continue;
        }
        $row = [
            'text'       => input_str($d['text'] ?? '', 300),
            'why'        => input_str($d['why'] ?? '', 1000),
            'immediate'  => input_str($d['immediate'] ?? '', 1000),
            'longterm'   => input_str($d['longterm'] ?? '', 1000),
            'characters' => input_str($d['characters'] ?? '', 1000),
            'world'      => input_str($d['world'] ?? '', 1000),
        ];
        if (implode('', $row) === '') {
            continue;
        }
        $effects = [];
        $raw = is_array($d['effects'] ?? null) ? $d['effects'] : [];
        foreach (array_keys(METRICS) as $m) {
            $v = (int)($raw[$m] ?? 0);
            if ($v !== 0) {
                $effects[$m] = max(-3, min(3, $v));
            }
        }
        $row['effects'] = $effects;
        $row['key'] = chr(65 + count($decisions));
        // Постоянный uid решения приходит из формы; новым строкам и подделкам выдаём новый.
        $uid = input_str($d['uid'] ?? '', 16);
        if (!preg_match('/^[A-Za-z0-9]{1,16}$/', $uid) || isset($seenUids[$uid])) {
            $uid = 'n' . bin2hex(random_bytes(4));
        }
        $seenUids[$uid] = true;
        $row['uid'] = $uid;
        $decisions[] = $row;
        if (count($decisions) >= MAX_DECISIONS) {
            break;
        }
    }
    $s['decisions'] = $decisions;

    $s['hidden'] = input_str($in['hidden'] ?? '', 4000);

    $a = is_array($in['ambiguity'] ?? null) ? $in['ambiguity'] : [];
    $s['ambiguity'] = [
        'conflict'  => input_str($a['conflict'] ?? '', 600),
        'for_one'   => input_str($a['for_one'] ?? '', 1000),
        'for_other' => input_str($a['for_other'] ?? '', 1000),
        'divide'    => input_str($a['divide'] ?? '', 1000),
    ];

    $s['continuation'] = [
        'possible' => ($in['continuation_possible'] ?? '') === 'yes',
        'text'     => input_str($in['continuation_text'] ?? '', 2000),
    ];
    $s['notes'] = input_str($in['notes'] ?? '', 4000);

    $checks = [];
    foreach (is_array($in['checklist'] ?? null) ? $in['checklist'] : [] as $c) {
        $c = (int)$c;
        if (isset(CHECKLIST[$c])) {
            $checks[] = $c;
        }
    }
    $s['checklist'] = array_values(array_unique($checks));

    return $s;
}

/** Ошибки валидации: ключ — якорь поля, значение — сообщение. */
function situation_validate(array $s): array
{
    $e = [];
    if ($s['author'] === '') {
        $e['author'] = 'Укажите имя или ник автора — это нужно для учёта вклада.';
    }
    if (!isset(CATEGORIES[$s['category']])) {
        $e['category'] = 'Выберите категорию.';
    }
    if (!isset(SITUATION_TYPES[$s['type']])) {
        $e['type'] = 'Выберите тип ситуации.';
    }
    if ($s['title'] === '') {
        $e['title'] = 'Укажите название ситуации.';
    }
    if ($s['world']['place'] === '') {
        $e['world_place'] = 'Укажите, где происходит ситуация.';
    }
    if ($s['world']['circumstances'] === '') {
        $e['world_circumstances'] = 'Опишите обстоятельства мира.';
    }
    if (word_count($s['story']) < 40) {
        $e['story'] = 'Опишите ситуацию подробнее: минимум 40 слов (рекомендуется 100–250).';
    }
    if (!$s['participants']) {
        $e['participants'] = 'Добавьте хотя бы одного участника.';
    } else {
        foreach ($s['participants'] as $p) {
            if ($p['name'] === '') {
                $e['participants'] = 'У каждого участника должно быть имя.';
                break;
            }
        }
    }
    if (!$s['facts']) {
        $e['facts'] = 'Укажите хотя бы один факт, известный игроку.';
    }
    if ($s['type'] === 'witness' || $s['type'] === 'public') {
        $n = count($s['witnesses']);
        if ($n < 1) {
            $e['witnesses'] = 'Для этого типа ситуации нужен хотя бы один свидетель.';
        } elseif ($s['type'] === 'witness' && $n > 5) {
            $e['witnesses'] = 'В ситуации со свидетелями — от 1 до 5 свидетелей.';
        } else {
            foreach ($s['witnesses'] as $w) {
                if ($w['name'] === '' || $w['claim'] === '') {
                    $e['witnesses'] = 'У каждого свидетеля должно быть имя и показания.';
                    break;
                }
            }
        }
    }
    $withText = 0;
    foreach ($s['decisions'] as $d) {
        if ($d['text'] === '') {
            $e['decisions'] = 'У каждого варианта должна быть формулировка решения.';
            break;
        }
        $withText++;
    }
    if (!isset($e['decisions']) && $withText < 4) {
        $e['decisions'] = 'Предложите минимум 4 варианта решения.';
    }
    if ($s['ambiguity']['conflict'] === '') {
        $e['ambiguity'] = 'Опишите главный конфликт — почему здесь нет очевидного ответа.';
    }
    return $e;
}

/**
 * Какой уровень заполнения достигнут (0 — даже «Идея» не готова). Те же правила проверяет create.js.
 *   1 Идея:  категория, название, завязка от IDEA_MIN_WORDS слов, 2+ варианта решения;
 *   2 Дело:  всё, что требует situation_validate (минимум для отбора);
 *   3 Досье: последствия и влияние на мир у 2+ решений, скрытая информация, аргументы обеих сторон.
 */
function situation_level(array $s): int
{
    $decisions = array_filter($s['decisions'], static fn(array $d): bool => ($d['text'] ?? '') !== '');
    $idea = isset(CATEGORIES[$s['category']]) && $s['title'] !== ''
        && word_count($s['story']) >= IDEA_MIN_WORDS && count($decisions) >= 2;
    if (!$idea) {
        return 0;
    }
    if (situation_validate(['author' => 'x'] + $s) !== []) { // подпись автора к уровню не относится
        return 1;
    }
    $withConsequences = count(array_filter($s['decisions'], 'decision_has_consequences'));
    $withEffects = count(array_filter($s['decisions'], static fn(array $d): bool => !empty($d['effects'])));
    $dossier = $withConsequences >= 2 && $withEffects >= 2 && trim($s['hidden']) !== ''
        && $s['ambiguity']['for_one'] !== '' && $s['ambiguity']['for_other'] !== '';
    return $dossier ? 3 : 2;
}

/** Черновик можно сохранить на любом этапе — нужно только название. */
function situation_validate_draft(array $s): array
{
    return $s['title'] === '' ? ['title' => 'Дайте черновику название — по нему вы найдёте его в профиле.'] : [];
}

/** Значения формы по умолчанию: 3 участника, 3 факта, 3 свидетеля, 3 решения. */
function situation_form_defaults(): array
{
    $s = situation_blank();
    $s['author'] = (string)(current_user()['display_name'] ?? '');
    return situation_form_pad($s);
}

function situation_form_pad(array $s): array
{
    $pad = static function (array $rows, int $min, $blank): array {
        while (count($rows) < $min) {
            $rows[] = $blank;
        }
        return $rows;
    };
    $s['participants'] = $pad($s['participants'], 3, ['name' => '', 'age' => '', 'role' => '', 'relations' => '', 'description' => '']);
    $s['facts']        = $pad($s['facts'], 3, '');
    $s['unknowns']     = $pad($s['unknowns'], 1, '');
    $s['witnesses']    = $pad($s['witnesses'], 3, ['name' => '', 'claim' => '', 'trust' => '', 'interest' => '']);
    // Для «Идеи» хватает 2–3 вариантов; на уровне «Дело» форма сама добавит строки до 4.
    $s['decisions']    = $pad($s['decisions'], 3, [
        'text' => '', 'why' => '', 'immediate' => '', 'longterm' => '', 'characters' => '', 'world' => '', 'effects' => [],
    ]);
    return $s;
}
