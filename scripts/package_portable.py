# -*- coding: utf-8 -*-
"""
打包便携版 zip: 项目代码 + runtime(内置 Python 及全部依赖)
用法: runtime\\python.exe scripts\\package_portable.py
"""
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(os.path.dirname(ROOT), "翻译工具-便携版.zip")

# 排除规则
EXCLUDE_DIRS = {".git", "uploads", "downloads", "__pycache__",
                "runtime/Lib/site-packages/pip/_vendor"}
EXCLUDE_FILES = {"翻译工具-便携版.zip"}


def should_skip(rel: str, is_dir: bool) -> bool:
    parts = rel.replace("\\", "/").split("/")
    for ex in EXCLUDE_DIRS:
        if ex in parts:
            return True
    if not is_dir and rel in EXCLUDE_FILES:
        return True
    return False


def main():
    # zipfile 以 "w" 模式打开会直接覆盖旧文件, 无需先删除
    count = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for dirpath, dirnames, filenames in os.walk(ROOT):
            # 过滤目录(原地修改 dirnames 使 os.walk 跳过)
            keep_dirs = []
            for d in dirnames:
                rel = os.path.relpath(os.path.join(dirpath, d), ROOT)
                if not should_skip(rel, True):
                    keep_dirs.append(d)
            dirnames[:] = keep_dirs

            for fn in filenames:
                fp = os.path.join(dirpath, fn)
                rel = os.path.relpath(fp, ROOT)
                if should_skip(rel, False):
                    continue
                arcname = rel.replace("\\", "/")
                zf.write(fp, arcname)
                count += 1
    print("打包完成: %s (%d 个文件)" % (OUT, count))
    print("大小: %.1f MB" % (os.path.getsize(OUT) / 1048576))


if __name__ == "__main__":
    main()
