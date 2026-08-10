# -*- coding: utf-8 -*-
"""
test_enhance.py — 提效功能测试(术语表/翻译记忆/多引擎)

运行: python -m unittest tests.test_enhance -v
"""
import unittest

from translator.core import glossary as g
from translator.core import tm as t
from translator.core import providers
from translator.core.engine import translate


class TestGlossary(unittest.TestCase):
    """术语表"""

    def setUp(self):
        g.clear()
        g.set_enabled(True)

    def tearDown(self):
        g.clear()

    def test_add_and_protect_en(self):
        g.add_term("en", "KPI", "关键绩效指标")
        protected, mapping = g.protect_terms("The KPI of team is good.", "en")
        self.assertNotIn("KPI", protected)
        self.assertIn("[[T0]]", protected)

    def test_restore(self):
        g.add_term("en", "KPI", "关键绩效指标")
        protected, mapping = g.protect_terms("The KPI is good.", "en")
        restored = g.restore_terms("[[T0]]is good.", mapping)
        self.assertIn("关键绩效指标", restored)

    def test_word_boundary(self):
        """英文术语须词边界匹配: KPI 不应匹配 KPIs"""
        g.add_term("en", "KPI", "关键绩效指标")
        protected, _ = g.protect_terms("The KPIs are growing.", "en")
        self.assertIn("KPIs", protected)  # 未被替换

    def test_zh_direction(self):
        g.add_term("zh", "接口", "API")
        protected, mapping = g.protect_terms("这个接口很好用。", "zh")
        self.assertIn("[[T0]]", protected)

    def test_disabled(self):
        g.set_enabled(False)
        g.add_term("en", "KPI", "关键绩效指标")
        protected, _ = g.protect_terms("The KPI is good.", "en")
        self.assertIn("KPI", protected)  # 未保护
        g.set_enabled(True)


class TestTranslationMemory(unittest.TestCase):
    """翻译记忆"""

    def setUp(self):
        t.clear()
        t.set_enabled(True)

    def tearDown(self):
        t.clear()

    def test_remember_lookup(self):
        t.remember("en", "zh", "Hello world", "你好世界")
        self.assertEqual(t.lookup("en", "zh", "Hello world"), "你好世界")
        self.assertIsNone(t.lookup("en", "zh", "Hello other"))

    def test_lang_pair_isolation(self):
        t.remember("en", "zh", "Good", "好")
        self.assertIsNone(t.lookup("zh", "en", "Good"))

    def test_stats(self):
        t.remember("en", "zh", "A", "甲")
        t.lookup("en", "zh", "A")
        stats = t.stats()
        self.assertEqual(stats["entries"], 1)
        self.assertGreaterEqual(stats["hits"], 1)

    def test_clear(self):
        t.remember("en", "zh", "A", "甲")
        t.clear()
        self.assertEqual(t.stats()["entries"], 0)

    def test_engine_tm_hit(self):
        """engine.translate 第二次相同输入应从翻译记忆命中"""
        r1 = translate("This is a unique sentence for TM test.", use_online=False)
        r2 = translate("This is a unique sentence for TM test.", use_online=False)
        self.assertEqual(r2["engine"], "tm")
        self.assertEqual(r1["translation"], r2["translation"])


class TestProviders(unittest.TestCase):
    """多引擎提供商"""

    def test_list_providers(self):
        names = [p["name"] for p in providers.list_providers()]
        self.assertIn("mymemory", names)
        self.assertIn("deepl", names)
        self.assertIn("openai", names)

    def test_mymemory_always_ready(self):
        self.assertTrue(providers.provider_ready("mymemory"))

    def test_unconfigured_provider_not_ready(self):
        # 未配置 key 时 deepl 不可用(测试环境不应有真实 key)
        self.assertFalse(providers.provider_ready("deepl"))

    def test_get_provider_fallback(self):
        # 无效名称回退 mymemory
        p = providers.get_provider("not_exist")
        self.assertEqual(p.name, "mymemory")


if __name__ == "__main__":
    unittest.main()
