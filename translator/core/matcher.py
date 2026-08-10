# -*- coding: utf-8 -*-
"""
matcher.py — 词典查询与匹配逻辑
包含:
- 英文短语最长匹配
- 英文词形还原(不规则表 + 规则后缀)
- 中文前向最大匹配(已在 tokenizer 中, 此处补充查询辅助)
"""
import re
from ..data.loader import get_dictionary

# ---------------------------------------------------------------
# 常用不规则动词/名词表 (原形 -> 各屈折形式)
# 用于反向查询: 输入屈折形式, 还原原形后查词典
# ---------------------------------------------------------------
IRREGULAR = {
    "am": "be", "is": "be", "are": "be", "was": "be", "were": "be",
    "been": "be", "being": "be",
    "go": "go", "went": "go", "gone": "go", "going": "go",
    "have": "have", "has": "have", "had": "have", "having": "have",
    "do": "do", "does": "do", "did": "do", "done": "do", "doing": "do",
    "make": "make", "made": "make", "making": "make",
    "take": "take", "took": "take", "taken": "take", "taking": "take",
    "get": "get", "got": "get", "gotten": "get", "getting": "get",
    "see": "see", "saw": "see", "seen": "see", "seeing": "see",
    "eat": "eat", "ate": "eat", "eaten": "eat", "eating": "eat",
    "run": "run", "ran": "run", "running": "run",
    "write": "write", "wrote": "write", "written": "write", "writing": "write",
    "read": "read", "reading": "read",
    "speak": "speak", "spoke": "speak", "spoken": "speak", "speaking": "speak",
    "think": "think", "thought": "think", "thinking": "think",
    "buy": "buy", "bought": "buy", "buying": "buy",
    "bring": "bring", "brought": "bring", "bringing": "bring",
    "come": "come", "came": "come", "coming": "come",
    "give": "give", "gave": "give", "given": "give", "giving": "give",
    "know": "know", "knew": "know", "known": "know", "knowing": "know",
    "say": "say", "said": "say", "saying": "say",
    "tell": "tell", "told": "tell", "telling": "tell",
    "feel": "feel", "felt": "feel", "feeling": "feel",
    "find": "find", "found": "find", "finding": "find",
    "teach": "teach", "taught": "teach", "teaching": "teach",
    "sleep": "sleep", "slept": "sleep", "sleeping": "sleep",
    "meet": "meet", "met": "meet", "meeting": "meet",
    "sit": "sit", "sat": "sit", "sitting": "sit",
    "stand": "stand", "stood": "stand", "standing": "stand",
    "swim": "swim", "swam": "swim", "swum": "swim", "swimming": "swim",
    "drink": "drink", "drank": "drink", "drunk": "drink", "drinking": "drink",
    "fly": "fly", "flew": "fly", "flown": "fly", "flying": "fly",
    "begin": "begin", "began": "begin", "begun": "begin", "beginning": "begin",
    "children": "child", "people": "person", "men": "man", "women": "woman",
    "feet": "foot", "teeth": "tooth", "mice": "mouse",
}

# 规则后缀剥离规则: (后缀, 剥离后形式)
SUFFIX_RULES = [
    ("ies", lambda w: w[:-3] + "y"),   # studies -> study
    ("es", lambda w: w[:-2]),          # boxes -> box
    ("s", lambda w: w[:-1]),           # books -> book
    ("ing", lambda w: w[:-3]),         # working -> work
    ("ed", lambda w: w[:-2]),          # worked -> work
    ("er", lambda w: w[:-2]),          # bigger -> bigg
    ("est", lambda w: w[:-3]),         # biggest -> bigg
    ("ly", lambda w: w[:-2]),          # quickly -> quick
    ("d", lambda w: w[:-1]),           # liked -> like
]


def lemmatize(word: str) -> list:
    """
    词形还原: 输入屈折形式, 返回候选原形列表。
    候选优先级: 不规则表原形 > 规则剥离形式 > 自身。
    例如: running -> [run, runn, running]; books -> [book, books]
    """
    w = word.lower()
    candidates = []

    # 1. 不规则表(最高优先级: went -> go, reading -> read)
    base = IRREGULAR.get(w)
    if base and base not in candidates:
        candidates.append(base)

    # 2. 规则后缀剥离
    for suffix, fn in SUFFIX_RULES:
        if w.endswith(suffix) and len(w) > len(suffix) + 1:
            stripped = fn(w)
            if stripped and stripped not in candidates:
                candidates.append(stripped)

    # 3. 双写字母还原: running -> runn -> run
    for c in list(candidates):
        for i in range(1, len(c)):
            if c[i] == c[i - 1]:
                reduced = c[:i - 1] + c[i:]
                if reduced not in candidates:
                    candidates.append(reduced)

    # 4. 自身(最后兜底)
    if w not in candidates:
        candidates.append(w)
    return candidates


def lookup_en_with_lemma(word: str):
    """
    英文单词查询(带词形还原)。
    返回 (译文列表, 命中原形) 或 (None, None)
    """
    data = get_dictionary()
    # 若词形本身是 IRREGULAR 表中的屈折形式, 优先查询其原形
    if word.lower() in IRREGULAR:
        base = IRREGULAR[word.lower()]
        result, is_override = data.lookup_en(base)
        if result:
            return result, base
    for cand in lemmatize(word):
        result, is_override = data.lookup_en(cand)
        if result:
            return result, cand
    return None, None


def longest_phrase_match(text: str, max_len: int = 12):
    """
    英文短语最长匹配: 在文本中寻找人工修正表中收录的最长短语。
    仅信任人工精选短语(如 "thank you", "good morning", "i love you"),
    不使用自动提取的松散短语键, 避免 "love apple" 这类组合词干扰单词翻译。
    返回 [(start, end, phrase, translation), ...]
    """
    data = get_dictionary()
    words = re.findall(r"[A-Za-z]+", text)
    n = len(words)
    matches = []
    i = 0
    while i < n:
        found = None
        for L in range(min(max_len, n - i), 1, -1):
            phrase = " ".join(words[i:i + L]).lower()
            if phrase in data.en_overrides:  # 仅人工精选短语
                found = (phrase, data.en_overrides[phrase].split("；")[0])
                break
        if found:
            matches.append((i, i + len(found[0].split()), found[0], found[1]))
            i += len(found[0].split())
        else:
            i += 1
    return matches
