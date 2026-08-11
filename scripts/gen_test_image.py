# -*- coding: utf-8 -*-
"""生成含英文文字的测试图片, 供图片识别翻译功能测试"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'uploads', 'test_image.png')

# 白底图片
img = Image.new('RGB', (900, 420), 'white')
draw = ImageDraw.Draw(img)

# 找一个系统英文字体
font_paths = [
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/calibri.ttf",
]
font = None
for fp in font_paths:
    if os.path.exists(fp):
        font = ImageFont.truetype(fp, 28)
        break
if font is None:
    font = ImageFont.load_default()

lines = [
    ("Welcome to TechNova Corporation", 40),
    ("Our mission is to empower every organization", 90),
    ("through intelligent technology and cloud computing.", 130),
    ("In fiscal year 2025, we achieved record revenue", 170),
    ("of 12.8 billion US dollars.", 210),
    ("Contact us: support@technova.example.com", 260),
]
for text, y in lines:
    draw.text((50, y), text, fill='black', font=font)

img.save(OUT)
print('测试图片生成:', OUT, img.size)
