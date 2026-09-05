#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快速测试 - 保持 SSH 连接并启动服务"""
import paramiko
import sys
import time

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

HOST = "claw.fe2fe.top"
PORT = 22
USERNAME = "claudetest"
PASSWORD = "ABC1986720abc"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, PORT, USERNAME, PASSWORD, timeout=10)
print("✓ SSH 连接成功\n")

# 先清理
print("1. 清理旧进程...")
ssh.exec_command(f"echo {PASSWORD} | sudo -S pkill -f 'qiniu-qvs-notifier-test' || true")
time.sleep(2)

# 后台启动 (使用 & 并立即返回)
print("2. 启动服务...")
ssh.exec_command("bash -c 'cd ~/qiniu-qvs-notifier-test && ./venv/bin/python run_web_v2.py > ~/qvs.log 2>&1 &'")

print("3. 等待 15 秒...")
time.sleep(15)

# 检查
print("\n4. 检查状态:")
stdin, stdout, stderr = ssh.exec_command("ps aux | grep '[r]un_web_v2.py'")
ps_out = stdout.read().decode('utf-8')
print("进程:", ps_out if ps_out.strip() else "未找到")

stdin, stdout, stderr = ssh.exec_command("ss -tlnp 2>/dev/null | grep 10000")
port_out = stdout.read().decode('utf-8')
print("端口:", port_out if port_out.strip() else "未监听")

stdin, stdout, stderr = ssh.exec_command("tail -20 ~/qvs.log")
log = stdout.read().decode('utf-8')
print("\n日志:\n", log)

stdin, stdout, stderr = ssh.exec_command("curl -s http://localhost:10000 | head -20")
http_out = stdout.read().decode('utf-8')
print("\nHTTP 测试:\n", http_out if http_out.strip() else "无响应")

print("\n" + "="*60)
print(f"访问地址: http://{HOST}:10000")
print("用户名: admin")
print("密码: admin123456")
print("="*60)

ssh.close()
