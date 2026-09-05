#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""简化的远程部署脚本"""
import paramiko
import time
import sys

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

    exit_status = stdout.channel.recv_exit_status()
    return exit_status

def main():
    print("=" * 60)
    print("远程服务器部署测试")
    print("=" * 60)

    # 连接
    print(f"\n连接到 {HOST}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, PORT, USERNAME, PASSWORD)
    print("✓ 连接成功\n")

    # 1. 检查并安装 pip
    print("=" * 60)
    print("1. 检查并安装 pip")
    print("=" * 60)
    run_command(ssh, "python3 -m pip --version || sudo apt-get update && sudo apt-get install -y python3-pip", sudo=True)

    # 2. 清理旧部署
    print("\n" + "=" * 60)
    print("2. 清理旧部署")
    print("=" * 60)
    run_command(ssh, "pkill -f 'qiniu-qvs-notifier-test' || true", sudo=True)
    run_command(ssh, "rm -rf ~/qiniu-qvs-notifier-test ~/.qvs-test")

    # 3. 创建目录并上传代码
    print("\n" + "=" * 60)
    print("3. 上传代码")
    print("=" * 60)
    run_command(ssh, "mkdir -p ~/qiniu-qvs-notifier-test")

    # 上传文件
    import os
    local_base = "e:/0708123/Projects/qiniu-qvs-notifier"
    sftp = ssh.open_sftp()

    def upload_recursive(local_path, remote_path):
        """递归上传目录"""
        for item in os.listdir(local_path):
            local_item = os.path.join(local_path, item)
            remote_item = f"{remote_path}/{item}"

            if os.path.isfile(local_item):
                # 跳过不需要的文件
                if item.endswith('.pyc') or item in ['.git', '.gitignore', 'test_deploy.py', 'deploy_simple.py']:
                    continue
                try:
                    sftp.put(local_item, remote_item)
                    print(f"   ✓ {remote_item}")
                except Exception as e:
                    print(f"   ✗ {remote_item}: {e}")
            elif os.path.isdir(local_item):
                # 跳过不需要的目录
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

    sftp.close()

    # 4. 安装依赖
    print("\n" + "=" * 60)
    print("4. 安装依赖")
    print("=" * 60)
    run_command(ssh, "cd ~/qiniu-qvs-notifier-test && python3 -m pip install --user -r requirements.txt")

    # 5. 创建配置
    print("\n" + "=" * 60)
    print("5. 创建配置")
    print("=" * 60)
    env_config = """QVS_DATA_DIR=/home/claudetest/.qvs-test
WEB_PORT=10000
SECRET_KEY=test-secret-key-12345
"""
    run_command(ssh, f"cat > ~/qiniu-qvs-notifier-test/.env << 'EOF'\n{env_config}\nEOF")

    # 6. 启动服务
    print("\n" + "=" * 60)
    print("6. 启动 Web 服务")
    print("=" * 60)
    run_command(ssh, "cd ~/qiniu-qvs-notifier-test && nohup python3 run_web_v2.py > ~/qvs-test.log 2>&1 &")

    print("\n等待 5 秒...")
    time.sleep(5)

    # 7. 检查状态
    print("\n" + "=" * 60)
    print("7. 检查服务状态")
    print("=" * 60)
    run_command(ssh, "ps aux | grep run_web_v2.py | grep -v grep")

    print("\n" + "=" * 60)
    print("8. 查看日志")
    print("=" * 60)
    run_command(ssh, "tail -30 ~/qvs-test.log")

    print("\n" + "=" * 60)
    print("部署完成！")
    print("=" * 60)
    print(f"\n访问地址: http://{HOST}:10000")
    print("\n管理员账号将在首次访问时创建")

    ssh.close()

if __name__ == "__main__":
    main()
