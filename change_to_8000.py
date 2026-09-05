#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""改回 8000 端口并重启"""
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

print("修改 .env 文件，改回 8000 端口...")
env_config = """QVS_DATA_DIR=/home/claudetest/.qvs-test
WEB_PORT=8000
SECRET_KEY=test-secret-key-12345-qvs-notifier
QVS_ADMIN_USERNAME=admin
QVS_ADMIN_PASSWORD=admin123456"""

stdin, stdout, stderr = ssh.exec_command(f"cat > ~/qiniu-qvs-notifier-test/.env << 'EOF'\n{env_config}\nEOF")
stdout.read()

print("✓ 已修改端口配置为 8000\n")

# 重启服务
print("重启服务...")
ssh.exec_command(f"echo {PASSWORD} | sudo -S pkill -9 -f 'qiniu-qvs-notifier-test'")
time.sleep(3)

ssh.exec_command("bash -c 'cd ~/qiniu-qvs-notifier-test && ./venv/bin/python run_web_v2.py > ~/qvs-8000.log 2>&1 &'")
time.sleep(10)

# 验证
stdin, stdout, stderr = ssh.exec_command("ps aux | grep '[r]un_web_v2.py'")
if stdout.read().decode('utf-8').strip():
    print("✓ 服务已启动")

stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep 8000")
if stdout.read().decode('utf-8').strip():
    print("✓ 端口 8000 正在监听")

stdin, stdout, stderr = ssh.exec_command("curl -s http://localhost:8000 | head -3")
http_result = stdout.read().decode('utf-8')
if http_result.strip():
    print("✓ HTTP 访问正常")

print(f"\n{'='*60}")
print(f"✓ 请测试: http://{HOST}:8000")
print(f"{'='*60}")

ssh.close()
