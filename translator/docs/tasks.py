# -*- coding: utf-8 -*-
"""
tasks.py — 文档翻译后台任务管理
上传的文档在后台线程中执行: 解析 -> 翻译 -> 导出(docx/pdf),
前端通过 task_id 轮询进度, 完成后下载结果。

任务状态机: pending -> running -> done | error
任务表保存在内存(单机场景); 服务重启后任务丢失, 输出文件保留在磁盘。
"""
import copy
import os
import threading
import time
import uuid

from .parser import parse_document
from .pipeline import translate_document
from .renderer import export_document, render_pdf_bilingual
from .block import DocumentModel, TextBlock, KIND_PARAGRAPH
from . import ocr as ocr_mod
from . import image_edit

# 输出目录: 项目根/uploads
UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "uploads",
)

_TASKS = {}              # task_id -> task dict
_TASKS_LOCK = threading.Lock()


def _new_task_id() -> str:
    return uuid.uuid4().hex[:12]


def create_task(filename: str, file_path: str, source: str,
                target: str, use_online: bool, bilingual: bool = False,
                kind: str = "document", output: str = "pdf") -> str:
    """创建任务并启动后台线程, 返回 task_id; kind: document | image; output: pdf | image"""
    task_id = _new_task_id()
    task = {
        "id": task_id,
        "status": "pending",        # pending|running|done|error
        "progress": 0, "total": 0, "current": "",
        "message": "任务已创建", "error": None,
        "source_name": filename,
        "bilingual": bilingual,     # 是否导出双语对照
        "kind": kind,               # document | image
        "output": output,           # pdf | image(仅图片任务有效, 原位替换)
        "files": {"docx": None, "pdf": None, "image": None},
        "created_at": time.time(), "updated_at": time.time(),
    }
    with _TASKS_LOCK:
        _TASKS[task_id] = task

    thread = threading.Thread(
        target=_run_task,
        args=(task_id, filename, file_path, source, target,
              use_online, bilingual, kind, output),
        daemon=True,
    )
    thread.start()
    return task_id


def get_task(task_id: str):
    """读取任务快照"""
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
        return dict(task) if task else None


def _update(task_id: str, **kwargs):
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
        if task:
            task.update(kwargs)
            task["updated_at"] = time.time()


def _run_task(task_id, filename, file_path, source, target, use_online,
              bilingual, kind, output):
    """后台执行: 解析(文档/图片OCR) -> 翻译 -> 导出(pdf/图片原位替换)"""
    try:
        # ---- 1. 解析 ----
        ocr_lines = None
        if kind == "image":
            _update(task_id, status="running", message="正在识别图片文字(OCR)…")
            ocr_lines = ocr_mod.ocr_image(file_path)
            model = DocumentModel()
            for ln in ocr_lines:
                if ln["text"].strip():
                    model.blocks.append(
                        TextBlock(ln["text"], kind=KIND_PARAGRAPH))
        else:
            _update(task_id, status="running", message="正在解析文档…")
            model = parse_document(filename, file_path)

        # 双语对照: 翻译前深拷贝保留原文模型(原译文导出行为不受影响)
        src_model = copy.deepcopy(model) if bilingual else None

        # ---- 2. 翻译 ----
        blocks = list(model.iter_blocks())
        total = len(blocks)
        if total == 0:
            raise ValueError("未能提取到可翻译的文本内容。")

        def on_progress(done, total_n, block_text):
            pct = int(done / total_n * 100) if total_n else 0
            _update(task_id, progress=pct, total=total_n,
                    current=block_text,
                    message=f"正在翻译… {done}/{total_n} 块 ({pct}%)")

        _update(task_id, message="正在翻译…")
        translate_document(model, source=source, target=target,
                           use_online=use_online, progress_cb=on_progress)

        # ---- 3. 导出 ----
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        base = os.path.join(UPLOAD_DIR, task_id)
        results = {}

        # 图片任务 + 原位替换: 在原图文字位置覆盖译文, 输出同格式图片
        if kind == "image" and output == "image":
            _update(task_id, message="正在生成译文图片…")
            ext = os.path.splitext(filename or "")[1].lower() or ".png"
            out_path = f"{base}{ext}"
            translated_lines = [b.text or "" for b in model.blocks]
            image_edit.overlay_translation(
                file_path, ocr_lines or [], translated_lines, out_path)
            results["image"] = out_path
        else:
            # 默认: 导出 PDF (仅支持 PDF 下载)
            _update(task_id, message="正在生成 PDF 文件…")
            out_path = f"{base}.pdf"
            if bilingual:
                render_pdf_bilingual(src_model, model, out_path)
            else:
                export_document(model, "pdf", out_path)
            results["pdf"] = out_path

        _update(task_id, status="done", progress=100,
                message="翻译完成", files=results)

    except Exception as e:
        _update(task_id, status="error",
                message="处理失败",
                error=str(e) or e.__class__.__name__)
