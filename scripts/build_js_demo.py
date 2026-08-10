#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_js_demo.py — 为纯前端演示版生成词典数据 (static-demo/js/dict.js)

从完整词典索引中提取高频子集, 输出浏览器可直接加载的 JS 文件:
    var DICT = {"zh_en": {...}, "en_zh": {...}, "overrides": {...}, "max_zh_len": N};

用法: python scripts/build_js_demo.py [top_n] [输出路径]
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_DIR = os.path.join(BASE, "translator", "data", "dictionary")


def build(top_n: int = 12000, out_path: str = None):
    with open(os.path.join(DICT_DIR, "zh_en.json"), encoding="utf-8") as f:
        zh_en = json.load(f)
    with open(os.path.join(DICT_DIR, "en_zh.json"), encoding="utf-8") as f:
        en_zh = json.load(f)
    with open(os.path.join(DICT_DIR, "overrides.json"), encoding="utf-8") as f:
        overrides = json.load(f)

    # 保留高频词条: 按 jieba 中文词频排序取前 top_n (保留常用词)
    entries = list(zh_en.items())
    if top_n and top_n < len(entries):
        try:
            import jieba
            jieba.dt.initialize()
            freq = jieba.dt.FREQ
            entries.sort(key=lambda kv: -freq.get(kv[0], 0))
            print("     使用 jieba 词频排序")
        except Exception:
            entries.sort(key=lambda kv: -len(kv[1]))  # 降级: 按释义数排序
            print("     [提示] jieba 不可用, 降级为释义数排序")
        zh_en_sub = dict(entries[:top_n])
    else:
        zh_en_sub = zh_en

    # 裁剪 en_zh: 仅保留能对应到 zh_en_sub 中词条的候选
    en_zh_sub = {}
    for k, v in en_zh.items():
        kept = [w for w in v if w in zh_en_sub or w in overrides.get("zh_en", {})]
        if kept:
            en_zh_sub[k] = kept
        elif k in overrides.get("en_zh", {}):
            en_zh_sub[k] = v

    max_zh_len = max(len(k) for k in zh_en_sub) if zh_en_sub else 4
    max_zh_len = min(max(4, max_zh_len), 32)

    data = {
        "zh_en": zh_en_sub,
        "en_zh": en_zh_sub,
        "zh_overrides": overrides.get("zh_en", {}),
        "en_overrides": overrides.get("en_zh", {}),
        "max_zh_len": max_zh_len,
    }

    js = "/* 词典数据: CC-CEDICT (CC BY-SA 4.0) + 人工修正表, 由 build_js_demo.py 生成 */\n"
    js += "var DICT = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"

    if out_path is None:
        out_path = os.path.join(BASE, "static-demo", "js", "dict.js")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"输出: {out_path}")
    print(f"中文词条: {len(zh_en_sub)} | 英文索引: {len(en_zh_sub)} | max_zh_len: {max_zh_len}")
    print(f"文件大小: {os.path.getsize(out_path)/1024:.0f} KB")


if __name__ == "__main__":
    top = int(sys.argv[1]) if len(sys.argv) > 1 else 12000
    out = sys.argv[2] if len(sys.argv) > 2 else None
    build(top_n=top, out_path=out)
