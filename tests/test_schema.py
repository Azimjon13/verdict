"""database/schema.sql (for importing by hand) must build the same tables, columns and indexes as the migrations."""
from pathlib import Path

import pymysql

from conftest import DB

SCHEMA = Path(__file__).resolve().parent.parent / 'database' / 'schema.sql'


def shape(cur, name):
    cur.execute('SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT FROM information_schema.COLUMNS'
                ' WHERE TABLE_SCHEMA = %s', (name,))
    columns = {(r[0], r[1]): r[2:] for r in cur.fetchall()}
    cur.execute('SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX)'
                ' FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = %s GROUP BY TABLE_NAME, INDEX_NAME, NON_UNIQUE', (name,))
    indexes = {(r[0], r[1]): (r[2], r[3]) for r in cur.fetchall()}
    return columns, indexes


def test_schema_sql_matches_the_migrations(app):
    manual = DB['name'] + '_sql'
    conn = pymysql.connect(host=DB['host'], port=DB['port'], user=DB['user'], password=DB['password'], charset='utf8mb4',
                           autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute('DROP DATABASE IF EXISTS `%s`' % manual)
            cur.execute('CREATE DATABASE `%s` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci' % manual)
            cur.execute('USE `%s`' % manual)
            sql = '\n'.join(line for line in SCHEMA.read_text(encoding='utf-8').splitlines() if not line.lstrip().startswith('--'))
            for statement in filter(str.strip, sql.split(';\n')):
                if not statement.strip().upper().startswith(('CREATE DATABASE', 'USE ')):  # the file picks its own database
                    cur.execute(statement)
            migrated, by_hand = shape(cur, DB['name']), shape(cur, manual)
            cur.execute("SELECT meta_value FROM meta WHERE meta_key = 'schema_version'")
            version = cur.fetchone()[0]
            cur.execute('DROP DATABASE `%s`' % manual)
    finally:
        conn.close()
    assert version == str(__import__('verdict.db', fromlist=['SCHEMA_VERSION']).SCHEMA_VERSION)
    for what, a, b in (('columns', migrated[0], by_hand[0]), ('indexes', migrated[1], by_hand[1])):
        assert sorted(set(a) - set(b)) == [], 'only the migrations have these %s' % what
        assert sorted(set(b) - set(a)) == [], 'only schema.sql has these %s' % what
        assert {k: a[k] for k in a if a[k] != b[k]} == {}, '%s differ' % what
