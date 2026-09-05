#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复后台启动脚本"""
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

# 清理
print("清理旧进程...")
stdin, stdout, stderr = ssh.exec_command(f"echo {PASSWORD} | sudo -S pkill -f 'qiniu-qvs-notifier-test' || true", get_pty=True)
stdout.read()
time.sleep(2)

print("=" * 60)
print("启动 Web 服务")
print("=" * 60)

# 使用 setsid 启动后台进程
cmd = """
cd /home/claudetest/qiniu-qvs-notifier-test && \
setsid /home/claudetest/qiniu-qvs-notifier-test/venv/bin/python \
/home/claudetest/qiniu-qvs-notifier-test/run_web_v2.py \
> /home/claudetest/qvs-web.log 2>&1 &
"""
stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=False)
stdout.read()

print("\n等待 10 秒让服务启动...")
time.sleep(10)

# 检查进程
print("\n检查服务状态：")
stdin, stdout, stderr = ssh.exec_command("ps aux | grep '[r]un_web_v2.py'", get_pty=True)
result = stdout.read().decode('utf-8')
if result.strip():
    print("✓ 服务正在运行")
    print(result)
else:
    print("⚠ 服务进程未找到")

# 检查端口
print("\n检查端口监听：")
stdin, stdout, stderr = ssh.exec_command("ss -tlnp 2>/dev/null | grep 10000 || netstat -tlnp 2>/dev/null | grep 10000 || lsof -i:10000 2>/dev/null || true", get_pty=True)
port_result = stdout.read().decode('utf-8')
if '10000' in port_result:
    print("✓ 端口 10000 正在监听")
    print(port_result)
else:
    print("⚠ 端口 10000 未监听")

# 查看日志
print("\n服务日志（最后 30 行）：")
stdin, stdout, stderr = ssh.exec_command("tail -30 /home/claudetest/qvs-web.log", get_pty=True)
log_content = stdout.read().decode('utf-8')
print(log_content)

# 测试 HTTP
print("\n测试 HTTP 访问：")
stdin, stdout, stderr = ssh.exec_command("curl -s -o /dev/null -w '%{http_code}' http://localhost:10000 2>&1", get_pty=True)
http_code = stdout.read().decode('utf-8').strip()
print(f"HTTP 响应码: {http_code}")

print("\n" + "=" * 60)
print("部署测试完成！")
print("=" * 60)
print(f"\n🌐 访问地址: http://{HOST}:10000")
print("\n👤 默认管理员账号:")
print("   用户名: admin")
print("   密码: admin123456")
print("\n📝 请在浏览器中访问上述 URL 进行审核")

ssh.close()
