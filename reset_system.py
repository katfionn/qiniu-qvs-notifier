#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""完全重置系统并创建新管理员"""
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
print("1. 停止服务")
print("=" * 60)
ssh.exec_command(f"echo {PASSWORD} | sudo -S pkill -9 -f 'qiniu-qvs-notifier-test'")
time.sleep(2)
print("✓ 服务已停止\n")

print("=" * 60)
print("2. 删除所有数据（重置系统）")
print("=" * 60)
ssh.exec_command("rm -rf ~/.qvs-test")
print("✓ 数据已清除\n")

print("=" * 60)
print("3. 启动服务")
print("=" * 60)
ssh.exec_command("bash -c 'cd ~/qiniu-qvs-notifier-test && ./venv/bin/python run_web_v2.py > ~/qvs-reset.log 2>&1 &'")
time.sleep(10)

stdin, stdout, stderr = ssh.exec_command("ps aux | grep '[r]un_web_v2.py'")
if stdout.read().decode('utf-8').strip():
    print("✓ 服务已启动\n")

print("=" * 60)
print("4. 创建管理员账号")
print("=" * 60)

# 创建管理员
cmd = '''curl -X POST http://localhost:10000/api/init/setup \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123456"}' '''

stdin, stdout, stderr = ssh.exec_command(cmd)
result = stdout.read().decode('utf-8')
print(result)

if "success" in result:
    print("\n✓ 管理员账号创建成功！")
else:
    print("\n⚠ 创建失败，查看日志：")
    stdin, stdout, stderr = ssh.exec_command("tail -20 ~/qvs-reset.log")
    print(stdout.read().decode('utf-8'))

print("\n" + "=" * 60)
print("重置完成！")
print("=" * 60)
print(f"\n🌐 访问地址: http://{HOST}:10000")
print("\n👤 管理员账号:")
print("   用户名: admin")
print("   密码: admin123456")
print("\n请刷新浏览器并登录")

ssh.close()
