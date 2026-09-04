#!/bin/bash
# 七牛 QVS 通知器 v2.0 安装脚本
# 参考 1Panel 的安装流程设计

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${CYAN}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

print_banner() {
    echo ""
    echo "========================================"
    echo "  七牛 QVS 通知器 v2.0 - 安装向导"
    echo "========================================"
    echo ""
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "需要 root 权限"
        log_info "请使用: sudo bash install.sh"
        exit 1
    fi
}

check_python() {
    log_info "检查 Python 环境..."
    if ! command -v python3 &> /dev/null; then
        log_error "未找到 Python 3"
        exit 1
    fi
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    log_success "Python 版本: $PYTHON_VERSION"
}

ask_data_dir() {
    echo ""
    log_info "步骤 1/4: 配置数据存储目录"
    echo "数据目录用于存储数据库文件、日志等"
    echo "默认位置: $SCRIPT_DIR/data"
    echo ""
    read -p "请输入数据存储目录 [回车使用默认]: " DATA_DIR_INPUT
    if [ -z "$DATA_DIR_INPUT" ]; then
        DATA_DIR="$SCRIPT_DIR/data"
    else
        DATA_DIR="$DATA_DIR_INPUT"
    fi
    mkdir -p "$DATA_DIR"
    log_success "数据目录: $DATA_DIR"
}

ask_admin_account() {
    echo ""
    log_info "步骤 2/4: 创建管理员账号"
    echo ""
    while true; do
        read -p "请输入管理员用户名 [默认: admin]: " ADMIN_USER
        ADMIN_USER=${ADMIN_USER:-admin}
        if [ ${#ADMIN_USER} -lt 3 ]; then
            log_error "用户名至少需要 3 个字符"
            continue
        fi
        break
    done

    while true; do
        read -s -p "请输入管理员密码（至少 6 个字符）: " ADMIN_PASS
        echo ""
        if [ ${#ADMIN_PASS} -lt 6 ]; then
            log_error "密码至少需要 6 个字符"
            continue
        fi
        read -s -p "请再次输入密码: " ADMIN_PASS_CONFIRM
        echo ""
        if [ "$ADMIN_PASS" != "$ADMIN_PASS_CONFIRM" ]; then
            log_error "两次密码输入不一致"
            continue
        fi
        break
    done
    log_success "管理员账号: $ADMIN_USER"
}

ask_web_port() {
    echo ""
    log_info "步骤 3/4: 配置 Web 服务端口"
    echo ""
    read -p "请输入 Web 服务端口 [默认: 8000]: " WEB_PORT
    WEB_PORT=${WEB_PORT:-8000}
    log_success "Web 端口: $WEB_PORT"
}

install_dependencies() {
    echo ""
    log_info "步骤 4/4: 安装 Python 依赖"
    echo ""
    cd "$SCRIPT_DIR"
    if [ ! -d "venv" ]; then
        log_info "创建虚拟环境..."
        python3 -m venv venv
    fi
    source venv/bin/activate
    log_info "安装依赖包..."
    pip install -r requirements.txt -q
    log_success "依赖安装完成"
}

generate_config() {
    log_info "生成配置文件..."
    cat > "$SCRIPT_DIR/.env" << EOF
QVS_DATA_DIR=$DATA_DIR
JWT_SECRET_KEY=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1)
WEB_PORT=$WEB_PORT
EOF
    log_success "配置文件: $SCRIPT_DIR/.env"
}

init_database() {
    log_info "初始化数据库..."
    cd "$SCRIPT_DIR"
    source venv/bin/activate
    python3 << EOF
import os, sys
sys.path.insert(0, "$SCRIPT_DIR")
os.environ['QVS_DATA_DIR'] = "$DATA_DIR"
from web.models.database import init_databases, create_first_admin
init_databases()
create_first_admin("$ADMIN_USER", "$ADMIN_PASS")
EOF
    log_success "数据库初始化完成"
}

create_system_command() {
    log_info "创建系统命令..."
    cat > /usr/local/bin/qvs << EOF
#!/bin/bash
cd "$SCRIPT_DIR"
source venv/bin/activate
python3 "$SCRIPT_DIR/qvs" "\$@"
EOF
    chmod +x /usr/local/bin/qvs
    chmod +x "$SCRIPT_DIR/qvs"
    log_success "系统命令: qvs"
}

create_systemd_service() {
    echo ""
    read -p "是否创建 systemd 服务（开机自启动）？(y/N): " create_service
    if [[ "$create_service" =~ ^[Yy]$ ]]; then
        log_info "创建 systemd 服务..."
        cat > /etc/systemd/system/qvs-notifier.service << EOF
[Unit]
Description=Qiniu QVS Notifier v2.0
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$SCRIPT_DIR
Environment="QVS_DATA_DIR=$DATA_DIR"
ExecStart=$SCRIPT_DIR/venv/bin/python $SCRIPT_DIR/run_web_v2.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF
        systemctl daemon-reload
        systemctl enable qvs-notifier
        log_success "systemd 服务已创建"
        read -p "是否立即启动服务？(y/N): " start_now
        if [[ "$start_now" =~ ^[Yy]$ ]]; then
            systemctl start qvs-notifier
            log_success "服务已启动"
        fi
    fi
}

print_completion() {
    echo ""
    echo "========================================"
    log_success "安装完成！"
    echo "========================================"
    echo ""
    echo "📍 数据目录: $DATA_DIR"
    echo "📍 配置文件: $SCRIPT_DIR/.env"
    echo ""
    echo "🎯 快捷命令:"
    echo "   qvs              - 启动 TUI 管理界面"
    echo "   qvs admin        - 管理员工具"
    echo ""
    echo "🌐 Web 访问:"
    if systemctl is-active --quiet qvs-notifier 2>/dev/null; then
        echo "   http://localhost:$WEB_PORT （服务已启动）"
    else
        echo "   启动: cd $SCRIPT_DIR && source venv/bin/activate && python run_web_v2.py"
    fi
    echo ""
    echo "👤 管理员账号:"
    echo "   用户名: $ADMIN_USER"
    echo "   密码: ********"
    echo ""
}

main() {
    print_banner
    check_root
    check_python
    ask_data_dir
    ask_admin_account
    ask_web_port
    install_dependencies
    generate_config
    init_database
    create_system_command
    create_systemd_service
    print_completion
}

main
