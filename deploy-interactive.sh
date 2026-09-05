#!/bin/bash
# 交互式部署脚本 - 会提示输入密码

set -e

echo "=== 开始部署 QVS Notifier UI 优化 ==="
echo ""
echo "服务器信息:"
echo "  主机: claw.fe2fe.top"
echo "  用户: claudetest"
echo "  密码: ABC1986720abc"
echo ""

# 连接服务器并更新
echo "正在连接服务器..."
ssh claudetest@claw.fe2fe.top << 'ENDSSH'
set -e

echo "  ✓ 已连接到服务器"
echo "  - 进入项目目录..."
cd ~/qiniu-qvs-notifier-test

echo "  - 拉取最新代码..."
git pull origin main || git pull

echo "  - 停止旧进程..."
pkill -9 -f "python.*run_web_v2.py" 2>/dev/null || echo "    没有运行中的进程"
sleep 2

echo "  - 启动新服务..."
nohup ~/qiniu-qvs-notifier-test/venv/bin/python run_web_v2.py > ~/qvs-test.log 2>&1 &

sleep 3
echo "  - 检查服务状态..."
if pgrep -f "python.*run_web_v2.py" > /dev/null; then
    echo "  ✓ 服务启动成功！"
    echo "  - 进程 PID: $(pgrep -f 'python.*run_web_v2.py')"
else
    echo "  ✗ 服务启动失败，查看日志:"
    tail -20 ~/qvs-test.log
    exit 1
fi

ENDSSH

echo ""
echo "=== 部署完成！==="
echo ""
echo "现在请："
echo "1. 访问 http://claw.fe2fe.top:10000"
echo "2. 按 Ctrl+Shift+R 强制刷新浏览器"
echo ""
