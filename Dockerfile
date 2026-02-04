# WeChat-Archiver Docker 镜像
# 用于一键部署微信公众号文章自动归档系统

FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY main.py .
COPY web_manager.py .
COPY run.sh .
COPY update_crontab.sh .

# 设置脚本权限
RUN chmod +x run.sh update_crontab.sh

# 创建必要的目录
RUN mkdir -p data logs

# 暴露端口
EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/groups || exit 1

# 启动命令（同时启动 Web 管理界面和 Crontab）
CMD python web_manager.py
