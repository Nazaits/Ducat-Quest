# db.py
import sqlite3
from contextlib import closing

DB = "ducat_quest.db"

def init_db():
    with closing(sqlite3.connect(DB)) as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            name TEXT,
            description TEXT,
            type TEXT,                    -- daily, weekly, one-time
            completed BOOLEAN DEFAULT 0,
            current_ducat_value REAL,
            initial_ducat_value REAL,
            last_completed TEXT,
            created_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY,
            text TEXT,
            submitted_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS shop_items (
            id INTEGER PRIMARY KEY,
            name TEXT,
            description TEXT,
            link TEXT,
            real_value REAL,
            ducat_value REAL,
            in_rotation INTEGER DEFAULT 0,
            bought INTEGER DEFAULT 0,
            added_at TEXT,
            image TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS user_stats (
            key TEXT PRIMARY KEY,
            value TEXT
        )""")
        # initialize stats
        for key, value in [
            ("ducats_earned", "0"),
            ("ducats_spent", "0"),
            ("budget", "500"),
            ("conversion_rate", "100"),
            ("last_shop_rotation", "2000-01-01T00:00:00")
        ]:
            c.execute("INSERT OR IGNORE INTO user_stats VALUES (?,?)", (key, value))
        conn.commit()


def query(sql, params=(), commit=False):
    with closing(sqlite3.connect(DB)) as conn:
        c = conn.cursor()
        c.execute(sql, params)
        result = c.fetchall()
        if commit: conn.commit()
    return result
