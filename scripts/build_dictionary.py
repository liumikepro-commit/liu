#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_dictionary.py — 从开源数据集构建双向翻译词典索引

数据源: CC-CEDICT (https://www.mdbg.net/chinese/dictionary?page=cc-cedict)
许可  : Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)

CC-CEDICT 每行格式:
    傳統 簡體 [拼音] /英文定義1/英文定義2/

本脚本将其解析并构建两个索引:
    zh_en.json : 简体中文词 -> 英文释义列表
    en_zh.json : 英文单词   -> 常用中文翻译列表 (由英文释义反向提取)

用法:
    python scripts/build_dictionary.py [cedict路径] [输出目录]
"""

import gzip
import json
import os
import re
import sys
from collections import defaultdict

# ------------------------- 正则工具 -------------------------

# 词条行: 传统 简体 [拼音] /定义1/定义2/
ENTRY_RE = re.compile(
    r"^(?P<trad>\S+)\s+(?P<simp>\S+)\s+\[(?P<pinyin>[^\]]+)\]\s+/(?P<defs>.*)/$"
)

# 英文释义中的括号说明, 如 "you (informal, as opposed to courteous 您)"
BRACKET_RE = re.compile(r"\([^)]*\)|\[[^\]]*\]")
# 英文释义中的非字母字符(保留空格和连字符)
NON_ALPHA_RE = re.compile(r"[^a-zA-Z\s\-]")
# 中文释义/词中的非中文字符
NON_CJK_RE = re.compile(r"[^\u4e00-\u9fff]")


# 需要丢弃的释义类型(量词/参见/异体等注释), 全部小写便于匹配
DISCARD_PATTERNS = (
    "cl:", "see also", "variant of", "old variant", "abbr.", "surname",
    "archaic", "erhua", "taiwan pr.", "mainland pr.",
)


def clean_gloss(gloss: str) -> str:
    """清洗单条英文释义: 去括号、去量词注释、去音标、去多余空白"""
    g = BRACKET_RE.sub(" ", gloss)      # 去掉括号说明
    g = NON_ALPHA_RE.sub(" ", g)        # 去掉标点/数字等
    g = re.sub(r"\s+", " ", g).strip()  # 合并空白
    return g


def is_discardable(gloss: str) -> bool:
    """判断释义是否为量词/参见等噪声"""
    g = gloss.lower()
    return any(p in g for p in DISCARD_PATTERNS)


def extract_keys(gloss: str) -> list:
    """
    从英文释义中提取可查询的关键词。
    英文释义往往是短语(如 "to eat")，我们同时索引短语与前几词。
    """
    g = clean_gloss(gloss)
    if not g:
        return []
    words = g.split(" ")
    keys = [w.lower() for w in words if len(w) >= 1]
    phrase = " ".join(keys[:3])
    return sorted(set(keys + [phrase]))


def load_entries(cedict_path: str):
    """解析 CC-CEDICT 文件, 返回词条迭代器 (simp, defs_list)"""
    opener = gzip.open if cedict_path.endswith(".gz") else open
    with opener(cedict_path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = ENTRY_RE.match(line)
            if not m:
                continue
            simp = m.group("simp")
            defs = [d.strip() for d in m.group("defs").split("/") if d.strip()]
            if simp and defs:
                yield simp, defs


def load_frequency() -> dict:
    """
    加载中文词频表(jieba 内置, 基于人民日报等大规模语料)。
    用于反向索引排序: 常用中文词(吃/书/水)排在生僻词(善本/坟/水华)前面。
    若 jieba 不可用则返回空表, 退化为长度排序。
    """
    try:
        import jieba
        jieba.dt.initialize()
        return dict(jieba.dt.FREQ)
    except Exception:
        print("      [提示] jieba 不可用, 词频排序降级为长度排序")
        return {}


def build(cedict_path: str, out_dir: str, top_n: int = 0):
    """
    构建双向索引。
    top_n: 若 >0 只保留词频最高的前 N 个简体词条(用于静态演示版瘦身)。
    """
    zh_en = {}       # 简体词 -> [英文释义...]
    en_zh = raw_en_zh = defaultdict(list)  # 英文词/短语 -> [中文...]

    entries = list(load_entries(cedict_path))
    print(f"[1/3] 解析词条: {len(entries)} 条")

    # 按释义数量粗排词条(释义多的通常更常用)，便于瘦身时优先保留
    if top_n > 0:
        entries.sort(key=lambda e: -len(e[1]))
        entries = entries[:top_n]
        print(f"     瘦身为 Top {top_n} 词条")

    # 第一遍: 建立 中文->英文 索引 (过滤噪声释义)
    zh_en = {}
    for simp, defs in entries:
        keep = [d for d in defs if not is_discardable(d)]
        if keep:
            zh_en[simp] = keep

    # 第二遍: 由英文释义反向提取 英文->中文 索引
    # 注意: 多词短语键(含空格)仅从主释义(第一条)提取, 避免 "love apple" 这类
    #       松散释义组合造成的噪声短语; 单词键可来自任意释义。
    for simp, defs in entries:
        seen = set()
        for idx, gloss in enumerate(defs):
            if is_discardable(gloss):
                continue
            for key in extract_keys(gloss):
                if not key or key in seen:
                    continue
                if " " in key and idx != 0:
                    continue  # 非主释义的多词短语: 丢弃
                seen.add(key)
                en_zh[key].append(simp)

    print(f"[2/3] 中文索引: {len(zh_en)} 词 | 英文索引: {len(raw_en_zh)} 词")

    # 英文侧排序: 主释义匹配(高置信) > 中文词频 > 中文长度
    freq = load_frequency()

    def rank(word: str):
        defs = zh_en.get(word, [])
        primary = clean_gloss(defs[0]) if defs else ""
        confirmed = 1 if key in primary else 0   # 该英文词是否为中文词的主释义
        f = freq.get(word, 0)
        return (-confirmed, -f, len(word))

    en_zh = {}
    for k, words in list(raw_en_zh.items()):
        # 丢弃超长键与单字母键(单字母键噪声大, 常见词由人工修正表兜底)
        if len(k) > 40 or len(k) == 1:
            continue
        key = k
        ranked = sorted(set(words), key=rank)
        en_zh[key] = ranked[:5]

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "zh_en.json"), "w", encoding="utf-8") as f:
        json.dump(zh_en, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(out_dir, "en_zh.json"), "w", encoding="utf-8") as f:
        json.dump(en_zh, f, ensure_ascii=False, separators=(",", ":"))
    print(f"[3/3] 输出完成 -> {out_dir}/zh_en.json, en_zh.json")


if __name__ == "__main__":
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cedict = sys.argv[1] if len(sys.argv) > 1 else os.path.join(base, "cedict.txt.gz")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(base, "translator", "data", "dictionary")
    top = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    build(cedict, out, top_n=top)
