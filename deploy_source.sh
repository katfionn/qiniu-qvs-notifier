#!/bin/bash
# 从源码安装部署脚本

set -e

echo "======================================"
echo "七牛 QVS 通知器 v2.0 - 源码安装"
echo "======================================"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未检测到 Python 3，请先安装 Python 3.11+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "✓ Python 已安装: $PYTHON_VERSION"
echo ""

# 检查 pip
if ! command -v pip3 &> /dev/null; then
    echo "❌ 未检测到 pip3，请先安装 pip"
    exit 1
fi

echo "✓ pip 已安装"
echo ""

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo "🔧 创建虚拟环境..."
    python3 -m venv venv
    echo "✓ 虚拟环境已创建"
    echo ""
fi

# 激活虚拟环境
echo "🔧 激活虚拟环境..."
source venv/bin/activate
echo "✓ 虚拟环境已激活"
echo ""

# 安装依赖
echo "📦 安装依赖..."
pip install -r requirements.txt -q
echo "✓ 依赖安装完成"
echo ""

# 检查是否首次运行
if [ ! -f "data/data.db" ]; then
    echo "🔧 首次运行，启动安装向导..."
    echo ""
    python -m qvs_notifier installer
    echo ""
fi

# 启动 Web 服务
echo "======================================"
echo "部署完成！"
echo "======================================"
echo ""
echo "📍 启动命令: python run_web_v2.py"
echo "📍 或使用 TUI: python -m qvs_notifier tui"
echo ""
echo "💡 使用以下命令启动 Web 服务:"
echo ""
echo "   source venv/bin/activate"
echo "   python run_web_v2.py"
echo ""
