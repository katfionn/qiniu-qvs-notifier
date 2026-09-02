# 配置说明

## 首次部署注意事项

本项目的敏感配置字段默认值为**空字符串**，而非占位符。这是为了确保：

1. ✅ 代码能正常启动
2. ✅ 配置可以通过 TUI 或 Web 界面设置
3. ✅ 公开仓库不包含真实密钥

## 配置方式

### 方式 1：TUI 安装器（推荐）

```bash
python install.py
```

在交互式界面中选择"配置"，输入：
- 七牛云 Access Key
- 七牛云 Secret Key  
- Webhook 地址

### 方式 2：Web 控制台

1. 启动服务后访问 `http://localhost:8000`
2. 在配置页面填写所有必需字段
3. 点击保存

### 方式 3：直接编辑配置文件

编辑 `config/settings.yaml`：

```yaml
qiniu:
  access_key: "your_access_key_here"
  secret_key: "your_secret_key_here"

webhook:
  url: "https://your-webhook-url"
  auth_type: "none"  # 或 sign, keyword
  secret: ""
  keyword: ""
  custom_body: '{"msgtype": "text", "text": {"content": "{message}"}}'
  template: "[{device} 设备{state}]"

schedule:
  mode: "loop"  # 或 once
  interval_seconds: 60

alert:
  notify_online: false
  notify_offline: true

ui:
  language: "zh-CN"  # 或 en-US
```

## Docker 部署

```bash
docker compose up -d --build
```

配置文件会自动持久化到 `./config` 目录。

## 故障排查

如果遇到 `Internal Server Error`：

1. 检查日志：`journalctl -u qiniu-qvs-notifier-web -n 50`
2. 确认 `config/settings.yaml` 格式正确
3. 确认所有必需字段已填写
