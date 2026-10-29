<?php
declare(strict_types=1);

defined('APP_ROOT') || exit;

/**
 * Хранение PHP-сессий в MySQL (таблица sessions).
 * В строке сессии запоминается user_id — так можно увидеть активные входы
 * пользователя и завершить их все (например, после смены пароля).
 */
final class DbSessionHandler implements SessionHandlerInterface, SessionUpdateTimestampHandlerInterface
{
    public function __construct(private int $lifetime)
    {
    }

    public function open(string $path, string $name): bool
    {
        return true;
    }

    public function close(): bool
    {
        return true;
    }

    public function read(string $id): string|false
    {
        $st = db()->prepare('SELECT data, last_activity FROM sessions WHERE id = ?');
        $st->execute([$id]);
        $row = $st->fetch();
        if (!$row || (int)$row['last_activity'] < time() - $this->lifetime) {
            return '';
        }
        return (string)$row['data'];
    }

    public function write(string $id, string $data): bool
    {
        $uid = isset($_SESSION['uid']) ? (int)$_SESSION['uid'] : null;
        $now = time();
        $st = db()->prepare('INSERT INTO sessions (id, user_id, data, last_activity) VALUES (?, ?, ?, ?)
            ON DUPLICATE KEY UPDATE user_id = ?, data = ?, last_activity = ?');
        return $st->execute([$id, $uid, $data, $now, $uid, $data, $now]);
    }

    public function destroy(string $id): bool
    {
        db()->prepare('DELETE FROM sessions WHERE id = ?')->execute([$id]);
        return true;
    }

    public function gc(int $max_lifetime): int|false
    {
        $st = db()->prepare('DELETE FROM sessions WHERE last_activity < ?');
        $st->execute([time() - $this->lifetime]);
        return $st->rowCount();
    }

    /** Для session.use_strict_mode: чужие и просроченные id не принимаются. */
    public function validateId(string $id): bool
    {
        $st = db()->prepare('SELECT 1 FROM sessions WHERE id = ? AND last_activity >= ?');
        $st->execute([$id, time() - $this->lifetime]);
        return (bool)$st->fetchColumn();
    }

    public function updateTimestamp(string $id, string $data): bool
    {
        db()->prepare('UPDATE sessions SET last_activity = ? WHERE id = ?')->execute([time(), $id]);
        return true;
    }
}

/** Завершить все сессии пользователя, кроме текущей. */
function sessions_revoke_others(int $userId): int
{
    $st = db()->prepare('DELETE FROM sessions WHERE user_id = ? AND id <> ?');
    $st->execute([$userId, session_id()]);
    return $st->rowCount();
}

function sessions_active_count(int $userId): int
{
    $st = db()->prepare('SELECT COUNT(*) FROM sessions WHERE user_id = ? AND last_activity >= ?');
    $st->execute([$userId, time() - (int)cfg('session_lifetime', 1209600)]);
    return (int)$st->fetchColumn();
}
