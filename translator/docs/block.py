# -*- coding: utf-8 -*-
"""
block.py — 文档结构化文本块模型

设计目标: 文档翻译流水线各环节(解析 -> 翻译 -> 重建)通过统一的
中间模型衔接, 既保留原文格式信息, 又对翻译引擎透明。

模型结构:
    DocumentModel
        .blocks  : [TextBlock]          顺序内容块(段落/标题/列表项/占位行)
        .tables  : [[[TextBlock]]]       表格(行 -> 单元格 -> 块)

TextBlock 携带格式元数据 style:
    {bold, italic, underline, font_size, color, align, level}
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# 块类型常量
KIND_PARAGRAPH = "paragraph"   # 普通段落
KIND_HEADING = "heading"       # 标题
KIND_LIST_ITEM = "list_item"   # 列表项
KIND_EMPTY = "empty"           # 空行(保留排版间隔)


@dataclass
class TextBlock:
    """一个可翻译的文本块"""
    text: str = ""
    kind: str = KIND_PARAGRAPH
    style: Dict = field(default_factory=dict)   # 格式元数据
    meta: Dict = field(default_factory=dict)    # 额外信息(如标题级别)

    def is_translatable(self) -> bool:
        """是否包含可翻译内容(空行/纯空白不翻译)"""
        return bool(self.text and self.text.strip())


@dataclass
class DocumentModel:
    """文档中间模型"""
    blocks: List[TextBlock] = field(default_factory=list)
    tables: List[List[List[TextBlock]]] = field(default_factory=list)
    meta: Dict = field(default_factory=dict)  # 文档级信息(来源格式/标题等)

    # ---- 遍历所有可翻译块(含表格单元格) ----
    def iter_blocks(self):
        """
        生成器: 依次产出 (location, block)。
        location: ("block", i) 或 ("cell", t, r, c, i), 可直接传给 set_text
        tables 层级: tables[表][行][列][单元格内块]
        """
        for i, b in enumerate(self.blocks):
            if b.is_translatable():
                yield ("block", i), b
        for t, table in enumerate(self.tables):
            for r, row in enumerate(table):
                for c, cell in enumerate(row):
                    for i, b in enumerate(cell):
                        if b.is_translatable():
                            yield ("cell", t, r, c, i), b

    # ---- 替换翻译后的文本(保持块结构不变) ----
    def set_text(self, location, new_text: str):
        """按 iter_blocks 产出的定位信息写回译文"""
        if location[0] == "block":
            _, i = location
            self.blocks[i].text = new_text
        else:  # cell
            _, t, r, c, i = location
            self.tables[t][r][c][i].text = new_text
