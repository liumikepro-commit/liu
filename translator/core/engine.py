# -*- coding: utf-8 -*-
"""
engine.py — 翻译核心引擎
职责: 语言检测、分句、逐句翻译(词典 + 简单语法规则)、可选在线增强、结果组装。

翻译策略(由高到低优先级):
1. 在线翻译 API 整句翻译(可配置开关, 失败自动回退本地)
2. 本地词典短语/单词查询(离线可用, 覆盖 12 万+ 词条)
3. 词形还原查询(处理时态/复数等屈折形式)
4. 未收录词: 原样保留并汇报, 供二次开发扩展

本模块不依赖第三方库, 标准库即可运行。
"""
import json
import urllib.parse
import urllib.request

from . import matcher
from . import tokenizer
from . import glossary as glossary_mod
from . import providers
from . import tm as tm_mod
from .languages import (
    detect_language as _detect_lang,
    is_supported_lang,
    is_zh,
    is_non_zh,
    validate_lang_pair,
    resolve_auto_lang,
    SUPPORTED_LANGUAGES,
    LOCAL_DICT_PAIRS,
)
from config import (
    ONLINE_TRANSLATE_ENABLED,
    ONLINE_TIMEOUT,
    MAX_INPUT_LEN,
    MAX_SENTENCE_LEN,
    ONLINE_API_URL,
)
from ..data.loader import get_dictionary
from ..utils import text as text_utils

# 英文 -> 中文 时省略的冠词
ARTICLES = {"the", "a", "an"}
# be 动词简单映射
BE_VERBS = {"am": "是", "is": "是", "are": "是", "was": "是", "were": "是"}
# 中文量词(中译英时省略)
ZH_CLASSIFIERS = {"个", "只", "本", "张", "把", "条", "件", "双", "块", "片",
                  "位", "名", "辆", "台", "间", "栋", "棵", "朵", "座"}


# ---------------------------------------------------------------
# 语言检测(委托给 languages 模块, 保持向后兼容)
# ---------------------------------------------------------------
def detect_language(text: str) -> str:
    """检测文本主要语言, 返回 SUPPORTED_LANGUAGES 中的代码或 'unknown'"""
    return _detect_lang(text)


# ---------------------------------------------------------------
# 英 -> 中 单句翻译
# ---------------------------------------------------------------
def translate_sentence_en_to_zh(sentence: str) -> dict:
    """
    英文单句 -> 中文。
    返回: {"text": 译文, "uncovered": [未收录词], "hits": 命中数, "misses": 未命中数}
    """
    data = get_dictionary()
    uncovered = []
    hits = misses = 0

    # 1. 先做短语匹配, 记录短语区间(基于单词序号)
    phrase_matches = matcher.longest_phrase_match(sentence)
    phrase_positions = {}  # 单词序号 -> 短语译文
    if phrase_matches:
        for start, end, phrase, translation in phrase_matches:
            for idx in range(start, end):
                phrase_positions[idx] = translation

    # 2. 单词级处理
    tokens = tokenizer.tokenize_en(sentence)
    out_parts = []
    word_index = -1
    for token, is_word in tokens:
        if not is_word:
            # 标点/空白: 原样保留(中文标点统一为全角句读由后面规则处理)
            out_parts.append(token)
            continue

        word_index += 1
        # 数字: 直接保留
        if text_utils.is_number_word(token):
            out_parts.append(token)
            continue
        # 短语命中: 用短语译文
        if word_index in phrase_positions:
            out_parts.append(phrase_positions[word_index])
            continue
        # 冠词: 中文无冠词, 省略
        if token.lower() in ARTICLES:
            continue
        # be 动词: 简单映射
        if token.lower() in BE_VERBS:
            out_parts.append(BE_VERBS[token.lower()])
            continue

        # 词典查询(带词形还原)
        result, matched_form = matcher.lookup_en_with_lemma(token)
        if result:
            hits += 1
            translation = _pick_zh(result)
            # 进行时: 原词以 ing 结尾 -> 加"正在"
            if token.lower().endswith("ing") and len(token) > 4:
                translation = "正在" + translation
            # 过去时: 原词以 ed 结尾且还原成功 -> 加"了"
            elif token.lower().endswith("ed") and matched_form != token.lower():
                translation = translation + "了"
            out_parts.append(translation)
        else:
            misses += 1
            uncovered.append(token)
            out_parts.append(token)  # 未收录: 保留原文

    # 3. 组装: 中文词之间不留空格
    result_text = _join_zh(out_parts)
    return {"text": result_text, "uncovered": uncovered, "hits": hits, "misses": misses}


def _pick_zh(results: list) -> str:
    """从候选中文译文中挑选最合适的(优先常用词)"""
    if not results:
        return ""
    return results[0]


def _join_zh(parts: list) -> str:
    """
    组装中文译文: 中文与中文之间不加空格, 但原文中的标点保留。
    """
    out = ""
    prev_cjk = False
    for part in parts:
        if not part:
            continue
        is_cjk = text_utils.has_cjk(part)
        if is_cjk and prev_cjk and out and not out.endswith((" ", "(", "[")):
            pass  # 中文字符间直接拼接
        elif out and prev_cjk and not is_cjk and part and part[0] not in ".,;:!?，。；：！？)】」":
            out += " "  # 中文后接英文时加空格
        out += part
        prev_cjk = is_cjk
    return out


# ---------------------------------------------------------------
# 中 -> 英 单句翻译
# ---------------------------------------------------------------
def translate_sentence_zh_to_en(sentence: str) -> dict:
    """
    中文单句 -> 英文。
    返回: {"text": 译文, "uncovered": [未收录词], "hits": 命中数, "misses": 未命中数}
    """
    data = get_dictionary()
    uncovered = []
    hits = misses = 0

    tokens = tokenizer.tokenize_zh(sentence)
    out_parts = []

    i = 0
    n = len(tokens)
    while i < n:
        token, is_word = tokens[i]

        # 标点/空白: 原样保留
        if not is_word:
            # 中文标点 -> 英文标点
            out_parts.append(_to_en_punct(token))
            i += 1
            continue

        # 数字: 保留
        if text_utils.is_number_word(token):
            out_parts.append(token)
            i += 1
            continue

        # 量词: 省略(单数时)
        if token in ZH_CLASSIFIERS and i > 0 and tokens[i - 1][1]:
            i += 1
            continue

        # 词典查询(修正表优先)
        result, is_override = data.lookup_zh(token)
        if result:
            hits += 1
            translation = result[0] if is_override else _clean_zh_en_gloss(result[0])
            # 多义译文取首选: "I / me" -> "I"; "like / love" -> "like"
            if "/" in translation:
                translation = translation.split("/")[0].strip()
            out_parts.append(translation)
        else:
            misses += 1
            uncovered.append(token)
            out_parts.append(token)  # 未收录: 保留原文(便于用户看懂)

        i += 1

    result_text = " ".join(p for p in out_parts if p)
    # 规范化英文输出中的多余空格
    result_text = _clean_en_text(result_text)
    return {"text": result_text, "uncovered": uncovered, "hits": hits, "misses": misses}


def _to_en_punct(ch: str) -> str:
    """中文标点 -> 英文标点"""
    mapping = {"，": ", ", "。": ". ", "！": "! ", "？": "? ",
               "：": ": ", "；": "; ", "、": ", ", "“": '"', "”": '"',
               "‘": "'", "’": "'", "（": "(", "）": ")", "…": "..."}
    return mapping.get(ch, ch)


def _clean_zh_en_gloss(gloss: str) -> str:
    """
    清洗中文词条释义, 提取最简洁的英文翻译:
    - "to eat; to consume" -> "eat"
    - "book; letter" -> "book"
    - "computer; CL:臺|台[tai2]" -> "computer"
    """
    g = gloss.split(";")[0].split(",")[0].strip()
    g = g.replace("CL:", "").strip()
    if g.startswith("to "):
        g = g[3:]
    return g


def _clean_en_text(text: str) -> str:
    """清理英文输出: 修正标点前的空格等"""
    import re
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text.strip()


# ---------------------------------------------------------------
# 在线翻译(增强)
# ---------------------------------------------------------------
def translate_online(text: str, source: str, target: str) -> str:
    """
    在线翻译(转发到当前配置的提供商, 支持 MyMemory/DeepL/百度/腾讯/OpenAI)。
    失败或异常时抛出异常, 由上层捕获并回退本地翻译。
    """
    return providers.translate_online(text, source, target)


# ---------------------------------------------------------------
# 对外主入口
# ---------------------------------------------------------------
def translate(text: str, source: str = "auto", target: str = "auto",
              use_online: bool = None) -> dict:
    """
    翻译入口函数(支持 10 种语言与汉语的双向翻译)。

    参数:
        text:     待翻译文本
        source:   'auto'|'zh'|'en'|'ja'|'ko'|'fr'|'de'|'es'|'ru'|'ar'|'pt'|'th'
        target:   'auto'|同上
        use_online: 是否使用在线增强; None 表示跟随全局配置

    翻译规则:
        - 汉语 <-> 非汉语: 直接翻译
        - 非汉语 <-> 非汉语: 通过汉语中转翻译(source -> zh -> target)
        - 本地词典仅支持英汉双向, 其他语言对依赖在线翻译

    返回 dict:
        translation  译文
        source/target 实际使用的语言
        engine        'online' | 'local' | 'hybrid' | 'tm' | 'relay'
        relay         bool, 是否使用了中转翻译
        coverage      本地词典覆盖率(0~1)
        uncovered     未收录词列表
        error         错误信息(或 None)
        warning       提示信息(或 None)
    """
    # ---- 0. 参数与配置 ----
    if use_online is None:
        use_online = ONLINE_TRANSLATE_ENABLED

    # ---- 1. 输入校验 ----
    if text is None or not str(text).strip():
        return {"error": "输入为空，请输入要翻译的内容。", "translation": "",
                "source": "unknown", "target": "unknown", "engine": "none",
                "coverage": 0.0, "uncovered": [], "warning": None, "relay": False}
    text = text_utils.normalize(str(text))
    if len(text) > MAX_INPUT_LEN:
        return {"error": f"输入过长（{len(text)} 字符），超过限制 {MAX_INPUT_LEN} 字符，请分段翻译。",
                "translation": "", "source": "unknown", "target": "unknown",
                "engine": "none", "coverage": 0.0, "uncovered": [], "warning": None, "relay": False}

    # ---- 2. 语言检测与解析 ----
    detected = detect_language(text)
    if detected == "unknown":
        return {"error": "无法识别语言，请检查输入内容或手动指定源语言。", "translation": "",
                "source": "unknown", "target": "unknown", "engine": "none",
                "coverage": 0.0, "uncovered": [], "warning": None, "relay": False}

    src, tgt = resolve_auto_lang(source, target, detected)

    # ---- 3. 语言对验证 ----
    is_valid, needs_relay, err_msg = validate_lang_pair(src, tgt)
    if not is_valid:
        return {"error": err_msg, "translation": "",
                "source": src, "target": tgt, "engine": "none",
                "coverage": 0.0, "uncovered": [], "warning": None, "relay": False}

    # ---- 4. 中转翻译: 非汉语 -> 汉语 -> 非汉语 ----
    if needs_relay:
        return _translate_relay(text, src, tgt, use_online)

    # ---- 5. 直接翻译: 汉语 <-> 非汉语 ----
    # 本地词典仅支持英汉双向
    has_local_dict = (src, tgt) in LOCAL_DICT_PAIRS

    # 非英汉语言对必须使用在线翻译
    if not has_local_dict and not use_online:
        lang_name = SUPPORTED_LANGUAGES.get(src, src) if is_zh(tgt) else SUPPORTED_LANGUAGES.get(tgt, tgt)
        return {"error": f"{lang_name}翻译需要在线增强支持，请开启「使用在线增强」选项。",
                "translation": "", "source": src, "target": tgt, "engine": "none",
                "coverage": 0.0, "uncovered": [], "warning": None, "relay": False}

    # ---- 6. 在线翻译(整段, 含术语表与翻译记忆) ----
    if use_online:
        # 术语保护: 整段替换术语为占位符(在线翻译会保留)
        p_text, term_map = (glossary_mod.protect_terms(text, src)
                            if glossary_mod.is_enabled() else (text, {}))
        # 翻译记忆: 整段命中直接复用历史译文
        tm_hit = tm_mod.lookup(src, tgt, text)
        if tm_hit:
            return {
                "translation": tm_hit,
                "source": src, "target": tgt,
                "engine": "tm", "coverage": 1.0, "uncovered": [],
                "error": None, "warning": None, "relay": False,
            }
        try:
            online_result = translate_online(p_text, src, tgt)
            if term_map:
                online_result = glossary_mod.restore_terms(online_result, term_map)
            tm_mod.remember(src, tgt, text, online_result)  # 记忆本次译文
            return {
                "translation": online_result,
                "source": src, "target": tgt,
                "engine": "online",
                "coverage": 1.0, "uncovered": [],
                "error": None,
                "warning": None,
                "relay": False,
            }
        except Exception:
            if not has_local_dict:
                # 非英汉语言对无法回退本地, 返回错误
                raise
            pass  # 英汉对静默回退本地

    # ---- 7. 本地翻译(仅英汉双向, 逐句) ----
    if not has_local_dict:
        return {"error": "本地词典仅支持英汉双向翻译，其他语言请开启在线增强。",
                "translation": "", "source": src, "target": tgt, "engine": "none",
                "coverage": 0.0, "uncovered": [], "warning": None, "relay": False}

    # ---- 8. 本地词典翻译(英汉双向) ----
    sentences = text_utils.split_sentences(text)
    if not sentences:
        return {"error": "无法切分文本。", "translation": "",
                "source": src, "target": tgt, "engine": "none",
                "coverage": 0.0, "uncovered": [], "warning": None, "relay": False}

    uncovered_all = []
    hits = misses = 0
    tm_hit_count = 0
    translated_sentences = []
    for sent in sentences:
        if len(sent) > MAX_SENTENCE_LEN:
            sent = sent[:MAX_SENTENCE_LEN]

        tm_hit = tm_mod.lookup(src, tgt, sent)
        if tm_hit:
            translated_sentences.append(tm_hit)
            tm_hit_count += 1
            continue

        p_sent, term_map = (glossary_mod.protect_terms(sent, src)
                            if glossary_mod.is_enabled() else (sent, {}))
        if src == "en":
            res = translate_sentence_en_to_zh(p_sent)
        else:
            res = translate_sentence_zh_to_en(p_sent)
        sentence_text = res["text"]
        if term_map:
            sentence_text = glossary_mod.restore_terms(sentence_text, term_map)
        tm_mod.remember(src, tgt, sent, sentence_text)

        translated_sentences.append(sentence_text)
        uncovered_all.extend(res["uncovered"])
        hits += res["hits"]
        misses += res["misses"]

    translation = " ".join(translated_sentences)
    if src == "zh":
        translation = _clean_en_text(translation)

    coverage = hits / (hits + misses) if (hits + misses) > 0 else 0.0
    uncovered = list(dict.fromkeys(uncovered_all))
    engine = "tm" if tm_hit_count == len(sentences) and tm_hit_count > 0 else "local"

    warning = None
    if uncovered:
        warning = ("以下词语未在词典中找到，已保留原文："
                   + "、".join(uncovered[:10])
                   + ("…" if len(uncovered) > 10 else ""))

    return {
        "translation": translation,
        "source": src, "target": tgt,
        "engine": engine,
        "coverage": round(coverage, 3),
        "uncovered": uncovered,
        "error": None,
        "warning": warning,
        "relay": False,
    }


def _translate_relay(text: str, src: str, tgt: str, use_online: bool) -> dict:
    """
    中转翻译: 非汉语A -> 汉语 -> 非汉语B
    通过汉语作为中间语言进行两步翻译。
    """
    # 第一步: 源语言 -> 汉语
    step1 = translate(text, source=src, target="zh", use_online=use_online)
    if step1.get("error"):
        return {
            "error": f"中转翻译第一步失败（{src}→zh）: {step1['error']}",
            "translation": "", "source": src, "target": tgt,
            "engine": "relay", "coverage": 0.0, "uncovered": [],
            "warning": None, "relay": True,
        }

    zh_text = step1["translation"]
    if not zh_text.strip():
        return {
            "error": "中转翻译中间结果为空，无法继续。",
            "translation": "", "source": src, "target": tgt,
            "engine": "relay", "coverage": 0.0, "uncovered": [],
            "warning": None, "relay": True,
        }

    # 第二步: 汉语 -> 目标语言
    step2 = translate(zh_text, source="zh", target=tgt, use_online=use_online)
    if step2.get("error"):
        return {
            "error": f"中转翻译第二步失败（zh→{tgt}）: {step2['error']}",
            "translation": "", "source": src, "target": tgt,
            "engine": "relay", "coverage": 0.0, "uncovered": [],
            "warning": None, "relay": True,
        }

    relay_warning = (f"已通过汉语中转翻译（{SUPPORTED_LANGUAGES.get(src, src)} → 中文 → "
                     f"{SUPPORTED_LANGUAGES.get(tgt, tgt)}），译文仅供参考。")

    return {
        "translation": step2["translation"],
        "source": src, "target": tgt,
        "engine": "relay",
        "coverage": 1.0, "uncovered": [],
        "error": None,
        "warning": relay_warning,
        "relay": True,
    }
