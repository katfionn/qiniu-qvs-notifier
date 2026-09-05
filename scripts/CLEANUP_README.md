# 清理测试环境脚本

这个脚本用于完全清理所有测试残留的进程、服务和文件。

## 使用方法

```bash
# 在项目根目录执行
sudo bash scripts/cleanup_all.sh
```

## 清理内容

### 1. 停止所有进程
- `run_web_v2.py` 进程
- 所有 QVS 相关的 Python 进程

### 2. 清理 systemd 服务
- `qvs-notifier.service`
- `qvs.service`
- `qiniu-qvs-notifier.service`

### 3. 删除命令
- `/usr/local/bin/qvs`
- `/usr/local/bin/qvs-notifier`

### 4. 测试目录
会检测并询问是否删除以下目录：
- `/tmp/qvs-test`
- `/tmp/qvs-loop-test`
- `/tmp/qvs-test-data`
- `/tmp/qvs-loop-data`
- `$HOME/qvs-test`
- `$HOME/qiniu-qvs-notifier-test`

### 5. 日志文件
- `/tmp/web*.log`
- `/tmp/qvs*.log`
- `/tmp/test*.log`

## 安全措施

- ✅ 双重确认（总体确认 + 目录删除确认）
- ✅ 详细的操作反馈
- ✅ 验证清理结果
- ✅ 不会删除当前项目代码

## 注意事项

⚠️ **此脚本会停止所有相关进程，请确保没有重要服务在运行！**

执行后建议：
1. 重启终端
2. 验证 `qvs` 命令是否已删除：`which qvs`
3. 验证进程是否已停止：`ps aux | grep qvs`
