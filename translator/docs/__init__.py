# -*- coding: utf-8 -*-
"""
docs — 文档导入与翻译模块
模块划分:
    block.py     结构化文本块模型(格式元数据)
    parser.py    文档解析(PDF/DOCX -> DocumentModel)
    pipeline.py  文档翻译流水线(分块翻译/专名保护/在线降级)
    renderer.py  文档重建导出(DocumentModel -> DOCX/PDF)
    tasks.py     后台任务管理(上传-翻译-导出的完整流程)
"""
