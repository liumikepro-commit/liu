# -*- coding: utf-8 -*-
"""
tm.py — 翻译记忆 (Translation Memory)
基于 SQLite 的轻量翻译记忆库:
- 翻译前按 (语言对 + 文本) 精确查库, 命中直接复用历史译文
- 翻译后自动记忆, 相同句子二次翻译秒回且保证一致性
适合: 合同、周报、技术文档中大量重复句子的工作场景

存储位置: translator/data/tm.sqlite (可通过 config.TM_DB_PATH 覆盖)
"""
import os
import sqlite3
import threading
import time

from config import TM_ENABLED, TM_DB_PATH

_DEFAULT_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "tm.sqlite",
)

_lock = threading.Lock()
_conn = None
_enabled = TM_ENABLED


def set_enabled(flag: bool):
    """动态开关(设置面板)"""
    global _enabled
    _enabled = bool(flag)


def is_enabled() -> bool:
    return _enabled


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        db_path = TM_DB_PATH or _DEFAULT_DB
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        _conn = sqlite3.connect(db_path, check_same_thread=False)
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_lang TEXT NOT NULL,
                target_lang TEXT NOT NULL,
                source_text TEXT NOT NULL,
                target_text TEXT NOT NULL,
                created_at REAL,
                use_count INTEGER DEFAULT 0
            )
        """)
        _conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_lang_text "
            "ON translations(source_lang, target_lang, source_text)")
        _conn.commit()
    return _conn


def lookup(source_lang: str, target_lang: str, text: str):
    """
    查询翻译记忆。
    返回命中译文 str, 未命中返回 None。
    """
    if not _enabled or not text or not text.strip():
        return None
    try:
        conn = _get_conn()
        with _lock:
            cur = conn.execute(
                "SELECT target_text FROM translations "
                "WHERE source_lang=? AND target_lang=? AND source_text=?",
                (source_lang, target_lang, text.strip()))
            row = cur.fetchone()
            if row:
                conn.execute(
                    "UPDATE translations SET use_count = use_count + 1 "
                    "WHERE source_lang=? AND target_lang=? AND source_text=?",
                    (source_lang, target_lang, text.strip()))
                conn.commit()
                return row[0]
    except Exception:
        pass
    return None


def remember(source_lang: str, target_lang: str, source_text: str,
             target_text: str):
    """记忆一条翻译(已存在则更新译文)"""
    if not _enabled or not source_text.strip() or not target_text.strip():
        return
    try:
        conn = _get_conn()
        with _lock:
            conn.execute(
                "INSERT INTO translations "
                "(source_lang, target_lang, source_text, target_text, created_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(source_lang, target_lang, source_text) "
                "DO UPDATE SET target_text = excluded.target_text",
                (source_lang, target_lang, source_text.strip(),
                 target_text.strip(), time.time()))
            conn.commit()
    except Exception:
        pass


def stats() -> dict:
    """返回记忆库统计(条目数/命中总数)"""
    try:
        conn = _get_conn()
        cur = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(use_count), 0) FROM translations")
        count, hits = cur.fetchone()
        return {"entries": count, "hits": hits, "enabled": _enabled}
    except Exception:
        return {"entries": 0, "hits": 0, "enabled": _enabled}


def clear():
    """清空翻译记忆"""
    try:
        conn = _get_conn()
        with _lock:
            conn.execute("DELETE FROM translations")
            conn.commit()
        return True
    except Exception:
        return False
