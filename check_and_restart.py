#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查服务器状态"""
import paramiko
import sys

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
ssh.connect(HOST, PORT, USERNAME, PASSWORD)
print("✓ SSH 连接成功\n")

print("=" * 60)
print("1. 检查所有 Python 进程")
print("=" * 60)
stdin, stdout, stderr = ssh.exec_command("ps aux | grep python | grep -v grep")
print(stdout.read().decode('utf-8'))

print("\n" + "=" * 60)
print("2. 检查所有监听端口")
print("=" * 60)
stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep -E '(8000|10000)'")
print(stdout.read().decode('utf-8'))

print("\n" + "=" * 60)
print("3. 查看最新日志")
print("=" * 60)
stdin, stdout, stderr = ssh.exec_command("tail -50 ~/qvs.log")
print(stdout.read().decode('utf-8'))

print("\n" + "=" * 60)
print("4. 清理所有旧进程并重新启动")
print("=" * 60)

# 强制清理所有相关进程
stdin, stdout, stderr = ssh.exec_command(f"echo {PASSWORD} | sudo -S pkill -9 -f 'qvs|qiniu' || true")
stdout.read()

import time
time.sleep(3)

# 删除旧数据目录
stdin, stdout, stderr = ssh.exec_command("rm -rf ~/.qvs-test")
stdout.read()

# 启动服务
stdin, stdout, stderr = ssh.exec_command("bash -c 'cd ~/qiniu-qvs-notifier-test && ./venv/bin/python run_web_v2.py > ~/qvs-new.log 2>&1 &'")
stdout.read()

print("等待 10 秒...")
time.sleep(10)

print("\n" + "=" * 60)
print("5. 验证新服务")
print("=" * 60)

stdin, stdout, stderr = ssh.exec_command("ps aux | grep '[r]un_web_v2.py'")
ps_result = stdout.read().decode('utf-8')
print("进程:", ps_result if ps_result.strip() else "未找到")

stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep 10000")
port_result = stdout.read().decode('utf-8')
print("端口:", port_result if port_result.strip() else "未监听")

stdin, stdout, stderr = ssh.exec_command("tail -30 ~/qvs-new.log")
print("\n新日志:\n", stdout.read().decode('utf-8'))

print("\n" + "=" * 60)
print(f"测试地址: http://{HOST}:10000")
print("=" * 60)

ssh.close()
