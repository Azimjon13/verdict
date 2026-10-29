<?php
/**
 * VERDICT — настройки сайта.
 *
 * База данных: MySQL 5.7+ / 8.0 или MariaDB 10.3+.
 * Если пользователь имеет право CREATE, база и таблицы создадутся автоматически
 * при первом открытии сайта. Иначе импортируйте database/schema.sql вручную.
 *
 * Любой параметр можно переопределить переменной окружения (VERDICT_DB_HOST и т. д.).
 */
return [
    'app_name' => 'VERDICT',

    'db' => [
        'host'     => getenv('VERDICT_DB_HOST') ?: '127.0.0.1',
        'port'     => (int)(getenv('VERDICT_DB_PORT') ?: 3306),
        'name'     => getenv('VERDICT_DB_NAME') ?: 'verdict',
        'user'     => getenv('VERDICT_DB_USER') ?: 'root',
        'password' => getenv('VERDICT_DB_PASSWORD') !== false ? (string)getenv('VERDICT_DB_PASSWORD') : '',
        'charset'  => 'utf8mb4',
    ],

    // Пароль первой учётной записи команды (логин: admin). Используется ОДИН раз — при
    // создании базы. Потом пароль меняется на странице «Профиль». Обязательно смените его.
    'admin_password' => getenv('VERDICT_ADMIN_PASSWORD') ?: 'verdict-admin',

    // Сколько живёт сессия без активности (секунды). Сессии хранятся в MySQL, таблица sessions.
    'session_lifetime' => 60 * 60 * 24 * 14,

    'timezone' => 'UTC',
];
