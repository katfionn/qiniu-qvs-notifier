#!/bin/bash
# 快速部署脚本 - 七牛 QVS 通知器 v2.0

set -e

echo "======================================"
echo "七牛 QVS 通知器 v2.0 - 快速部署"
echo "======================================"
echo ""

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ 未检测到 Docker，请先安装 Docker"
    exit 1
fi

echo "✓ Docker 已安装"
echo ""

# 停止并删除旧容器（如果存在）
if docker ps -a | grep -q qvs-notifier; then
    echo "🔄 停止并删除旧容器..."
    docker stop qvs-notifier 2>/dev/null || true
    docker rm qvs-notifier 2>/dev/null || true
    echo "✓ 旧容器已删除"
    echo ""
fi

# 拉取最新镜像
echo "📦 拉取最新 Docker 镜像..."
docker pull ghcr.io/katfionn/qiniu-qvs-notifier:v2.0.0
echo "✓ 镜像拉取完成"
echo ""

# 创建数据目录
mkdir -p ./data
echo "✓ 数据目录已创建: ./data"
echo ""

# 启动容器
echo "🚀 启动容器..."
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  --restart always \
  --name qvs-notifier \
  ghcr.io/katfionn/qiniu-qvs-notifier:v2.0.0

echo "✓ 容器已启动"
echo ""

# 等待容器启动
echo "⏳ 等待服务启动..."
sleep 5

# 检查容器状态
if docker ps | grep -q qvs-notifier; then
    echo "✓ 容器运行正常"
    echo ""
    echo "======================================"
    echo "部署完成！"
    echo "======================================"
    echo ""
    echo "📍 访问地址: http://localhost:8000"
    echo "📍 服务器地址: http://$(hostname -I | awk '{print $1}'):8000"
    echo ""
    echo "📋 管理命令:"
    echo "  查看日志: docker logs -f qvs-notifier"
    echo "  停止服务: docker stop qvs-notifier"
    echo "  启动服务: docker start qvs-notifier"
    echo "  重启服务: docker restart qvs-notifier"
    echo "  删除容器: docker rm -f qvs-notifier"
    echo ""
    echo "💡 首次访问将自动进入安装向导，请创建管理员账号"
    echo ""
else
    echo "❌ 容器启动失败，请查看日志:"
    echo "   docker logs qvs-notifier"
    exit 1
fi
