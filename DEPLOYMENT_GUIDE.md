# 🚀 v2.0 部署测试指南

## ✅ 已完成

1. ✅ 完整的后端 API（27 个接口）
2. ✅ Element Plus Web UI
3. ✅ JWT 认证系统
4. ✅ APScheduler 任务调度器
5. ✅ TUI v2 管理界面
6. ✅ 安装向导（支持数据目录选择）
7. ✅ 代码已推送到 GitHub
8. ✅ Docker 镜像自动构建中

---

## 📦 服务器部署步骤

### 方式一：Docker 部署（推荐）

```bash
# 1. SSH 连接到服务器
ssh user@your-server

# 2. 克隆仓库
git clone https://github.com/Katfionn/qiniu-qvs-notifier.git
cd qiniu-qvs-notifier

# 3. 等待 Docker 镜像构建完成
# 访问：https://github.com/Katfionn/qiniu-qvs-notifier/actions
# 等待 "Docker Image CI/CD" 工作流完成（约 5-10 分钟）

# 4. 运行一键部署脚本
chmod +x deploy.sh
./deploy.sh

# 5. 访问 Web UI
# http://your-server-ip:8000
```

### 方式二：手动 Docker 部署

```bash
# 等待镜像构建完成后
docker pull ghcr.io/katfionn/qiniu-qvs-notifier:v2.0.0

# 运行容器
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  --restart always \
  --name qvs-notifier \
  ghcr.io/katfionn/qiniu-qvs-notifier:v2.0.0

# 查看日志
docker logs -f qvs-notifier
```

### 方式三：源码部署（推荐用于开发）

```bash
# 1. 克隆仓库
git clone https://github.com/Katfionn/qiniu-qvs-notifier.git
cd qiniu-qvs-notifier

# 2. 运行安装脚本（创建系统级快捷命令）
sudo ./install.sh

# 3. 首次运行安装向导
qvs installer

# 4. 启动 TUI 管理界面
qvs

# 或启动 Web 服务
source venv/bin/activate
python run_web_v2.py
```

**快捷命令**：
- `qvs` - 启动 TUI 管理界面
- `qvs admin` - 管理员工具
- `qvs installer` - 运行安装向导
- `qvs tui` - 启动 TUI（同 qvs）

---

## 🎯 首次安装流程

### 自动安装向导

首次运行时会自动进入安装向导：

**步骤 1：选择数据存储位置**
```
请输入数据存储目录 [./data]: /path/to/your/data
```
- 直接回车使用默认位置 `./data`
- 或输入自定义路径，例如：`/var/lib/qvs-notifier`

**步骤 2：创建管理员账号**
```
请输入管理员用户名 [admin]: admin
请输入管理员密码: ******
请再次输入密码: ******
```

**完成**
```
✓ 管理员账号创建成功！
✓ 配置已保存到: .env

数据目录: /path/to/your/data
账号数据: /path/to/your/data/data.db
日志数据: /path/to/your/data/logs.db

访问地址: http://localhost:8000
```

---

## 🔐 登录 Web UI

1. 访问 `http://your-server-ip:8000`
2. 使用安装时创建的管理员账号登录
3. 开始配置监控任务

---

## 📋 配置监控任务

### 1. 创建监听渠道

进入「监听渠道管理」→「创建渠道」

**七牛云配置**：
- 渠道名称：`七牛云生产环境`
- 服务商类型：`qiniu`
- Access Key：`你的 AK`
- Secret Key：`你的 SK`
- Namespace ID：`你的命名空间 ID`

### 2. 创建通知渠道

进入「通知渠道管理」→「创建渠道」

**NTFY 配置**：
- 渠道名称：`NTFY 告警`
- 通知类型：`ntfy`
- 服务器地址：`https://ntfy.sh`
- Topic：`your-topic-name`

**Webhook 配置**：
- 渠道名称：`Webhook 告警`
- 通知类型：`webhook`
- Webhook URL：`https://your-webhook-url`

### 3. 创建监控任务

进入「任务管理」→「创建任务」

- 任务名称：`生产设备监控`
- 监听渠道：选择刚创建的七牛云渠道
- Cron 表达式：`*/5 * * * *`（每 5 分钟）
- 国标 ID：可选，留空监控所有设备
- 通知渠道：选择刚创建的通知渠道
- 启用状态：✅ 启用

### 4. 验证调度器

进入「系统设置」查看调度器状态：
- 运行状态：✅ 运行中
- 已加载任务：1 个

---

## 🔧 管理命令

### Docker 容器管理

```bash
# 查看日志
docker logs -f qvs-notifier

# 停止容器
docker stop qvs-notifier

# 启动容器
docker start qvs-notifier

# 重启容器
docker restart qvs-notifier

# 删除容器
docker rm -f qvs-notifier

# 更新镜像
docker pull ghcr.io/katfionn/qiniu-qvs-notifier:latest
docker rm -f qvs-notifier
./deploy.sh
```

### 源码部署管理

```bash
# 快捷命令（安装后）
qvs                    # 启动 TUI 管理界面
qvs admin              # 管理员工具
qvs installer          # 运行安装向导

# 或使用完整命令
source venv/bin/activate
python -m qvs_notifier tui        # 启动 TUI
python -m qvs_notifier admin      # 管理员工具
python run_web_v2.py              # 启动 Web 服务
```

---

## 🗃️ 数据存储

### 数据目录结构

```
data/                      # 数据目录（可自定义）
├── data.db                # 账号、任务、渠道配置
└── logs.db                # 任务日志、通知日志
```

### 备份数据

```bash
# 备份数据目录
tar -czf qvs-backup-$(date +%Y%m%d).tar.gz data/

# 或单独备份数据库
cp data/data.db data/data.db.backup
cp data/logs.db data/logs.db.backup
```

### 恢复数据

```bash
# 解压备份
tar -xzf qvs-backup-20260903.tar.gz

# 或直接替换数据库文件
cp data.db.backup data/data.db
cp logs.db.backup data/logs.db

# 重启服务
docker restart qvs-notifier
```

---

## 🐛 故障排查

### 1. 容器无法启动

```bash
# 查看容器日志
docker logs qvs-notifier

# 检查端口占用
netstat -tulpn | grep 8000

# 检查数据目录权限
ls -la data/
```

### 2. 无法访问 Web UI

```bash
# 检查容器是否运行
docker ps | grep qvs-notifier

# 检查防火墙
sudo firewall-cmd --list-ports
sudo ufw status

# 开放 8000 端口
sudo firewall-cmd --add-port=8000/tcp --permanent
sudo firewall-cmd --reload
```

### 3. 任务未执行

- 检查任务是否启用
- 检查调度器状态（系统设置页面）
- 查看任务日志
- 检查 Cron 表达式是否正确

### 4. 通知发送失败

- 检查通知渠道配置是否正确
- 测试 NTFY 服务器连通性：`curl https://ntfy.sh/your-topic`
- 测试 Webhook URL 连通性
- 查看通知日志

---

## 📊 监控指标

### 系统状态

- 调度器运行状态
- 已加载任务数量
- 最近任务执行情况

### 任务日志

- 任务执行时间
- 在线/离线设备数量
- 执行状态（成功/失败）
- 错误信息

### 通知日志

- 通知发送时间
- 通知渠道
- 发送状态（成功/失败）
- 错误信息

---

## 🔗 相关链接

- **GitHub**: https://github.com/Katfionn/qiniu-qvs-notifier
- **Actions**: https://github.com/Katfionn/qiniu-qvs-notifier/actions
- **安装文档**: docs/INSTALL_V2.md
- **完整报告**: V2_COMPLETE.md
- **Cron 表达式**: https://crontab.guru/

---

## ⚡ 快速测试清单

- [ ] 克隆仓库到服务器
- [ ] 等待 Docker 镜像构建完成
- [ ] 运行部署脚本
- [ ] 访问 Web UI
- [ ] 完成安装向导
- [ ] 登录管理界面
- [ ] 创建监听渠道
- [ ] 创建通知渠道
- [ ] 创建监控任务
- [ ] 启用任务
- [ ] 检查调度器状态
- [ ] 等待任务执行
- [ ] 查看任务日志
- [ ] 验证通知发送

---

**准备就绪！现在可以在服务器上测试部署了！** 🎉
