#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""启动服务并保持运行"""
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
print("启动 Web 服务（后台运行）")
print("=" * 60)

# 启动服务
stdin, stdout, stderr = ssh.exec_command(
    "cd ~/qiniu-qvs-notifier-test && nohup ./venv/bin/python run_web_v2.py > ~/qvs-web.log 2>&1 &",
    get_pty=True
)
stdout.read()

print("\n等待 5 秒...")
time.sleep(5)

# 检查进程
print("\n检查服务状态：")
stdin, stdout, stderr = ssh.exec_command("ps aux | grep '[q]iniu-qvs-notifier-test'", get_pty=True)
result = stdout.read().decode('utf-8')
if result.strip():
    print("✓ 服务正在运行")
    print(result)
else:
    print("✗ 服务未运行")

# 检查端口
print("\n检查端口监听：")
stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep 10000", get_pty=True)
port_result = stdout.read().decode('utf-8')
if port_result.strip():
    print("✓ 端口 10000 正在监听")
    print(port_result)
else:
    print("✗ 端口 10000 未监听")
    print("\n查看日志：")
    stdin, stdout, stderr = ssh.exec_command("tail -30 ~/qvs-web.log", get_pty=True)
    print(stdout.read().decode('utf-8'))

# 测试 HTTP 访问
print("\n测试 HTTP 访问：")
stdin, stdout, stderr = ssh.exec_command("curl -s -o /dev/null -w '%{http_code}' http://localhost:10000", get_pty=True)
http_code = stdout.read().decode('utf-8').strip()
if '200' in http_code:
    print(f"✓ HTTP 响应正常 (状态码: {http_code})")
else:
    print(f"⚠ HTTP 响应: {http_code}")

print("\n" + "=" * 60)
print("部署完成！")
print("=" * 60)
print(f"\n🌐 访问地址: http://{HOST}:10000")
print("\n👤 管理员账号:")
print("   用户名: admin")
print("   密码: admin123456")
print("\n📝 请在浏览器中打开上述地址进行审核测试")

ssh.close()
