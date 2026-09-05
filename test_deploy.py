#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""远程服务器部署测试脚本"""
import paramiko
import time
import sys
import os

# 设置输出编码
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# SSH 连接配置
HOST = "claw.fe2fe.top"
PORT = 22
USERNAME = "claudetest"
PASSWORD = "ABC1986720abc"

def execute_command(ssh, command, print_output=True):
    """执行命令并返回输出"""
    stdin, stdout, stderr = ssh.exec_command(command)
    exit_status = stdout.channel.recv_exit_status()
    output = stdout.read().decode('utf-8')
    error = stderr.read().decode('utf-8')

    if print_output:
        if output:
            print(output)
        if error:
            print(f"Error: {error}", file=sys.stderr)

    return exit_status, output, error

def main():
    print("=" * 60)
    print("开始远程服务器部署测试")
    print("=" * 60)

    # 连接服务器
    print(f"\n1. 连接到远程服务器 {HOST}:{PORT}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(HOST, PORT, USERNAME, PASSWORD)
        print("✓ SSH 连接成功\n")
    except Exception as e:
        print(f"✗ SSH 连接失败: {e}")
        return

    # 检查环境
    print("2. 检查服务器环境...")
    execute_command(ssh, "python3 --version")
    execute_command(ssh, "git --version")
    execute_command(ssh, "pip3 --version")

    # 清理旧环境
    print("\n3. 清理旧部署...")
    execute_command(ssh, "pkill -f run_web_v2.py || true")
    execute_command(ssh, "rm -rf ~/qiniu-qvs-notifier-test")
    execute_command(ssh, "rm -rf ~/.qvs-test")

    # 克隆代码（从本地推送当前修改）
    print("\n4. 准备代码...")
    local_project_dir = "e:/0708123/Projects/qiniu-qvs-notifier"

    # 创建临时目录并上传代码
    execute_command(ssh, "mkdir -p ~/qiniu-qvs-notifier-test")

    print("   上传代码到服务器...")
    sftp = ssh.open_sftp()

    # 需要上传的文件和目录
    files_to_upload = [
        "run_web_v2.py",
        "requirements.txt",
    ]

    dirs_to_upload = [
        "qvs_notifier",
        "web",
    ]

    import os
    import glob

    # 上传单个文件
    for file_path in files_to_upload:
        local_file = os.path.join(local_project_dir, file_path)
        remote_file = f"~/qiniu-qvs-notifier-test/{file_path}"

        try:
            sftp.put(local_file, remote_file.replace("~", f"/home/{USERNAME}"))
            print(f"   ✓ {file_path}")
        except Exception as e:
            print(f"   ✗ {file_path}: {e}")

    # 上传目录
    def upload_dir(local_dir, remote_dir):
        """递归上传目录"""
        for root, dirs, files in os.walk(local_dir):
            # 跳过 __pycache__
            if "__pycache__" in root:
                continue

            for file in files:
                if file.endswith(".pyc"):
                    continue

                local_file = os.path.join(root, file)
                rel_path = os.path.relpath(local_file, local_project_dir)
                remote_file = f"/home/{USERNAME}/qiniu-qvs-notifier-test/{rel_path}".replace("\\", "/")

                # 创建远程目录
                remote_file_dir = "/".join(remote_file.split("/")[:-1])
                execute_command(ssh, f"mkdir -p {remote_file_dir}", print_output=False)

                try:
                    sftp.put(local_file, remote_file)
                except Exception as e:
                    print(f"   ✗ {rel_path}: {e}")

    for dir_name in dirs_to_upload:
        local_dir = os.path.join(local_project_dir, dir_name)
        upload_dir(local_dir, f"~/qiniu-qvs-notifier-test/{dir_name}")
        print(f"   ✓ {dir_name}/")


    sftp.close()

    # 安装依赖
    print("\n5. 安装依赖...")
    execute_command(ssh, "cd ~/qiniu-qvs-notifier-test && python3 -m pip install --user -r requirements.txt")

    # 配置环境变量
    print("\n6. 创建配置文件...")
    env_content = """QVS_DATA_DIR=/home/claudetest/.qvs-test
WEB_PORT=10000
SECRET_KEY=test-secret-key-for-deployment-test-only
"""
    execute_command(ssh, f'echo "{env_content}" > ~/qiniu-qvs-notifier-test/.env')

    # 运行安装向导（非交互式）
    print("\n7. 初始化数据库和管理员账号...")
    # 由于是首次运行，会触发安装向导
    # 我们需要通过环境变量配置

    # 启动 Web 服务
    print("\n8. 启动 Web 服务...")
    execute_command(ssh, "cd ~/qiniu-qvs-notifier-test && nohup python3 run_web_v2.py > ~/qvs-web.log 2>&1 &")

    print("   等待服务启动...")
    time.sleep(5)

    # 检查服务状态
    print("\n9. 检查服务状态...")
    status, output, error = execute_command(ssh, "ps aux | grep run_web_v2.py | grep -v grep")

    if "run_web_v2.py" in output:
        print("✓ Web 服务已启动")
        print(f"\n服务访问地址: http://{HOST}:10000")
        print("\n管理员账号:")
        print("  用户名: admin")
        print("  密码: (在安装向导中设置的密码)")

        # 显示日志
        print("\n10. 查看服务日志 (最后 20 行):")
        execute_command(ssh, "tail -20 ~/qvs-web.log")
    else:
        print("✗ Web 服务启动失败")
        print("\n查看错误日志:")
        execute_command(ssh, "tail -50 ~/qvs-web.log")

    ssh.close()
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
