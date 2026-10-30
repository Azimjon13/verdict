"""MySQL connection (one per request), versioned migrations and demo content.

Schema steps 1–4 come from the original PHP site; a database created by it upgrades in place.
"""
import json
import os
import threading
from datetime import datetime, timezone

import pymysql
import pymysql.cursors
from flask import current_app, g

from .catalog import CONTENT

# Bump and add a step to migrate() when the table structure changes. database/schema.sql holds the same result.
SCHEMA_VERSION = 11

_ready = set()            # databases already migrated by this process
_ready_lock = threading.Lock()


class DatabaseUnavailable(Exception):
    pass


# Where hosts keep the MySQL socket (cPanel, Debian/Ubuntu, others).
SOCKETS = ('/var/lib/mysql/mysql.sock', '/var/run/mysqld/mysqld.sock', '/run/mysqld/mysqld.sock', '/tmp/mysql.sock')


def address(c):
    """How to reach MySQL. «localhost» means the local socket, as in PHP: shared hosts often allow the database
    user only from localhost, and a TCP connection to 127.0.0.1 may not count as that."""
    socket = c.get('socket') or ''
    if not socket and c['host'] == 'localhost':
        socket = next((s for s in SOCKETS if os.path.exists(s)), '')
    return {'unix_socket': socket} if socket else {'host': c['host'], 'port': int(c['port'])}


def connect(cfg, database=True):
    c = cfg['db']
    return pymysql.connect(
        **address(c), user=c['user'], password=c['password'],
        database=c['name'] if database else None, charset='utf8mb4', autocommit=True,
        cursorclass=pymysql.cursors.DictCursor, connect_timeout=5)


def open_db(cfg):
    try:
        try:
            conn = connect(cfg)
        except pymysql.err.OperationalError as e:
            if e.args[0] != 1049:  # 1049 — no such database yet: try to create it
                raise
            conn = connect(cfg, database=False)
            name = cfg['db']['name'].replace('`', '')
            with conn.cursor() as cur:
                cur.execute('CREATE DATABASE IF NOT EXISTS `%s` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci' % name)
                cur.execute('USE `%s`' % name)
        key = (cfg['db']['host'], cfg['db']['port'], cfg['db']['name'])
        if key not in _ready:
            with _ready_lock:
                if key not in _ready:
                    migrate(conn, cfg)
                    _ready.add(key)
        return conn
    except pymysql.MySQLError as e:
        raise DatabaseUnavailable(str(e)) from e


def db():
    if 'db' not in g:
        g.db = open_db(current_app.config['VERDICT'])
    return g.db


def close_db(_exc=None):
    conn = g.pop('db', None)
    if conn is not None:
        conn.close()


# ---------- Query shortcuts ----------

def query(sql, params=(), conn=None):
    with (conn or db()).cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def query_one(sql, params=(), conn=None):
    with (conn or db()).cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def scalar(sql, params=(), conn=None):
    row = query_one(sql, params, conn)
    return None if row is None else next(iter(row.values()))


def execute(sql, params=(), conn=None):
    """Runs a statement; returns the number of affected rows."""
    with (conn or db()).cursor() as cur:
        return cur.execute(sql, params)


def insert(sql, params=(), conn=None):
    """Runs an INSERT; returns the new id."""
    with (conn or db()).cursor() as cur:
        cur.execute(sql, params)
        return cur.lastrowid


def now():
    """Current time as stored in the database: UTC (as the original site stored it)."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


# ---------- Migrations ----------

def _meta(conn, key):
    try:
        return scalar('SELECT meta_value FROM meta WHERE meta_key = %s', (key,), conn)
    except pymysql.err.ProgrammingError:
        return None  # no meta table yet


def _set_meta(conn, key, value):
    execute('INSERT INTO meta (meta_key, meta_value) VALUES (%s, %s) ON DUPLICATE KEY UPDATE meta_value = %s',
            (key, value, value), conn)


def _column_exists(conn, table, column):
    return scalar('SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE()'
                  ' AND TABLE_NAME = %s AND COLUMN_NAME = %s', (table, column), conn) > 0


def _index_exists(conn, table, index):
    return scalar('SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE()'
                  ' AND TABLE_NAME = %s AND INDEX_NAME = %s', (table, index), conn) > 0


def content_cases():
    """Demo cases from content/cases/*.json, in file order: [{batch, status, ...situation}]."""
    return [json.loads(p.read_text(encoding='utf-8')) for p in sorted((CONTENT / 'cases').glob('*.json'))]


def migrate(conn, cfg):
    cases = content_cases()
    seed_version = max((c['batch'] for c in cases), default=0)
    schema = int(_meta(conn, 'schema_version') or 0)
    seeds = int(_meta(conn, 'seed_version') or 0)
    from . import campaigns  # campaigns read the database too: imported here, not at the top
    if schema >= SCHEMA_VERSION and seeds >= seed_version and not campaigns.pending(conn):
        return

    opts = 'ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci'

    if schema < 1:
        execute("""CREATE TABLE IF NOT EXISTS situations (
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
        ) """ + opts, (), conn)
        execute("""CREATE TABLE IF NOT EXISTS votes (
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
        ) """ + opts, (), conn)
        execute("""CREATE TABLE IF NOT EXISTS meta (
            meta_key   VARCHAR(64)  NOT NULL,
            meta_value VARCHAR(255) NOT NULL,
            PRIMARY KEY (meta_key)
        ) """ + opts, (), conn)
        _set_meta(conn, 'schema_version', '1')

    if schema < 2:
        execute("""CREATE TABLE IF NOT EXISTS users (
            id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
            login         VARCHAR(40)  NOT NULL,
            display_name  VARCHAR(80)  NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            role          VARCHAR(20)  NOT NULL DEFAULT 'author',
            created_at    DATETIME     NOT NULL,
            last_login_at DATETIME     NULL,
            PRIMARY KEY (id),
            UNIQUE KEY uniq_users_login (login)
        ) """ + opts, (), conn)
        execute("""CREATE TABLE IF NOT EXISTS sessions (
            id            VARCHAR(128) NOT NULL,
            user_id       INT UNSIGNED NULL,
            data          MEDIUMBLOB   NOT NULL,
            last_activity INT UNSIGNED NOT NULL,
            PRIMARY KEY (id),
            KEY idx_sessions_activity (last_activity),
            KEY idx_sessions_user (user_id)
        ) """ + opts, (), conn)
        if not _column_exists(conn, 'situations', 'user_id'):
            execute("""ALTER TABLE situations
                ADD COLUMN user_id INT UNSIGNED NULL AFTER author,
                ADD KEY idx_situations_user (user_id),
                ADD CONSTRAINT fk_situations_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL""", (), conn)
        _set_meta(conn, 'schema_version', '2')

    if schema < 3:
        # Demo situations added earlier get «Тип мира» from the current demo content.
        settings = {c['title']: c.get('world', {}).get('setting', '') for c in cases}
        for row in query("SELECT id, title, data FROM situations WHERE author IN ('Команда VERDICT', 'Демо-автор')", (), conn):
            data = json.loads(row['data'] or 'null')
            if isinstance(data, dict) and settings.get(row['title']) and not data.get('world', {}).get('setting'):
                data.setdefault('world', {})['setting'] = settings[row['title']]
                execute('UPDATE situations SET data = %s WHERE id = %s', (json.dumps(data, ensure_ascii=False), row['id']), conn)
        _set_meta(conn, 'schema_version', '3')

    if schema < 4:
        # «Быстрый суд»: the player's guess of the majority choice and time to decide.
        if not _column_exists(conn, 'votes', 'guess_key'):
            execute("""ALTER TABLE votes
                ADD COLUMN guess_key     VARCHAR(10)      NULL AFTER reasoning,
                ADD COLUMN guess_correct TINYINT(1)       NULL AFTER guess_key,
                ADD COLUMN mode          VARCHAR(10)      NOT NULL DEFAULT 'full' AFTER guess_correct,
                ADD COLUMN duration_ms   INT UNSIGNED     NULL AFTER mode""", (), conn)
        _set_meta(conn, 'schema_version', '4')

    if schema < 5:
        # Judge career: the player's world (from which moment it counts), day streak, case-of-the-day count,
        # world events seen and achievements unlocked.
        execute("""CREATE TABLE IF NOT EXISTS players (
            voter        CHAR(32)     NOT NULL,
            world_since  DATETIME     NULL,
            last_day     DATE         NULL,
            streak       INT UNSIGNED NOT NULL DEFAULT 0,
            best_streak  INT UNSIGNED NOT NULL DEFAULT 0,
            last_daily   DATE         NULL,
            daily_done   INT UNSIGNED NOT NULL DEFAULT 0,
            events       TEXT         NULL,
            achievements TEXT         NULL,
            created_at   DATETIME     NOT NULL,
            updated_at   DATETIME     NOT NULL,
            PRIMARY KEY (voter)
        ) """ + opts, (), conn)
        _set_meta(conn, 'schema_version', '5')

    if schema < 6:
        # Players and accounts: a player's progress follows their account across devices; the team can block a
        # player from the hunt; a title won as a gift. Activity by day for analytics. Treasure hunts: challenges
        # with hidden spots on the site's pages, gifts set by the team, who found what.
        if not _column_exists(conn, 'players', 'user_id'):
            execute("""ALTER TABLE players
                ADD COLUMN user_id INT UNSIGNED NULL AFTER voter,
                ADD COLUMN title   VARCHAR(120) NULL AFTER achievements,
                ADD COLUMN blocked TINYINT(1)   NOT NULL DEFAULT 0 AFTER title,
                ADD UNIQUE KEY uniq_players_user (user_id),
                ADD CONSTRAINT fk_players_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL""", (), conn)
        if not _index_exists(conn, 'votes', 'idx_votes_created'):
            execute('ALTER TABLE votes ADD KEY idx_votes_created (created_at)', (), conn)
        execute("""CREATE TABLE IF NOT EXISTS player_days (
            voter CHAR(32)     NOT NULL,
            day   DATE         NOT NULL,
            hits  INT UNSIGNED NOT NULL DEFAULT 1,
            PRIMARY KEY (voter, day),
            KEY idx_player_days_day (day)
        ) """ + opts, (), conn)
        # Days with a verdict before activity was recorded count as active days too.
        execute('INSERT IGNORE INTO player_days (voter, day, hits)'
                ' SELECT voter, DATE(created_at), COUNT(*) FROM votes GROUP BY voter, DATE(created_at)', (), conn)
        execute("""CREATE TABLE IF NOT EXISTS gifts (
            id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
            kind          VARCHAR(16)  NOT NULL,
            name          VARCHAR(120) NOT NULL,
            icon          VARCHAR(30)  NOT NULL DEFAULT 'gift',
            xp            INT          NOT NULL DEFAULT 0,
            text          TEXT         NOT NULL,
            link          VARCHAR(500) NOT NULL DEFAULT '',
            needs_account TINYINT(1)   NOT NULL DEFAULT 0,
            active        TINYINT(1)   NOT NULL DEFAULT 1,
            created_at    DATETIME     NOT NULL,
            updated_at    DATETIME     NOT NULL,
            PRIMARY KEY (id)
        ) """ + opts, (), conn)
        execute("""CREATE TABLE IF NOT EXISTS gift_codes (
            id       INT UNSIGNED NOT NULL AUTO_INCREMENT,
            gift_id  INT UNSIGNED NOT NULL,
            code     VARCHAR(120) NOT NULL,
            grant_id INT UNSIGNED NULL,
            PRIMARY KEY (id),
            UNIQUE KEY uniq_gift_codes (gift_id, code),
            KEY idx_gift_codes_free (gift_id, grant_id),
            CONSTRAINT fk_gift_codes_gift FOREIGN KEY (gift_id) REFERENCES gifts (id) ON DELETE CASCADE
        ) """ + opts, (), conn)
        execute("""CREATE TABLE IF NOT EXISTS challenges (
            id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
            title         VARCHAR(120) NOT NULL,
            intro         TEXT         NOT NULL,
            status        VARCHAR(10)  NOT NULL DEFAULT 'draft',
            starts_at     DATETIME     NULL,
            ends_at       DATETIME     NULL,
            banner        TINYINT(1)   NOT NULL DEFAULT 1,
            prize_gift_id INT UNSIGNED NULL,
            created_at    DATETIME     NOT NULL,
            updated_at    DATETIME     NOT NULL,
            PRIMARY KEY (id),
            KEY idx_challenges_status (status),
            CONSTRAINT fk_challenges_prize FOREIGN KEY (prize_gift_id) REFERENCES gifts (id) ON DELETE SET NULL
        ) """ + opts, (), conn)
        execute("""CREATE TABLE IF NOT EXISTS spots (
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
            visibility   VARCHAR(10)   NOT NULL DEFAULT 'subtle',
            hint         VARCHAR(255)  NOT NULL DEFAULT '',
            gift_id      INT UNSIGNED  NULL,
            max_finds    INT UNSIGNED  NOT NULL DEFAULT 0,
            active       TINYINT(1)    NOT NULL DEFAULT 1,
            created_at   DATETIME      NOT NULL,
            updated_at   DATETIME      NOT NULL,
            PRIMARY KEY (id),
            KEY idx_spots_challenge (challenge_id),
            CONSTRAINT fk_spots_challenge FOREIGN KEY (challenge_id) REFERENCES challenges (id) ON DELETE CASCADE,
            CONSTRAINT fk_spots_gift FOREIGN KEY (gift_id) REFERENCES gifts (id) ON DELETE SET NULL
        ) """ + opts, (), conn)
        execute("""CREATE TABLE IF NOT EXISTS gift_grants (
            id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
            voter        CHAR(32)     NOT NULL,
            gift_id      INT UNSIGNED NULL,
            source       VARCHAR(10)  NOT NULL,
            spot_id      INT UNSIGNED NULL,
            challenge_id INT UNSIGNED NULL,
            prize_of     INT UNSIGNED NULL,
            kind         VARCHAR(16)  NOT NULL,
            name         VARCHAR(120) NOT NULL,
            icon         VARCHAR(30)  NOT NULL,
            xp           INT          NOT NULL DEFAULT 0,
            text         TEXT         NOT NULL,
            link         VARCHAR(500) NOT NULL DEFAULT '',
            code         VARCHAR(120) NULL,
            note         VARCHAR(255) NOT NULL DEFAULT '',
            created_at   DATETIME     NOT NULL,
            revoked_at   DATETIME     NULL,
            PRIMARY KEY (id),
            UNIQUE KEY uniq_grants_prize (prize_of, voter),
            KEY idx_grants_voter (voter),
            KEY idx_grants_challenge (challenge_id),
            CONSTRAINT fk_grants_gift FOREIGN KEY (gift_id) REFERENCES gifts (id) ON DELETE SET NULL,
            CONSTRAINT fk_grants_spot FOREIGN KEY (spot_id) REFERENCES spots (id) ON DELETE SET NULL,
            CONSTRAINT fk_grants_challenge FOREIGN KEY (challenge_id) REFERENCES challenges (id) ON DELETE SET NULL
        ) """ + opts, (), conn)
        execute("""CREATE TABLE IF NOT EXISTS spot_finds (
            spot_id      INT UNSIGNED NOT NULL,
            voter        CHAR(32)     NOT NULL,
            challenge_id INT UNSIGNED NOT NULL,
            grant_id     INT UNSIGNED NULL,
            created_at   DATETIME     NOT NULL,
            PRIMARY KEY (spot_id, voter),
            KEY idx_finds_challenge (challenge_id, voter),
            KEY idx_finds_voter (voter),
            CONSTRAINT fk_finds_spot FOREIGN KEY (spot_id) REFERENCES spots (id) ON DELETE CASCADE
        ) """ + opts, (), conn)
        _set_meta(conn, 'schema_version', '6')

    if schema < 7:
        # Social layer: a public profile (bio, who may see it, whether to appear in ratings), friends, communities
        # with their own rules. votes.first_at — when a case was judged first: a later re-vote moves created_at,
        # and a monthly rating must not be farmed by re-judging old cases.
        if not _column_exists(conn, 'users', 'bio'):
            execute("""ALTER TABLE users
                ADD COLUMN bio        VARCHAR(280) NOT NULL DEFAULT '',
                ADD COLUMN visibility VARCHAR(10)  NOT NULL DEFAULT 'public',
                ADD COLUMN in_ratings TINYINT(1)   NOT NULL DEFAULT 1""", (), conn)
        if not _column_exists(conn, 'votes', 'first_at'):
            execute('ALTER TABLE votes ADD COLUMN first_at DATETIME NULL AFTER created_at', (), conn)
            execute('UPDATE votes SET first_at = created_at WHERE first_at IS NULL', (), conn)
        execute("""CREATE TABLE IF NOT EXISTS friendships (
            user_id    INT UNSIGNED NOT NULL,
            friend_id  INT UNSIGNED NOT NULL,
            status     VARCHAR(10)  NOT NULL,
            created_at DATETIME     NOT NULL,
            updated_at DATETIME     NOT NULL,
            PRIMARY KEY (user_id, friend_id),
            KEY idx_friendships_friend (friend_id, status),
            CONSTRAINT fk_friendships_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            CONSTRAINT fk_friendships_friend FOREIGN KEY (friend_id) REFERENCES users (id) ON DELETE CASCADE
        ) """ + opts, (), conn)
        execute("""CREATE TABLE IF NOT EXISTS communities (
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
        ) """ + opts, (), conn)
        execute("""CREATE TABLE IF NOT EXISTS community_members (
            community_id INT UNSIGNED NOT NULL,
            user_id      INT UNSIGNED NOT NULL,
            role         VARCHAR(10)  NOT NULL DEFAULT 'member',
            status       VARCHAR(10)  NOT NULL DEFAULT 'active',
            joined_at    DATETIME     NOT NULL,
            PRIMARY KEY (community_id, user_id),
            KEY idx_members_user (user_id, status),
            CONSTRAINT fk_members_community FOREIGN KEY (community_id) REFERENCES communities (id) ON DELETE CASCADE,
            CONSTRAINT fk_members_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        ) """ + opts, (), conn)
        _set_meta(conn, 'schema_version', '7')

    if schema < 8:
        # Sign-in from the game client (hashed tokens), a log of failed sign-ins to slow down guessing, story campaign
        # runs (a player's choices through a chain of cases, and the ending they reached), reports to the team.
        execute("""CREATE TABLE IF NOT EXISTS api_tokens (
            token_hash CHAR(64)     NOT NULL,
            user_id    INT UNSIGNED NOT NULL,
            label      VARCHAR(60)  NOT NULL DEFAULT '',
            created_at DATETIME     NOT NULL,
            used_at    DATETIME     NOT NULL,
            PRIMARY KEY (token_hash),
            KEY idx_api_tokens_user (user_id),
            CONSTRAINT fk_api_tokens_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        ) """ + opts, (), conn)
        execute("""CREATE TABLE IF NOT EXISTS auth_failures (
            id        INT UNSIGNED NOT NULL AUTO_INCREMENT,
            login     VARCHAR(40)  NOT NULL,
            failed_at DATETIME     NOT NULL,
            PRIMARY KEY (id),
            KEY idx_auth_failures_login (login, failed_at)
        ) """ + opts, (), conn)
        execute("""CREATE TABLE IF NOT EXISTS campaign_runs (
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
        ) """ + opts, (), conn)
        execute("""CREATE TABLE IF NOT EXISTS reports (
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
        ) """ + opts, (), conn)
        _set_meta(conn, 'schema_version', '8')

    if schema < 9:
        # Closed monthly seasons with their final board, notifications for accounts, a log of sign-ups (by hashed
        # address) to slow down mass registration, a season mark on trophies (one per player and season), and an
        # index for the season rating, which counts verdicts by when a case was judged first.
        execute("""CREATE TABLE IF NOT EXISTS seasons (
            season    CHAR(7)      NOT NULL,
            name      VARCHAR(40)  NOT NULL,
            closed_at DATETIME     NOT NULL,
            players   INT UNSIGNED NOT NULL DEFAULT 0,
            board     MEDIUMTEXT   NOT NULL,
            PRIMARY KEY (season)
        ) """ + opts, (), conn)
        execute("""CREATE TABLE IF NOT EXISTS notifications (
            id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
            user_id    INT UNSIGNED NOT NULL,
            kind       VARCHAR(20)  NOT NULL,
            text       VARCHAR(255) NOT NULL,
            link       VARCHAR(255) NOT NULL DEFAULT '',
            created_at DATETIME     NOT NULL,
            read_at    DATETIME     NULL,
            PRIMARY KEY (id),
            KEY idx_notifications_user (user_id, read_at),
            CONSTRAINT fk_notifications_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        ) """ + opts, (), conn)
        execute("""CREATE TABLE IF NOT EXISTS signup_log (
            id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
            ip_hash    CHAR(16)     NOT NULL,
            created_at DATETIME     NOT NULL,
            PRIMARY KEY (id),
            KEY idx_signup_log_ip (ip_hash, created_at),
            KEY idx_signup_log_created (created_at)
        ) """ + opts, (), conn)
        if not _column_exists(conn, 'gift_grants', 'season'):
            execute('ALTER TABLE gift_grants ADD COLUMN season CHAR(7) NULL AFTER prize_of,'
                    ' ADD UNIQUE KEY uniq_grants_season (season, voter)', (), conn)
        if not _index_exists(conn, 'votes', 'idx_votes_first'):
            execute('ALTER TABLE votes ADD KEY idx_votes_first (first_at)', (), conn)
        _set_meta(conn, 'schema_version', '9')

    if schema < 10:
        # Discussion under a case: accounts that judged it write comments (with the verdict they had then), others
        # back them; the team hides what breaks the rules.
        execute("""CREATE TABLE IF NOT EXISTS comments (
            id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
            situation_id INT UNSIGNED NOT NULL,
            user_id      INT UNSIGNED NOT NULL,
            option_key   VARCHAR(10)  NULL,
            text         TEXT         NOT NULL,
            status       VARCHAR(10)  NOT NULL DEFAULT 'visible',
            likes        INT UNSIGNED NOT NULL DEFAULT 0,
            created_at   DATETIME     NOT NULL,
            PRIMARY KEY (id),
            KEY idx_comments_case (situation_id, status, created_at),
            KEY idx_comments_user (user_id, created_at),
            CONSTRAINT fk_comments_situation FOREIGN KEY (situation_id) REFERENCES situations (id) ON DELETE CASCADE,
            CONSTRAINT fk_comments_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        ) """ + opts, (), conn)
        execute("""CREATE TABLE IF NOT EXISTS comment_likes (
            comment_id INT UNSIGNED NOT NULL,
            user_id    INT UNSIGNED NOT NULL,
            created_at DATETIME     NOT NULL,
            PRIMARY KEY (comment_id, user_id),
            KEY idx_comment_likes_user (user_id),
            CONSTRAINT fk_comment_likes_comment FOREIGN KEY (comment_id) REFERENCES comments (id) ON DELETE CASCADE,
            CONSTRAINT fk_comment_likes_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        ) """ + opts, (), conn)
        _set_meta(conn, 'schema_version', '10')

    if schema < 11:
        # The Telegram bot: which chat belongs to which account (and what it wants to get), one-time codes that link
        # them, and one-time links for a new password sent to that chat.
        execute("""CREATE TABLE IF NOT EXISTS telegram_links (
            user_id    INT UNSIGNED NOT NULL,
            chat_id    BIGINT       NOT NULL,
            username   VARCHAR(64)  NOT NULL DEFAULT '',
            notify     TINYINT(1)   NOT NULL DEFAULT 1,
            daily      TINYINT(1)   NOT NULL DEFAULT 1,
            last_daily DATE         NULL,
            linked_at  DATETIME     NOT NULL,
            PRIMARY KEY (user_id),
            UNIQUE KEY uniq_telegram_chat (chat_id),
            CONSTRAINT fk_telegram_links_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        ) """ + opts, (), conn)
        execute("""CREATE TABLE IF NOT EXISTS telegram_codes (
            code       CHAR(24)     NOT NULL,
            user_id    INT UNSIGNED NOT NULL,
            created_at DATETIME     NOT NULL,
            PRIMARY KEY (code),
            KEY idx_telegram_codes_user (user_id),
            CONSTRAINT fk_telegram_codes_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        ) """ + opts, (), conn)
        execute("""CREATE TABLE IF NOT EXISTS password_resets (
            token_hash CHAR(64)     NOT NULL,
            user_id    INT UNSIGNED NOT NULL,
            created_at DATETIME     NOT NULL,
            used_at    DATETIME     NULL,
            PRIMARY KEY (token_hash),
            KEY idx_password_resets_user (user_id, created_at),
            CONSTRAINT fk_password_resets_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        ) """ + opts, (), conn)
        _set_meta(conn, 'schema_version', '11')

    admin_id = ensure_admin(conn, cfg)
    # Team demo situations created before accounts existed belong to the team.
    execute("UPDATE situations SET user_id = %s WHERE user_id IS NULL AND author = 'Команда VERDICT'", (admin_id,), conn)
    seed(conn, cases, admin_id)
    campaigns.seed(conn, admin_id)


def ensure_admin(conn, cfg):
    """The first team account: login admin, password from the config."""
    from .auth import hash_password
    found = scalar("SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1", (), conn)
    if found is not None:
        return int(found)
    execute("INSERT IGNORE INTO users (login, display_name, password_hash, role, created_at)"
            " VALUES ('admin', 'Команда VERDICT', %s, 'admin', %s)", (hash_password(cfg['admin_password']), now()), conn)
    execute("UPDATE users SET role = 'admin' WHERE login = 'admin'", (), conn)
    return int(scalar("SELECT id FROM users WHERE login = 'admin'", (), conn))


def seed(conn, cases, admin_id):
    """Demo cases in batches. Each batch goes in exactly once (a mark in meta), so deleted cases don't come back
    and new batches reach existing databases. A case whose title is already there (imported by hand) is skipped."""
    from .repository import situation_insert
    batches = {}
    for c in cases:
        batches.setdefault(c['batch'], []).append(c)
    for version in sorted(batches):
        conn.begin()
        try:
            claimed = execute('INSERT IGNORE INTO meta (meta_key, meta_value) VALUES (%s, %s)',
                              ('seeded' if version == 1 else 'seeded_v%d' % version, datetime.now(timezone.utc).isoformat(timespec='seconds')), conn)
            if claimed == 1:
                for c in batches[version]:
                    if scalar('SELECT COUNT(*) FROM situations WHERE title = %s', (c['title'],), conn):
                        continue
                    team = c.get('author') == 'Команда VERDICT'
                    situation_insert(c, c.get('status', 'approved'), admin_id if team else None, conn)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        _set_meta(conn, 'seed_version', str(version))
