#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""完整部署并测试脚本"""
import paramiko
import time
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

def run_command(ssh, command, sudo=False):
    """执行命令并实时显示输出"""
    if sudo:
        command = f"echo {PASSWORD} | sudo -S {command}"

    print(f"\n$ {command}")
    stdin, stdout, stderr = ssh.exec_command(command, get_pty=True)

    while True:
        line = stdout.readline()
        if not line:
            break
        print(line.rstrip())

    return stdout.channel.recv_exit_status()

def main():
    print("=" * 60)
    print("完整部署测试")
    print("=" * 60)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, PORT, USERNAME, PASSWORD)
    print("✓ SSH 连接成功\n")

    # 1. 清理旧部署
    print("\n" + "=" * 60)
    print("1. 清理旧部署")
    print("=" * 60)
    run_command(ssh, "pkill -f 'qiniu-qvs-notifier-test' || true", sudo=True)
    run_command(ssh, "rm -rf ~/qiniu-qvs-notifier-test ~/.qvs-test")

    # 2. 创建目录并上传代码
    print("\n" + "=" * 60)
    print("2. 上传最新代码")
    print("=" * 60)
    run_command(ssh, "mkdir -p ~/qiniu-qvs-notifier-test")

    local_base = "e:/0708123/Projects/qiniu-qvs-notifier"
    sftp = ssh.open_sftp()

    def upload_recursive(local_path, remote_path):
        """递归上传目录"""
        for item in os.listdir(local_path):
            local_item = os.path.join(local_path, item)
            remote_item = f"{remote_path}/{item}"

            if os.path.isfile(local_item):
                if item.endswith('.pyc'):
                    continue
                try:
                    sftp.put(local_item, remote_item)
                except Exception as e:
                    print(f"   ✗ {remote_item}: {e}")
            elif os.path.isdir(local_item):
                if item in ['__pycache__', '.git', '.venv', 'venv', 'node_modules', '.claude']:
                    continue
                try:
                    sftp.mkdir(remote_item)
                except:
                    pass
                upload_recursive(local_item, remote_item)

    # 上传关键文件
    files = ['run_web_v2.py', 'requirements.txt']
    for f in files:
        sftp.put(os.path.join(local_base, f), f"/home/{USERNAME}/qiniu-qvs-notifier-test/{f}")
        print(f"   ✓ {f}")

    # 上传目录
    for d in ['qvs_notifier', 'web']:
        try:
            sftp.mkdir(f"/home/{USERNAME}/qiniu-qvs-notifier-test/{d}")
        except:
            pass
        upload_recursive(os.path.join(local_base, d), f"/home/{USERNAME}/qiniu-qvs-notifier-test/{d}")
        print(f"   ✓ {d}/")

    sftp.close()

    # 3. 创建虚拟环境（如果不存在）
    print("\n" + "=" * 60)
    print("3. 准备虚拟环境")
    print("=" * 60)
    run_command(ssh, "cd ~/qiniu-qvs-notifier-test && [ -d venv ] || python3 -m venv venv")
    run_command(ssh, "cd ~/qiniu-qvs-notifier-test && ./venv/bin/pip install --q -r requirements.txt")

    # 4. 创建配置（含必要的环境变量）
    print("\n" + "=" * 60)
    print("4. 创建配置")
    print("=" * 60)
    env_config = """QVS_DATA_DIR=/home/claudetest/.qvs-test
WEB_PORT=10000
SECRET_KEY=test-secret-key-12345-qvs-notifier
QVS_ADMIN_USERNAME=admin
QVS_ADMIN_PASSWORD=admin123456"""
    run_command(ssh, f"cat > ~/qiniu-qvs-notifier-test/.env << 'EOF'\n{env_config}\nEOF")

    # 5. 启动服务（后台）
    print("\n" + "=" * 60)
    print("5. 启动 Web 服务")
    print("=" * 60)
    run_command(ssh, "cd ~/qiniu-qvs-notifier-test && nohup ./venv/bin/python run_web_v2.py > ~/qvs-test.log 2>&1 &")

    print("\n等待 10 秒让服务启动...")
    time.sleep(10)

    # 6. 检查状态
    print("\n" + "=" * 60)
    print("6. 检查服务状态")
    print("=" * 60)
    run_command(ssh, "ps aux | grep 'qiniu-qvs-notifier-test' | grep -v grep")

    # 7. 查看日志
    print("\n" + "=" * 60)
    print("7. 查看启动日志")
    print("=" * 60)
    run_command(ssh, "tail -50 ~/qvs-test.log")

    # 8. 测试端口
    print("\n" + "=" * 60)
    print("8. 测试端口监听")
    print("=" * 60)
    run_command(ssh, "ss -tlnp | grep 10000")

    # 9. 测试HTTP请求
    print("\n" + "=" * 60)
    print("9. 测试 HTTP 访问")
    print("=" * 60)
    run_command(ssh, "curl -I http://localhost:10000")

    print("\n" + "=" * 60)
    print("部署完成！")
    print("=" * 60)
    print(f"\n✓ 访问地址: http://{HOST}:10000")
    print("\n默认管理员账号:")
    print("  用户名: admin")
    print("  密码: admin123456")
    print("\n请在浏览器中打开上述地址进行测试")

    ssh.close()

if __name__ == "__main__":
    main()
