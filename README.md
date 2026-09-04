# 七牛 QVS 通知器 v2.0

[![Docker Image CI/CD](https://github.com/Katfionn/qiniu-qvs-notifier/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/Katfionn/qiniu-qvs-notifier/actions/workflows/docker-publish.yml)

[简体中文](README.md) | [English](docs/README.en.md)

通过 NTFY、Webhook 等多种渠道，在七牛云视频监控设备状态异常时发送实时告警通知。

## ✨ v2.0 新特性

- 🎯 **任务化管理** - 灵活的 Cron 表达式调度
- 🌐 **多服务商支持** - 不再局限于七牛云
- 🔔 **多通知渠道** - NTFY、Webhook（可扩展）
- 👥 **账号体系** - JWT 认证 + 多用户管理
- 💾 **数据分离** - 配置数据和日志数据独立存储
- 🎨 **现代化 UI** - Element Plus 专业界面
- 🖥️ **强大 TUI** - 友好的终端管理界面
- 🚀 **一键安装** - 自动安装向导

---

## 🚀 快速开始

### 方式一：Docker（推荐）

```bash
# 拉取并运行
docker run -d \
  -p 8000:8000 \
  -v ./data:/app/data \
  --restart always \
  --name qvs-notifier \
  ghcr.io/katfionn/qiniu-qvs-notifier:latest

# 访问 Web UI
# http://localhost:8000
```

### 方式二：一键部署脚本

```bash
git clone https://github.com/Katfionn/qiniu-qvs-notifier.git
cd qiniu-qvs-notifier
chmod +x deploy.sh
./deploy.sh
```

### 方式三：源码安装（推荐用于开发）

```bash
# 1. 克隆仓库
git clone https://github.com/Katfionn/qiniu-qvs-notifier.git
cd qiniu-qvs-notifier

# 2. 安装系统命令（需要 sudo）
sudo ./install.sh

# 3. 首次运行安装向导
qvs installer

# 4. 启动 TUI 管理界面
qvs
```

---

## 📋 快捷命令

安装后，可以使用以下快捷命令（类似 Alist）：

```bash
qvs                    # 启动 TUI 管理界面
qvs admin              # 管理员工具（查看/重置密码）
qvs installer          # 运行安装向导
```

或使用完整命令：

```bash
python -m qvs_notifier tui        # TUI 管理界面
python -m qvs_notifier admin      # 管理员工具
python run_web_v2.py              # 启动 Web 服务
```

---

## 🎯 使用流程

### 1. 首次安装

首次运行会自动进入安装向导：

```
步骤 1: 选择数据存储位置
  请输入数据存储目录 [./data]: 

步骤 2: 创建管理员账号
  请输入管理员用户名 [admin]: 
  请输入管理员密码: 
```

### 2. 登录 Web UI

访问 `http://localhost:8000`，使用管理员账号登录。

### 3. 配置监控任务

**创建监听渠道（数据来源）**：
- 进入「监听渠道管理」
- 配置七牛云 AK/SK 和 Namespace ID

**创建通知渠道（告警目标）**：
- 进入「通知渠道管理」
- 配置 NTFY 或 Webhook

**创建监控任务**：
- 进入「任务管理」
- 设置 Cron 表达式（例如：`*/5 * * * *` 表示每 5 分钟）
- 关联监听渠道和通知渠道
- 启用任务

### 4. 完成！

调度器会自动执行监控，检测到离线设备时发送通知。

---

## 🖥️ TUI 管理界面

启动 TUI：`qvs`

```
======================================================================
              七牛 QVS 通知器 v2.0 - 管理界面
======================================================================

系统状态
  任务: 3 个 | 监听渠道: 1 个 | 通知渠道: 2 个

请选择操作
  📋 任务管理
  📡 监听渠道管理
  🔔 通知渠道管理
  ⚙️  系统管理
  ❌ 退出
```

**功能**：
- 任务管理：创建、查看、启用/禁用、删除任务
- 监听渠道：配置七牛云或自定义服务商
- 通知渠道：配置 NTFY、Webhook
- 系统管理：查看信息、管理员账号

---

## 📚 文档

- **安装指南**：[docs/INSTALL_V2.md](docs/INSTALL_V2.md)
- **部署测试**：[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- **产品需求**：[docs/PRD.md](docs/PRD.md)
- **完成报告**：[V2_COMPLETE.md](V2_COMPLETE.md)

---

## 🔧 管理命令

### Docker

```bash
docker logs -f qvs-notifier        # 查看日志
docker stop qvs-notifier           # 停止容器
docker start qvs-notifier          # 启动容器
docker restart qvs-notifier        # 重启容器
```

### 源码部署

```bash
qvs                                # TUI 管理界面
qvs admin                          # 管理员工具
source venv/bin/activate
python run_web_v2.py               # Web 服务
```

---

## 🌟 核心功能

### 任务管理
- ✅ 灵活的 Cron 表达式调度
- ✅ 多任务并行执行
- ✅ 任务启用/禁用
- ✅ 完整的任务日志

### 多服务商支持
- ✅ 七牛云 QVS
- ✅ 自定义服务商（架构已完成）

### 多通知渠道
- ✅ NTFY.sh 推送
- ✅ Webhook
- ✅ 一个任务支持多个通知渠道

### 账号体系
- ✅ JWT 认证（7 天有效期）
- ✅ 管理员/普通用户角色
- ✅ 用户管理（管理员权限）

### 数据分离
- ✅ `data.db` - 账号、任务、渠道配置
- ✅ `logs.db` - 任务日志、通知日志

---

## 🔐 安全建议

1. **修改 JWT 密钥**（生产环境）：
   ```bash
   # 编辑 .env 文件
   JWT_SECRET_KEY=your-random-secret-key
   ```

2. **使用强密码**：管理员密码至少 12 位

3. **限制访问**：使用反向代理（Nginx）+ HTTPS

4. **定期备份**：
   ```bash
   tar -czf backup-$(date +%Y%m%d).tar.gz data/
   ```

---

## 📊 系统要求

### Docker
- Docker 20.10+
- 512MB 内存
- 1GB 磁盘空间

### 源码安装
- Python 3.11+
- Linux / macOS / Windows
- 512MB 内存

---

## 🐛 故障排查

### 无法访问 Web UI
```bash
# 检查容器状态
docker ps | grep qvs-notifier

# 查看日志
docker logs qvs-notifier

# 检查端口
netstat -tulpn | grep 8000
```

### 任务未执行
- 检查任务是否启用
- 查看调度器状态（系统设置页面）
- 检查 Cron 表达式：https://crontab.guru/

### 通知发送失败
- 检查通知渠道配置
- 测试 NTFY：`curl https://ntfy.sh/your-topic`
- 查看通知日志

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

MIT License

---

## 🔗 相关链接

- **GitHub**: https://github.com/Katfionn/qiniu-qvs-notifier
- **Docker Hub**: https://github.com/Katfionn/qiniu-qvs-notifier/pkgs/container/qiniu-qvs-notifier
- **Issues**: https://github.com/Katfionn/qiniu-qvs-notifier/issues

---

**开发**: v2.0.0 | **状态**: ✅ 完成 | **更新**: 2026-09-03
