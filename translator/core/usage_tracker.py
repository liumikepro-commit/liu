# -*- coding: utf-8 -*-
"""用量追踪: 记录每次翻译调用, 提供统计查询"""
import os, sqlite3, threading
from datetime import datetime

_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "usage.sqlite")
_lock = threading.Lock()

def _db():
    os.makedirs(os.path.dirname(_DB), exist_ok=True)
    c = sqlite3.connect(_DB); c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS usage_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, date TEXT, engine TEXT,
        source TEXT, target TEXT, input_chars INTEGER, output_chars INTEGER,
        est_tokens INTEGER, success INTEGER, error TEXT)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_date ON usage_log(date)")
    c.commit(); return c

def record(engine, source, target, in_c, out_c, ok=True, err=None):
    t = datetime.now()
    zh = (source=="zh") or (target=="zh")
    ratio = 1.5 if zh else 4.0
    tok = int(in_c/ratio + out_c/ratio)
    with _lock:
        c = _db(); c.execute("INSERT INTO usage_log(ts,date,engine,source,target,input_chars,output_chars,est_tokens,success,error) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (t.strftime("%Y-%m-%d %H:%M:%S"), t.strftime("%Y-%m-%d"), engine, source or "", target or "",
             in_c, out_c, tok, 1 if ok else 0, err)); c.commit(); c.close()

def stats():
    with _lock:
        c = _db()
        today = dict(c.execute("SELECT COUNT(*) AS count, SUM(input_chars) AS i, SUM(output_chars) AS o, SUM(est_tokens) AS t, SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) AS ok FROM usage_log WHERE date=date('now')").fetchone() or {})
        total = dict(c.execute("SELECT COUNT(*) AS count, SUM(input_chars) AS i, SUM(output_chars) AS o, SUM(est_tokens) AS t FROM usage_log").fetchone() or {})
        daily = [dict(r) for r in c.execute("SELECT date, COUNT(*) AS count, SUM(est_tokens) AS tokens FROM usage_log GROUP BY date ORDER BY date DESC LIMIT 30")]
        engines = [dict(r) for r in c.execute("SELECT engine, COUNT(*) AS count, SUM(est_tokens) AS tokens FROM usage_log GROUP BY engine ORDER BY count DESC")]
        c.close()
    return {"today": today, "total": total, "daily": daily, "engines": engines}
