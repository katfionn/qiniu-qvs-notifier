#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""彻底清理并重启"""
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

print("=" * 60)
print("1. 强制杀死所有相关进程")
print("=" * 60)

# 杀死具体的进程
commands = [
    f"echo {PASSWORD} | sudo -S kill -9 1533833 1533850 1535293 2>/dev/null || true",
    f"echo {PASSWORD} | sudo -S pkill -9 -f 'run_web_v2' || true",
    f"echo {PASSWORD} | sudo -S pkill -9 -f 'qvs-notifier' || true",
]

for cmd in commands:
    ssh.exec_command(cmd)
    time.sleep(1)

print("✓ 已清理旧进程\n")

time.sleep(3)

# 验证清理
stdin, stdout, stderr = ssh.exec_command("ps aux | grep -E '(qvs|qiniu)' | grep -v grep")
remaining = stdout.read().decode('utf-8').strip()
if remaining:
    print("⚠ 仍有进程存在:")
    print(remaining)
else:
    print("✓ 所有相关进程已清理\n")

# 检查端口
stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep -E '(8000|10000)'")
ports = stdout.read().decode('utf-8').strip()
if ports:
    print("⚠ 端口仍被占用:")
    print(ports)
else:
    print("✓ 端口已释放\n")

print("=" * 60)
print("2. 启动新服务")
print("=" * 60)

stdin, stdout, stderr = ssh.exec_command("bash -c 'cd ~/qiniu-qvs-notifier-test && ./venv/bin/python run_web_v2.py > ~/qvs-final.log 2>&1 &'")
stdout.read()

print("等待 12 秒让服务完全启动...")
time.sleep(12)

print("\n" + "=" * 60)
print("3. 验证新服务")
print("=" * 60)

stdin, stdout, stderr = ssh.exec_command("ps aux | grep '[r]un_web_v2.py'")
ps_result = stdout.read().decode('utf-8')
if ps_result.strip():
    print("✓ 服务正在运行:")
    print(ps_result)
else:
    print("✗ 服务未运行")

stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep 10000")
port_result = stdout.read().decode('utf-8')
if port_result.strip():
    print("\n✓ 端口 10000 正在监听:")
    print(port_result)
else:
    print("\n✗ 端口 10000 未监听")

stdin, stdout, stderr = ssh.exec_command("tail -30 ~/qvs-final.log")
log = stdout.read().decode('utf-8')
print("\n服务日志:")
print(log)

stdin, stdout, stderr = ssh.exec_command("curl -s -o /dev/null -w '%{http_code}' http://localhost:10000")
http_code = stdout.read().decode('utf-8').strip()
print(f"\nHTTP 测试: {http_code}")

print("\n" + "=" * 60)
print(f"✓ 请测试: http://{HOST}:10000")
print("=" * 60)

ssh.close()
