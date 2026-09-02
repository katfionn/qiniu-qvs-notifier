# 使用轻量级的 Python 3.11 Alpine 镜像作为基础
FROM python:3.11-alpine

# 设置工作目录
WORKDIR /app

# 设置环境变量，防止 python 生成 .pyc 文件，并启用无缓冲输出
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Shanghai

# 安装系统依赖（如需编译 C 扩展，可按需添加 gcc, musl-dev 等）
RUN apk add --no-cache tzdata

# 先拷贝 requirements.txt 利用 Docker 缓存机制加速构建
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝项目源代码
COPY web/ web/
COPY run_web.py .

# 创建配置和数据的挂载目录
RUN mkdir -p config

# 暴露 FastAPI 的默认端口
EXPOSE 8000

# 启动 Web 和 监控守护进程
CMD ["python", "run_web.py", "--no-reload"]
