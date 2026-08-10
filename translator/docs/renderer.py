# -*- coding: utf-8 -*-
"""
renderer.py — 文档重建与导出模块
将翻译后的 DocumentModel 渲染为:
- .docx: python-docx 重建(保留段落样式/字体/加粗/表格/列表)
- .pdf : reportlab 生成(标题/段落/列表/表格/分页, 自动注册中文字体)

导出格式说明:
- Word 翻译后导出 .docx: 结构级版式完整保留(标题层级、粗体、字号、对齐、表格)
- PDF 翻译后导出 .pdf: 由于 PDF 无结构化版式, 采用"版式重建"策略
  (按内容结构重新排版), 保证内容完整与排版美观, 非逐像素还原。
"""
import os

from .block import DocumentModel, KIND_HEADING, KIND_LIST_ITEM, KIND_EMPTY

# 中文粗体字体(Windows 微软雅黑; 按顺序探测)
_CJK_BOLD_FONTS = [
    "C:/Windows/Fonts/msyhbd.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
]
_CJK_REGULAR_FONTS = [
    "C:/Windows/Fonts/msyh.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]


# ---------------------------------------------------------------
# Word (.docx) 导出
# ---------------------------------------------------------------
def render_docx(model: DocumentModel, out_path: str):
    """将文档模型渲染为 .docx"""
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt

    doc = Document()

    # 文档默认字体(兼顾中文)
    try:
        normal = doc.styles["Normal"]
        normal.font.name = "Microsoft YaHei"
        normal.font.size = Pt(11)
    except Exception:
        pass

    _apply_align = {
        0: WD_ALIGN_PARAGRAPH.LEFT,
        1: WD_ALIGN_PARAGRAPH.CENTER,
        2: WD_ALIGN_PARAGRAPH.RIGHT,
        3: WD_ALIGN_PARAGRAPH.JUSTIFY,
    }

    def add_paragraph(text: str, kind: str, style: dict, meta: dict):
        if kind == KIND_EMPTY or not text.strip():
            doc.add_paragraph("")
            return
        p = doc.add_paragraph()
        run = p.add_run(text)

        if style.get("bold"):
            run.bold = True
        if style.get("italic"):
            run.italic = True
        if style.get("font_size"):
            run.font.size = Pt(style["font_size"])
        align = style.get("align")
        if align in _apply_align:
            p.alignment = _apply_align[align]

        if kind == KIND_HEADING:
            level = meta.get("level", 1)
            p.style = doc.styles[f"Heading {min(level, 4)}"]
            run.bold = True
        elif kind == KIND_LIST_ITEM:
            p.style = doc.styles["List Bullet"]
        return p

    # 顺序块
    for b in model.blocks:
        add_paragraph(b.text, b.kind, b.style, b.meta)

    # 表格
    for table_model in model.tables:
        if not table_model:
            continue
        n_rows = len(table_model)
        n_cols = max(len(r) for r in table_model)
        table = doc.add_table(rows=n_rows, cols=n_cols)
        table.style = "Table Grid"
        for r, row in enumerate(table_model):
            for c, cell_blocks in enumerate(row):
                if c >= n_cols:
                    continue
                cell = table.cell(r, c)
                # 清空默认段落, 写入单元格块
                cell.text = ""
                for cb in cell_blocks:
                    para = cell.paragraphs[0] if cb is cell_blocks[0] and not cell.paragraphs[0].text else cell.add_paragraph()
                    para.add_run(cb.text)
        doc.add_paragraph("")  # 表格后空行

    doc.save(out_path)


# ---------------------------------------------------------------
# PDF 导出
# ---------------------------------------------------------------
def _register_cjk_fonts() -> tuple:
    """
    注册中文字体到 reportlab, 返回 (普通字体名, 粗体字体名)。
    动态探测系统中文字体; 找不到时回退 Helvetica(中文将无法显示)。
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    reg_path = next((p for p in _CJK_REGULAR_FONTS if os.path.exists(p)), None)
    bold_path = next((p for p in _CJK_BOLD_FONTS if os.path.exists(p)), None)

    if reg_path:
        pdfmetrics.registerFont(TTFont("CJK", reg_path))
        if bold_path:
            pdfmetrics.registerFont(TTFont("CJK-Bold", bold_path))
            return "CJK", "CJK-Bold"
        return "CJK", "CJK"  # 无粗体时粗体退化为普通
    return "Helvetica", "Helvetica-Bold"


def render_pdf(model: DocumentModel, out_path: str):
    """将文档模型渲染为 PDF (版式重建)"""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    )
    from reportlab.lib.utils import simpleSplit

    font_name, font_bold = _register_cjk_fonts()

    styles = {
        "body": ParagraphStyle(
            "body", fontName=font_name, fontSize=11, leading=18,
            alignment=TA_JUSTIFY, wordWrap="CJK"),
        "heading1": ParagraphStyle(
            "h1", fontName=font_bold, fontSize=20, leading=26,
            spaceBefore=14, spaceAfter=10, textColor=colors.black),
        "heading2": ParagraphStyle(
            "h2", fontName=font_bold, fontSize=16, leading=22,
            spaceBefore=10, spaceAfter=8),
        "heading3": ParagraphStyle(
            "h3", fontName=font_bold, fontSize=13, leading=18,
            spaceBefore=8, spaceAfter=6),
        "list": ParagraphStyle(
            "list", fontName=font_name, fontSize=11, leading=18,
            leftIndent=18, bulletIndent=6, wordWrap="CJK"),
        "table": ParagraphStyle(
            "table", fontName=font_name, fontSize=10, leading=14, wordWrap="CJK"),
    }

    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=model.meta.get("title", "English Translator"),
    )
    story = []

    for b in model.blocks:
        text = b.text or ""
        if b.kind == KIND_EMPTY or not text.strip():
            story.append(Spacer(1, 6))
            continue
        if b.kind == KIND_HEADING:
            level = b.meta.get("level", 1)
            st = styles.get(f"heading{min(level, 3)}", styles["heading1"])
            story.append(Paragraph(_escape(text), st))
        elif b.kind == KIND_LIST_ITEM:
            story.append(Paragraph(_escape(text), styles["list"],
                                   bulletText="•"))
        else:
            align = b.style.get("align", 4)
            st = styles["body"]
            if align == 1:
                st = ParagraphStyle("c", parent=st, alignment=TA_CENTER)
            elif align == 2:
                st = ParagraphStyle("r", parent=st, alignment=TA_RIGHT)
            if b.style.get("bold"):
                st = ParagraphStyle("b", parent=st, fontName=font_bold)
            story.append(Paragraph(_escape(text), st))

    # 表格
    for table_model in model.tables:
        if not table_model:
            continue
        data = []
        for row in table_model:
            data.append([
                Paragraph(_escape(" ".join(
                    cb.text for cb in cell
                    if cb.text and cb.text.strip())), styles["table"])
                for cell in row
            ])
        if data:
            t = Table(data, hAlign="LEFT")
            t.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(t)
            story.append(Spacer(1, 8))

    doc.build(story)


def _escape(text: str) -> str:
    """转义 XML 特殊字符(Paragraph 使用 XML 标记)"""
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;"))


# ---------------------------------------------------------------
# 统一入口
# ---------------------------------------------------------------
def export_document(model: DocumentModel, fmt: str, out_path: str):
    """按格式导出文档; fmt: docx | pdf"""
    if fmt == "docx":
        render_docx(model, out_path)
    elif fmt == "pdf":
        render_pdf(model, out_path)
    else:
        raise ValueError(f"不支持的导出格式: {fmt}")
