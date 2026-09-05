#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手动调试启动问题"""
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
ssh.connect(HOST, PORT, USERNAME, PASSWORD)
print("✓ SSH 连接成功\n")

# 1. 检查文件
print("=" * 60)
print("1. 检查 run_web_v2.py 内容（前50行）")
print("=" * 60)
stdin, stdout, stderr = ssh.exec_command("head -50 ~/qiniu-qvs-notifier-test/run_web_v2.py")
print(stdout.read().decode('utf-8'))

# 2. 手动运行一次，直接看输出
print("\n" + "=" * 60)
print("2. 手动运行（10秒后自动终止）")
print("=" * 60)

# 使用 screen 或 直接运行并获取输出
stdin, stdout, stderr = ssh.exec_command(
    "cd ~/qiniu-qvs-notifier-test && timeout 10 ./venv/bin/python run_web_v2.py 2>&1",
    get_pty=True
)

# 读取输出
while True:
    line = stdout.readline()
    if not line:
        break
    print(line.rstrip())

print("\n" + "=" * 60)
print("3. 检查是否有错误")
print("=" * 60)
error = stderr.read().decode('utf-8')
if error:
    print(error)
else:
    print("无错误输出")

ssh.close()
