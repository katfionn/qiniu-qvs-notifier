#!/bin/bash
# 安装脚本 - 创建系统级别的快捷命令

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "======================================"
echo "安装七牛 QVS 通知器 v2.0"
echo "======================================"
echo ""

# 检查是否为 root
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  需要 root 权限来创建系统命令"
    echo "请使用: sudo ./install.sh"
    exit 1
fi

# 1. 创建符号链接到 /usr/local/bin
echo "📦 创建快捷命令..."
ln -sf "$SCRIPT_DIR/qvs" /usr/local/bin/qvs
chmod +x "$SCRIPT_DIR/qvs"

echo "✓ 快捷命令已创建: qvs"
echo ""

# 2. 安装 Python 依赖
echo "📦 检查 Python 环境..."
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python 3，请先安装 Python 3.11+"
    exit 1
fi

echo "✓ Python 已安装"
echo ""

# 询问是否安装依赖
read -p "是否安装 Python 依赖？(y/N): " install_deps
if [[ "$install_deps" =~ ^[Yy]$ ]]; then
    echo "📦 安装依赖..."
    cd "$SCRIPT_DIR"

    if [ -d "venv" ]; then
        echo "✓ 使用现有虚拟环境"
        source venv/bin/activate
    else
        echo "📦 创建虚拟环境..."
        python3 -m venv venv
        source venv/bin/activate
    fi

    pip install -r requirements.txt -q
    echo "✓ 依赖安装完成"
    echo ""
fi

echo "======================================"
echo "安装完成！"
echo "======================================"
echo ""
echo "📍 快捷命令："
echo "   qvs              - 启动 TUI 管理界面"
echo "   qvs admin        - 管理员工具"
echo "   qvs installer    - 运行安装向导"
echo ""
echo "💡 首次使用请运行: qvs installer"
echo ""
