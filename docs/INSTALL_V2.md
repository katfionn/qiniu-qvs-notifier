# 七牛 QVS 通知器 v2.0 安装指南

## 版本说明

**v2.0 重大更新**：
- ✅ 多服务商支持（不再局限于七牛）
- ✅ 任务化管理（灵活配置监控任务）
- ✅ 多通知渠道（NTFY.sh、Webhook）
- ✅ 账号体系（Web UI 支持多用户）
- ✅ 数据分离（账号数据和日志数据独立存储）
- ✅ 任务调度（基于 Cron 表达式）

---

## 一、Docker 安装（推荐）

### 1.1 使用预构建镜像

```bash
# 1. 拉取镜像
docker pull ghcr.io/katfionn/qiniu-qvs-notifier:latest

# 2. 首次运行（会自动启动安装向导）
docker run -it --rm \
  -p 8000:8000 \
  -v ./data:/app/data \
  --name qvs-notifier \
  ghcr.io/katfionn/qiniu-qvs-notifier:latest

# 按照提示创建管理员账号

# 3. 后台运行
docker run -d \
  -p 8000:8000 \
  -v ./data:/app/data \
  --restart always \
  --name qvs-notifier \
  ghcr.io/katfionn/qiniu-qvs-notifier:latest
```

### 1.2 从源码构建

```bash
git clone https://github.com/Katfionn/qiniu-qvs-notifier.git
cd qiniu-qvs-notifier
docker build -t qvs-notifier:v2 .
docker run -d -p 8000:8000 -v ./data:/app/data --name qvs-notifier qvs-notifier:v2
```

### 1.3 数据持久化

容器使用 `-v ./data:/app/data` 挂载数据目录，包含：
- `data.db` - 账号和配置数据
- `logs.db` - 任务执行日志

---

## 二、源码安装

### 2.1 系统要求

- Python 3.11+
- pip

### 2.2 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/Katfionn/qiniu-qvs-notifier.git
cd qiniu-qvs-notifier

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行安装向导（首次运行）
python -m qvs_notifier installer

# 按照提示创建管理员账号

# 5. 启动 Web 服务
python run_web_v2.py
```

访问 `http://localhost:8000` 使用 Web UI。

### 2.3 TUI 管理界面

```bash
# 启动 TUI（终端管理界面）
python -m qvs_notifier tui
```

TUI 提供完整的管理功能，无需登录认证。

---

## 三、首次配置

### 3.1 创建管理员账号

**Docker 安装**：首次运行容器时，自动进入安装向导

**源码安装**：
```bash
python -m qvs_notifier installer
```

按照提示输入：
- 管理员用户名（至少 3 个字符）
- 管理员密码（至少 6 个字符）

### 3.2 数据目录

源码安装时，数据存储在项目根目录的 `data/` 文件夹：

```
data/
├── data.db      # 账号、任务、渠道配置
└── logs.db      # 任务执行日志
```

可以在 TUI 的"系统管理"中查看数据目录位置。

---

## 四、管理员工具

### 4.1 查看管理员信息

```bash
python -m qvs_notifier admin
```

### 4.2 重置管理员密码

```bash
python -m qvs_notifier admin
# 选择"重置管理员密码"
```

### 4.3 从 v1 迁移数据

```bash
python -m qvs_notifier migrate
```

自动迁移：
- v1 配置文件 → v2 监听渠道和通知渠道
- v1 设备数据 → 导出为文本文件

---

## 五、使用方式

### 5.1 Web UI（推荐）

1. 访问 `http://localhost:8000`
2. 使用管理员账号登录
3. 创建监听渠道（数据来源）
4. 创建通知渠道（告警目标）
5. 创建任务并配置 Cron 表达式
6. 启用任务，调度器自动执行

### 5.2 TUI（终端界面）

```bash
python -m qvs_notifier tui
```

功能菜单：
- **任务管理** - 创建、查看、启用/禁用任务
- **监听渠道管理** - 配置服务商（七牛/自定义）
- **通知渠道管理** - 配置通知方式（NTFY/Webhook）
- **系统管理** - 查看系统信息、管理员账号

---

## 六、配置示例

### 6.1 创建七牛监听渠道

**Web UI**：
1. 进入"监听渠道管理"
2. 点击"创建渠道"
3. 填写：
   - 渠道名称：七牛云生产环境
   - 服务商类型：qiniu
   - Access Key：你的 AK
   - Secret Key：你的 SK
   - Namespace ID：你的命名空间 ID

**TUI**：
1. 主菜单 → 监听渠道管理 → 创建新渠道
2. 按照提示填写配置

### 6.2 创建 NTFY 通知渠道

**Web UI**：
1. 进入"通知渠道管理"
2. 点击"创建渠道"
3. 填写：
   - 渠道名称：NTFY 告警
   - 通知类型：ntfy
   - 服务器地址：https://ntfy.sh
   - Topic：your-topic-name

**TUI**：
1. 主菜单 → 通知渠道管理 → 创建新渠道
2. 选择 ntfy 类型并填写配置

### 6.3 创建监控任务

**Web UI**：
1. 进入"任务管理"
2. 点击"创建任务"
3. 填写：
   - 任务名称：生产环境设备监控
   - 监听渠道：选择已创建的七牛渠道
   - Cron 表达式：`*/5 * * * *`（每 5 分钟）
   - 国标 ID：可选，留空监控所有设备
   - 通知渠道：选择已创建的 NTFY 渠道
4. 启用任务

**TUI**：
1. 主菜单 → 任务管理 → 创建新任务
2. 按照提示填写并启用

---

## 七、Cron 表达式说明

格式：`分钟 小时 日 月 星期`

常用示例：
- `*/5 * * * *` - 每 5 分钟
- `0 * * * *` - 每小时
- `0 */2 * * *` - 每 2 小时
- `0 9 * * *` - 每天上午 9 点
- `0 9 * * 1-5` - 工作日上午 9 点

在线工具：https://crontab.guru/

---

## 八、systemd 服务（Linux）

创建服务文件 `/etc/systemd/system/qvs-notifier.service`：

```ini
[Unit]
Description=Qiniu QVS Notifier v2.0
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/qiniu-qvs-notifier
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python run_web_v2.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable qvs-notifier
sudo systemctl start qvs-notifier
sudo systemctl status qvs-notifier
```

---

## 九、常见问题

### 9.1 忘记管理员密码

```bash
python -m qvs_notifier admin
# 选择"重置管理员密码"
```

### 9.2 数据存储在哪里？

**Docker**：挂载的 `./data` 目录
**源码**：项目根目录的 `data/` 文件夹

### 9.3 如何备份数据？

备份 `data/` 目录下的两个文件：
```bash
cp data/data.db data/data.db.backup
cp data/logs.db data/logs.db.backup
```

### 9.4 调度器未执行任务

1. 检查任务是否启用（Web UI 或 TUI）
2. 检查 Cron 表达式是否正确
3. 查看 Web 服务日志

### 9.5 从 v1 升级到 v2

```bash
# 1. 备份 v1 数据
cp -r config config.backup

# 2. 运行迁移脚本
python -m qvs_notifier migrate

# 3. 在 TUI/Web UI 中编辑迁移的任务
```

---

## 十、API 文档

启动服务后访问：
- Swagger UI：`http://localhost:8000/docs`
- ReDoc：`http://localhost:8000/redoc`

主要接口：
- `POST /api/auth/login` - 用户登录
- `GET /api/tasks` - 获取任务列表
- `POST /api/tasks` - 创建任务
- `GET /api/source-channels` - 获取监听渠道
- `GET /api/notification-channels` - 获取通知渠道
- `GET /api/scheduler/status` - 调度器状态

---

## 十一、安全建议

1. **修改默认 JWT 密钥**：
   ```bash
   export JWT_SECRET_KEY="your-random-secret-key"
   ```

2. **使用强密码**：管理员密码至少 12 位，包含大小写字母、数字、符号

3. **限制访问**：生产环境使用反向代理（Nginx）并启用 HTTPS

4. **定期备份**：定期备份 `data/` 目录

---

## 参考资源

- [在线 Cron 表达式生成器](https://crontab.guru/)
- [NTFY.sh 官方文档](https://ntfy.sh/)
- [项目 GitHub](https://github.com/Katfionn/qiniu-qvs-notifier)
- [问题反馈](https://github.com/Katfionn/qiniu-qvs-notifier/issues)

Sources:
- [Configuration file](https://alistgo.com/config/configuration.html)
- [AlistGo/alist](https://github.com/AlistGo/alist)
