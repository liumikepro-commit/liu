# -*- coding: utf-8 -*-
"""
tokenizer.py — 中英文分词器
- 英文: 按空白/标点切分, 保留标点 token 用于重组
- 中文: 前向最大匹配(基于词典键), 未匹配字符按单字保留
"""
import re
from ..data.loader import get_dictionary

# 英文词 token: 字母/数字/连字符/撇号
EN_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['\-][A-Za-z0-9]+)*")
# 标点 token
PUNCT_RE = re.compile(r"[^\w\s]")


def tokenize_en(text: str) -> list:
    """
    英文分词: 返回 [(token, is_word), ...]
    is_word=True 表示可查询的单词, False 表示标点/空白(原样保留)
    """
    tokens = []
    for match in EN_WORD_RE.finditer(text):
        start = match.start()
        if start > (tokens[-1][2] if tokens else -1):
            # 间隔部分(标点+空白)按原样保留为不可查询 token
            gap = text[tokens[-1][2] if tokens else 0:start]
            tokens.append((gap, False, start))
        tokens.append((match.group(0), True, match.end()))
    # 末尾残留
    if tokens:
        tail = text[tokens[-1][2]:]
    else:
        tail = text
    if tail:
        tokens.append((tail, False, len(text)))
    return [(t, w) for t, w, _ in tokens]


def tokenize_zh(text: str) -> list:
    """
    中文分词: 前向最大匹配。
    返回 [(token, is_word), ...]
    匹配优先级: 词典短语 > 单字(未收录的单字也作为 token 保留)
    """
    data = get_dictionary()
    data.ensure_loaded()  # 确保词典已加载
    tokens = []
    i = 0
    n = len(text)
    max_len = data.max_zh_len
    while i < n:
        matched = None
        # 从最长可能长度向前尝试匹配
        for L in range(min(max_len, n - i), 0, -1):
            cand = text[i:i + L]
            if cand in data.zh_en or cand in data.zh_overrides:
                matched = cand
                break
        if matched:
            tokens.append((matched, True))
            i += len(matched)
        else:
            # 无匹配: 按单字(若为中文)或原字符输出
            tokens.append((text[i], text[i] in data.zh_en or text[i] in data.zh_overrides))
            i += 1
    return tokens
