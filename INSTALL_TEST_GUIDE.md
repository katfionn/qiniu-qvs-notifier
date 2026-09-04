# 🚀 v2.0 安装测试指南

## ✅ 完成状态

所有代码已推送到 GitHub，包括：
- ✅ 完整的交互式安装脚本（参考 1Panel 设计）
- ✅ is_first_run() 异常处理修复
- ✅ TUI 初始化检查修复
- ✅ qvs 快捷命令支持子命令
- ✅ systemd 服务支持

---

## 📦 服务器测试步骤

### 1. 克隆仓库

```bash
ssh user@your-server
git clone https://github.com/Katfionn/qiniu-qvs-notifier.git
cd qiniu-qvs-notifier
```

### 2. 运行安装脚本

```bash
sudo bash install.sh
```

### 3. 安装向导（4 个步骤）

**步骤 1/4: 配置数据存储目录**
```
请输入数据存储目录 [回车使用默认]: 
# 建议：直接回车使用默认 ./data
# 或输入：/var/lib/qvs-notifier
```

**步骤 2/4: 创建管理员账号**
```
请输入管理员用户名 [默认: admin]: admin
请输入管理员密码（至少 6 个字符）: ******
请再次输入密码: ******
```

**步骤 3/4: 配置 Web 服务端口**
```
请输入 Web 服务端口 [默认: 8000]: 8000
```

**步骤 4/4: 安装 Python 依赖**
```
# 自动安装，需要等待几分钟
```

**可选：创建 systemd 服务**
```
是否创建 systemd 服务（开机自启动）？(y/N): y
是否立即启动服务？(y/N): y
```

### 4. 安装完成

会显示：
```
========================================
[SUCCESS] 安装完成！
========================================

📍 数据目录: /path/to/data
📍 配置文件: /path/to/.env

🎯 快捷命令:
   qvs              - 启动 TUI 管理界面
   qvs admin        - 管理员工具

🌐 Web 访问:
   http://localhost:8000 （服务已启动）

👤 管理员账号:
   用户名: admin
   密码: ********
```

---

## 🖥️ 使用 TUI

### 启动 TUI

```bash
qvs
```

会显示：
```
======================================================================
              七牛 QVS 通知器 v2.0 - 管理界面
======================================================================

系统状态
  任务: 0 个 | 监听渠道: 0 个 | 通知渠道: 0 个

请选择操作
  📋 任务管理
  📡 监听渠道管理
  🔔 通知渠道管理
  ⚙️  系统管理
  ❌ 退出

使用方向键选择，回车确认
```

### TUI 功能测试

1. **创建监听渠道**
   - 选择「📡 监听渠道管理」→「➕ 创建新渠道」
   - 填写七牛云配置（AK/SK/Namespace）

2. **创建通知渠道**
   - 选择「🔔 通知渠道管理」→「➕ 创建新渠道」
   - 选择 NTFY 或 Webhook

3. **创建监控任务**
   - 选择「📋 任务管理」→「➕ 创建新任务」
   - 配置 Cron 表达式（如：`*/5 * * * *`）
   - 关联监听渠道和通知渠道

4. **查看系统信息**
   - 选择「⚙️  系统管理」→「📊 查看系统信息」

---

## 🌐 Web UI 测试

### 1. 访问 Web UI

```bash
# 如果安装时启动了 systemd 服务
http://your-server-ip:8000

# 如果未启动服务，手动启动
cd /path/to/qiniu-qvs-notifier
source venv/bin/activate
python run_web_v2.py
```

### 2. 登录

使用安装时创建的管理员账号登录。

### 3. 功能测试

- ✅ 任务管理（创建、编辑、删除、启用/禁用）
- ✅ 监听渠道管理
- ✅ 通知渠道管理
- ✅ 系统设置（调度器状态）
- ✅ 用户管理（管理员）

---

## 🔧 管理命令

### 查看服务状态

```bash
systemctl status qvs-notifier
```

### 查看日志

```bash
# systemd 服务日志
journalctl -u qvs-notifier -f

# 或直接运行查看
cd /path/to/qiniu-qvs-notifier
source venv/bin/activate
python run_web_v2.py
```

### 重启服务

```bash
systemctl restart qvs-notifier
```

### 停止服务

```bash
systemctl stop qvs-notifier
```

---

## 🐛 常见问题

### 1. 安装时提示权限不足

```bash
# 需要使用 sudo
sudo bash install.sh
```

### 2. TUI 提示"系统尚未初始化"

```bash
# 说明未运行安装脚本
sudo bash install.sh
```

### 3. Web UI 无法访问

```bash
# 检查服务是否运行
systemctl status qvs-notifier

# 检查端口
netstat -tulpn | grep 8000

# 检查防火墙
sudo ufw status
sudo ufw allow 8000/tcp
```

### 4. 找不到 qvs 命令

```bash
# 检查是否安装
which qvs

# 重新创建链接
sudo ln -sf /path/to/qiniu-qvs-notifier/qvs /usr/local/bin/qvs
```

---

## ✅ 测试清单

- [ ] 克隆仓库成功
- [ ] 安装脚本运行成功
- [ ] 完成 4 个安装步骤
- [ ] 创建 systemd 服务（可选）
- [ ] qvs 命令可用
- [ ] TUI 界面正常显示
- [ ] 创建监听渠道成功
- [ ] 创建通知渠道成功
- [ ] 创建监控任务成功
- [ ] Web UI 可访问
- [ ] 登录成功
- [ ] Web UI 功能正常

---

**所有准备就绪！现在可以在服务器上测试安装了！** 🎉
