# -*- coding: utf-8 -*-
"""
test_engine.py — 翻译引擎单元测试
覆盖: 双向翻译、自动检测、空输入、长文本、特殊字符、词形还原、数字保留等。

运行: python -m unittest tests/test_engine.py -v
"""
import unittest

from translator.core.engine import translate, detect_language
from translator.core import matcher


class TestLanguageDetect(unittest.TestCase):
    """语言检测"""

    def test_en(self):
        self.assertEqual(detect_language("Hello, how are you today?"), "en")

    def test_zh(self):
        self.assertEqual(detect_language("你好，今天天气怎么样？"), "zh")

    def test_mixed(self):
        self.assertEqual(detect_language("Hello 你好"), "zh")

    def test_unknown(self):
        self.assertEqual(detect_language("1234567890"), "unknown")


class TestEnToZh(unittest.TestCase):
    """英译中"""

    def test_basic_words(self):
        r = translate("hello world", use_online=False)
        self.assertEqual(r["source"], "en")
        self.assertEqual(r["target"], "zh")
        self.assertIn("你好", r["translation"])
        self.assertIn("世界", r["translation"])

    def test_stemming(self):
        """词形还原: 复数/进行时/过去式"""
        r = translate("I like reading books", use_online=False)
        self.assertIn("读", r["translation"])
        self.assertIn("书", r["translation"])

    def test_numbers_kept(self):
        r = translate("There are 3 apples and 2 books", use_online=False)
        self.assertIn("3", r["translation"])
        self.assertIn("2", r["translation"])

    def test_irregular_verb(self):
        r = translate("I went to school", use_online=False)
        self.assertIn("去", r["translation"])
        self.assertIn("学校", r["translation"])

    def test_unknown_word_kept(self):
        r = translate("hello xyzzyplugh", use_online=False)
        self.assertIn("xyzzyplugh", r["translation"])  # 未收录词保留原文
        self.assertTrue(r["uncovered"])

    def test_phrase_match(self):
        r = translate("thank you", use_online=False)
        self.assertIn("谢谢", r["translation"])


class TestZhToEn(unittest.TestCase):
    """中译英"""

    def test_basic_words(self):
        r = translate("你好世界", use_online=False)
        self.assertEqual(r["source"], "zh")
        self.assertIn("Hello", r["translation"])
        self.assertIn("world", r["translation"])

    def test_sentence(self):
        r = translate("我喜欢学习英语", use_online=False)
        t = r["translation"].lower()
        self.assertTrue("like" in t and ("study" in t or "learn" in t), r["translation"])

    def test_to_prefix_removed(self):
        """动词释义 'to eat' 应清理为 'eat'"""
        r = translate("吃", use_online=False)
        self.assertIn("eat", r["translation"].lower())

    def test_unknown_kept(self):
        r = translate("你好 氪金鰬", use_online=False)
        self.assertTrue(r["translation"])  # 不崩溃


class TestEdgeCases(unittest.TestCase):
    """边界情况"""

    def test_empty_input(self):
        r = translate("   ", use_online=False)
        self.assertIsNotNone(r["error"])

    def test_none_input(self):
        r = translate(None, use_online=False)
        self.assertIsNotNone(r["error"])

    def test_long_input(self):
        long_text = "hello " * 2000  # 超过 5000 字符
        r = translate(long_text, use_online=False)
        self.assertIsNotNone(r["error"])  # 应提示过长

    def test_special_chars(self):
        r = translate("Hello! <b>bold</b> & 'quotes'", use_online=False)
        self.assertTrue(r["translation"])

    def test_emoji(self):
        r = translate("I love apple 🍎", use_online=False)
        self.assertTrue("爱" in r["translation"] or "喜欢" in r["translation"],
                        r["translation"])

    def test_numbers_only(self):
        r = translate("3.14", use_online=False)
        self.assertEqual(r["source"], "unknown")
        self.assertIsNotNone(r["error"])

    def test_multi_sentence(self):
        r = translate("Hello. How are you?", use_online=False)
        self.assertTrue(r["translation"])


class TestMatcher(unittest.TestCase):
    """匹配模块"""

    def test_lemmatize(self):
        self.assertIn("run", matcher.lemmatize("running"))
        self.assertIn("study", matcher.lemmatize("studies"))
        self.assertIn("be", matcher.lemmatize("was"))
        self.assertIn("go", matcher.lemmatize("went"))
        self.assertIn("book", matcher.lemmatize("books"))

    def test_lookup_with_lemma(self):
        result, form = matcher.lookup_en_with_lemma("running")
        self.assertIsNotNone(result)
        self.assertEqual(form, "run")


if __name__ == "__main__":
    unittest.main()
