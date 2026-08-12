# -*- coding: utf-8 -*-
"""
image_edit.py — 图片就地翻译(在原图文字位置覆盖译文)
将 OCR 识别出的文字区域用白色遮盖, 在原位置绘制译文,
输出与原图相同格式的图片(漫画汉化式效果)。

依赖: Pillow(随 rapidocr_onnxruntime 一并安装)
"""
import os

# 中文字体候选(Windows / Linux)
_CJK_FONT_PATHS = [
    "C:/Windows/Fonts/msyh.ttc",        # 微软雅黑
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",      # 黑体
    "C:/Windows/Fonts/simsun.ttc",      # 宋体
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
]


def find_cjk_font() -> str:
    """查找可用的中文字体文件; 找不到返回空串"""
    for p in _CJK_FONT_PATHS:
        if os.path.exists(p):
            return p
    return ""


def _wrap_text(text: str, font, max_width, draw) -> list:
    """按像素宽度将文本换行"""
    lines, cur = [], ""
    for ch in text:
        test = cur + ch
        if draw.textlength(test, font=font) <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def _extract_bg_color(img, x0, y0, x1, y1) -> tuple:
    """
    提取文字框周围一圈像素的平均颜色, 作为替换区域的背景色。
    这样译文背景与原图背景融合, 看起来像原文字被擦除、露出原图背景。
    """
    ring_w = max(2, (y1 - y0) // 6)
    w, h = img.width, img.height
    samples = []

    def _sample(x, y):
        if 0 <= x < w and 0 <= y < h:
            px = img.getpixel((x, y))
            if isinstance(px, tuple) and len(px) >= 3:
                samples.append(px[:3])

    # 上/下/左/右四条带(步长采样控制开销)
    step = max(1, ring_w // 2)
    for x in range(x0, x1 + 1, step):
        for yy in range(y0 - ring_w, y0):
            _sample(x, yy)
        for yy in range(y1 + 1, y1 + ring_w + 1):
            _sample(x, yy)
    for y in range(y0, y1 + 1, step):
        for xx in range(x0 - ring_w, x0):
            _sample(xx, y)
        for xx in range(x1 + 1, x1 + ring_w + 1):
            _sample(xx, y)

    if not samples:
        return (255, 255, 255)
    n = len(samples)
    return (sum(s[0] for s in samples) // n,
            sum(s[1] for s in samples) // n,
            sum(s[2] for s in samples) // n)


def _extract_text_color(img, x0, y0, x1, y1, bg_color) -> tuple:
    """
    从文字框内像素提取文字笔画颜色(与背景差异最大的像素群的平均色)。
    需在遮盖原文字之前调用, 用于让译文颜色与原文字保持一致。
    """
    bg_r, bg_g, bg_b = bg_color
    diffs = []
    for y in range(y0, y1 + 1, 2):
        for x in range(x0, x1 + 1, 2):
            px = img.getpixel((x, y))
            if not isinstance(px, tuple) or len(px) < 3:
                continue
            r, g, b = px[0], px[1], px[2]
            dist = abs(r - bg_r) + abs(g - bg_g) + abs(b - bg_b)
            diffs.append((dist, (r, g, b)))
    if not diffs:
        return (0, 0, 0)
    # 取差异最大的前 10%(笔画像素), 取平均抗噪声
    diffs.sort(key=lambda d: d[0], reverse=True)
    top = diffs[:max(1, len(diffs) // 10)]
    n = len(top)
    return (sum(p[1][0] for p in top) // n,
            sum(p[1][1] for p in top) // n,
            sum(p[1][2] for p in top) // n)


def overlay_translation(image_path: str, src_lines: list,
                        translated_lines: list, out_path: str):
    """
    在原图文字位置覆盖译文, 输出图片。

    参数:
        image_path:       原图路径
        src_lines:        OCR 结果行列表 [{"box": [[x,y]x4], "text": ...}, ...]
        translated_lines: 与 src_lines 一一对应的译文文本列表
        out_path:         输出图片路径(扩展名决定格式, 与原图同格式)
    """
    from PIL import Image, ImageDraw, ImageFont

    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    font_path = find_cjk_font()

    for line, trans in zip(src_lines, translated_lines):
        text = (trans or "").strip()
        if not text:
            continue
        box = line.get("box")
        if not box or len(box) < 4:
            continue

        # 文字区域轴对齐包围盒(留少量边距)
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        pad = 3
        x0, y0 = max(0, int(min(xs)) - pad), max(0, int(min(ys)) - pad)
        x1, y1 = int(max(xs)) + pad, int(max(ys)) + pad
        # 防止超出图片边界
        x1 = min(x1, img.width - 1)
        y1 = min(y1, img.height - 1)
        if x1 <= x0 or y1 <= y0:
            continue

        # 用周围原图背景色填充替换区域(替代白色), 使译文融入原图背景
        bg_color = _extract_bg_color(img, x0, y0, x1, y1)
        # 提取原文字笔画颜色(须在遮盖前), 译文沿用同一颜色
        text_color = _extract_text_color(img, x0, y0, x1, y1, bg_color)
        draw.rectangle([x0, y0, x1, y1], fill=bg_color)

        # 译文字号: 适配框高(约 0.8 倍行高), 最小 8pt
        box_h = y1 - y0
        box_w = x1 - x0
        font_size = max(8, int(box_h * 0.8))

        # 找不到中文字体时用默认字体(中文可能显示为方块)
        if font_path:
            font = ImageFont.truetype(font_path, font_size)
        else:
            font = ImageFont.load_default()

        # 文本换行适配框宽
        lines_txt = _wrap_text(text, font, box_w, draw)
        line_h = font_size + 2

        # 垂直居中, 逐行绘制(颜色与原文字一致)
        total_h = len(lines_txt) * line_h
        y = y0 + max(0, (box_h - total_h) // 2)
        for lt in lines_txt:
            tw = draw.textlength(lt, font=font)
            x = x0 + max(0, (box_w - tw) // 2)
            draw.text((x, y), lt, fill=text_color, font=font)
            y += line_h

    # 保存(保持原格式; JPG 需转 RGB, 已在上方 convert)
    img.save(out_path)
    return out_path
