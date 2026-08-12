# -*- coding: utf-8 -*-
"""
ocr.py — 图片文字识别(OCR)
使用 RapidOCR(基于 PaddleOCR 模型的 onnx 推理版本, 纯 Python, 无系统依赖),
识别图片中的文字, 并按阅读顺序重组为 DocumentModel, 供翻译流水线使用。

流程: 图片 -> OCR(检测框+文本) -> 阅读顺序排序 -> DocumentModel -> 翻译 -> PDF
"""
import os
import threading

from .block import DocumentModel, TextBlock, KIND_PARAGRAPH, KIND_EMPTY

# 允许的图片扩展名
SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".tif"}

_engine = None
_engine_lock = threading.Lock()


def validate_image_format(filename: str):
    """校验是否为支持的图片格式, 不支持时抛出 ValueError(清晰中文提示)"""
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in SUPPORTED_IMAGE_EXTS:
        raise ValueError(
            f"不支持的图片格式「{ext or '无扩展名'}」，请上传 "
            + " / ".join(sorted(SUPPORTED_IMAGE_EXTS)) + " 格式的图片。")
    return ext


def _get_engine():
    """懒加载 OCR 引擎(单例)"""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                try:
                    from rapidocr_onnxruntime import RapidOCR
                except Exception as exc:
                    raise RuntimeError(
                        f"OCR 组件加载失败: {exc}。"
                        f"若提示缺少共享库，请在系统安装 onnxruntime 运行依赖"
                        f"(Linux: libgomp1)。")
                _engine = RapidOCR()
    return _engine


def ocr_image(image_path: str) -> list:
    """
    识别图片中的文字。

    返回: [{"text": str, "box": [[x,y]*4], "score": float}, ...]
    已按阅读顺序(自上而下、自左而右)排序。
    """
    engine = _get_engine()
    result = engine(image_path)

    lines = []
    if result is None:
        return lines

    # RapidOCR 返回结构: 可能是 (识别列表, 额外信息) 元组或直接是识别列表
    # 识别列表: 每项为 [box, text, score]; box: [[x,y] x4] 四点坐标
    if isinstance(result, tuple):
        result = result[0] if result else []
    if not isinstance(result, (list, tuple)):
        return lines

    for item in result:
        try:
            box = item[0]
            text = str(item[1] or "").strip()
            score = float(item[2]) if len(item) > 2 else 0.0
        except (IndexError, TypeError, ValueError):
            continue
        if not text:
            continue
        lines.append({"text": text, "box": box, "score": score})

    return _sort_reading_order(lines)


def _sort_reading_order(lines: list) -> list:
    """按阅读顺序排序: 先按行(y 中心)分组, 行内按 x 排序"""
    if not lines:
        return []

    def box_center(ln):
        pts = ln["box"]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (sum(xs) / len(xs), sum(ys) / len(ys))

    # 计算每行中心点
    for ln in lines:
        cx, cy = box_center(ln)
        ln["_cx"], ln["_cy"] = cx, cy

    # 按 y 中心排序
    ordered = sorted(lines, key=lambda ln: ln["_cy"])

    # 聚合成行: 相邻 y 差值小于阈值(按行高约 1.5 倍估)视为同一行
    rows = []
    cur_row = []
    last_y = None
    for ln in ordered:
        if last_y is None or abs(ln["_cy"] - last_y) <= 15:
            cur_row.append(ln)
            last_y = ln["_cy"]
        else:
            rows.append(cur_row)
            cur_row = [ln]
            last_y = ln["_cy"]
    if cur_row:
        rows.append(cur_row)

    # 行内按 x 排序, 拼成最终顺序
    result = []
    for row in rows:
        row.sort(key=lambda ln: ln["_cx"])
        result.extend(row)
    return result


def image_to_model(image_path: str) -> DocumentModel:
    """
    图片 OCR 结果 -> DocumentModel。
    每个识别出的文本行生成一个段落块; 识别为空时返回含空提示的模型。
    """
    lines = ocr_image(image_path)
    model = DocumentModel()
    if not lines:
        model.blocks.append(TextBlock(
            "（未能从图片中识别出文字，请确认图片清晰或包含印刷文字。）",
            kind=KIND_EMPTY))
        return model
    for ln in lines:
        text = ln["text"]
        if text.strip():
            model.blocks.append(TextBlock(text, kind=KIND_PARAGRAPH))
    return model
