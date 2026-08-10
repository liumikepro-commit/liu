# -*- coding: utf-8 -*-
"""
wsgi.py — WSGI 入口(供 gunicorn / uWSGI 等生产服务器使用)

用法:
    gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
"""
from run import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
