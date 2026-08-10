# -*- coding: utf-8 -*-
"""
pipeline.py — 文档翻译流水线
衔接: 解析(DocumentModel) -> 分块翻译 -> 写回(DocumentModel)

要点:
1. 逐块翻译, 保持文档结构与格式元数据不变
2. 在线翻译分块请求(MyMemory 单请求限制 ~500 字符), 自动限速/重试
3. 在线连续失败自动降级为本地词典引擎
4. 专有名词保护: 英译中时, 人名/地名/机构名等以占位符保护, 翻译后还原
"""
import re
import time

from ..core.engine import detect_language, translate as translate_text
from ..core.engine import translate_online
from ..core import glossary as glossary_mod
from ..core import tm as tm_mod
from ..core.languages import (
    is_supported_lang,
    is_zh,
    is_non_zh,
    validate_lang_pair,
    resolve_auto_lang,
    SUPPORTED_LANGUAGES,
    LOCAL_DICT_PAIRS,
)
from ..utils import text as text_utils
from .block import DocumentModel

# 在线单请求最大字符数(留余量给 URL 编码)
ONLINE_CHUNK_LIMIT = 420
# 在线请求间隔(秒), 规避公共 API 频率限制
ONLINE_SLEEP = 0.15
# 连续失败多少次后降级本地引擎
ONLINE_MAX_CONSECUTIVE_FAIL = 3

# 专有名词占位符: [[P0]], [[P1]] ...
_PLACEHOLDER_RE = re.compile(r"\[\[P(\d+)\]\]")

# 专有名词占位符: [[PN0]], [[PN1]] ...
# 使用带字母的罕见格式, 本地词典引擎查不到时原样保留, 保证翻译后可靠还原
_PLACEHOLDER_RE = re.compile(r"\[\[PN(\d+)\]\]")


def _is_dict_word(word: str) -> bool:
    """判断英文词是否被本地词典收录(收录则按普通词翻译)"""
    from ..data.loader import get_dictionary
    data = get_dictionary()
    w = word.lower()
    return w in data.en_overrides or w in data.en_zh


def _extract_proper_nouns(text: str) -> list:
    """
    识别英文专有名词候选(仅本地词典引擎使用):
    - 连续大写词序列(如 New York): 序列中任一词词典未收录 -> 视为专名
    - 单独大写词(如 Microsoft): 词典未收录 -> 视为专名
    词典已收录的词(Alice/Annual/New 等)按普通词翻译, 避免误保护。
    """
    matches = list(re.finditer(r"[A-Za-z]+", text))
    words = [m.group(0) for m in matches]
    positions = [(m.group(0), m.start()) for m in matches]

    nouns = []
    i = 0
    n = len(words)
    while i < n:
        w, pos = positions[i]
        # 大写首字母且不是全大写缩写(如 OK, USA 保留)
        if w[0].isupper() and not (len(w) <= 4 and w.isupper()):
            # 向后扩展连续大写词序列
            j = i
            seq = [w]
            while j + 1 < n and positions[j + 1][1] == positions[j][1] + len(words[j]) + 1 \
                    and words[j + 1][0].isupper():
                seq.append(words[j + 1])
                j += 1

            if len(seq) >= 2:
                # 序列中任一词未收录 -> 整个序列视为专名(保留原名)
                if any(not _is_dict_word(x) for x in seq):
                    nouns.append(" ".join(seq))
                i = j + 1
                continue
            # 单独大写词: 词典未收录才保护
            if not _is_dict_word(w):
                nouns.append(w)
        i += 1
    return nouns


def _protect_proper_nouns(text: str) -> tuple:
    """将专名替换为占位符, 返回 (保护后文本, {占位符: 原文})"""
    nouns = _extract_proper_nouns(text)
    if not nouns:
        return text, {}
    mapping = {}
    protected = text
    for k, noun in enumerate(dict.fromkeys(nouns)):  # 去重
        placeholder = f"[[PN{k}]]"
        mapping[placeholder] = noun
        # 用正则替换词边界(避免替换到子串)
        protected = re.sub(rf"\b{re.escape(noun)}\b", placeholder, protected, count=1)
    return protected, mapping


def _restore_proper_nouns(text: str, mapping: dict) -> str:
    """翻译完成后将占位符还原为专名原文"""
    if not mapping:
        return text
    for placeholder, noun in mapping.items():
        text = text.replace(placeholder, noun)
    return text


# ---------------------------------------------------------------
# 单块翻译(带分块/限速/降级/专名保护)
# ---------------------------------------------------------------
class _Translator:
    """
    文档翻译器(支持 10 种语言与汉语双向翻译)。

    专名保护策略:
    - 在线引擎: 直接翻译原文(在线翻译自带专名处理能力)
    - 本地引擎: 仅英译中时对词典未收录的专名做占位保护, 翻译后还原

    中转翻译:
    - 非汉语A -> 汉语 -> 非汉语B: 两步翻译
    """

    def __init__(self, source: str, target: str, use_online: bool):
        self.source = source
        self.target = target
        self.use_online = use_online
        self.consecutive_fail = 0
        self.engine = "online"
        self.protect_nouns = (source == "en")  # 仅英译中需要专名保护
        self.relay = False
        # 判断是否需要中转
        _, needs_relay, _ = validate_lang_pair(source, target)
        self.needs_relay = needs_relay

    def translate_chunk(self, text: str) -> str:
        """翻译单个文本块(可能内部再分块或中转)"""
        # 中转翻译: 非汉语A -> 汉语 -> 非汉语B
        if self.needs_relay:
            return self._translate_relay(text)

        if self.engine == "local" or not self.use_online:
            return self._translate_local(text)

        # 在线路径: 按长度分块
        try:
            if len(text) <= ONLINE_CHUNK_LIMIT:
                result = self._online_with_retry(text)
            else:
                result = self._translate_long(text)
            self.consecutive_fail = 0
            self.engine = "online"
            return result
        except Exception:
            self.consecutive_fail += 1
            has_local = (self.source, self.target) in LOCAL_DICT_PAIRS
            if self.consecutive_fail >= ONLINE_MAX_CONSECUTIVE_FAIL and has_local:
                self.engine = "local"
            if has_local:
                return self._translate_local(text)
            raise  # 非英汉语言对无法回退本地

    def _translate_relay(self, text: str) -> str:
        """中转翻译: 源语言 -> 汉语 -> 目标语言"""
        # 第一步: 源语言 -> 汉语
        step1_tr = _Translator(self.source, "zh", self.use_online)
        step1_tr.engine = self.engine
        zh_text = step1_tr.translate_chunk(text)
        self.engine = step1_tr.engine

        if not zh_text or not zh_text.strip():
            return text  # 中转失败, 返回原文

        # 第二步: 汉语 -> 目标语言
        step2_tr = _Translator("zh", self.target, self.use_online)
        step2_tr.engine = self.engine
        result = step2_tr.translate_chunk(zh_text)
        self.engine = step2_tr.engine
        self.relay = True
        return result

    def _translate_long(self, text: str) -> str:
        """长块: 按句子切分后逐句在线翻译, 拼接返回"""
        sentences = text_utils.split_sentences(text)
        parts = []
        for sent in sentences:
            if not sent.strip():
                continue
            if len(sent) <= ONLINE_CHUNK_LIMIT:
                parts.append(self._online_with_retry(sent))
            else:
                # 超长句: 按字符硬切
                for piece in _hard_split(sent, ONLINE_CHUNK_LIMIT):
                    parts.append(self._online_with_retry(piece))
        return " ".join(p for p in parts if p)

    def _online_with_retry(self, text: str) -> str:
        """在线翻译单块(含术语表与翻译记忆), 失败重试一次"""
        # 术语保护
        p_text, term_map = (glossary_mod.protect_terms(text, self.source)
                            if glossary_mod.is_enabled() else (text, {}))
        # 翻译记忆: 整块命中直接复用
        tm_hit = tm_mod.lookup(self.source, self.target, text)
        if tm_hit:
            return tm_hit
        try:
            result = translate_online(p_text, self.source, self.target)
        except Exception:
            time.sleep(0.3)
            result = translate_online(p_text, self.source, self.target)
        if term_map:
            result = glossary_mod.restore_terms(result, term_map)
        tm_mod.remember(self.source, self.target, text, result)
        return result

    def _translate_local(self, text: str) -> str:
        """本地词典引擎翻译(带专名保护)"""
        work_text, noun_map = text, {}
        if self.protect_nouns:
            work_text, noun_map = _protect_proper_nouns(text)

        r = translate_text(work_text, source=self.source, target=self.target,
                           use_online=False)
        translated = r.get("translation", "") if not r.get("error") else ""

        if noun_map:
            translated = _restore_proper_nouns(translated, noun_map)
        return translated


def _hard_split(text: str, limit: int) -> list:
    """按字符硬切成长度 <= limit 的片段(保持语义切在标点处优先)"""
    if len(text) <= limit:
        return [text]
    pieces = []
    buf = ""
    for ch in text:
        buf += ch
        if len(buf) >= limit:
            pieces.append(buf)
            buf = ""
    if buf:
        pieces.append(buf)
    return pieces


# ---------------------------------------------------------------
# 文档级翻译入口
# ---------------------------------------------------------------
def translate_document(model: DocumentModel, source: str = "auto",
                       target: str = "auto", use_online: bool = True,
                       progress_cb=None) -> DocumentModel:
    """
    翻译整个文档模型, 返回翻译后的新模型(块结构/格式不变)。

    参数:
        source/target: auto | zh | en | ja | ko | fr | de | es | ru | ar | pt | th
        use_online: 是否启用在线增强(失败自动降级本地, 仅英汉对)
        progress_cb: 可选回调 func(done, total, block_text) 报告进度

    翻译规则:
        - 汉语 <-> 非汉语: 直接翻译
        - 非汉语 <-> 非汉语: 通过汉语中转翻译
        - 本地词典仅支持英汉双向, 其他语言对依赖在线翻译
    """
    # 语言检测: 用首个可翻译块判断方向
    first_text = next((b.text for _, b in model.iter_blocks()), "")
    detected = detect_language(first_text) if first_text else "unknown"
    src, tgt = resolve_auto_lang(source, target, detected)

    if src == "unknown":
        raise ValueError("无法识别文档语言，请在翻译前手动选择源语言。")

    # 语言对验证
    is_valid, needs_relay, err_msg = validate_lang_pair(src, tgt)
    if not is_valid:
        raise ValueError(err_msg)

    # 非英汉语言对必须在线
    has_local = (src, tgt) in LOCAL_DICT_PAIRS
    if not has_local and not use_online:
        lang_name = SUPPORTED_LANGUAGES.get(tgt if is_zh(src) else src, "")
        raise ValueError(f"{lang_name}翻译需要在线增强支持，请开启在线增强选项。")

    translator = _Translator(src, tgt, use_online)

    # 收集所有可翻译块
    locations = list(model.iter_blocks())
    total = len(locations)

    for done, (location, block) in enumerate(locations, 1):
        raw = block.text
        if not raw or not raw.strip():
            continue

        # 翻译(专名保护在 _Translator 内部按引擎类型处理)
        translated = translator.translate_chunk(raw).strip()

        # 写回(保留块结构)
        model.set_text(location, translated)

        if progress_cb:
            progress_cb(done, total, raw[:30])

        time.sleep(ONLINE_SLEEP)  # 限速, 规避公共 API 频率限制

    model.meta["translated"] = True
    model.meta["source_lang"] = src
    model.meta["target_lang"] = tgt
    model.meta["engine"] = translator.engine
    return model
