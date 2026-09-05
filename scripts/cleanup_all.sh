#!/bin/bash

# 七牛 QVS 通知器 - 完全清理脚本
# 停止并删除所有测试残留

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}================================${NC}"
echo -e "${CYAN}  QVS 通知器 - 完全清理工具${NC}"
echo -e "${CYAN}================================${NC}\n"

echo -e "${YELLOW}警告：此脚本将清理所有与 QVS 通知器相关的进程和文件${NC}\n"
echo -e "将执行以下操作："
echo "  1. 停止所有 run_web_v2.py 进程"
echo "  2. 停止所有 Python QVS 相关进程"
echo "  3. 停止并删除 systemd 服务"
echo "  4. 删除 qvs 命令"
echo "  5. 列出可能的测试目录"
echo ""

read -p "确认继续？[y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${CYAN}已取消${NC}"
    exit 0
fi

echo ""
echo -e "${CYAN}[1/5] 停止 Web 服务进程...${NC}"
# 停止所有 run_web_v2.py 进程
if pgrep -f "run_web_v2.py" > /dev/null; then
    sudo pkill -9 -f "run_web_v2.py" || true
    echo -e "${GREEN}  ✓ 已停止 run_web_v2.py 进程${NC}"
else
    echo -e "${YELLOW}  - 无运行的 run_web_v2.py 进程${NC}"
fi

echo ""
echo -e "${CYAN}[2/5] 停止其他 QVS 相关进程...${NC}"
# 停止其他可能的 QVS 进程
if pgrep -f "qvs" | grep -v $$ > /dev/null; then
    sudo pkill -9 -f "qvs_notifier" || true
    sudo pkill -9 -f "qiniu.*qvs" || true
    echo -e "${GREEN}  ✓ 已停止相关进程${NC}"
else
    echo -e "${YELLOW}  - 无其他 QVS 进程${NC}"
fi

echo ""
echo -e "${CYAN}[3/5] 清理 systemd 服务...${NC}"
# 停止并删除所有可能的 systemd 服务
for service in qvs-notifier qvs qiniu-qvs-notifier; do
    if systemctl list-units --full -all | grep -q "$service.service"; then
        echo "  停止 $service.service..."
        sudo systemctl stop "$service" 2>/dev/null || true
        sudo systemctl disable "$service" 2>/dev/null || true
        sudo rm -f "/etc/systemd/system/$service.service"
        echo -e "${GREEN}  ✓ 已删除 $service.service${NC}"
    fi
done

sudo systemctl daemon-reload 2>/dev/null || true
echo -e "${GREEN}  ✓ systemd 已重载${NC}"

echo ""
echo -e "${CYAN}[4/5] 删除命令...${NC}"
# 删除可能的命令
for cmd in qvs qvs-notifier; do
    if [ -f "/usr/local/bin/$cmd" ]; then
        sudo rm -f "/usr/local/bin/$cmd"
        echo -e "${GREEN}  ✓ 已删除 /usr/local/bin/$cmd${NC}"
    fi
done

echo ""
echo -e "${CYAN}[5/5] 检查测试目录...${NC}"
echo -e "${YELLOW}以下是可能的测试目录，请手动确认是否删除：${NC}\n"

# 查找可能的测试目录
TEST_DIRS=(
    "/tmp/qvs-test"
    "/tmp/qvs-loop-test"
    "/tmp/qvs-test-data"
    "/tmp/qvs-loop-data"
    "$HOME/qvs-test"
    "$HOME/qiniu-qvs-notifier-test"
)

FOUND_DIRS=()
for dir in "${TEST_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo -e "  ${YELLOW}[存在]${NC} $dir"
        FOUND_DIRS+=("$dir")
    fi
done

if [ ${#FOUND_DIRS[@]} -eq 0 ]; then
    echo -e "  ${GREEN}未发现测试目录${NC}"
else
    echo ""
    read -p "是否删除以上测试目录？[y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        for dir in "${FOUND_DIRS[@]}"; do
            sudo rm -rf "$dir"
            echo -e "${GREEN}  ✓ 已删除 $dir${NC}"
        done
    else
        echo -e "${CYAN}  - 已跳过删除测试目录${NC}"
    fi
fi

echo ""
echo -e "${CYAN}检查日志文件...${NC}"
# 清理临时日志
LOG_FILES=(
    "/tmp/web*.log"
    "/tmp/qvs*.log"
    "/tmp/test*.log"
    "/tmp/*qvs*.log"
)

for pattern in "${LOG_FILES[@]}"; do
    if ls $pattern 2>/dev/null | head -1 > /dev/null; then
        sudo rm -f $pattern
        echo -e "${GREEN}  ✓ 已删除日志: $pattern${NC}"
    fi
done

echo ""
echo -e "${CYAN}验证清理结果...${NC}"
echo ""

# 验证进程
if pgrep -f "run_web_v2.py\|qvs" > /dev/null; then
    echo -e "${RED}  ✗ 仍有进程在运行${NC}"
    ps aux | grep -E "run_web_v2.py|qvs" | grep -v grep
else
    echo -e "${GREEN}  ✓ 无相关进程运行${NC}"
fi

# 验证 systemd 服务
if systemctl list-units --full -all | grep -qE "qvs.*\.service"; then
    echo -e "${RED}  ✗ 仍有 systemd 服务${NC}"
    systemctl list-units --full -all | grep "qvs"
else
    echo -e "${GREEN}  ✓ 无 systemd 服务${NC}"
fi

# 验证命令
if command -v qvs &> /dev/null; then
    echo -e "${RED}  ✗ qvs 命令仍存在${NC}"
else
    echo -e "${GREEN}  ✓ qvs 命令已删除${NC}"
fi

echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}  清理完成！${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo -e "${CYAN}提示：${NC}"
echo "  1. 建议重启终端以刷新环境变量"
echo "  2. 如需删除当前项目，请手动执行："
echo "     cd .."
echo "     rm -rf qiniu-qvs-notifier"
echo ""
