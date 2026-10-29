<?php
declare(strict_types=1);

defined('APP_ROOT') || exit;

/** Увеличьте и добавьте шаг в db_migrate(), если меняете структуру таблиц. */
const DB_SCHEMA_VERSION = 4;
/** Номер последнего пакета демо-ситуаций в seed.php. */
const SEED_VERSION = 2;

function db(): PDO
{
    static $pdo = null;
    if ($pdo instanceof PDO) {
        return $pdo;
    }

    $c = cfg('db');
    $options = [
        PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES   => false,
    ];
    $server = sprintf('mysql:host=%s;port=%d;charset=%s', $c['host'], $c['port'], $c['charset']);

    try {
        try {
            $pdo = new PDO($server . ';dbname=' . $c['name'], $c['user'], $c['password'], $options);
        } catch (PDOException $e) {
            // 1049 — базы ещё нет: пробуем создать её сами.
            if ((int)($e->errorInfo[1] ?? 0) !== 1049 && !str_contains($e->getMessage(), '1049')) {
                throw $e;
            }
            $pdo = new PDO($server, $c['user'], $c['password'], $options);
            $pdo->exec('CREATE DATABASE IF NOT EXISTS `' . str_replace('`', '', $c['name']) . '` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci');
            $pdo->exec('USE `' . str_replace('`', '', $c['name']) . '`');
        }
        db_migrate($pdo);
    } catch (PDOException $e) {
        $pdo = null;
        db_fail($e);
    }

    return $pdo;
}

function db_meta(PDO $pdo, string $key): ?string
{
    try {
        $st = $pdo->prepare('SELECT meta_value FROM meta WHERE meta_key = ?');
        $st->execute([$key]);
        $v = $st->fetchColumn();
        return $v === false ? null : (string)$v;
    } catch (PDOException) {
        return null; // таблицы meta ещё нет
    }
}

function db_set_meta(PDO $pdo, string $key, string $value): void
{
    $pdo->prepare('INSERT INTO meta (meta_key, meta_value) VALUES (?, ?) ON DUPLICATE KEY UPDATE meta_value = ?')
        ->execute([$key, $value, $value]);
}

function db_column_exists(PDO $pdo, string $table, string $column): bool
{
    $st = $pdo->prepare('SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND COLUMN_NAME = ?');
    $st->execute([$table, $column]);
    return (int)$st->fetchColumn() > 0;
}

/**
 * Пошаговые миграции + демо-данные. Тот же итоговый SQL лежит в database/schema.sql.
 */
function db_migrate(PDO $pdo): void
{
    $schema = (int)(db_meta($pdo, 'schema_version') ?? 0);
    $seeds = (int)(db_meta($pdo, 'seed_version') ?? 0);
    if ($schema >= DB_SCHEMA_VERSION && $seeds >= SEED_VERSION) {
        return;
    }

    $opts = 'ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci';

    if ($schema < 1) {
        $pdo->exec("CREATE TABLE IF NOT EXISTS situations (
            id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
            category   VARCHAR(40)  NOT NULL,
            type       VARCHAR(20)  NOT NULL,
            title      VARCHAR(200) NOT NULL,
            author     VARCHAR(120) NOT NULL DEFAULT '',
            status     VARCHAR(20)  NOT NULL DEFAULT 'pending',
            data       LONGTEXT     NOT NULL,
            created_at DATETIME     NOT NULL,
            updated_at DATETIME     NOT NULL,
            PRIMARY KEY (id),
            KEY idx_situations_status (status),
            KEY idx_situations_category (category)
        ) $opts");
        $pdo->exec("CREATE TABLE IF NOT EXISTS votes (
            id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
            situation_id INT UNSIGNED NOT NULL,
            option_key   VARCHAR(10)  NOT NULL,
            reasoning    TEXT         NOT NULL,
            voter        CHAR(32)     NOT NULL,
            created_at   DATETIME     NOT NULL,
            PRIMARY KEY (id),
            UNIQUE KEY uniq_votes_situation_voter (situation_id, voter),
            KEY idx_votes_voter (voter),
            CONSTRAINT fk_votes_situation FOREIGN KEY (situation_id) REFERENCES situations (id) ON DELETE CASCADE
        ) $opts");
        $pdo->exec("CREATE TABLE IF NOT EXISTS meta (
            meta_key   VARCHAR(64)  NOT NULL,
            meta_value VARCHAR(255) NOT NULL,
            PRIMARY KEY (meta_key)
        ) $opts");
        db_set_meta($pdo, 'schema_version', '1');
    }

    if ($schema < 2) {
        $pdo->exec("CREATE TABLE IF NOT EXISTS users (
            id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
            login         VARCHAR(40)  NOT NULL,
            display_name  VARCHAR(80)  NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role          VARCHAR(20)  NOT NULL DEFAULT 'author',
            created_at    DATETIME     NOT NULL,
            last_login_at DATETIME     NULL,
            PRIMARY KEY (id),
            UNIQUE KEY uniq_users_login (login)
        ) $opts");
        $pdo->exec("CREATE TABLE IF NOT EXISTS sessions (
            id            VARCHAR(128) NOT NULL,
            user_id       INT UNSIGNED NULL,
            data          MEDIUMBLOB   NOT NULL,
            last_activity INT UNSIGNED NOT NULL,
            PRIMARY KEY (id),
            KEY idx_sessions_activity (last_activity),
            KEY idx_sessions_user (user_id)
        ) $opts");
        if (!db_column_exists($pdo, 'situations', 'user_id')) {
            $pdo->exec('ALTER TABLE situations
                ADD COLUMN user_id INT UNSIGNED NULL AFTER author,
                ADD KEY idx_situations_user (user_id),
                ADD CONSTRAINT fk_situations_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL');
        }
        db_set_meta($pdo, 'schema_version', '2');
    }

    if ($schema < 3) {
        // Демо-ситуации, добавленные раньше, получают «Тип мира» из обновлённых seed-файлов.
        $settings = [];
        foreach (require __DIR__ . '/seed.php' as $batch) {
            foreach ($batch as $seed) {
                $settings[$seed['title']] = $seed['world']['setting'] ?? '';
            }
        }
        $update = $pdo->prepare('UPDATE situations SET data = ? WHERE id = ?');
        foreach ($pdo->query("SELECT id, title, data FROM situations WHERE author IN ('Команда VERDICT', 'Демо-автор')") as $row) {
            $data = json_decode($row['data'], true);
            if (is_array($data) && ($settings[$row['title']] ?? '') !== '' && empty($data['world']['setting'])) {
                $data['world']['setting'] = $settings[$row['title']];
                $update->execute([json_encode($data, JSON_UNESCAPED_UNICODE), $row['id']]);
            }
        }
        db_set_meta($pdo, 'schema_version', '3');
    }

    if ($schema < 4) {
        // «Быстрый суд»: догадка игрока о выборе большинства и время на решение.
        if (!db_column_exists($pdo, 'votes', 'guess_key')) {
            $pdo->exec("ALTER TABLE votes
                ADD COLUMN guess_key     VARCHAR(10)      NULL AFTER reasoning,
                ADD COLUMN guess_correct TINYINT(1)       NULL AFTER guess_key,
                ADD COLUMN mode          VARCHAR(10)      NOT NULL DEFAULT 'full' AFTER guess_correct,
                ADD COLUMN duration_ms   INT UNSIGNED     NULL AFTER mode");
        }
        db_set_meta($pdo, 'schema_version', '4');
    }

    $adminId = db_ensure_admin($pdo);
    // Демо-ситуации команды, созданные до появления учётных записей, привязываем к команде.
    $pdo->prepare("UPDATE situations SET user_id = ? WHERE user_id IS NULL AND author = 'Команда VERDICT'")->execute([$adminId]);

    db_seed($pdo, require __DIR__ . '/seed.php', $adminId);
}

/** Первая учётная запись команды: логин admin, пароль из config.php. */
function db_ensure_admin(PDO $pdo): int
{
    $id = $pdo->query("SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1")->fetchColumn();
    if ($id !== false) {
        return (int)$id;
    }
    $pdo->prepare("INSERT IGNORE INTO users (login, display_name, password_hash, role, created_at) VALUES ('admin', 'Команда VERDICT', ?, 'admin', ?)")
        ->execute([password_hash((string)cfg('admin_password'), PASSWORD_DEFAULT), date('Y-m-d H:i:s')]);
    $pdo->exec("UPDATE users SET role = 'admin' WHERE login = 'admin'");
    return (int)$pdo->query("SELECT id FROM users WHERE login = 'admin'")->fetchColumn();
}

/**
 * Демо-ситуации пакетами. Каждый пакет добавляется ровно один раз (метка в meta),
 * поэтому удалённые ситуации не возвращаются, а новые пакеты доезжают до старых баз.
 */
function db_seed(PDO $pdo, array $batches, int $adminId): void
{
    ksort($batches);
    foreach ($batches as $version => $situations) {
        $pdo->beginTransaction();
        $claim = $pdo->prepare('INSERT IGNORE INTO meta (meta_key, meta_value) VALUES (?, ?)');
        $claim->execute([$version === 1 ? 'seeded' : 'seeded_v' . $version, date('c')]);
        if ($claim->rowCount() === 1) {
            foreach ($situations as $s) {
                $teamOwned = ($s['author'] ?? '') === 'Команда VERDICT';
                situation_insert($pdo, $s, $s['status'] ?? 'approved', $teamOwned ? $adminId : null);
            }
        }
        $pdo->commit();
        db_set_meta($pdo, 'seed_version', (string)$version);
    }
}

/** Понятная страница вместо фатальной ошибки, если MySQL недоступен. */
function db_fail(PDOException $e): never
{
    $c = cfg('db');
    http_response_code(503);
    $isApi = str_contains((string)($_SERVER['SCRIPT_NAME'] ?? ''), '/api/');
    if ($isApi) {
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode(['ok' => false, 'error' => 'База данных недоступна.'], JSON_UNESCAPED_UNICODE);
        exit;
    }
    header('Content-Type: text/html; charset=utf-8');
    $where = e($c['user'] . '@' . $c['host'] . ':' . $c['port'] . ' / ' . $c['name']);
    echo '<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        . '<title>База данных недоступна — VERDICT</title><style>'
        . 'body{margin:0;min-height:100vh;display:grid;place-items:center;background:#03050b;color:#e8edff;font:16px/1.6 system-ui,sans-serif;padding:16px}'
        . '.box{max-width:620px;border:1px solid rgba(255,77,109,.4);border-radius:16px;padding:28px;background:rgba(20,10,20,.6)}'
        . 'h1{font-size:20px;margin:0 0 12px;color:#ff8fa5}code{background:rgba(255,255,255,.06);padding:2px 6px;border-radius:4px;font-size:14px}'
        . 'li{margin:6px 0}small{color:#95a0c3}</style></head><body><div class="box">'
        . '<h1>Не удалось подключиться к MySQL</h1>'
        . '<p>Сайт пытался подключиться как <code>' . $where . '</code>.</p><ol>'
        . '<li>Убедитесь, что MySQL запущен (в Open Server Panel — модуль MySQL-8.0 включён и сервер стартовал).</li>'
        . '<li>Проверьте хост, порт, логин и пароль в <code>config.php</code>.</li>'
        . '<li>Если у пользователя нет права создавать базы, создайте базу и импортируйте <code>database/schema.sql</code>.</li>'
        . '</ol><p><small>Ошибка: ' . e($e->getMessage()) . '</small></p></div></body></html>';
    exit;
}
