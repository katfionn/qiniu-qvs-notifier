#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手动调试部署"""
import paramiko
import sys
import os

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

HOST = "claw.fe2fe.top"
PORT = 22
USERNAME = "claudetest"
PASSWORD = "ABC1986720abc"

def run_command(ssh, command):
    """执行命令并实时显示输出"""
    print(f"\n$ {command}")
    stdin, stdout, stderr = ssh.exec_command(command, get_pty=True)

    while True:
        line = stdout.readline()
        if not line:
            break
        print(line.rstrip())

    return stdout.channel.recv_exit_status()

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, PORT, USERNAME, PASSWORD)
print("✓ SSH 连接成功\n")

# 1. 检查目录和文件
print("=" * 60)
print("1. 检查部署目录")
print("=" * 60)
run_command(ssh, "ls -la ~/qiniu-qvs-notifier-test/")
run_command(ssh, "cat ~/qiniu-qvs-notifier-test/.env")

# 2. 手动运行一次看错误
print("\n" + "=" * 60)
print("2. 手动运行查看错误")
print("=" * 60)
run_command(ssh, "cd ~/qiniu-qvs-notifier-test && ./venv/bin/python run_web_v2.py &")

import time
time.sleep(3)

# 3. 查看进程
print("\n" + "=" * 60)
print("3. 查看进程")
print("=" * 60)
run_command(ssh, "ps aux | grep python | grep qiniu")

ssh.close()
