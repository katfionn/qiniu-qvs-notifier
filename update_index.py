#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上传修复后的 index.html"""
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

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, PORT, USERNAME, PASSWORD)
print("✓ SSH 连接成功\n")

# 上传修复后的 index.html
local_file = "e:/0708123/Projects/qiniu-qvs-notifier/web/templates/index.html"
remote_file = "/home/claudetest/qiniu-qvs-notifier-test/web/templates/index.html"

sftp = ssh.open_sftp()
sftp.put(local_file, remote_file)
sftp.close()
print("✓ 已上传 index.html")

# 重启服务
print("\n重启服务...")
ssh.exec_command(f"echo {PASSWORD} | sudo -S pkill -f 'qiniu-qvs-notifier-test'")
import time
time.sleep(2)

ssh.exec_command("bash -c 'cd ~/qiniu-qvs-notifier-test && ./venv/bin/python run_web_v2.py > ~/qvs.log 2>&1 &'")
print("等待 10 秒...")
time.sleep(10)

# 验证
stdin, stdout, stderr = ssh.exec_command("ps aux | grep '[r]un_web_v2.py'")
if stdout.read().decode('utf-8').strip():
    print("✓ 服务已重启")
else:
    print("✗ 服务未启动，查看日志：")
    stdin, stdout, stderr = ssh.exec_command("tail -20 ~/qvs.log")
    print(stdout.read().decode('utf-8'))

print(f"\n✓ 请刷新浏览器测试: http://{HOST}:10000")

ssh.close()
