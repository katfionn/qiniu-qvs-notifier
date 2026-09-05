#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上传所有修改并重启服务"""
import paramiko
import sys
import os
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

local_base = "e:/0708123/Projects/qiniu-qvs-notifier"
remote_base = f"/home/{USERNAME}/qiniu-qvs-notifier-test"

# 上传修改的文件
files_to_upload = [
    "run_web_v2.py",
    "web/main_v2.py",
    "web/templates/index.html"
]

sftp = ssh.open_sftp()
for file in files_to_upload:
    local_file = os.path.join(local_base, file)
    remote_file = f"{remote_base}/{file}"
    sftp.put(local_file, remote_file)
    print(f"✓ 已上传 {file}")
sftp.close()

# 重启服务
print("\n重启服务...")
ssh.exec_command(f"echo {PASSWORD} | sudo -S pkill -f 'qiniu-qvs-notifier-test'")
time.sleep(3)

ssh.exec_command("bash -c 'cd ~/qiniu-qvs-notifier-test && ./venv/bin/python run_web_v2.py > ~/qvs.log 2>&1 &'")
print("等待 10 秒...")
time.sleep(10)

# 验证
stdin, stdout, stderr = ssh.exec_command("ps aux | grep '[r]un_web_v2.py'")
if stdout.read().decode('utf-8').strip():
    print("✓ 服务已重启")

    stdin, stdout, stderr = ssh.exec_command("ss -tlnp 2>/dev/null | grep 10000")
    if stdout.read().decode('utf-8').strip():
        print("✓ 端口 10000 正在监听")
    else:
        print("⚠ 端口未监听")
else:
    print("✗ 服务未启动")

print(f"\n{'='*60}")
print(f"✓ 请刷新浏览器测试: http://{HOST}:10000")
print(f"{'='*60}")
print("\n现在系统会：")
print("1. 首次启动直接成功（无需配置）")
print("2. 访问 Web 时检测未初始化")
print("3. 显示初始化向导让用户配置管理员")
print("\n⚠ 注意：初始化向导页面还在开发中")
print("   当前可以通过 API 手动初始化：")
print(f"   curl -X POST http://{HOST}:10000/api/init/setup \\")
print('     -H "Content-Type: application/json" \\')
print('     -d \'{"username":"admin","password":"admin123456"}\'')

ssh.close()
