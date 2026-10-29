<?php
declare(strict_types=1);

define('APP_ROOT', dirname(__DIR__));

$CONFIG = require APP_ROOT . '/config.php';

date_default_timezone_set($CONFIG['timezone'] ?? 'UTC');
mb_internal_encoding('UTF-8');

header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: SAMEORIGIN');
header('Referrer-Policy: same-origin');

require __DIR__ . '/catalog.php';
require __DIR__ . '/helpers.php';
require __DIR__ . '/db.php';
require __DIR__ . '/repository.php';
require __DIR__ . '/auth.php';
require __DIR__ . '/session.php';
require __DIR__ . '/form.php';
require __DIR__ . '/comic.php';
require __DIR__ . '/judge.php';

/* Сессии хранятся в MySQL (таблица sessions). */
$sessionLifetime = (int)cfg('session_lifetime', 1209600);
$https = !empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off';
ini_set('session.use_strict_mode', '1');
ini_set('session.use_only_cookies', '1');
ini_set('session.gc_maxlifetime', (string)$sessionLifetime);
ini_set('session.gc_probability', '1');
ini_set('session.gc_divisor', '100');
session_set_save_handler(new DbSessionHandler($sessionLifetime), true);
session_name('verdict_sid');
session_set_cookie_params([
    'lifetime' => $sessionLifetime,
    'path'     => '/',
    'secure'   => $https,
    'httponly' => true,
    'samesite' => 'Lax',
]);
session_start();

// Продлеваем cookie активным посетителям, чтобы вход не слетал через 14 дней работы.
if (!headers_sent() && ($_COOKIE[session_name()] ?? '') === session_id()) {
    setcookie(session_name(), session_id(), [
        'expires'  => time() + $sessionLifetime,
        'path'     => '/',
        'secure'   => $https,
        'httponly' => true,
        'samesite' => 'Lax',
    ]);
}

voter_id();
