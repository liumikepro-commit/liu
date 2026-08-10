# ============================================================
# Dockerfile — 多语言翻译 Agent 一键容器化部署
# 构建:  docker build -t translator .
# 运行:  docker run -d -p 5000:5000 --name translator translator
# 云平台(Railway/Fly.io/Render 等)会自动注入 PORT 环境变量
# ============================================================
FROM python:3.11-slim

WORKDIR /app

# 安装系统中文字体(供 PDF 导出渲染中文)与基本工具
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 创建上传/下载目录
RUN mkdir -p /app/uploads && chmod 777 /app/uploads

# 非 root 用户运行(安全实践)
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

# 使用 gunicorn 生产服务器, 自动读取 PORT 环境变量
CMD ["sh", "-c", "gunicorn wsgi:app --bind 0.0.0.0:${PORT:-5000} --workers 2 --timeout 120"]
