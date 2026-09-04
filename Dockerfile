# 使用轻量级的 Python 3.11 Alpine 镜像作为基础
FROM python:3.11-alpine

# 设置工作目录
WORKDIR /app

# 设置环境变量，防止 python 生成 .pyc 文件，并启用无缓冲输出
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Shanghai

# 安装系统依赖（包括 gcc 等编译工具，用于编译 bcrypt 等包）
RUN apk add --no-cache tzdata gcc musl-dev libffi-dev

# 先拷贝 requirements.txt 利用 Docker 缓存机制加速构建
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝项目源代码
COPY qvs_notifier/ qvs_notifier/
COPY web/ web/
COPY scripts/ scripts/
COPY run_web_v2.py .

# 创建数据目录（用于 data.db 和 logs.db）
RUN mkdir -p data

# 暴露 FastAPI 的默认端口
EXPOSE 8000

# 启动 Web 服务（v2 版本，包含自动安装向导和调度器）
CMD ["python", "run_web_v2.py"]
