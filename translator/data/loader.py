# -*- coding: utf-8 -*-
"""
loader.py — 数据加载模块
负责加载词典索引(zh_en.json / en_zh.json)与人工精选修正表(overrides.json)。
采用懒加载 + 单例缓存, 首次使用时才读盘, 避免无谓启动开销。

数据来源: CC-CEDICT 开源词典 (CC BY-SA 4.0), 详见 dictionary/README.md
"""
import json
import os
import threading

# 数据目录
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dictionary")


class DictionaryData:
    """双向翻译词典数据容器"""

    def __init__(self, data_dir: str = DATA_DIR):
        self._dir = data_dir
        self._lock = threading.Lock()
        self._loaded = False

        self.en_zh = {}        # 英文词/短语 -> [中文候选(按常用度排序)]
        self.zh_en = {}        # 中文词 -> [英文释义]
        self.zh_overrides = {}  # 中文词 -> 首选英文(人工精选)
        self.en_overrides = {}  # 英文词 -> 首选中文(人工精选)
        self.max_zh_len = 4    # 最长中文词条长度(用于最大匹配)

    # ---------- 加载 ----------
    def ensure_loaded(self):
        """确保数据已加载(幂等, 线程安全)"""
        self._ensure_loaded()

    def _ensure_loaded(self):
        """懒加载: 线程安全, 只加载一次"""
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._load_all()
            self._loaded = True

    def _load_all(self):
        en_path = os.path.join(self._dir, "en_zh.json")
        zh_path = os.path.join(self._dir, "zh_en.json")
        ov_path = os.path.join(self._dir, "overrides.json")

        if os.path.exists(en_path):
            with open(en_path, encoding="utf-8") as f:
                self.en_zh = json.load(f)
        if os.path.exists(zh_path):
            with open(zh_path, encoding="utf-8") as f:
                self.zh_en = json.load(f)
        if os.path.exists(ov_path):
            with open(ov_path, encoding="utf-8") as f:
                ov = json.load(f)
                self.zh_overrides = ov.get("zh_en", {})
                self.en_overrides = ov.get("en_zh", {})

        # 计算最长中文词条(含修正表), 用于前向最大匹配
        max_zh = 0
        for k in self.zh_en:
            if len(k) > max_zh:
                max_zh = len(k)
        for k in self.zh_overrides:
            if len(k) > max_zh:
                max_zh = len(k)
        self.max_zh_len = min(max(4, max_zh), 32)  # 限制上限防止异常性能开销

    # ---------- 查询 ----------
    def lookup_en(self, word: str):
        """
        英文 -> 中文查询(含人工修正表优先)。
        返回 (译文列表, 是否修正表命中)
        """
        self._ensure_loaded()
        word = word.lower()
        if word in self.en_overrides:
            return self.en_overrides[word].split("；"), True
        if word in self.en_zh:
            return self.en_zh[word], False
        return None, False

    def lookup_zh(self, word: str):
        """
        中文 -> 英文查询(含人工修正表优先)。
        返回 (译文列表, 是否修正表命中)
        """
        self._ensure_loaded()
        if word in self.zh_overrides:
            return [self.zh_overrides[word]], True
        if word in self.zh_en:
            return self.zh_en[word], False
        return None, False


# 模块级单例
_DICT = DictionaryData()


def get_dictionary() -> DictionaryData:
    """获取全局词典单例"""
    return _DICT
