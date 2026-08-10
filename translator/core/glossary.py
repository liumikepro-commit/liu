# -*- coding: utf-8 -*-
"""
glossary.py — 自定义术语表
用户维护的行业术语表, 翻译时强制使用指定译法(优先级最高)。

工作场景: 通用引擎会把行业黑话翻错(KPI/VPC/接口), 术语表保证
"译得准"——这是文档翻译提效的第一优先级能力。

存储: translator/data/glossary.json (可通过 config.GLOSSARY_PATH 覆盖)
格式: {"en": {"KPI": "关键绩效指标（KPI）", ...}, "zh": {"接口": "API", ...}}
      en 组: 英译中时生效; zh 组: 中译英时生效

实现策略(双层):
- 翻译前: 扫描原文中的术语 -> 替换为 [[T0]] 占位符(在线翻译会保留)
- 翻译后: 将占位符替换为术语指定译文
- 对本地词典引擎同样生效(占位符原样通过)
"""
import json
import os
import re
import threading

from config import GLOSSARY_ENABLED, GLOSSARY_PATH
from .languages import SUPPORTED_LANGUAGES

_DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "glossary.json",
)

_lock = threading.Lock()
_cache = None          # {"en": {term: target}, "zh": {term: target}}
_enabled = GLOSSARY_ENABLED

_PLACEHOLDER_RE = re.compile(r"\[\[T(\d+)\]\]")


def set_enabled(flag: bool):
    global _enabled
    _enabled = bool(flag)


def is_enabled() -> bool:
    return _enabled


def _path() -> str:
    return GLOSSARY_PATH or _DEFAULT_PATH


def _load():
    """加载术语表(带缓存), 支持所有语言的术语方向"""
    global _cache
    path = _path()
    try:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            # 确保所有支持的语言都有对应字典(向后兼容旧格式)
            _cache = {}
            for lang in SUPPORTED_LANGUAGES:
                _cache[lang] = data.get(lang, {})
            # 合并文件中可能存在的额外语言键
            for lang, terms in data.items():
                if lang not in _cache:
                    _cache[lang] = terms
        else:
            _cache = {lang: {} for lang in SUPPORTED_LANGUAGES}
    except Exception:
        _cache = {lang: {} for lang in SUPPORTED_LANGUAGES}
    return _cache


def get_terms() -> dict:
    """返回术语表 {lang: {term: target}}"""
    with _lock:
        if _cache is None:
            _load()
        return _cache


def add_term(lang: str, term: str, target: str):
    """新增/更新术语; lang: 任意支持的语言代码"""
    with _lock:
        if _cache is None:
            _load()
        if lang not in _cache:
            _cache[lang] = {}
        _cache[lang][term] = target
        _save_locked()


def remove_term(lang: str, term: str):
    """删除术语"""
    with _lock:
        if _cache is None:
            _load()
        _cache.get(lang, {}).pop(term, None)
        _save_locked()


def _save_locked():
    path = _path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_cache, f, ensure_ascii=False, indent=2)


def clear():
    """清空术语表"""
    with _lock:
        global _cache
        _cache = {lang: {} for lang in SUPPORTED_LANGUAGES}
        _save_locked()


# ---------------------------------------------------------------
# 占位保护与还原
# ---------------------------------------------------------------
def protect_terms(text: str, lang: str) -> tuple:
    """
    将文本中的术语替换为占位符。
    lang: 源语言方向(en 或 zh)
    返回 (保护后文本, {占位符: 术语指定译文})
    """
    if not _enabled:
        return text, {}
    terms = get_terms().get(lang, {})
    if not terms:
        return text, {}

    mapping = {}
    protected = text
    k = 0
    # 术语按长度降序, 优先匹配长术语
    for term in sorted(terms, key=len, reverse=True):
        if not term:
            continue
        target = terms[term]
        placeholder = f"[[T{k}]]"
        k += 1
        # 词边界匹配(英文)或直接匹配(中文)
        if re.match(r"^[A-Za-z]", term):
            pattern = rf"\b{re.escape(term)}\b"
        else:
            pattern = re.escape(term)
        if re.search(pattern, protected):
            mapping[placeholder] = target
            protected = re.sub(pattern, placeholder, protected)
    return protected, mapping


def restore_terms(text: str, mapping: dict) -> str:
    """将占位符替换为术语指定译文(优先级: 还原失败则保留占位符原文形式)"""
    if not mapping:
        return text
    for placeholder, target in mapping.items():
        text = text.replace(placeholder, target)
    return text
