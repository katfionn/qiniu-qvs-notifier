#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""使用 screen 启动服务"""
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

# 清理旧进程和 screen 会话
print("清理旧进程...")
stdin, stdout, stderr = ssh.exec_command(f"echo {PASSWORD} | sudo -S pkill -f 'qiniu-qvs-notifier-test' || true", get_pty=True)
stdout.read()
stdin, stdout, stderr = ssh.exec_command("screen -ls | grep qvs-web | cut -d. -f1 | awk '{print $1}' | xargs -I {} screen -X -S {} quit || true", get_pty=True)
stdout.read()

time.sleep(2)

print("=" * 60)
print("启动 Web 服务（使用 screen 会话）")
print("=" * 60)

# 使用 screen 启动服务
cmd = "cd ~/qiniu-qvs-notifier-test && screen -dmS qvs-web bash -c './venv/bin/python run_web_v2.py 2>&1 | tee ~/qvs-web.log'"
stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
stdout.read()

print("\n等待 8 秒让服务启动...")
time.sleep(8)

# 检查进程
print("\n检查服务状态：")
stdin, stdout, stderr = ssh.exec_command("ps aux | grep '[v]env/bin/python run_web_v2.py'", get_pty=True)
result = stdout.read().decode('utf-8')
if result.strip():
    print("✓ 服务正在运行")
    print(result)
else:
    print("✗ 服务未运行")

# 检查端口
print("\n检查端口监听：")
stdin, stdout, stderr = ssh.exec_command("ss -tlnp | grep 10000 || netstat -tlnp 2>/dev/null | grep 10000 || true", get_pty=True)
port_result = stdout.read().decode('utf-8')
if '10000' in port_result:
    print("✓ 端口 10000 正在监听")
    print(port_result)
else:
    print("⚠ 端口 10000 未检测到")

# 查看日志
print("\n服务日志（最后 20 行）：")
stdin, stdout, stderr = ssh.exec_command("tail -20 ~/qvs-web.log", get_pty=True)
log_content = stdout.read().decode('utf-8')
print(log_content)

# 测试 HTTP 访问
print("\n测试 HTTP 访问：")
stdin, stdout, stderr = ssh.exec_command("curl -s -o /dev/null -w '%{http_code}' http://localhost:10000", get_pty=True)
http_code = stdout.read().decode('utf-8').strip()
if '200' in http_code or '30' in http_code:
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
print("\n📝 请在浏览器中打开上述地址进行审核")
print("\n💡 提示:")
print("   - 查看实时日志: tail -f ~/qvs-web.log")
print("   - 进入 screen 会话: screen -r qvs-web")
print("   - 停止服务: screen -X -S qvs-web quit")

ssh.close()
