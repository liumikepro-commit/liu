# -*- coding: utf-8 -*-
"""
usage_tracker.py — 翻译用量追踪
记录每次翻译调用的引擎、语言对、字符数、成功/失败，提供每日统计查询。
数据存储在 SQLite (translator/data/usage.sqlite)，与翻译记忆 (tm.sqlite) 鷃力互不干扰。
"""
import os
import sqlite3
import threading
from datetime import datetime

_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "usage.sqlite",
)
_lock = threading.Lock()

# 粗略 token 估算系数 (OpenAI 风格: 1 token ~ 4 字符英文 / ~1.5 字符中文)
# 仅用于参考，实际计费以各引擎后台为准
TOKEN_RATIO_EN = 4.0
TOKEN_RATIO_ZH = 1.5


def _get_db():
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            date TEXT NOT NULL,
            engine TEXT NOT NULL,
            source TEXT,
            target TEXT,
            input_chars INTEGER DEFAULT 0,
            output_chars INTEGER DEFAULT 0,
            est_tokens INTEGER DEFAULT 0,
            success INTEGER DEFAULT 1,
            error TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_usage_date ON usage_log(date)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_usage_engine ON usage_log(engine)
    """)
    conn.commit()
    return conn


def _estimate_tokens(input_chars, output_chars, source, target):
    zh = "zh"
    src_is_zh = source == zh
    tgt_is_zh = target == zh
    in_ratio = TOKEN_RATIO_ZH if src_is_zh else TOKEN_RATIO_EN
    out_ratio = TOKEN_RATIO_ZH if tgt_is_zh else TOKEN_RATIO_EN
    return int(input_chars / in_ratio + output_chars / out_ratio)


def record(engine, source, target, input_chars, output_chars,
           success=True, error=None):
    now = datetime.now()
    est_tokens = _estimate_tokens(input_chars, output_chars, source, target)
    with _lock:
        conn = _get_db()
        conn.execute(
            "INSERT INTO usage_log "
            "(ts, date, engine, source, target, input_chars, output_chars, "
            "est_tokens, success, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (now.strftime("%Y-%m-%d %H:%M:%S"),
             now.strftime("%Y-%m-%d"),
             engine, source or "", target or "",
             input_chars, output_chars, est_tokens,
             1 if success else 0, error)
        )
        conn.commit()
        conn.close()


def daily_stats(days=30):
    with _lock:
        conn = _get_db()
        rows = conn.execute("""
            SELECT date,
                   COUNT(*)                     AS count,
                   SUM(input_chars)             AS total_input,
                   SUM(output_chars)            AS total_output,
                   SUM(est_tokens)              AS total_tokens,
                   SUM(CASE WHEN success=1
                       THEN 1 ELSE 0 END)       AS success_count,
                   SUM(CASE WHEN success=0
                       THEN 1 ELSE 0 END)       AS fail_count
            FROM usage_log
            WHERE date >= date('now', ?)
            GROUP BY date
            ORDER BY date DESC
        """, (f"-{days} days",)).fetchall()
        conn.close()
    return [dict(r) for r in rows]


def engine_stats():
    with _lock:
        conn = _get_db()
        rows = conn.execute("""
            SELECT engine,
                   COUNT(*)                     AS count,
                   SUM(input_chars)             AS total_input,
                   SUM(output_chars)            AS total_output,
                   SUM(est_tokens)              AS total_tokens,
                   SUM(CASE WHEN success=1
                       THEN 1 ELSE 0 END)       AS success_count
            FROM usage_log
            GROUP BY engine
            ORDER BY count DESC
        """).fetchall()
        conn.close()
    return [dict(r) for r in rows]


def recent_records(limit=50):
    with _lock:
        conn = _get_db()
        rows = conn.execute("""
            SELECT ts, engine, source, target,
                   input_chars, output_chars, est_tokens,
                   success, error
            FROM usage_log
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
    return [dict(r) for r in rows]


def total_stats():
    with _lock:
        conn = _get_db()
        row = conn.execute("""
            SELECT COUNT(*)                     AS total_calls,
                   SUM(input_chars)             AS total_input,
                   SUM(output_chars)            AS total_output,
                   SUM(est_tokens)              AS total_tokens,
                   SUM(CASE WHEN success=1
                       THEN 1 ELSE 0 END)       AS success_count,
                   SUM(CASE WHEN success=0
                       THEN 1 ELSE 0 END)       AS fail_count
            FROM usage_log
        """).fetchone()
        conn.close()
    return dict(row) if row else {}


def today_stats():
    with _lock:
        conn = _get_db()
        row = conn.execute("""
            SELECT COUNT(*)                     AS count,
                   SUM(input_chars)             AS total_input,
                   SUM(output_chars)            AS total_output,
                   SUM(est_tokens)              AS total_tokens,
                   SUM(CASE WHEN success=1
                       THEN 1 ELSE 0 END)       AS success_count,
                   SUM(CASE WHEN success=0
                       THEN 1 ELSE 0 END)       AS fail_count
            FROM usage_log
            WHERE date = date('now')
        """).fetchone()
        conn.close()
    return dict(row) if row else {}


def clear():
    with _lock:
        conn = _get_db()
        conn.execute("DELETE FROM usage_log")
        conn.execute(
            "DELETE FROM sqlite_sequence WHERE name='usage_log'")
        conn.commit()
        conn.close()
