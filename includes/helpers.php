<?php
declare(strict_types=1);

defined('APP_ROOT') || exit;

function cfg(string $key, $default = null)
{
    global $CONFIG;
    return $CONFIG[$key] ?? $default;
}

function e($value): string
{
    return htmlspecialchars((string)($value ?? ''), ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

/** Текст с абзацами: пустая строка — новый абзац, перенос — <br>. */
function paragraphs(?string $text): string
{
    $text = trim((string)$text);
    if ($text === '') {
        return '';
    }
    $html = '';
    foreach (preg_split('/\R{2,}/u', $text) as $p) {
        $html .= '<p>' . nl2br(e(trim($p))) . '</p>';
    }
    return $html;
}

function icon(string $name, string $class = ''): string
{
    static $icons = null;
    $icons ??= require __DIR__ . '/icons.php';
    $body = $icons[$name] ?? $icons['circle'];
    $cls = trim('icon ' . $class);
    return '<svg class="' . e($cls) . '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' . $body . '</svg>';
}

/** Иконка для пункта неонового списка: <option<?= option_icon('crown', 45) ?>> */
function option_icon(string $icon, ?int $hue = null): string
{
    return ' data-icon="' . e(icon($icon)) . '"' . ($hue !== null ? ' data-hue="' . $hue . '"' : '');
}

function logo_svg(string $class = 'logo'): string
{
    static $n = 0;
    $id = 'logo-grad-' . (++$n);
    return '<svg class="' . e($class) . '" viewBox="0 0 32 32" fill="none" aria-hidden="true">'
        . '<defs><linearGradient id="' . $id . '" x1="4" y1="2" x2="28" y2="30" gradientUnits="userSpaceOnUse">'
        . '<stop offset="0" stop-color="#2be4ff"/><stop offset="1" stop-color="#8b5cf6"/></linearGradient></defs>'
        . '<path d="M16 2.5 27.7 9.25v13.5L16 29.5 4.3 22.75V9.25Z" stroke="url(#' . $id . ')" stroke-width="1.6"/>'
        . '<path d="M10.5 10.5 16 21l5.5-10.5" stroke="#fff" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/>'
        . '<circle cx="16" cy="25" r="1.4" fill="#2be4ff"/></svg>';
}

function asset(string $path): string
{
    $file = APP_ROOT . '/assets/' . $path;
    $v = is_file($file) ? (string)filemtime($file) : '1';
    return 'assets/' . $path . '?v=' . $v;
}

/* ---------- Безопасность ---------- */

function csrf_token(): string
{
    if (empty($_SESSION['csrf'])) {
        $_SESSION['csrf'] = bin2hex(random_bytes(16));
    }
    return $_SESSION['csrf'];
}

function csrf_field(): string
{
    return '<input type="hidden" name="_csrf" value="' . e(csrf_token()) . '">';
}

function csrf_valid(): bool
{
    $token = $_POST['_csrf'] ?? ($_SERVER['HTTP_X_CSRF_TOKEN'] ?? '');
    return is_string($token) && $token !== '' && hash_equals(csrf_token(), $token);
}

/** Анонимный идентификатор игрока (cookie на год). */
function voter_id(): string
{
    static $id = null;
    if ($id !== null) {
        return $id;
    }
    $cookie = $_COOKIE['verdict_vid'] ?? '';
    if (!is_string($cookie) || !preg_match('/^[a-f0-9]{32}$/', $cookie)) {
        $cookie = bin2hex(random_bytes(16));
        if (!headers_sent()) {
            setcookie('verdict_vid', $cookie, [
                'expires'  => time() + 31536000,
                'path'     => '/',
                'httponly' => true,
                'samesite' => 'Lax',
            ]);
        }
        $_COOKIE['verdict_vid'] = $cookie;
    }
    return $id = $cookie;
}

function redirect(string $url): never
{
    header('Location: ' . $url);
    exit;
}

/** Разрешаем возвращаться только на собственные страницы сайта. */
function safe_back($url): string
{
    $url = is_string($url) ? $url : '';
    return preg_match('/^[a-z\-]+\.php(\?[\w=&%\-.]*)?$/i', $url) ? $url : '';
}

function flash(string $type, string $message): void
{
    $_SESSION['flash'][] = ['type' => $type, 'message' => $message];
}

function take_flashes(): array
{
    $f = $_SESSION['flash'] ?? [];
    unset($_SESSION['flash']);
    return $f;
}

/** Ключ копии формы в localStorage браузера: своя у каждого автора и у каждой ситуации. */
function autosave_key(?int $situationId): string
{
    return 'verdict:create:u' . (int)current_user_id() . ':' . ($situationId ? 's' . $situationId : 'new');
}

/** После сохранения на сервере браузер удалит свою копию формы (см. app.js, data-autosave-clear). */
function autosave_clear(string $key): void
{
    $_SESSION['autosave_clear'][] = $key;
}

function take_autosave_clear(): array
{
    $keys = $_SESSION['autosave_clear'] ?? [];
    unset($_SESSION['autosave_clear']);
    return array_values(array_unique($keys));
}

/* ---------- Текст ---------- */

function word_count(string $text): int
{
    return (int)preg_match_all('/[\p{L}\p{N}]+(?:[\'’\-][\p{L}\p{N}]+)*/u', $text);
}

function plural(int $n, string $one, string $few, string $many): string
{
    $n = abs($n) % 100;
    $n1 = $n % 10;
    if ($n > 10 && $n < 20) {
        return $many;
    }
    if ($n1 > 1 && $n1 < 5) {
        return $few;
    }
    if ($n1 === 1) {
        return $one;
    }
    return $many;
}

function excerpt(string $text, int $length = 160): string
{
    $text = trim(preg_replace('/\s+/u', ' ', $text));
    if (mb_strlen($text) <= $length) {
        return $text;
    }
    $cut = mb_substr($text, 0, $length);
    $space = mb_strrpos($cut, ' ');
    if ($space !== false && $space > $length * 0.6) {
        $cut = mb_substr($cut, 0, $space);
    }
    return rtrim($cut, " ,.;:—-") . '…';
}

/** 95000 → «1 мин 35 с», 42000 → «42 с». */
function format_duration(int $ms): string
{
    $sec = (int)round($ms / 1000);
    return $sec >= 60 ? intdiv($sec, 60) . ' мин ' . ($sec % 60) . ' с' : $sec . ' с';
}

function format_date(string $datetime): string
{
    $ts = strtotime($datetime);
    return $ts ? date('d.m.Y', $ts) : '';
}

function case_number(int $id): string
{
    return '№ ' . str_pad((string)$id, 4, '0', STR_PAD_LEFT);
}

function initials(string $name): string
{
    $name = trim(preg_replace('/[«»"„“]/u', '', $name));
    $parts = preg_split('/\s+/u', $name, -1, PREG_SPLIT_NO_EMPTY);
    if (!$parts) {
        return '?';
    }
    $out = mb_strtoupper(mb_substr($parts[0], 0, 1));
    if (isset($parts[1])) {
        $out .= mb_strtoupper(mb_substr($parts[1], 0, 1));
    }
    return $out;
}

/** Стабильный оттенок для аватара по имени. */
function name_hue(string $name): int
{
    return crc32($name) % 360;
}

function category_style(string $category): string
{
    return '--h:' . (CATEGORIES[$category]['hue'] ?? 190);
}

/* ---------- Игровая логика ---------- */

/**
 * Индекс спорности: нормированная энтропия распределения голосов (0–100).
 * 0 — все выбрали одно и то же, 100 — голоса разделились поровну между всеми вариантами.
 */
function controversy(array $counts, int $options): array
{
    $total = array_sum($counts);
    if ($total < 2 || $options < 2) {
        return ['value' => null, 'label' => 'Мало данных', 'level' => 'none'];
    }
    $h = 0.0;
    foreach ($counts as $c) {
        if ($c > 0) {
            $p = $c / $total;
            $h -= $p * log($p);
        }
    }
    $value = (int)round(min(1, $h / log($options)) * 100);
    if ($value >= 70) {
        return ['value' => $value, 'label' => 'Жаркий спор', 'level' => 'hot'];
    }
    if ($value >= 50) {
        return ['value' => $value, 'label' => 'Разногласия', 'level' => 'high'];
    }
    if ($value >= 25) {
        return ['value' => $value, 'label' => 'Есть сомнения', 'level' => 'mid'];
    }
    return ['value' => $value, 'label' => 'Единодушие', 'level' => 'low'];
}

/* Состояние мира хранится в сессии: [situation_id => ['key' => 'A', 'effects' => [...]]]. */

function world_record(int $situationId, string $key, array $effects): void
{
    $_SESSION['world'][$situationId] = ['key' => $key, 'effects' => $effects, 'at' => time()];
}

function world_metrics(): array
{
    $sum = array_fill_keys(array_keys(METRICS), 0);
    foreach ($_SESSION['world'] ?? [] as $entry) {
        foreach ($entry['effects'] ?? [] as $k => $v) {
            if (isset($sum[$k])) {
                $sum[$k] += (int)$v;
            }
        }
    }
    $out = [];
    foreach ($sum as $k => $v) {
        $out[$k] = max(0, min(100, 50 + $v * METRIC_STEP));
    }
    return $out;
}

function world_count(): int
{
    return count($_SESSION['world'] ?? []);
}

function world_reset(): void
{
    unset($_SESSION['world']);
}

/* ---------- Шаблоны ---------- */

/** $bg — интенсивность фона: high (главная, архив) или calm (страницы для чтения и форм). */
function page_header(string $title = '', string $active = '', string $bodyClass = '', string $bg = 'high'): void
{
    include APP_ROOT . '/includes/layout/header.php';
}

function page_footer(array $scripts = []): void
{
    include APP_ROOT . '/includes/layout/footer.php';
}

function partial(string $name, array $vars = []): string
{
    extract($vars, EXTR_SKIP);
    ob_start();
    include APP_ROOT . '/includes/partials/' . $name . '.php';
    return (string)ob_get_clean();
}

function json_response(array $data, int $status = 200): never
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
    exit;
}

/** Метка уровня заполнения ситуации (см. LEVELS и situation_level()). */
function level_chip(int $level, string $class = 'chip-sm'): string
{
    if ($level < 1) {
        return '<span class="chip ' . $class . ' chip-level lvl-0" title="Ещё не готова даже идея">' . icon('edit') . 'Набросок</span>';
    }
    $l = LEVELS[$level];
    return '<span class="chip ' . $class . ' chip-level lvl-' . $level . '" title="Уровень ' . $level . ' из 3: ' . e($l['desc']) . '">'
        . icon($l['icon']) . 'Ур. ' . $level . ' · ' . e($l['name']) . '</span>';
}

/** data-атрибуты модального подтверждения для смены статуса ситуации. */
function status_confirm_attrs(string $to, string $title): string
{
    $map = [
        'approved' => ['Добавить в игру', 'Ситуация «%s» появится в архиве дел, и игроки смогут выносить по ней вердикты.', 'В игру', 'success'],
        'rejected' => ['Отклонить ситуацию', 'Ситуация «%s» будет отклонена и не попадёт в игру. Решение можно изменить позже.', 'Отклонить', 'danger'],
        'pending'  => ['Вернуть на отбор', 'Ситуация «%s» вернётся на отбор и пропадёт из архива дел, пока её снова не одобрят.', 'Вернуть', 'warn'],
    ];
    [$heading, $message, $ok, $tone] = $map[$to] ?? $map['pending'];
    return ' data-confirm="' . e(sprintf($message, $title)) . '" data-confirm-title="' . e($heading) . '"'
        . ' data-confirm-ok="' . e($ok) . '" data-confirm-tone="' . $tone . '"';
}
