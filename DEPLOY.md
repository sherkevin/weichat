# WeChat-Archiver 一键部署指南

## 📦 项目说明

WeChat-Archiver 是一个微信公众号文章自动归档系统，支持：
- ✅ 自动抓取公众号文章
- ✅ 转换为 Markdown 格式
- ✅ 下载图片到本地（防盗链处理）
- ✅ 按分组存储
- ✅ 自动推送到 GitHub
- ✅ Web 管理界面
- ✅ 定时自动更新

---

## 🚀 快速部署（全新服务器）

### 方法一：一键部署脚本（推荐）

```bash
# 1. 下载项目
git clone https://github.com/sherkevin/weichat.git
cd weichat

# 2. 运行部署脚本
sudo bash deploy.sh
```

**脚本会自动完成**：
- 安装 Docker 和 Docker Compose
- 配置 Docker 镜像加速
- 创建项目目录和配置文件
- 配置 GitHub SSH 密钥
- 启动所有服务（wewe-rss + wechat-archiver）
- 配置定时任务（每6小时运行一次）

---

### 方法二：手动部署

#### 1. 安装 Docker

**Ubuntu/Debian:**
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

**CentOS/RHEL:**
```bash
sudo yum install -y yum-utils
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo yum install -y docker-ce docker-ce-cli containerd.io
```

启动 Docker：
```bash
sudo systemctl start docker
sudo systemctl enable docker
```

#### 2. 启动服务

```bash
cd weichat
docker-compose -f docker-compose.prod.yml up -d --build
```

#### 3. 配置 GitHub（可选，如果需要推送）

```bash
# 生成 SSH 密钥
ssh-keygen -t ed25519 -C "your-email@example.com"

# 查看公钥并添加到 GitHub
cat ~/.ssh/id_ed25519.pub
```

访问 https://github.com/settings/keys 添加公钥。

---

## 📋 配置步骤

### 1. 访问 wewe-rss 管理界面

```
http://<服务器IP>:4000/dash
```

**操作步骤**：
1. 输入密码（默认：`admin123`）
2. 点击「账号管理」→「添加账号」
3. 扫码登录微信读书
4. 点击「公众号源」→「添加」
5. 粘贴公众号文章链接（如：`https://mp.weixin.qq.com/s/xxxxx`）
6. 等待识别并订阅

### 2. 获取 RSS URL

在公众号列表中点击「RSS」按钮，复制生成的链接。

### 3. 访问 Web 管理界面

```
http://<服务器IP>:5000
```

**操作步骤**：
1. 创建分组（如：「科技类」、「论文」）
2. 选择分组
3. 添加 RSS 源：
   - 名称：公众号名称
   - URL：粘贴刚才获取的 RSS 链接

### 4. 修改 GitHub 配置

编辑 `config.yaml`：

```yaml
github_remote_url: "git@github.com:YOUR_USERNAME/YOUR_REPO_NAME.git"
```

重启服务：
```bash
docker-compose -f docker-compose.prod.yml restart wechat-archiver
```

---

## 🧪 测试运行

```bash
# 手动运行归档任务
docker exec wechat-archiver python main.py
```

成功后会看到：
```
✅ 处理分组: 论文
✅ 处理文章: 文章标题
✅ 文章保存成功: /app/data/论文/posts/xxx.md
✅ Git 提交成功
✅ 推送到远程仓库成功
```

---

## 📊 数据存储位置

```
/root/weichat/data/
├── <分组名>/
│   ├── posts/              # Markdown 文章
│   │   ├── 2026-02-04-文章标题.md
│   │   └── ...
│   └── assets/             # 图片文件
│       ├── img_xxx.jpg
│       └── ...
├── wewe-rss/              # wewe-rss 数据
└── .git/                  # Git 仓库
```

---

## ⚙️ 常用命令

### 查看服务状态
```bash
docker ps
```

### 查看日志
```bash
# wewe-rss 日志
docker logs -f wewe-rss

# wechat-archiver 日志
docker logs -f wechat-archiver
```

### 重启服务
```bash
docker-compose -f docker-compose.prod.yml restart
```

### 停止服务
```bash
docker-compose -f docker-compose.prod.yml down
```

### 更新代码
```bash
git pull
docker-compose -f docker-compose.prod.yml up -d --build
```

---

## 🔁 备份与恢复

### 备份

```bash
# 备份配置和数据
tar -czf wechat-archiver-backup-$(date +%Y%m%d).tar.gz \
    config.yaml \
    data/ \
    docker-compose.prod.yml
```

### 恢复（在新服务器上）

```bash
# 1. 解压备份
tar -xzf wechat-archiver-backup-YYYYMMDD.tar.gz

# 2. 运行部署脚本
sudo bash deploy.sh

# 3. 恢复数据
docker-compose -f docker-compose.prod.yml restart
```

---

## 🌐 访问地址

| 服务 | 端口 | 地址 | 用途 |
|------|------|------|------|
| **wewe-rss** | 4000 | `http://<IP>:4000/dash` | 添加公众号，获取 RSS |
| **Web 管理** | 5000 | `http://<IP>:5000` | 管理分组和 RSS 源 |

**注意**：请在云服务器安全组开放 4000 和 5000 端口。

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

MIT License
