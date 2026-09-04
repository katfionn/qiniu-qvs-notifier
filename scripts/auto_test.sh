#!/bin/bash
# 完整的自动化测试脚本 - 模拟真实用户操作

set -e

LOG_FILE="/tmp/qvs-test-$(date +%Y%m%d-%H%M%S).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "开始自动化测试"
log "=========================================="

# 0. 清理环境
log "清理旧的测试环境..."
cd /tmp
rm -rf qvs-test-auto
mkdir -p qvs-test-auto
cd qvs-test-auto

# 1. 克隆仓库
log "克隆仓库..."
git clone https://github.com/Katfionn/qiniu-qvs-notifier.git 2>&1 | tee -a "$LOG_FILE"
cd qiniu-qvs-notifier

# 2. 创建自动化输入文件
log "准备安装向导输入..."
cat > /tmp/install-input.txt << EOF


8000
y
y
EOF

# 3. 运行安装脚本（自动输入）
log "运行安装脚本..."
sudo bash install.sh < /tmp/install-input.txt 2>&1 | tee -a "$LOG_FILE" || {
    log "ERROR: 安装脚本失败"
    cat "$LOG_FILE"
    exit 1
}

# 4. 检查安装结果
log "检查安装结果..."

# 检查 qvs 命令
if command -v qvs &> /dev/null; then
    log "OK: qvs 命令已安装"
else
    log "ERROR: qvs 命令未找到"
    exit 1
fi

# 检查数据库
if [ -f "/tmp/qvs-test-auto/qiniu-qvs-notifier/data/data.db" ]; then
    log "OK: 数据库已创建"
else
    log "ERROR: 数据库文件不存在"
    exit 1
fi

# 检查配置文件
if [ -f "/tmp/qvs-test-auto/qiniu-qvs-notifier/.env" ]; then
    log "OK: 配置文件已创建"
    cat /tmp/qvs-test-auto/qiniu-qvs-notifier/.env | tee -a "$LOG_FILE"
else
    log "ERROR: 配置文件不存在"
    exit 1
fi

# 5. 测试 Web 服务启动
log "测试 Web 服务启动..."
cd /tmp/qvs-test-auto/qiniu-qvs-notifier
source venv/bin/activate
timeout 10 python run_web_v2.py > /tmp/web-test.log 2>&1 &
WEB_PID=$!
sleep 5

# 检查进程
if ps -p $WEB_PID > /dev/null; then
    log "OK: Web 服务已启动 (PID: $WEB_PID)"

    # 测试 HTTP 请求
    if curl -s http://localhost:8000 > /dev/null; then
        log "OK: Web 服务响应正常"
    else
        log "ERROR: Web 服务无响应"
        cat /tmp/web-test.log | tee -a "$LOG_FILE"
    fi

    kill $WEB_PID
else
    log "ERROR: Web 服务启动失败"
    cat /tmp/web-test.log | tee -a "$LOG_FILE"
    exit 1
fi

# 6. 测试 API 接口
log "测试登录 API..."
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"admin123"}')

if echo "$LOGIN_RESPONSE" | grep -q "access_token"; then
    log "OK: 登录成功"
    echo "$LOGIN_RESPONSE" | tee -a "$LOG_FILE"
else
    log "ERROR: 登录失败"
    echo "$LOGIN_RESPONSE" | tee -a "$LOG_FILE"
    exit 1
fi

# 7. 生成测试报告
log "=========================================="
log "测试完成！"
log "=========================================="
log "完整日志: $LOG_FILE"

cat << REPORT

测试总结：
✓ 仓库克隆成功
✓ 安装脚本执行成功
✓ qvs 命令已安装
✓ 数据库已创建
✓ 配置文件已生成
✓ Web 服务可启动
✓ API 接口可访问
✓ 登录功能正常

下一步：
1. 访问 http://your-server:8000 测试 Web UI
2. 使用 qvs 命令测试 TUI
3. 创建监控任务测试完整流程

REPORT

echo "完整日志已保存到: $LOG_FILE"
