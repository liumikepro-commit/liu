# -*- coding: utf-8 -*-
"""
api.py — Flask Web 服务
提供:
    GET  /                         静态页面(用户界面)
    GET  /api/health               健康检查
    POST /api/translate            文本翻译接口
    POST /api/documents/translate  文档翻译接口(上传 PDF/DOCX)
    GET  /api/documents/status/<task_id>  文档翻译进度轮询
    GET  /api/documents/download/<task_id> 下载翻译结果(PDF)
    GET/PUT /api/settings          引擎/API Key/开关 设置
    GET/POST/DELETE /api/glossary  自定义术语表管理
    GET  /api/tm/stats, POST /api/tm/clear  翻译记忆管理
"""
import json
import os
import time

from flask import Blueprint, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

from ..core.engine import translate
from ..core import providers, glossary as glossary_mod, tm as tm_mod
from ..core.languages import SUPPORTED_LANGUAGES as LANG_MAP
from ..docs.parser import validate_format
from ..docs import tasks as doc_tasks

# 静态资源目录
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
TEMPLATE_DIR = os.path.join(STATIC_DIR, "templates")

web_bp = Blueprint(
    "web", __name__,
    static_folder=STATIC_DIR,
    static_url_path="/static",
    template_folder=TEMPLATE_DIR,
)

# 支持的语言(含 auto, 供前端下拉与接口校验)
SUPPORTED_LANGUAGES = {"auto": "自动检测"}
SUPPORTED_LANGUAGES.update(LANG_MAP)

# 上传限制
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB

# 运行时设置文件
SETTINGS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "settings.json",
)


@web_bp.route("/")
def index():
    """用户界面主页"""
    return render_template("index.html")


@web_bp.route("/api/health")
def health():
    """健康检查(便于容器/监控探活)"""
    return jsonify({"status": "ok", "service": "multi-translator"})


@web_bp.route("/api/languages")
def api_languages():
    """返回支持的语言列表(供前端下拉渲染)"""
    langs = [{"code": k, "name": v} for k, v in SUPPORTED_LANGUAGES.items()]
    return jsonify({"languages": langs})


@web_bp.route("/api/translate", methods=["POST"])
def api_translate():
    """
    文本翻译接口。
    请求体(JSON):
        {"text": "...", "source": "auto|en|zh", "target": "auto|en|zh", "use_online": true}
    响应:
        {"translation": "...", "source": "...", "target": "...",
         "engine": "...", "coverage": 0.95, "uncovered": [...],
         "error": null, "warning": null}
    """
    try:
        payload = request.get_json(silent=True) or {}
    except Exception:
        return jsonify({"error": "请求体不是合法的 JSON。"}), 400

    text = payload.get("text", "")
    source = payload.get("source", "auto")
    target = payload.get("target", "auto")
    use_online = payload.get("use_online")

    # 参数合法性校验
    if source not in SUPPORTED_LANGUAGES:
        return jsonify({"error": f"不支持的 source: {source}"}), 400
    if target not in SUPPORTED_LANGUAGES:
        return jsonify({"error": f"不支持的 target: {target}"}), 400

    result = translate(text, source=source, target=target, use_online=use_online)
    if result.get("error"):
        return jsonify(result), 400
    return jsonify(result)


# ================================================================
# 文档翻译接口
# ================================================================
@web_bp.route("/api/documents/translate", methods=["POST"])
def api_document_translate():
    """
    文档翻译接口(multipart/form-data):
        file:        PDF 或 DOCX 文件
        source:      auto|en|zh
        target:      auto|en|zh
        use_online:  true|false
    响应: {"task_id": "...", "message": "任务已创建"}
    """
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "未收到文件，请选择要翻译的文档。"}), 400

    filename = uploaded.filename
    # 格式校验(不支持/损坏格式给出清晰中文提示)
    try:
        validate_format(filename)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # 大小校验
    uploaded.stream.seek(0, os.SEEK_END)
    size = uploaded.stream.tell()
    uploaded.stream.seek(0)
    if size > MAX_UPLOAD_SIZE:
        return jsonify({"error": f"文件过大（{size // 1024 // 1024}MB），"
                                 f"单文件请控制在 {MAX_UPLOAD_SIZE // 1024 // 1024}MB 以内。"}), 400

    source = request.form.get("source", "auto")
    target = request.form.get("target", "auto")
    use_online = request.form.get("use_online", "true").lower() == "true"

    if source not in SUPPORTED_LANGUAGES:
        return jsonify({"error": f"不支持的 source: {source}"}), 400
    if target not in SUPPORTED_LANGUAGES:
        return jsonify({"error": f"不支持的 target: {target}"}), 400

    # 保存上传文件到临时区
    os.makedirs(doc_tasks.UPLOAD_DIR, exist_ok=True)
    safe_name = secure_filename(filename) or "document"
    save_path = os.path.join(
        doc_tasks.UPLOAD_DIR,
        f"src_{int(time.time())}_{safe_name}",
    )
    uploaded.save(save_path)

    task_id = doc_tasks.create_task(
        filename=filename,
        file_path=save_path,
        source=source,
        target=target,
        use_online=use_online,
    )
    return jsonify({"task_id": task_id, "message": "任务已创建"})


@web_bp.route("/api/documents/status/<task_id>")
def api_document_status(task_id):
    """文档翻译进度查询(前端轮询)"""
    task = doc_tasks.get_task(task_id)
    if not task:
        return jsonify({"error": f"任务不存在或已过期: {task_id}"}), 404
    return jsonify(task)


@web_bp.route("/api/documents/download/<task_id>")
def api_document_download(task_id):
    """下载翻译结果文件(PDF)"""
    task = doc_tasks.get_task(task_id)
    if not task:
        return jsonify({"error": "任务不存在。"}), 404
    if task["status"] != "done":
        return jsonify({"error": f"任务尚未完成（当前状态: {task['status']}）。"}), 400

    # 仅支持导出 PDF
    path = task["files"].get("pdf")
    if not path or not os.path.exists(path):
        return jsonify({"error": "翻译结果文件不存在，请重新翻译。"}), 404

    base = os.path.splitext(task["source_name"])[0] or "translated"
    download_name = f"{base}_translated.pdf"
    return send_file(
        path, as_attachment=True,
        download_name=download_name,
    )



# ================================================================
# 设置 / 术语表 / 翻译记忆 接口
# ================================================================
def _load_settings_file() -> dict:
    """读取运行时设置文件"""
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_settings_file(settings: dict):
    """持久化运行时设置"""
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def _apply_settings_runtime(settings: dict):
    """应用设置到运行中的各模块"""
    providers.apply_settings(settings)
    if "tm_enabled" in settings:
        tm_mod.set_enabled(bool(settings["tm_enabled"]))
    if "glossary_enabled" in settings:
        glossary_mod.set_enabled(bool(settings["glossary_enabled"]))


@web_bp.route("/api/settings", methods=["GET"])
def api_get_settings():
    """读取当前设置(Key 只返回是否已配置, 不回显明文)"""
    settings = _load_settings_file()
    providers_list = providers.list_providers()
    current = settings.get("translator_provider", "google")

    def mask(name):
        return bool(settings.get(name, ""))

    return jsonify({
        "translator_provider": current,
        "providers": providers_list,
        "deepl_configured": mask("deepl_api_key"),
        "baidu_configured": mask("baidu_app_id") and mask("baidu_secret_key"),
        "tencent_configured": mask("tencent_secret_id") and mask("tencent_secret_key"),
        "openai_configured": mask("openai_api_key"),
        "tm_enabled": tm_mod.is_enabled(),
        "glossary_enabled": glossary_mod.is_enabled(),
        "tm_stats": tm_mod.stats(),
        "glossary": glossary_mod.get_terms(),
    })


@web_bp.route("/api/settings", methods=["PUT"])
def api_put_settings():
    """保存设置(API Key 等)"""
    try:
        payload = request.get_json(silent=True) or {}
    except Exception:
        return jsonify({"error": "请求体不是合法的 JSON。"}), 400

    allowed = {
        "translator_provider", "deepl_api_key", "baidu_app_id",
        "baidu_secret_key", "tencent_secret_id", "tencent_secret_key",
        "openai_api_key", "openai_base_url", "openai_model",
        "tm_enabled", "glossary_enabled",
    }
    settings = _load_settings_file()
    for key, value in payload.items():
        if key in allowed and value is not None:
            settings[key] = value

    if settings.get("translator_provider") not in (
            "google", "mymemory", "deepl", "baidu", "tencent", "openai"):
        return jsonify({"error": "不支持的翻译引擎。"}), 400

    _save_settings_file(settings)
    _apply_settings_runtime(settings)
    return jsonify({"ok": True, "message": "设置已保存"})


@web_bp.route("/api/glossary", methods=["POST"])
def api_add_glossary():
    """新增/更新术语: {lang: 语言代码, term: 原文, target: 指定译文}"""
    payload = request.get_json(silent=True) or {}
    lang = payload.get("lang", "en")
    term = (payload.get("term") or "").strip()
    target = (payload.get("target") or "").strip()
    if lang not in LANG_MAP:
        return jsonify({"error": f"不支持的语言: {lang}"}), 400
    if not term or not target:
        return jsonify({"error": "术语与译文不能为空。"}), 400
    glossary_mod.add_term(lang, term, target)
    return jsonify({"ok": True, "message": f"术语「{term}」已添加",
                    "glossary": glossary_mod.get_terms()})


@web_bp.route("/api/glossary", methods=["DELETE"])
def api_delete_glossary():
    """删除术语: ?lang=en&term=KPI"""
    lang = request.args.get("lang", "en")
    term = request.args.get("term", "")
    if lang not in LANG_MAP:
        return jsonify({"error": f"不支持的语言: {lang}"}), 400
    glossary_mod.remove_term(lang, term)
    return jsonify({"ok": True, "glossary": glossary_mod.get_terms()})


@web_bp.route("/api/tm/stats")
def api_tm_stats():
    """翻译记忆统计"""
    return jsonify(tm_mod.stats())


@web_bp.route("/api/tm/clear", methods=["POST"])
def api_tm_clear():
    """清空翻译记忆"""
    tm_mod.clear()
    return jsonify({"ok": True, "message": "翻译记忆已清空",
                    "stats": tm_mod.stats()})
