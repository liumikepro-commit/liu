# -*- coding: utf-8 -*-
"""端到端验证双语对照导出: 解析 -> 翻译 -> render_pdf_bilingual"""
import copy
import os
import sys

# 确保项目根目录在模块搜索路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from translator.docs.parser import parse_document
from translator.docs.pipeline import translate_document
from translator.docs.renderer import render_pdf_bilingual

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'uploads', 'test_english.docx')
OUT = os.path.join(ROOT, 'uploads', '_bilingual_test.pdf')

# 1. 解析原文
model = parse_document('test_english.docx', SRC)
src_model = copy.deepcopy(model)
print('解析完成: blocks=%d tables=%d' % (len(model.blocks), len(model.tables)))

# 2. 翻译(在线)
def on_progress(done, total, text):
    if done % 5 == 0 or done == total:
        print('  翻译进度: %d/%d' % (done, total))

translate_document(model, source='en', target='zh',
                   use_online=True, progress_cb=on_progress)
print('翻译完成')

# 3. 双语对照导出
render_pdf_bilingual(src_model, model, OUT)
size = os.path.getsize(OUT)
print('双语 PDF 生成成功: %s (%d bytes)' % (OUT, size))

# 4. 验证: 原单译文导出仍可用(不破坏旧功能)
from translator.docs.renderer import export_document
OUT2 = os.path.join(ROOT, 'uploads', '_plain_test.pdf')
export_document(model, 'pdf', OUT2)
print('单译文 PDF 仍正常: %d bytes' % os.path.getsize(OUT2))
print('OK')
