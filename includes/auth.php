<?php
declare(strict_types=1);

defined('APP_ROOT') || exit;

const LOGIN_PATTERN = '/^[A-Za-z0-9_.\-]{3,40}$/';
const PASSWORD_MIN = 8;
const ROLES = [
    'author' => 'Автор',
    'admin'  => 'Команда',
];

/* ---------- Текущий пользователь ---------- */

function current_user(): ?array
{
    static $cache = [];
    $uid = (int)($_SESSION['uid'] ?? 0);
    if ($uid <= 0) {
        return null;
    }
    if (!array_key_exists($uid, $cache)) {
        $cache[$uid] = user_find($uid);
        if ($cache[$uid] === null) {
            unset($_SESSION['uid']);
        }
    }
    return $cache[$uid];
}

function current_user_id(): ?int
{
    $u = current_user();
    return $u ? (int)$u['id'] : null;
}

function is_logged_in(): bool
{
    return current_user() !== null;
}

function is_admin(): bool
{
    return (current_user()['role'] ?? '') === 'admin';
}

function require_login(string $back, string $message = 'Войдите, чтобы продолжить.'): void
{
    if (is_logged_in()) {
        return;
    }
    flash('error', $message);
    redirect('login.php?back=' . rawurlencode($back));
}

function owns_situation(array $s): bool
{
    $uid = current_user_id();
    return $uid !== null && (int)($s['user_id'] ?? 0) === $uid;
}

/** Команда редактирует всё; автор — только свои черновики и ситуации на отборе. */
function can_edit_situation(array $s): bool
{
    return is_admin() || (owns_situation($s) && in_array($s['status'], ['draft', 'pending'], true));
}

/** Черновик видят только автор и команда; остальные ситуации открыты всем. */
function can_view_situation(array $s): bool
{
    return $s['status'] !== 'draft' || is_admin() || owns_situation($s);
}

/** Сохранить как черновик можно новую ситуацию или свою, пока она не прошла отбор. */
function can_save_draft(?array $s): bool
{
    return $s === null || (owns_situation($s) && in_array($s['status'], ['draft', 'pending'], true));
}

/** Скрытую информацию видят команда и сам автор. */
function can_see_hidden(array $s): bool
{
    return is_admin() || owns_situation($s);
}

/* ---------- Пользователи ---------- */

function user_find(int $id): ?array
{
    $st = db()->prepare('SELECT id, login, display_name, role, created_at, last_login_at FROM users WHERE id = ?');
    $st->execute([$id]);
    return $st->fetch() ?: null;
}

function user_find_by_login(string $login): ?array
{
    $st = db()->prepare('SELECT * FROM users WHERE login = ?');
    $st->execute([$login]);
    return $st->fetch() ?: null;
}

/** Все пользователи со счётчиками ситуаций. */
function users_all(): array
{
    return db()->query('SELECT u.id, u.login, u.display_name, u.role, u.created_at, u.last_login_at,
            COUNT(s.id) AS situations,
            SUM(s.status = \'approved\') AS approved
        FROM users u LEFT JOIN situations s ON s.user_id = u.id
        GROUP BY u.id ORDER BY u.role = \'admin\' DESC, u.id')->fetchAll();
}

function user_create(string $login, string $displayName, string $password, string $role = 'author'): int
{
    db()->prepare('INSERT INTO users (login, display_name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)')
        ->execute([$login, $displayName, password_hash($password, PASSWORD_DEFAULT), $role, date('Y-m-d H:i:s')]);
    return (int)db()->lastInsertId();
}

function user_update_name(int $id, string $displayName): void
{
    db()->prepare('UPDATE users SET display_name = ? WHERE id = ?')->execute([$displayName, $id]);
    // Имя автора хранится и в ситуациях — обновляем, чтобы подпись не расходилась.
    db()->prepare('UPDATE situations SET author = ? WHERE user_id = ?')->execute([$displayName, $id]);
}

function user_set_password(int $id, string $password): void
{
    db()->prepare('UPDATE users SET password_hash = ? WHERE id = ?')
        ->execute([password_hash($password, PASSWORD_DEFAULT), $id]);
}

function user_set_role(int $id, string $role): void
{
    db()->prepare('UPDATE users SET role = ? WHERE id = ?')->execute([$role, $id]);
}

function admins_count(): int
{
    return (int)db()->query("SELECT COUNT(*) FROM users WHERE role = 'admin'")->fetchColumn();
}

/* ---------- Вход и выход ---------- */

function auth_attempt(string $login, string $password): ?array
{
    static $dummy = null;
    $user = user_find_by_login($login);
    // Хеш проверяется и для несуществующего логина — время ответа не выдаёт, есть ли такой пользователь.
    $dummy ??= password_hash('verdict-timing-guard', PASSWORD_DEFAULT);
    $valid = password_verify($password, $user['password_hash'] ?? $dummy);
    if (!$user || !$valid) {
        return null;
    }
    if (password_needs_rehash($user['password_hash'], PASSWORD_DEFAULT)) {
        user_set_password((int)$user['id'], $password);
    }
    return $user;
}

function auth_login(array $user): void
{
    session_regenerate_id(true);
    $_SESSION['uid'] = (int)$user['id'];
    unset($_SESSION['login_fail']);
    db()->prepare('UPDATE users SET last_login_at = ? WHERE id = ?')->execute([date('Y-m-d H:i:s'), $user['id']]);
}

function auth_logout(): void
{
    unset($_SESSION['uid']);
    session_regenerate_id(true);
}

/** Секунд до следующей попытки входа (0 — можно пробовать). */
function login_lock_seconds(): int
{
    $f = $_SESSION['login_fail'] ?? null;
    if (!$f || $f['n'] < 5) {
        return 0;
    }
    return max(0, (int)$f['until'] - time());
}

function login_register_failure(): void
{
    $f = $_SESSION['login_fail'] ?? ['n' => 0, 'until' => 0];
    $f['n']++;
    if ($f['n'] >= 5) {
        $f['until'] = time() + min(300, 30 * 2 ** ($f['n'] - 5));
    }
    $_SESSION['login_fail'] = $f;
}

/* ---------- Проверка форм ---------- */

function registration_validate(string $login, string $name, string $password, string $confirm): array
{
    $e = [];
    if (!preg_match(LOGIN_PATTERN, $login)) {
        $e['login'] = 'Логин: 3–40 символов — латинские буквы, цифры, точка, дефис или подчёркивание.';
    } elseif (user_find_by_login($login)) {
        $e['login'] = 'Такой логин уже занят.';
    }
    $e += name_validate($name);
    $e += password_validate($password, $confirm);
    return $e;
}

function name_validate(string $name): array
{
    $len = mb_strlen($name);
    return ($len < 2 || $len > 80) ? ['display_name' => 'Имя или ник: от 2 до 80 символов.'] : [];
}

function password_validate(string $password, string $confirm): array
{
    if (mb_strlen($password) < PASSWORD_MIN) {
        return ['password' => 'Пароль должен быть не короче ' . PASSWORD_MIN . ' символов.'];
    }
    if (strlen($password) > 200) {
        return ['password' => 'Пароль слишком длинный.'];
    }
    if ($password !== $confirm) {
        return ['password_confirm' => 'Пароли не совпадают.'];
    }
    return [];
}
