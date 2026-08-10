# -*- coding: utf-8 -*-
"""
providers.py — 翻译引擎提供商
统一在线翻译接口: translate(text, source, target) -> str

支持提供商:
- MyMemory : 免费公共 API, 无需 Key (默认)
- DeepL    : 需要 API Key, 支持免费版
- 百度翻译  : 需要 APP_ID + 密钥
- 腾讯云TMT : 需要 SecretId + SecretKey
- OpenAI   : 兼容接口(可接 DeepSeek/通义等), 质量最高

未配置 Key 的提供商自动回退 MyMemory。
Key 可配置于 config.py, 或通过 Web 界面「设置」动态保存(settings.json)。
"""
import hashlib
import json
import os
import random
import time
import urllib.parse
import urllib.request

from config import (
    ONLINE_API_URL,
    ONLINE_TIMEOUT,
    TRANSLATOR_PROVIDER,
    DEEPL_API_KEY,
    BAIDU_APP_ID,
    BAIDU_SECRET_KEY,
    TENCENT_SECRET_ID,
    TENCENT_SECRET_KEY,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
)
from .languages import (
    MYMEMORY_LANG_MAP,
    DEEPL_LANG_MAP,
    BAIDU_LANG_MAP,
    TENCENT_LANG_MAP,
    OPENAI_LANG_MAP,
    is_supported_lang,
)

# 运行时动态配置(来自 Web 设置面板)会覆盖 config.py
_RUNTIME_SETTINGS = {}


def apply_settings(settings: dict):
    """应用 Web 设置面板保存的运行时配置(覆盖 config 常量)"""
    _RUNTIME_SETTINGS.update({k: v for k, v in settings.items() if v is not None})


def _get(key: str, default=""):
    """读取配置: 运行时设置优先, 其次 config.py"""
    v = _RUNTIME_SETTINGS.get(key)
    if v not in (None, ""):
        return v
    return default


# ---------------------------------------------------------------
# 基类与各提供商
# ---------------------------------------------------------------
class BaseProvider:
    name = "base"
    display_name = "基础引擎"

    def translate(self, text: str, source: str, target: str) -> str:
        raise NotImplementedError


class MyMemoryProvider(BaseProvider):
    """MyMemory 免费公共 API(无需 Key), 支持 10 种语言与汉语互译"""
    name = "mymemory"
    display_name = "MyMemory (免费)"

    def translate(self, text, source, target):
        src = MYMEMORY_LANG_MAP.get(source, source)
        tgt = MYMEMORY_LANG_MAP.get(target, target)
        langpair = f"{src}|{tgt}"
        url = ONLINE_API_URL.format(
            q=urllib.parse.quote(text), langpair=urllib.parse.quote(langpair))
        req = urllib.request.Request(url, headers={"User-Agent": "MultiTranslator/2.0"})
        with urllib.request.urlopen(req, timeout=ONLINE_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        translated = payload.get("responseData", {}).get("translatedText")
        status = payload.get("responseStatus")
        if not translated or status not in (200, None):
            raise RuntimeError(f"MyMemory 返回错误: status={status}")
        if translated.startswith("MYMEMORY WARNING"):
            raise RuntimeError("MyMemory 免费额度已用尽，请稍后再试或配置自有 API Key。")
        return translated


class DeepLProvider(BaseProvider):
    """DeepL API(需 Key, 支持免费版), 支持 10 种语言"""
    name = "deepl"
    display_name = "DeepL (需 Key)"

    def translate(self, text, source, target):
        api_key = _get("deepl_api_key", DEEPL_API_KEY)
        if not api_key:
            raise RuntimeError("未配置 DeepL API Key")
        host = "https://api-free.deepl.com/v2/translate"
        form = urllib.parse.urlencode({
            "text": text,
            "source_lang": DEEPL_LANG_MAP.get(source, source.upper()),
            "target_lang": DEEPL_LANG_MAP.get(target, target.upper()),
        }).encode()
        req = urllib.request.Request(
            host, data=form,
            headers={"Authorization": f"DeepL-Auth-Key {api_key}",
                     "Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=ONLINE_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        try:
            return payload["translations"][0]["text"]
        except (KeyError, IndexError):
            raise RuntimeError("DeepL 返回格式异常")


class BaiduProvider(BaseProvider):
    """百度翻译开放平台(需 APP_ID + 密钥), 支持 10 种语言"""
    name = "baidu"
    display_name = "百度翻译 (需 Key)"

    def translate(self, text, source, target):
        appid = _get("baidu_app_id", BAIDU_APP_ID)
        secret = _get("baidu_secret_key", BAIDU_SECRET_KEY)
        if not appid or not secret:
            raise RuntimeError("未配置百度翻译 APP_ID / 密钥")
        salt = str(random.randint(32768, 65536))
        sign = hashlib.md5((appid + text + salt + secret).encode()).hexdigest()
        params = urllib.parse.urlencode({
            "q": text,
            "from": BAIDU_LANG_MAP.get(source, source),
            "to": BAIDU_LANG_MAP.get(target, target),
            "appid": appid, "salt": salt, "sign": sign,
        })
        url = "https://fanyi-api.baidu.com/api/trans/vip/translate?" + params
        with urllib.request.urlopen(url, timeout=ONLINE_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if "error_code" in payload:
            raise RuntimeError(f"百度翻译错误: {payload.get('error_code')} "
                               f"{payload.get('error_msg', '')}")
        try:
            return "".join(item["dst"] for item in payload["trans_result"])
        except (KeyError, TypeError):
            raise RuntimeError("百度翻译返回格式异常")


class TencentProvider(BaseProvider):
    """腾讯云机器翻译 TMT(需 SecretId + SecretKey), 支持 10 种语言"""
    name = "tencent"
    display_name = "腾讯云TMT (需 Key)"

    def translate(self, text, source, target):
        secret_id = _get("tencent_secret_id", TENCENT_SECRET_ID)
        secret_key = _get("tencent_secret_key", TENCENT_SECRET_KEY)
        if not secret_id or not secret_key:
            raise RuntimeError("未配置腾讯云 SecretId / SecretKey")

        endpoint = "tmt.tencentcloudapi.com"
        service = "tmt"
        host = f"{endpoint}"
        region = "ap-guangzhou"
        action = "TextTranslate"
        version = "2018-03-21"
        algorithm = "TC3-HMAC-SHA256"

        timestamp = int(time.time())
        date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))
        payload = json.dumps({
            "SourceText": text,
            "Source": TENCENT_LANG_MAP.get(source, source),
            "Target": TENCENT_LANG_MAP.get(target, target),
            "ProjectId": 0,
        })
        # 1. 拼接规范请求串
        ct = "application/json; charset=utf-8"
        canonical_headers = (f"content-type:{ct}\nhost:{host}\nx-tc-action:{action.lower()}\n")
        signed_headers = "content-type;host;x-tc-action"
        hashed_payload = hashlib.sha256(payload.encode()).hexdigest()
        canonical_request = "\n".join([
            "POST", "/", "", canonical_headers, signed_headers, hashed_payload])
        # 2. 拼接待签名字符串
        credential_scope = f"{date}/{service}/tc3_request"
        hashed_canonical = hashlib.sha256(canonical_request.encode()).hexdigest()
        string_to_sign = "\n".join([
            algorithm, str(timestamp), credential_scope, hashed_canonical])
        # 3. 计算签名 (TC3-HMAC-SHA256)
        import hmac

        def _hmac_bytes(key, msg):
            return hmac.new(key, msg.encode(), hashlib.sha256).digest()

        def _hmac_hex(key, msg):
            return hmac.new(key, msg.encode(), hashlib.sha256).hexdigest()

        secret_date = _hmac_bytes(("TC3" + secret_key).encode(), date)
        secret_service = _hmac_bytes(secret_date, service)
        secret_signing = _hmac_bytes(secret_service, "tc3_request")
        signature = _hmac_hex(secret_signing, string_to_sign)
        # 4. 组装 Authorization
        authorization = (f"{algorithm} Credential={secret_id}/{credential_scope}, "
                         f"SignedHeaders={signed_headers}, Signature={signature}")
        headers = {
            "Authorization": authorization,
            "Content-Type": ct,
            "Host": host,
            "X-TC-Action": action,
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Version": version,
            "X-TC-Region": region,
        }
        req = urllib.request.Request(
            f"https://{host}/", data=payload.encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=ONLINE_TIMEOUT) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        if "Response" in result and "Error" in result["Response"]:
            err = result["Response"]["Error"]
            raise RuntimeError(f"腾讯云错误: {err.get('Code')} {err.get('Message', '')}")
        return result["Response"]["TargetText"]


class OpenAIProvider(BaseProvider):
    """OpenAI 兼容接口(质量最高), 支持 10 种语言"""
    name = "openai"
    display_name = "OpenAI 兼容 (需 Key)"

    def translate(self, text, source, target):
        api_key = _get("openai_api_key", OPENAI_API_KEY)
        if not api_key:
            raise RuntimeError("未配置 OpenAI API Key")
        base = _get("openai_base_url", OPENAI_BASE_URL)
        model = _get("openai_model", OPENAI_MODEL)

        src_name = OPENAI_LANG_MAP.get(source, source)
        tgt_name = OPENAI_LANG_MAP.get(target, target)

        body = json.dumps({
            "model": model,
            "messages": [
                {"role": "system",
                 "content": f"You are a professional translator. Translate the user's "
                            f"text from {src_name} to {tgt_name}. Output only the "
                            f"translated text, no explanations."},
                {"role": "user", "content": text},
            ],
            "temperature": 0.3,
        }).encode()
        req = urllib.request.Request(
            base.rstrip("/") + "/chat/completions", data=body,
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=ONLINE_TIMEOUT * 2) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        try:
            return payload["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError):
            raise RuntimeError("OpenAI 返回格式异常")


# ---------------------------------------------------------------
# 提供商工厂
# ---------------------------------------------------------------
_PROVIDERS = {
    "mymemory": MyMemoryProvider,
    "deepl": DeepLProvider,
    "baidu": BaiduProvider,
    "tencent": TencentProvider,
    "openai": OpenAIProvider,
}

_PROVIDER_CACHE = {}


def get_provider(name: str = None) -> BaseProvider:
    """
    获取翻译提供商实例。
    未指定 name 时用 config.TRANSLATOR_PROVIDER;
    若该提供商未配置 Key(不可用), 自动回退 MyMemory。
    """
    name = name or _get("translator_provider", TRANSLATOR_PROVIDER)
    if name not in _PROVIDERS:
        name = "mymemory"
    cls = _PROVIDERS[name]
    if name not in _PROVIDER_CACHE:
        _PROVIDER_CACHE[name] = cls()
    return _PROVIDER_CACHE[name]


def provider_ready(name: str) -> bool:
    """判断指定提供商是否已配置可用 Key(MyMemory 永远可用)"""
    if name == "mymemory":
        return True
    checks = {
        "deepl": lambda: bool(_get("deepl_api_key", DEEPL_API_KEY)),
        "baidu": lambda: bool(_get("baidu_app_id", BAIDU_APP_ID)
                               and _get("baidu_secret_key", BAIDU_SECRET_KEY)),
        "tencent": lambda: bool(_get("tencent_secret_id", TENCENT_SECRET_ID)
                                 and _get("tencent_secret_key", TENCENT_SECRET_KEY)),
        "openai": lambda: bool(_get("openai_api_key", OPENAI_API_KEY)),
    }
    return checks.get(name, lambda: False)()


def translate_online(text: str, source: str, target: str) -> str:
    """在线翻译统一入口(兼容旧调用): 使用当前配置的提供商"""
    provider = get_provider()
    return provider.translate(text, source, target)


def list_providers() -> list:
    """返回提供商列表(供设置面板展示)"""
    return [
        {"name": p.name, "display": p.display_name,
         "configured": provider_ready(p.name)}
        for p in _PROVIDERS.values()
    ]


# 加载运行时设置(若存在 settings.json)
def _load_runtime_settings():
    settings_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "settings.json")
    if os.path.exists(settings_path):
        try:
            with open(settings_path, encoding="utf-8") as f:
                apply_settings(json.load(f))
        except Exception:
            pass


_load_runtime_settings()
