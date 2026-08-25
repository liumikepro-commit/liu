# -*- coding: utf-8 -*-
"""
config.py — 全局配置
部署或二次开发时, 可按需调整以下参数。
"""
import os

# ---------- 输入限制 ----------
MAX_INPUT_LEN = 100000        # 单次请求最大输入字符数(超长文本在线翻译自动分块)
MAX_SENTENCE_LEN = 500      # 单句最大长度(超长截断, 防性能问题)

# ---------- 在线翻译增强 ----------
# 默认使用 Google 翻译免费端点(无需注册/Key, 质量好, 无配额限制)。
# Google 不可达(如国内内网)时自动回退 MyMemory 免费公共 API。
# 占位符: {q}=原文URL编码, {langpair}=语言对(如 en|zh-CN)
ONLINE_TRANSLATE_ENABLED = True
ONLINE_API_URL = "https://api.mymemory.translated.net/get?q={q}&langpair={langpair}"
ONLINE_TIMEOUT = 15          # 在线请求超时(秒), 超时/失败自动回退本地翻译

# ---------- 翻译引擎提供商(自定义 API Key) ----------
# 可选: google | mymemory | deepl | baidu | tencent | openai
# google/mymemory 为免费引擎(互为备用); 其余需要配置 Key。
# 也可在 Web 界面「设置」中动态配置(保存在 translator/data/settings.json)。
TRANSLATOR_PROVIDER = "libretranslate"

DEEPL_API_KEY = ""          # DeepL: https://www.deepl.com/pro-api (支持免费版)
BAIDU_APP_ID = ""           # 百度翻译开放平台: https://fanyi-api.baidu.com
BAIDU_SECRET_KEY = ""
TENCENT_SECRET_ID = ""      # 腾讯云机器翻译 TMT: https://cloud.tencent.com/product/tmt
TENCENT_SECRET_KEY = ""
OPENAI_API_KEY = ""         # OpenAI 兼容接口(可填 DeepSeek/通义/自建网关)
OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_MODEL = "gpt-4o-mini"
LIBRETRANSLATE_URL = "https://libretranslate.com"  # LibreTranslate 实例地址，可自建
LIBRETRANSLATE_API_KEY = ""  # 公共实例可能需要免费 API Key，自建则不需要

# ---------- 翻译记忆 (Translation Memory) ----------
TM_ENABLED = True           # 重复句子自动复用历史译文(SQLite 存储)
TM_DB_PATH = ""             # 留空则使用 translator/data/tm.sqlite

# ---------- 自定义术语表 ----------
GLOSSARY_ENABLED = True     # 术语表: 强制使用指定译法
GLOSSARY_PATH = ""          # 留空则使用 translator/data/glossary.json

# ---------- Web 服务 ----------
HOST = "0.0.0.0"            # 绑定地址: 0.0.0.0 允许局域网/容器外部访问
PORT = int(os.environ.get("PORT", 5000))  # 端口(云平台通过 PORT 环境变量注入)
DEBUG = False               # 生产环境关闭调试模式
