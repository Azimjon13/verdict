-- VERDICT — структура базы данных (MySQL 5.7+ / 8.0, MariaDB 10.3+), версия схемы 8.
-- Сайт создаёт и обновляет эти таблицы сам при первом запуске. Этот файл нужен, если у
-- пользователя MySQL нет права CREATE: создайте базу и импортируйте его вручную
-- (phpMyAdmin / HeidiSQL / mysql -u root -p < database/schema.sql).
-- 48 демо-ситуаций добавятся автоматически при первом открытии сайта.

CREATE DATABASE IF NOT EXISTS `verdict` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `verdict`;

-- Учётные записи. role: author (автор) | admin (команда).
CREATE TABLE IF NOT EXISTS users (
    id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
    login         VARCHAR(40)  NOT NULL,
    display_name  VARCHAR(80)  NOT NULL,
    password_hash VARCHAR(255) NOT NULL,                  -- password_hash() / bcrypt
    role          VARCHAR(20)  NOT NULL DEFAULT 'author',
    created_at    DATETIME     NOT NULL,
    last_login_at DATETIME     NULL,
    bio           VARCHAR(280) NOT NULL DEFAULT '',         -- «о себе» в публичном профиле
    visibility    VARCHAR(10)  NOT NULL DEFAULT 'public',   -- кто видит профиль: public | friends | private
    in_ratings    TINYINT(1)   NOT NULL DEFAULT 1,          -- показывать в рейтингах
    PRIMARY KEY (id),
    UNIQUE KEY uniq_users_login (login)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Сессии сайта (см. verdict/sessions.py).
CREATE TABLE IF NOT EXISTS sessions (
    id            VARCHAR(128) NOT NULL,
    user_id       INT UNSIGNED NULL,
    data          MEDIUMBLOB   NOT NULL,
    last_activity INT UNSIGNED NOT NULL,                  -- unix time
    PRIMARY KEY (id),
    KEY idx_sessions_activity (last_activity),
    KEY idx_sessions_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS situations (
    id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
    category   VARCHAR(40)  NOT NULL,
    type       VARCHAR(20)  NOT NULL,
    title      VARCHAR(200) NOT NULL,
    author     VARCHAR(120) NOT NULL DEFAULT '',
    user_id    INT UNSIGNED NULL,                         -- владелец (автор) ситуации
    status     VARCHAR(20)  NOT NULL DEFAULT 'pending',   -- draft | pending | approved | rejected
    data       LONGTEXT     NOT NULL,                     -- JSON по структуре шаблона ситуации
    created_at DATETIME     NOT NULL,
    updated_at DATETIME     NOT NULL,
    PRIMARY KEY (id),
    KEY idx_situations_status (status),
    KEY idx_situations_category (category),
    KEY idx_situations_user (user_id),
    CONSTRAINT fk_situations_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS votes (
    id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
    situation_id INT UNSIGNED NOT NULL,
    option_key   VARCHAR(10)  NOT NULL,                   -- A..H или other
    reasoning    TEXT         NOT NULL,
    guess_key    VARCHAR(10)  NULL,                       -- «Быстрый суд»: какой выбор игрок приписал большинству
    guess_correct TINYINT(1)  NULL,                       -- 1/0 — угадал ли; NULL — не угадывал или сравнивать было не с кем
    mode         VARCHAR(10)  NOT NULL DEFAULT 'full',    -- full (полное дело) | quick (быстрый суд)
    duration_ms  INT UNSIGNED NULL,                       -- сколько игрок решал, от открытия дела до вердикта
    voter        CHAR(32)     NOT NULL,                   -- анонимный id игрока из cookie
    created_at   DATETIME     NOT NULL,
    first_at     DATETIME     NULL,                       -- когда дело рассудили впервые (повторный голос его не меняет)
    PRIMARY KEY (id),
    UNIQUE KEY uniq_votes_situation_voter (situation_id, voter),
    KEY idx_votes_voter (voter),
    KEY idx_votes_created (created_at),
    CONSTRAINT fk_votes_situation FOREIGN KEY (situation_id) REFERENCES situations (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Карьера игрока (анонимный id из cookie или X-Voter-Id): с какого момента считается мир, серия дней,
-- дела дня, события мира и достижения. Строка появляется при первом вердикте.
-- user_id — аккаунт игрока: после входа прогресс следует за аккаунтом на любом устройстве.
CREATE TABLE IF NOT EXISTS players (
    voter        CHAR(32)     NOT NULL,
    user_id      INT UNSIGNED NULL,
    world_since  DATETIME     NULL,
    last_day     DATE         NULL,
    streak       INT UNSIGNED NOT NULL DEFAULT 0,
    best_streak  INT UNSIGNED NOT NULL DEFAULT 0,
    last_daily   DATE         NULL,
    daily_done   INT UNSIGNED NOT NULL DEFAULT 0,
    events       TEXT         NULL,
    achievements TEXT         NULL,
    title        VARCHAR(120) NULL,                       -- титул, полученный в подарок
    blocked      TINYINT(1)   NOT NULL DEFAULT 0,         -- 1 — команда отстранила игрока от охоты за тайниками
    created_at   DATETIME     NOT NULL,
    updated_at   DATETIME     NOT NULL,
    PRIMARY KEY (voter),
    UNIQUE KEY uniq_players_user (user_id),
    CONSTRAINT fk_players_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Дни, когда игрок заходил (для аналитики: активные игроки, удержание).
CREATE TABLE IF NOT EXISTS player_days (
    voter CHAR(32)     NOT NULL,
    day   DATE         NOT NULL,
    hits  INT UNSIGNED NOT NULL DEFAULT 1,                -- просмотров страниц за день
    PRIMARY KEY (voter, day),
    KEY idx_player_days_day (day)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Подарки, которые команда раздаёт через тайники или вручную.
-- kind: xp (опыт) | badge (трофей) | title (титул) | code (уникальный код из пула) | message (сообщение, ссылка).
CREATE TABLE IF NOT EXISTS gifts (
    id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
    kind          VARCHAR(16)  NOT NULL,
    name          VARCHAR(120) NOT NULL,
    icon          VARCHAR(30)  NOT NULL DEFAULT 'gift',
    xp            INT          NOT NULL DEFAULT 0,       -- опыт к рангу (у любого вида подарка)
    text          TEXT         NOT NULL,                 -- что прочтёт нашедший
    link          VARCHAR(500) NOT NULL DEFAULT '',
    needs_account TINYINT(1)   NOT NULL DEFAULT 0,       -- 1 — забрать можно только войдя в аккаунт
    active        TINYINT(1)   NOT NULL DEFAULT 1,
    created_at    DATETIME     NOT NULL,
    updated_at    DATETIME     NOT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Пул кодов для подарков вида code: каждый нашедший получает свой код.
CREATE TABLE IF NOT EXISTS gift_codes (
    id       INT UNSIGNED NOT NULL AUTO_INCREMENT,
    gift_id  INT UNSIGNED NOT NULL,
    code     VARCHAR(120) NOT NULL,
    grant_id INT UNSIGNED NULL,                          -- кому выдан (gift_grants.id); NULL — свободен
    PRIMARY KEY (id),
    UNIQUE KEY uniq_gift_codes (gift_id, code),
    KEY idx_gift_codes_free (gift_id, grant_id),
    CONSTRAINT fk_gift_codes_gift FOREIGN KEY (gift_id) REFERENCES gifts (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Охота за тайниками. status: draft | active | ended; идёт, если active и сейчас между starts_at и ends_at (UTC).
CREATE TABLE IF NOT EXISTS challenges (
    id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
    title         VARCHAR(120) NOT NULL,
    intro         TEXT         NOT NULL,
    status        VARCHAR(10)  NOT NULL DEFAULT 'draft',
    starts_at     DATETIME     NULL,
    ends_at       DATETIME     NULL,
    banner        TINYINT(1)   NOT NULL DEFAULT 1,       -- значок охоты с прогрессом на всех страницах
    prize_gift_id INT UNSIGNED NULL,                     -- главный приз за все тайники охоты
    created_at    DATETIME     NOT NULL,
    updated_at    DATETIME     NOT NULL,
    PRIMARY KEY (id),
    KEY idx_challenges_status (status),
    CONSTRAINT fk_challenges_prize FOREIGN KEY (prize_gift_id) REFERENCES gifts (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Тайники. page — страница сайта (имя маршрута, * — все страницы) или unity:<сцена> для игрового клиента;
-- path — только этот адрес; selector + x, y (% от ширины и высоты элемента) — где именно.
CREATE TABLE IF NOT EXISTS spots (
    id           INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    challenge_id INT UNSIGNED  NOT NULL,
    label        VARCHAR(120)  NOT NULL DEFAULT '',
    page         VARCHAR(60)   NOT NULL DEFAULT '*',
    path         VARCHAR(255)  NOT NULL DEFAULT '',
    selector     VARCHAR(500)  NOT NULL DEFAULT '',
    x            DECIMAL(5,2)  NOT NULL DEFAULT 50,
    y            DECIMAL(5,2)  NOT NULL DEFAULT 50,
    icon         VARCHAR(30)   NOT NULL DEFAULT 'gem',
    size         SMALLINT UNSIGNED NOT NULL DEFAULT 24,
    visibility   VARCHAR(10)   NOT NULL DEFAULT 'subtle', -- faint | subtle | visible
    hint         VARCHAR(255)  NOT NULL DEFAULT '',
    gift_id      INT UNSIGNED  NULL,
    max_finds    INT UNSIGNED  NOT NULL DEFAULT 0,        -- 0 — без ограничения; N — только первые N нашедших
    active       TINYINT(1)    NOT NULL DEFAULT 1,
    created_at   DATETIME      NOT NULL,
    updated_at   DATETIME      NOT NULL,
    PRIMARY KEY (id),
    KEY idx_spots_challenge (challenge_id),
    CONSTRAINT fk_spots_challenge FOREIGN KEY (challenge_id) REFERENCES challenges (id) ON DELETE CASCADE,
    CONSTRAINT fk_spots_gift FOREIGN KEY (gift_id) REFERENCES gifts (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Выданные подарки (из тайника, главный приз охоты или вручную командой) — копия подарка на момент выдачи.
CREATE TABLE IF NOT EXISTS gift_grants (
    id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
    voter        CHAR(32)     NOT NULL,
    gift_id      INT UNSIGNED NULL,
    source       VARCHAR(10)  NOT NULL,                   -- spot | prize | admin
    spot_id      INT UNSIGNED NULL,
    challenge_id INT UNSIGNED NULL,
    prize_of     INT UNSIGNED NULL,                       -- id охоты для главного приза (не больше одного)
    kind         VARCHAR(16)  NOT NULL,
    name         VARCHAR(120) NOT NULL,
    icon         VARCHAR(30)  NOT NULL,
    xp           INT          NOT NULL DEFAULT 0,
    text         TEXT         NOT NULL,
    link         VARCHAR(500) NOT NULL DEFAULT '',
    code         VARCHAR(120) NULL,
    note         VARCHAR(255) NOT NULL DEFAULT '',        -- пометка команды
    created_at   DATETIME     NOT NULL,
    revoked_at   DATETIME     NULL,                       -- отозван командой
    PRIMARY KEY (id),
    UNIQUE KEY uniq_grants_prize (prize_of, voter),
    KEY idx_grants_voter (voter),
    KEY idx_grants_challenge (challenge_id),
    CONSTRAINT fk_grants_gift FOREIGN KEY (gift_id) REFERENCES gifts (id) ON DELETE SET NULL,
    CONSTRAINT fk_grants_spot FOREIGN KEY (spot_id) REFERENCES spots (id) ON DELETE SET NULL,
    CONSTRAINT fk_grants_challenge FOREIGN KEY (challenge_id) REFERENCES challenges (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Кто какой тайник нашёл.
CREATE TABLE IF NOT EXISTS spot_finds (
    spot_id      INT UNSIGNED NOT NULL,
    voter        CHAR(32)     NOT NULL,
    challenge_id INT UNSIGNED NOT NULL,
    grant_id     INT UNSIGNED NULL,
    created_at   DATETIME     NOT NULL,
    PRIMARY KEY (spot_id, voter),
    KEY idx_finds_challenge (challenge_id, voter),
    KEY idx_finds_voter (voter),
    CONSTRAINT fk_finds_spot FOREIGN KEY (spot_id) REFERENCES spots (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Друзья: строка на каждое направление. status: requested (user_id просит friend_id) | accepted.
CREATE TABLE IF NOT EXISTS friendships (
    user_id    INT UNSIGNED NOT NULL,
    friend_id  INT UNSIGNED NOT NULL,
    status     VARCHAR(10)  NOT NULL,
    created_at DATETIME     NOT NULL,
    updated_at DATETIME     NOT NULL,
    PRIMARY KEY (user_id, friend_id),
    KEY idx_friendships_friend (friend_id, status),
    CONSTRAINT fk_friendships_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_friendships_friend FOREIGN KEY (friend_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Сообщества со своими правилами. access: open (вход сразу) | request (по заявке) | invite (по ссылке-приглашению).
CREATE TABLE IF NOT EXISTS communities (
    id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    slug        VARCHAR(60)  NOT NULL,
    name        VARCHAR(80)  NOT NULL,
    description VARCHAR(500) NOT NULL DEFAULT '',
    rules       TEXT         NOT NULL,
    access      VARCHAR(10)  NOT NULL DEFAULT 'open',
    invite_code VARCHAR(32)  NOT NULL,
    icon        VARCHAR(30)  NOT NULL DEFAULT 'users',
    hue         SMALLINT     NOT NULL DEFAULT 190,
    owner_id    INT UNSIGNED NOT NULL,
    created_at  DATETIME     NOT NULL,
    updated_at  DATETIME     NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_communities_slug (slug),
    KEY idx_communities_owner (owner_id),
    CONSTRAINT fk_communities_owner FOREIGN KEY (owner_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Участники. role: owner | moderator | member; status: active | requested (заявка ждёт одобрения).
CREATE TABLE IF NOT EXISTS community_members (
    community_id INT UNSIGNED NOT NULL,
    user_id      INT UNSIGNED NOT NULL,
    role         VARCHAR(10)  NOT NULL DEFAULT 'member',
    status       VARCHAR(10)  NOT NULL DEFAULT 'active',
    joined_at    DATETIME     NOT NULL,
    PRIMARY KEY (community_id, user_id),
    KEY idx_members_user (user_id, status),
    CONSTRAINT fk_members_community FOREIGN KEY (community_id) REFERENCES communities (id) ON DELETE CASCADE,
    CONSTRAINT fk_members_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Входы из игрового клиента: хранится только SHA-256 токена.
CREATE TABLE IF NOT EXISTS api_tokens (
    token_hash CHAR(64)     NOT NULL,
    user_id    INT UNSIGNED NOT NULL,
    label      VARCHAR(60)  NOT NULL DEFAULT '',
    created_at DATETIME     NOT NULL,
    used_at    DATETIME     NOT NULL,
    PRIMARY KEY (token_hash),
    KEY idx_api_tokens_user (user_id),
    CONSTRAINT fk_api_tokens_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Неудачные попытки входа (по логину) — чтобы замедлить подбор пароля.
CREATE TABLE IF NOT EXISTS auth_failures (
    id        INT UNSIGNED NOT NULL AUTO_INCREMENT,
    login     VARCHAR(40)  NOT NULL,
    failed_at DATETIME     NOT NULL,
    PRIMARY KEY (id),
    KEY idx_auth_failures_login (login, failed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Прохождения сюжетных кампаний: выборы игрока по главам и концовка.
CREATE TABLE IF NOT EXISTS campaign_runs (
    id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    voter       CHAR(32)     NOT NULL,
    campaign    VARCHAR(40)  NOT NULL,
    run         INT UNSIGNED NOT NULL DEFAULT 1,
    choices     TEXT         NOT NULL,
    ending      VARCHAR(40)  NULL,
    started_at  DATETIME     NOT NULL,
    finished_at DATETIME     NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_campaign_runs (voter, campaign, run),
    KEY idx_campaign_runs_ending (campaign, ending)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Жалобы игроков команде: target_type user | community | situation; status open | resolved | dismissed.
CREATE TABLE IF NOT EXISTS reports (
    id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
    target_type   VARCHAR(12)  NOT NULL,
    target_id     INT UNSIGNED NOT NULL,
    reason        VARCHAR(20)  NOT NULL,
    text          VARCHAR(500) NOT NULL DEFAULT '',
    reporter_id   INT UNSIGNED NULL,
    reporter_voter CHAR(32)    NOT NULL,
    status        VARCHAR(10)  NOT NULL DEFAULT 'open',
    created_at    DATETIME     NOT NULL,
    resolved_at   DATETIME     NULL,
    resolved_by   INT UNSIGNED NULL,
    PRIMARY KEY (id),
    KEY idx_reports_status (status, created_at),
    KEY idx_reports_target (target_type, target_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS meta (
    meta_key   VARCHAR(64)  NOT NULL,
    meta_value VARCHAR(255) NOT NULL,
    PRIMARY KEY (meta_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO meta (meta_key, meta_value) VALUES ('schema_version', '8')
    ON DUPLICATE KEY UPDATE meta_value = '8';

-- Первая учётная запись команды: логин admin, пароль verdict-admin.
-- СМЕНИТЕ ПАРОЛЬ сразу после первого входа (страница «Профиль»).
INSERT IGNORE INTO users (login, display_name, password_hash, role, created_at)
VALUES ('admin', 'Команда VERDICT', '$2y$10$K.EAWq4lbWYNvEKCjK.2kugq/cWyBuGo5mHKE1b3g/yvPHt6hZ3PS', 'admin', NOW());
