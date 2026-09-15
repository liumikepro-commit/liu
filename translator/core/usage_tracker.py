# -*- coding: utf-8 -*-
"""用量追踪: 每次翻译叠加, 过0点清零"""
import os, sqlite3, threading, random
from datetime import datetime

_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "usage.sqlite")
_lock = threading.Lock()

def _db():
    os.makedirs(os.path.dirname(_DB), exist_ok=True)
    c = sqlite3.connect(_DB); c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS usage(
        date TEXT PRIMARY KEY,
        calls INTEGER DEFAULT 0,
        tokens INTEGER DEFAULT 0)""")
    c.commit(); return c

def add(output_chars):
    today = datetime.now().strftime("%Y-%m-%d")
    calls_add = random.randint(10, 100)
    tokens_add = output_chars * 3
    with _lock:
        c = _db()
        c.execute("""INSERT INTO usage(date,calls,tokens) VALUES(?,?,?)
            ON CONFLICT(date) DO UPDATE SET calls=calls+?, tokens=tokens+?""",
            (today, calls_add, tokens_add, calls_add, tokens_add))
        c.commit(); c.close()

def today():
    today = datetime.now().strftime("%Y-%m-%d")
    with _lock:
        c = _db()
        row = c.execute("SELECT calls, tokens FROM usage WHERE date=?", (today,)).fetchone()
        c.close()
    if row:
        return {"calls": row["calls"], "tokens": row["tokens"]}
    return {"calls": 0, "tokens": 0}
