# -*- coding: utf-8 -*-
"""
text.py — 文本处理工具
负责: 文本规范化、全角/半角转换、分句、语言检测、特殊字符处理。
"""
import re

# 中文字符范围
CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
# 英文字母
LATIN_RE = re.compile(r"[a-zA-Z]")
# 分句: 句号/问号/感叹号/省略号/换行
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?\.]{1})[\s\n]*|\n+")
# 全角字符范围(用于全角转半角)
FULLWIDTH_MAP = {chr(0xFF01 + i): chr(0x21 + i) for i in range(94)}


def normalize(text: str) -> str:
    """
    文本规范化:
    1. 全角字符 -> 半角
    2. 合并多余空白/换行
    3. 去除首尾空白
    """
    if not text:
        return ""
    # 全角 -> 半角
    out = []
    for ch in text:
        if ch in FULLWIDTH_MAP:
            out.append(FULLWIDTH_MAP[ch])
        elif ch == "\u3000":  # 全角空格
            out.append(" ")
        else:
            out.append(ch)
    text = "".join(out)
    # 合并空白与换行(保留单个换行作为分段)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sentences(text: str) -> list:
    """
    将长文本按句子边界切分, 返回句子列表。
    支持: 中文句号/问号/感叹号、英文句点/问号/感叹号、换行分段。
    注意: 英文缩写如 "Mr." "U.S.A." 后的句点不切分。
    """
    # 保护常见英文缩写, 避免被误切分
    protected = text.replace("Mr.", "Mr<DOT>").replace("Mrs.", "Mrs<DOT>") \
                     .replace("Dr.", "Dr<DOT>").replace("U.S.", "US<DOT>")
    # 先按换行分段, 再按标点分句
    chunks = []
    for para in protected.split("\n"):
        para = para.strip()
        if not para:
            continue
        parts = SENTENCE_SPLIT_RE.split(para)
        for p in parts:
            p = p.strip()
            if p:
                chunks.append(p.replace("<DOT>", "."))
    return chunks


def has_cjk(text: str) -> bool:
    """是否包含中文字符"""
    return bool(CJK_RE.search(text))


def has_latin(text: str) -> bool:
    """是否包含英文字母"""
    return bool(LATIN_RE.search(text))


def count_cjk(text: str) -> int:
    """统计中文字符数量"""
    return len(CJK_RE.findall(text))


def count_latin(text: str) -> int:
    """统计英文字母数量"""
    return len(LATIN_RE.findall(text))


def strip_punct(text: str) -> str:
    """去掉首尾标点(用于检测语言时的清理)"""
    return re.sub(r"^[\s\W_]+|[\s\W_]+$", "", text)


def is_number_word(token: str) -> bool:
    """判断 token 是否为数字/数字串(如 2024, 3.14, 100%)"""
    return bool(re.fullmatch(r"[-+]?\d[\d,\.]*%?", token))


def escape_html(text: str) -> str:
    """HTML 转义, 防止 XSS"""
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))
