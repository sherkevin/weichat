#!/bin/bash
# WeChat-Archiver 一键部署脚本
# 适用于全新的 Linux 服务器（Ubuntu 20.04+, CentOS 7+）
# 用法: bash deploy.sh

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为 root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "此脚本需要 root 权限运行"
        log_info "请使用: sudo bash deploy.sh"
        exit 1
    fi
}

# 检测操作系统
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$ID
        OS_VERSION=$VERSION_ID
    else
        log_error "无法检测操作系统"
        exit 1
    fi
    log_info "检测到操作系统: $OS $OS_VERSION"
}

# 安装 Docker
install_docker() {
    if command -v docker &> /dev/null; then
        log_info "Docker 已安装"
        return
    fi

    log_info "安装 Docker..."

    case $OS in
        ubuntu|debian)
            apt-get update -qq
            apt-get install -y -qq ca-certificates curl gnupg
            install -m 0755 -d /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/${OS}/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            chmod a+r /etc/apt/keyrings/docker.gpg
            echo \
              "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/${OS} \
              $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
              tee /etc/apt/sources.list.d/docker.list > /dev/null
            apt-get update -qq
            apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose
            ;;
        centos|rhel|rocky|almalinux)
            yum install -y -q yum-utils
            yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            yum install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin
            ;;
        *)
            log_error "不支持的操作系统: $OS"
            exit 1
            ;;
    esac

    systemctl start docker
    systemctl enable docker

    log_info "Docker 安装完成"
}

# 配置 Docker 镜像（中国大陆用户）
configure_docker_mirror() {
    log_info "配置 Docker 镜像加速（中国大陆）..."

    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json <<EOF
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://dockerproxy.com"
  ]
}
EOF

    systemctl daemon-reload
    systemctl restart docker

    log_info "Docker 镜像配置完成"
}

# 创建项目目录
setup_project() {
    log_info "创建项目目录..."

    mkdir -p data/{posts,assets,wewe-rss}
    mkdir -p logs

    # 创建默认配置文件
    if [[ ! -f config.yaml ]]; then
        log_info "创建默认配置文件..."
        cat > config.yaml <<'EOF'
# WeChat-Archiver 配置文件

github_repo_path: "/app/data"
github_remote_url: "git@github.com:YOUR_USERNAME/YOUR_REPO_NAME.git"
github_branch: "main"
git_user_name: "WeChat Archiver"
git_user_email: "archiver@localhost"

# 分组配置
groups:
  - name: "示例分组"
    feeds:
      # 添加 wewe-rss 的公众号 RSS 源
      # - name: "公众号名称"
      #   url: "http://wewe-rss:4000/feeds/xxxxx.atom"

# 抓取配置
fetch:
  max_articles: 10
  timeout: 30
  max_retries: 3
  retry_delay: 5

# 存储配置
storage:
  data_dir: "/app/data"
  posts_dir: "posts"
  assets_dir: "assets"
  date_format: "%Y-%m-%d"

# 图片下载配置
image:
  download_enabled: true
  download_timeout: 30
  max_size_mb: 10

# 日志配置
logging:
  level: "INFO"
EOF
    fi

    log_info "项目目录创建完成"
}

# 配置 GitHub SSH
setup_github_ssh() {
    log_info "配置 GitHub SSH..."

    if [[ ! -f ~/.ssh/id_ed25519 ]]; then
        log_info "生成 SSH 密钥..."
        ssh-keygen -t ed25519 -C "wechat-archiver@$(hostname)" -f ~/.ssh/id_ed25519 -N ""
        log_info "SSH 密钥已生成"
        echo ""
        echo "请将以下公钥添加到 GitHub:"
        echo "----------------------------------------"
        cat ~/.ssh/id_ed25519.pub
        echo "----------------------------------------"
        echo "GitHub SSH Keys 设置: https://github.com/settings/keys"
        echo ""
    else
        log_info "SSH 密钥已存在"
    fi

    # 测试 SSH 连接
    if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
        log_info "GitHub SSH 连接成功"
    else
        log_warn "GitHub SSH 连接失败，请检查密钥配置"
    fi
}

# 启动服务
start_services() {
    log_info "构建并启动服务..."

    # 拉取 wewe-rss 镜像
    log_info "拉取 wewe-rss 镜像..."
    docker pull cooderl/wewe-rss-sqlite:latest

    # 构建并启动服务
    log_info "启动 Docker 服务..."
    docker-compose -f docker-compose.prod.yml up -d --build

    # 等待服务启动
    log_info "等待服务启动..."
    sleep 10

    # 检查服务状态
    if docker ps | grep -q wewe-rss; then
        log_info "✅ wewe-rss 启动成功"
    else
        log_error "wewe-rss 启动失败"
    fi

    if docker ps | grep -q wechat-archiver; then
        log_info "✅ wechat-archiver 启动成功"
    else
        log_error "wechat-archiver 启动失败"
    fi
}

# 配置 Crontab
setup_crontab() {
    log_info "配置 Crontab 定时任务..."

    # 每6小时运行一次归档任务
    (crontab -l 2>/dev/null | grep -v "wechat-archiver"; echo "0 */6 * * * docker exec wechat-archiver python main.py >> /app/logs/cron.log 2>&1") | crontab -

    log_info "Crontab 已配置为每6小时运行一次"
}

# 显示访问信息
show_access_info() {
    echo ""
    echo "=================================================="
    echo "  🎉 部署完成！"
    echo "=================================================="
    echo ""
    echo "📱 访问地址："
    echo "   - wewe-rss 管理界面: http://<服务器IP>:4000/dash"
    echo "   - Web 管理界面:     http://<服务器IP>:5000"
    echo ""
    echo "📝 下一步操作："
    echo "   1. 访问 wewe-rss (端口 4000) 登录微信读书并添加公众号"
    echo "   2. 获取公众号的 RSS URL"
    echo "   3. 访问 Web 管理界面 (端口 5000) 添加 RSS 源"
    echo "   4. 运行测试: docker exec wechat-archiver python main.py"
    echo ""
    echo "📊 数据存储位置："
    echo "   - 文章: ./data/<分组名>/posts/"
    echo "   - 图片: ./data/<分组名>/assets/"
    echo ""
    echo "🔧 常用命令："
    echo "   - 查看日志: docker logs -f wewe-rss"
    echo "   - 查看日志: docker logs -f wechat-archiver"
    echo "   - 重启服务: docker-compose -f docker-compose.prod.yml restart"
    echo "   - 停止服务: docker-compose -f docker-compose.prod.yml down"
    echo ""
    echo "⚠️  重要提醒："
    echo "   - 请在华为云安全组开放端口: 4000, 5000"
    echo "   - 请修改 config.yaml 中的 GitHub 仓库 URL"
    echo "   - 建议定期备份 ./data 目录"
    echo ""
    echo "=================================================="
}

# 主函数
main() {
    echo "=================================================="
    echo "  WeChat-Archiver 一键部署脚本"
    echo "=================================================="
    echo ""

    check_root
    detect_os
    install_docker
    configure_docker_mirror
    setup_project
    setup_github_ssh
    start_services
    setup_crontab
    show_access_info
}

# 运行主函数
main "$@"
