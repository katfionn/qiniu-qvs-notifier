#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""使用虚拟环境的部署脚本"""
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

    exit_status = stdout.channel.recv_exit_status()
    return exit_status

def main():
    print("=" * 60)
    print("远程服务器部署测试 (使用虚拟环境)")
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
    print("2. 上传代码")
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
                if item.endswith('.pyc') or item in ['.gitignore']:
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

    files = ['run_web_v2.py', 'requirements.txt']
    for f in files:
        sftp.put(os.path.join(local_base, f), f"/home/{USERNAME}/qiniu-qvs-notifier-test/{f}")
        print(f"   ✓ {f}")

    for d in ['qvs_notifier', 'web']:
        try:
            sftp.mkdir(f"/home/{USERNAME}/qiniu-qvs-notifier-test/{d}")
        except:
            pass
        upload_recursive(os.path.join(local_base, d), f"/home/{USERNAME}/qiniu-qvs-notifier-test/{d}")
        print(f"   ✓ {d}/")

    sftp.close()

    # 3. 创建虚拟环境
    print("\n" + "=" * 60)
    print("3. 创建虚拟环境")
    print("=" * 60)
    run_command(ssh, "cd ~/qiniu-qvs-notifier-test && python3 -m venv venv")

    # 4. 安装依赖
    print("\n" + "=" * 60)
    print("4. 安装依赖")
    print("=" * 60)
    run_command(ssh, "cd ~/qiniu-qvs-notifier-test && ./venv/bin/pip install -r requirements.txt")

    # 5. 创建配置
    print("\n" + "=" * 60)
    print("5. 创建配置")
    print("=" * 60)
    env_config = """QVS_DATA_DIR=/home/claudetest/.qvs-test
WEB_PORT=10000
SECRET_KEY=test-secret-key-12345-qvs-notifier"""
    run_command(ssh, f"cat > ~/qiniu-qvs-notifier-test/.env << 'EOF'\n{env_config}\nEOF")

    # 6. 启动服务
    print("\n" + "=" * 60)
    print("6. 启动 Web 服务")
    print("=" * 60)
    run_command(ssh, "cd ~/qiniu-qvs-notifier-test && nohup ./venv/bin/python run_web_v2.py > ~/qvs-test.log 2>&1 &")

    print("\n等待 8 秒...")
    time.sleep(8)

    # 7. 检查状态
    print("\n" + "=" * 60)
    print("7. 检查服务状态")
    print("=" * 60)
    run_command(ssh, "ps aux | grep 'qiniu-qvs-notifier-test' | grep -v grep")

    # 8. 查看日志
    print("\n" + "=" * 60)
    print("8. 查看启动日志")
    print("=" * 60)
    run_command(ssh, "tail -50 ~/qvs-test.log")

    # 9. 测试端口
    print("\n" + "=" * 60)
    print("9. 测试端口监听")
    print("=" * 60)
    run_command(ssh, "ss -tlnp | grep 10000 || netstat -tlnp | grep 10000")

    print("\n" + "=" * 60)
    print("部署完成！")
    print("=" * 60)
    print(f"\n✓ 访问地址: http://{HOST}:10000")
    print("\n首次访问将自动创建管理员账号")
    print("请在浏览器中打开上述地址测试")

    ssh.close()

if __name__ == "__main__":
    main()
