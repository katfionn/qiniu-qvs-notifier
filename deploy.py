#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自动部署脚本 - 使用 paramiko SSH"""
import sys
import io
import paramiko
import time

# 修复 Windows 控制台编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# SSH 配置
HOST = "claw.fe2fe.top"
PORT = 22
USERNAME = "claudetest"
PASSWORD = "ABC1986720abc"

print("=== 开始部署 QVS Notifier UI 优化 ===\n")

try:
    # 创建 SSH 客户端
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print(f"连接到服务器 {HOST}...")
    client.connect(HOST, PORT, USERNAME, PASSWORD, timeout=10)
    print("✓ 已连接\n")

    # 拉取代码
    print("拉取最新代码...")
    stdin, stdout, stderr = client.exec_command("cd ~/qiniu-qvs-notifier-test && git pull")
    print(stdout.read().decode())

    # 停止旧进程
    print("停止旧服务...")
    stdin, stdout, stderr = client.exec_command("pkill -9 -f 'python.*run_web_v2.py'")
    time.sleep(2)
    print("✓ 旧进程已停止\n")

    # 启动新服务
    print("启动新服务...")
    stdin, stdout, stderr = client.exec_command(
        "cd ~/qiniu-qvs-notifier-test && nohup ~/qiniu-qvs-notifier-test/venv/bin/python run_web_v2.py > ~/qvs-test.log 2>&1 &"
    )
    time.sleep(3)

    # 检查服务状态
    print("检查服务状态...")
    stdin, stdout, stderr = client.exec_command("pgrep -af 'python.*run_web_v2.py'")
    result = stdout.read().decode()
    if result:
        print(f"✓ 服务启动成功！\n{result}")
    else:
        print("✗ 服务启动失败，查看日志:")
        stdin, stdout, stderr = client.exec_command("tail -20 ~/qvs-test.log")
        print(stdout.read().decode())

    client.close()

    print("\n=== 部署完成！===")
    print("\n请访问 http://claw.fe2fe.top:10000")
    print("记得按 Ctrl+Shift+R 强制刷新浏览器！\n")

except Exception as e:
    print(f"✗ 部署失败: {e}")
    exit(1)
