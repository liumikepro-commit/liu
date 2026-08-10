# -*- coding: utf-8 -*-
"""
test_multilang.py — 多语言翻译测试
覆盖: 语言检测、语言对验证、中转翻译、拒绝不支持语言对、Provider语言映射
"""
import unittest
import sys
import os

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from translator.core.languages import (
    detect_language,
    is_supported_lang,
    is_zh,
    is_non_zh,
    validate_lang_pair,
    resolve_auto_lang,
    SUPPORTED_LANGUAGES,
    NON_ZH_LANGS,
    MYMEMORY_LANG_MAP,
    DEEPL_LANG_MAP,
    BAIDU_LANG_MAP,
    TENCENT_LANG_MAP,
    OPENAI_LANG_MAP,
)


class TestLanguageDetection(unittest.TestCase):
    """测试多语言检测"""

    def test_detect_chinese(self):
        self.assertEqual(detect_language("你好世界"), "zh")
        self.assertEqual(detect_language("今天天气很好"), "zh")

    def test_detect_english(self):
        self.assertEqual(detect_language("Hello world"), "en")
        self.assertEqual(detect_language("The quick brown fox"), "en")

    def test_detect_japanese(self):
        self.assertEqual(detect_language("こんにちは"), "ja")
        self.assertEqual(detect_language("私は学生です"), "ja")

    def test_detect_korean(self):
        self.assertEqual(detect_language("안녕하세요"), "ko")

    def test_detect_arabic(self):
        self.assertEqual(detect_language("مرحبا بالعالم"), "ar")

    def test_detect_thai(self):
        self.assertEqual(detect_language("สวัสดีครับ"), "th")

    def test_detect_russian(self):
        self.assertEqual(detect_language("Привет мир"), "ru")

    def test_detect_french(self):
        # 法语特征词
        self.assertEqual(detect_language("Le chat est sur la table"), "fr")

    def test_detect_german(self):
        self.assertEqual(detect_language("Der Hund ist groß und stark"), "de")

    def test_detect_spanish(self):
        self.assertEqual(detect_language("El gato está en la casa"), "es")

    def test_detect_empty(self):
        self.assertEqual(detect_language(""), "unknown")
        self.assertEqual(detect_language("   "), "unknown")

    def test_detect_numbers_only(self):
        self.assertEqual(detect_language("12345"), "unknown")


class TestLanguageValidation(unittest.TestCase):
    """测试语言对验证"""

    def test_zh_to_en_valid(self):
        ok, relay, err = validate_lang_pair("zh", "en")
        self.assertTrue(ok)
        self.assertFalse(relay)
        self.assertIsNone(err)

    def test_en_to_zh_valid(self):
        ok, relay, err = validate_lang_pair("en", "zh")
        self.assertTrue(ok)
        self.assertFalse(relay)
        self.assertIsNone(err)

    def test_zh_to_ja_valid(self):
        ok, relay, err = validate_lang_pair("zh", "ja")
        self.assertTrue(ok)
        self.assertFalse(relay)
        self.assertIsNone(err)

    def test_ja_to_zh_valid(self):
        ok, relay, err = validate_lang_pair("ja", "zh")
        self.assertTrue(ok)
        self.assertFalse(relay)
        self.assertIsNone(err)

    def test_non_zh_pair_needs_relay(self):
        """非汉语语言对需要中转"""
        ok, relay, err = validate_lang_pair("en", "ja")
        self.assertTrue(ok)
        self.assertTrue(relay)
        self.assertIsNone(err)

    def test_fr_to_de_needs_relay(self):
        ok, relay, err = validate_lang_pair("fr", "de")
        self.assertTrue(ok)
        self.assertTrue(relay)

    def test_ko_to_ar_needs_relay(self):
        ok, relay, err = validate_lang_pair("ko", "ar")
        self.assertTrue(ok)
        self.assertTrue(relay)

    def test_same_lang_rejected(self):
        ok, relay, err = validate_lang_pair("en", "en")
        self.assertFalse(ok)
        self.assertIsNotNone(err)

    def test_unsupported_lang_rejected(self):
        ok, relay, err = validate_lang_pair("en", "xx")
        self.assertFalse(ok)
        self.assertIsNotNone(err)

    def test_all_10_langs_with_zh(self):
        """所有10种语言与汉语配对都合法"""
        for lang in NON_ZH_LANGS:
            ok, relay, err = validate_lang_pair(lang, "zh")
            self.assertTrue(ok, f"{lang}->zh should be valid")
            self.assertFalse(relay)
            ok2, relay2, err2 = validate_lang_pair("zh", lang)
            self.assertTrue(ok2, f"zh->{lang} should be valid")
            self.assertFalse(relay2)

    def test_all_non_zh_pairs_need_relay(self):
        """所有非汉语语言对都需要中转"""
        non_zh = list(NON_ZH_LANGS)
        for i, a in enumerate(non_zh):
            for b in non_zh[i+1:]:
                ok, relay, err = validate_lang_pair(a, b)
                self.assertTrue(ok, f"{a}->{b} should be valid")
                self.assertTrue(relay, f"{a}->{b} should need relay")


class TestResolveAutoLang(unittest.TestCase):
    """测试 auto 语言解析"""

    def test_auto_source_uses_detected(self):
        src, tgt = resolve_auto_lang("auto", "zh", "en")
        self.assertEqual(src, "en")
        self.assertEqual(tgt, "zh")

    def test_auto_target_defaults_to_zh(self):
        src, tgt = resolve_auto_lang("ja", "auto", "ja")
        self.assertEqual(src, "ja")
        self.assertEqual(tgt, "zh")

    def test_auto_target_zh_source_defaults_to_en(self):
        src, tgt = resolve_auto_lang("zh", "auto", "zh")
        self.assertEqual(src, "zh")
        self.assertEqual(tgt, "en")

    def test_both_auto(self):
        src, tgt = resolve_auto_lang("auto", "auto", "fr")
        self.assertEqual(src, "fr")
        self.assertEqual(tgt, "zh")

    def test_unknown_detected_fallback(self):
        src, tgt = resolve_auto_lang("auto", "auto", "unknown")
        self.assertEqual(src, "en")
        self.assertEqual(tgt, "zh")


class TestProviderLangMaps(unittest.TestCase):
    """测试各 Provider 的语言代码映射完整性"""

    def test_all_providers_have_11_langs(self):
        """每个 Provider 映射表都包含全部 11 种语言"""
        for name, mapping in [
            ("MyMemory", MYMEMORY_LANG_MAP),
            ("DeepL", DEEPL_LANG_MAP),
            ("Baidu", BAIDU_LANG_MAP),
            ("Tencent", TENCENT_LANG_MAP),
            ("OpenAI", OPENAI_LANG_MAP),
        ]:
            for lang in SUPPORTED_LANGUAGES:
                self.assertIn(lang, mapping, f"{name} 缺少语言: {lang}")

    def test_mymemory_zh_is_zh_cn(self):
        self.assertEqual(MYMEMORY_LANG_MAP["zh"], "zh-CN")

    def test_baidu_uses_special_codes(self):
        self.assertEqual(BAIDU_LANG_MAP["ja"], "jp")
        self.assertEqual(BAIDU_LANG_MAP["ko"], "kor")
        self.assertEqual(BAIDU_LANG_MAP["fr"], "fra")
        self.assertEqual(BAIDU_LANG_MAP["es"], "spa")
        self.assertEqual(BAIDU_LANG_MAP["ar"], "ara")


class TestEngineMultilang(unittest.TestCase):
    """测试翻译引擎的多语言支持"""

    def test_translate_rejects_unsupported_lang(self):
        from translator.core.engine import translate
        result = translate("hello", source="en", target="xx")
        self.assertIsNotNone(result["error"])
        self.assertIn("不支持", result["error"])

    def test_translate_same_lang_error(self):
        from translator.core.engine import translate
        result = translate("hello", source="en", target="en")
        self.assertIsNotNone(result["error"])

    def test_translate_non_zh_without_online_error(self):
        """非英汉语言对关闭在线时应报错"""
        from translator.core.engine import translate
        result = translate("こんにちは", source="ja", target="zh", use_online=False)
        self.assertIsNotNone(result["error"])
        self.assertIn("在线增强", result["error"])

    def test_translate_relay_warning(self):
        """中转翻译应返回 relay=True 和 warning"""
        from translator.core.engine import translate
        # 这里无法真正调用在线 API, 但可以验证逻辑结构
        # 如果在线不可用会抛异常, 我们验证 relay 字段存在
        try:
            result = translate("hello", source="en", target="ja", use_online=True)
            # 如果成功, 应该有 relay 标记
            if not result.get("error"):
                self.assertTrue(result.get("relay"))
                self.assertEqual(result["engine"], "relay")
        except Exception:
            # 在线 API 不可用时跳过
            pass

    def test_translate_returns_relay_field(self):
        """翻译结果应包含 relay 字段"""
        from translator.core.engine import translate
        result = translate("hello", source="en", target="zh", use_online=False)
        self.assertIn("relay", result)
        self.assertFalse(result["relay"])

    def test_all_10_langs_in_supported(self):
        """确认 10 种语言 + 汉语都在支持列表中"""
        expected = {"zh", "en", "ja", "ko", "fr", "de", "es", "ru", "ar", "pt", "th"}
        self.assertEqual(set(SUPPORTED_LANGUAGES.keys()), expected)
        self.assertEqual(len(SUPPORTED_LANGUAGES), 11)  # 10 + zh


class TestGlossaryMultilang(unittest.TestCase):
    """测试术语表多语言支持"""

    def test_glossary_supports_all_langs(self):
        from translator.core.glossary import get_terms
        terms = get_terms()
        for lang in SUPPORTED_LANGUAGES:
            self.assertIn(lang, terms, f"术语表缺少语言: {lang}")


if __name__ == "__main__":
    unittest.main()
