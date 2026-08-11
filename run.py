#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run.py — 翻译 Agent 启动入口

用法:
    python run.py            # 启动 Web 服务(默认 http://localhost:5000)
    python run.py --port 8080
    python run.py --no-online # 关闭在线增强, 仅用本地词典

也可以直接作为库调用:
    from translator.core.engine import translate
    print(translate("Hello world", source="auto", target="auto")["translation"])
"""
import argparse

from flask import Flask

from config import DEBUG, HOST, PORT, ONLINE_TRANSLATE_ENABLED
from translator.web import web_bp


def create_app() -> Flask:
    """Flask 应用工厂"""
    # static_folder=None: 静态资源统一由 web_bp 提供, 避免路由冲突
    app = Flask(__name__, static_folder=None)
    app.register_blueprint(web_bp)
    return app


def main():
    parser = argparse.ArgumentParser(description="翻译 Agent")
    parser.add_argument("--host", default=HOST, help="绑定地址")
    parser.add_argument("--port", type=int, default=PORT, help="端口")
    parser.add_argument("--no-online", action="store_true",
                        help="关闭在线翻译增强(仅使用本地词典)")
    args = parser.parse_args()

    app = create_app()

    if args.no_online:
        import config
        config.ONLINE_TRANSLATE_ENABLED = False
        print("[提示] 在线增强已关闭, 仅使用本地词典翻译。")

    print("=" * 52)
    print("  翻译 Agent (English Translator)")
    print(f"  在线增强: {'开启' if ONLINE_TRANSLATE_ENABLED else '关闭'}")
    print(f"  服务地址: http://{args.host}:{args.port}")
    print("=" * 52)
    app.run(host=args.host, port=args.port, debug=DEBUG)


if __name__ == "__main__":
    main()
