#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""直接运行服务并查看输出"""
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

# 直接运行服务（前台）看输出
print("=" * 60)
print("直接启动服务（显示实时输出）")
print("=" * 60)
print("\n$ cd ~/qiniu-qvs-notifier-test && ./venv/bin/python run_web_v2.py\n")

stdin, stdout, stderr = ssh.exec_command(
    "cd ~/qiniu-qvs-notifier-test && timeout 15 ./venv/bin/python run_web_v2.py",
    get_pty=True
)

# 实时显示输出
import select
while True:
    if stdout.channel.exit_status_ready():
        break

    # 检查是否有可读数据
    rl, wl, xl = select.select([stdout.channel], [], [], 0.1)
    if len(rl) > 0:
        data = stdout.channel.recv(1024).decode('utf-8')
        if data:
            print(data, end='', flush=True)

# 读取剩余输出
remaining = stdout.read().decode('utf-8')
if remaining:
    print(remaining, flush=True)

error_output = stderr.read().decode('utf-8')
if error_output:
    print("\n错误输出:", error_output)

ssh.close()
