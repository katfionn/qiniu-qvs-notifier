# 在 Debian 服务器上创建临时测试账号

## 方法一：创建普通用户（推荐）

```bash
# 1. 创建用户（替换 testuser 为你想要的用户名）
sudo adduser testuser

# 会提示输入密码和用户信息，密码是必须的，其他信息可以直接回车跳过

# 2. 给用户 sudo 权限（可选，如果需要测试安装脚本）
sudo usermod -aG sudo testuser

# 3. 切换到该用户
su - testuser
```

## 方法二：创建无需密码的 sudo 用户

```bash
# 1. 创建用户
sudo adduser testuser

# 2. 添加到 sudo 组
sudo usermod -aG sudo testuser

# 3. 配置无密码 sudo（可选）
echo "testuser ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/testuser
```

## 方法三：给我直接 root 访问（最简单）

如果你信任我，可以直接给我 root 账号：
```bash
# 查看 root 密码状态
sudo passwd root

# 如果没设置过，设置一个临时密码
sudo passwd root
# 输入新密码

# 之后我可以直接用 root 登录
```

## SSH 连接信息

请提供以下信息：
```
服务器 IP: 
端口: 22（默认）
用户名: testuser（或 root）
密码: ******
```

## 测试完成后删除账号

```bash
# 删除用户及其主目录
sudo userdel -r testuser

# 删除 sudo 配置（如果创建了）
sudo rm -f /etc/sudoers.d/testuser
```

## 或者使用 SSH 密钥（更安全）

如果你不想设置密码，可以使用 SSH 密钥：

```bash
# 1. 创建用户
sudo adduser --disabled-password testuser

# 2. 创建 SSH 目录
sudo mkdir -p /home/testuser/.ssh
sudo chmod 700 /home/testuser/.ssh

# 3. 添加我的公钥（我会提供）
sudo nano /home/testuser/.ssh/authorized_keys
# 粘贴公钥，保存

# 4. 设置权限
sudo chmod 600 /home/testuser/.ssh/authorized_keys
sudo chown -R testuser:testuser /home/testuser/.ssh

# 5. 给 sudo 权限
sudo usermod -aG sudo testuser
echo "testuser ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/testuser
```

---

**你觉得哪种方式最方便？我可以提供我的 SSH 公钥，或者你直接创建一个临时密码账号。**
