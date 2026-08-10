# -*- coding: utf-8 -*-
"""
languages.py — 多语言配置中心
定义支持的 10 种语言及其与汉语的双向翻译规则。

核心规则:
1. 支持 10 种语言与汉语的双向翻译: 英语/日语/韩语/法语/德语/西班牙语/俄语/阿拉伯语/葡萄牙语/泰语
2. 每种语言仅支持与汉语之间的双向翻译
3. 非汉语语言之间通过汉语中转翻译
4. 不支持的语言对拒绝翻译
"""
import re

# ============================================================
# 支持的语言定义
# ============================================================
# 内部语言代码 -> 显示名称
SUPPORTED_LANGUAGES = {
    "zh": "中文",
    "en": "英语",
    "ja": "日语",
    "ko": "韩语",
    "fr": "法语",
    "de": "德语",
    "es": "西班牙语",
    "ru": "俄语",
    "ar": "阿拉伯语",
    "pt": "葡萄牙语",
    "th": "泰语",
}

# 非汉语语言列表(用于判断是否需要中转)
NON_ZH_LANGS = {k for k in SUPPORTED_LANGUAGES if k != "zh"}

# 本地词典支持的语言对(仅英汉双向)
LOCAL_DICT_PAIRS = {("en", "zh"), ("zh", "en")}

# ============================================================
# 各翻译引擎的语言代码映射
# ============================================================

# MyMemory: ISO 639-1, 中文用 zh-CN
MYMEMORY_LANG_MAP = {
    "zh": "zh-CN",
    "en": "en",
    "ja": "ja",
    "ko": "ko",
    "fr": "fr",
    "de": "de",
    "es": "es",
    "ru": "ru",
    "ar": "ar",
    "pt": "pt",
    "th": "th",
}

# DeepL: 大写 ISO 639-1
DEEPL_LANG_MAP = {
    "zh": "ZH",
    "en": "EN",
    "ja": "JA",
    "ko": "KO",
    "fr": "FR",
    "de": "DE",
    "es": "ES",
    "ru": "RU",
    "ar": "AR",
    "pt": "PT",
    "th": "TH",
}

# 百度翻译: 特殊缩写
BAIDU_LANG_MAP = {
    "zh": "zh",
    "en": "en",
    "ja": "jp",
    "ko": "kor",
    "fr": "fra",
    "de": "de",
    "es": "spa",
    "ru": "ru",
    "ar": "ara",
    "pt": "pt",
    "th": "th",
}

# 腾讯云 TMT: 小写 ISO 639-1 (API 内部会转大写)
TENCENT_LANG_MAP = {
    "zh": "zh",
    "en": "en",
    "ja": "ja",
    "ko": "ko",
    "fr": "fr",
    "de": "de",
    "es": "es",
    "ru": "ru",
    "ar": "ar",
    "pt": "pt",
    "th": "th",
}

# OpenAI: 语言全称(用于 prompt)
OPENAI_LANG_MAP = {
    "zh": "Simplified Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ru": "Russian",
    "ar": "Arabic",
    "pt": "Portuguese",
    "th": "Thai",
}

# 语言代码 -> Unicode 范围正则(用于自动检测)
# 注意: 日文假名(平假名/片假名)是日文独有, 优先于中文汉字检测
LANG_DETECT_RULES = [
    # 先匹配独有文字系统(日文假名/韩文/阿拉伯文/泰文)
    ("ja", re.compile(r"[\u3040-\u309f\u30a0-\u30ff]")),      # 平假名 + 片假名
    ("ko", re.compile(r"[\uac00-\ud7af]")),                     # 韩文音节
    ("ar", re.compile(r"[\u0600-\u06ff\u0750-\u077f]")),       # 阿拉伯文
    ("th", re.compile(r"[\u0e00-\u0e7f]")),                     # 泰文
    ("ru", re.compile(r"[\u0400-\u04ff]")),                     # 西里尔文(俄文)
    ("zh", re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")),       # CJK 汉字(中日韩共用)
    # 拉丁文系的语言无法仅凭 Unicode 范围区分, 需要后续启发式判断
]

# 拉丁文系语言特征(用于区分 en/fr/de/es/pt)
LATIN_LANG_HINTS = {
    "de": re.compile(r"\b(der|die|das|und|nicht|ist|ein|eine|mit|sich|auf|für|von|zu|den)\b", re.I),
    "es": re.compile(r"\b(el|la|los|las|que|de|y|un|una|con|por|para|en|es|del|se)\b", re.I),
    "fr": re.compile(r"\b(le|la|les|de|et|un|une|que|qui|dans|pour|avec|est|sur|ne|pas)\b", re.I),
    "pt": re.compile(r"\b(o|a|os|as|que|de|e|um|uma|com|por|para|em|não|do|da)\b", re.I),
    "en": re.compile(r"\b(the|and|is|are|was|were|to|of|in|for|with|that|this|have|has)\b", re.I),
}


def detect_language(text: str) -> str:
    """
    检测文本的主要语言。
    返回 SUPPORTED_LANGUAGES 中的语言代码, 或 'unknown'。

    检测策略:
    1. 先检查特殊文字系统(日文假名/韩文/阿拉伯文/泰文/俄文/中文)
    2. 若为拉丁文系, 用常见词频启发式区分英/法/德/西/葡
    """
    if not text or not text.strip():
        return "unknown"

    # 1. 特殊文字系统检测
    counts = {}
    for lang, pattern in LANG_DETECT_RULES:
        n = len(pattern.findall(text))
        if n > 0:
            counts[lang] = n

    if counts:
        # 取匹配数最多的语言
        best = max(counts, key=counts.get)
        return best

    # 2. 拉丁文系语言检测
    latin_count = len(re.findall(r"[a-zA-Zà-ÿÀ-Ÿ]", text))
    if latin_count == 0:
        return "unknown"

    # 用常见功能词区分
    hint_scores = {}
    for lang, pattern in LATIN_LANG_HINTS.items():
        matches = pattern.findall(text)
        if matches:
            hint_scores[lang] = len(matches)

    if hint_scores:
        return max(hint_scores, key=hint_scores.get)

    # 默认归为英语(最常见的拉丁文)
    return "en"


def is_supported_lang(lang: str) -> bool:
    """判断语言代码是否受支持"""
    return lang in SUPPORTED_LANGUAGES


def is_zh(lang: str) -> bool:
    """是否为汉语"""
    return lang == "zh"


def is_non_zh(lang: str) -> bool:
    """是否为非汉语语言"""
    return lang in NON_ZH_LANGS


def validate_lang_pair(source: str, target: str) -> tuple:
    """
    验证语言对是否合法。

    规则:
    - source 和 target 都必须是支持的语言(不支持 auto, 调用方需先解析)
    - source == target: 无需翻译
    - zh <-> X: 直接翻译(合法)
    - X <-> Y (均非汉语): 需要中转翻译(合法, 但标记为 relay)
    - 不支持的语言: 拒绝

    返回: (is_valid: bool, needs_relay: bool, error: str or None)
    """
    if not is_supported_lang(source):
        return (False, False, f"不支持的源语言: {source}")
    if not is_supported_lang(target):
        return (False, False, f"不支持的目标语言: {target}")
    if source == target:
        return (False, False, "源语言与目标语言相同，无需翻译。")

    # 汉语 <-> 非汉语: 直接翻译
    if is_zh(source) or is_zh(target):
        return (True, False, None)

    # 非汉语 <-> 非汉语: 需要中转
    return (True, True, None)


def resolve_auto_lang(source: str, target: str, detected: str) -> tuple:
    """
    解析 auto 语言代码, 返回实际的 (source, target)。

    规则:
    - source=auto: 用检测结果
    - target=auto: 取与 source 相反的(如果 source 非 zh 则 target=zh, 反之取 detected 或默认 en)
    - 仅当有 auto 时才做互补处理, 用户显式设置的语言对不强制改变
    """
    has_auto = (source == "auto" or target == "auto")

    src = source if source != "auto" else detected
    if src == "unknown":
        src = "en"  # 默认回退

    tgt = target if target != "auto" else None
    if not tgt:
        # auto: 取与 source 互补的语言
        tgt = "zh" if is_non_zh(src) else "en"

    # 仅在 auto 模式下, 如果最终 src == tgt, 强制切换
    if has_auto and src == tgt:
        tgt = "zh" if is_non_zh(src) else "en"

    return src, tgt
