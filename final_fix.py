#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""彻底修复权限并重置"""
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

print("1. 强制停止所有服务")
commands = [
    f"echo {PASSWORD} | sudo -S pkill -9 -f 'run_web_v2'",
    f"echo {PASSWORD} | sudo -S pkill -9 -f 'qiniu-qvs-notifier-test'",
]
for cmd in commands:
    ssh.exec_command(cmd)
time.sleep(3)
print("✓ 已停止\n")

print("2. 删除数据并修复权限")
ssh.exec_command(f"echo {PASSWORD} | sudo -S rm -rf ~/.qvs-test")
ssh.exec_command("mkdir -p ~/.qvs-test")
ssh.exec_command("chmod 755 ~/.qvs-test")
time.sleep(1)
print("✓ 数据目录已重建\n")

print("3. 启动服务")
ssh.exec_command("bash -c 'cd ~/qiniu-qvs-notifier-test && ./venv/bin/python run_web_v2.py > ~/qvs.log 2>&1 &'")
time.sleep(12)

stdin, stdout, stderr = ssh.exec_command("ps aux | grep '[r]un_web_v2.py'")
ps_out = stdout.read().decode('utf-8')
if ps_out.strip():
    print("✓ 服务运行中\n")
else:
    print("✗ 服务未启动\n")

print("4. 创建管理员")
time.sleep(2)
cmd = "curl -X POST http://localhost:10000/api/init/setup -H 'Content-Type: application/json' -d '{\"username\":\"admin\",\"password\":\"admin123456\"}'"
stdin, stdout, stderr = ssh.exec_command(cmd)
result = stdout.read().decode('utf-8')
print(result)

if "success" in result:
    print("\n✓ 管理员创建成功！")
    print("\n" + "="*60)
    print("登录信息:")
    print("="*60)
    print(f"URL: http://{HOST}:10000")
    print("用户名: admin")
    print("密码: admin123456")
    print("="*60)
else:
    print("\n查看日志:")
    stdin, stdout, stderr = ssh.exec_command("tail -30 ~/qvs.log")
    print(stdout.read().decode('utf-8'))

ssh.close()
