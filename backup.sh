#!/bin/bash
# WeChat-Archiver 打包脚本
# 用于打包整个项目，方便迁移到新服务器

set -e

GREEN='\033[0;32m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

# 获取项目目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="$PROJECT_DIR"
OUTPUT_FILE="$OUTPUT_DIR/wechat-archiver-backup.tar.gz"

log_info "开始打包项目..."

# 检查必要文件
REQUIRED_FILES=(
    "main.py"
    "web_manager.py"
    "requirements.txt"
    "config.yaml"
    "docker-compose.prod.yml"
    "Dockerfile"
    "DEPLOY.md"
    "deploy.sh"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [[ ! -f "$PROJECT_DIR/$file" ]]; then
        echo "警告: 文件不存在 $file"
    fi
done

# 创建临时排除文件
EXCLUDE_FILE="$PROJECT_DIR/.exclude.tmp"
cat > "$EXCLUDE_FILE" <<'EOF'
venv/
__pycache__/
*.pyc
*.pyo
*.pyd
.git/
.gitignore
*.log
logs/*.log
data/posts/*
data/assets/*
data/wewe-rss/*
.DS_Store
Thumbs.db
exclude.tmp
EOF

# 打包项目（排除数据和临时文件）
log_info "打包文件中..."
tar -czf "$OUTPUT_FILE" \
    -X "$EXCLUDE_FILE" \
    -C "$PROJECT_DIR" \
    main.py \
    web_manager.py \
    requirements.txt \
    config.yaml \
    docker-compose.prod.yml \
    Dockerfile \
    run.sh \
    update_crontab.sh \
    deploy.sh \
    README.md \
    DEPLOY.md \
    docs/ \
    data/.git/ \
    data/posts/.gitkeep \
    data/assets/.gitkeep

# 清理临时文件
rm -f "$EXCLUDE_FILE"

log_info "打包完成！"
echo ""
echo "备份文件: $OUTPUT_FILE"
echo "文件大小: $(du -h "$OUTPUT_FILE" | cut -f1)"
echo ""
echo "迁移步骤："
echo "1. 将 $OUTPUT_FILE 传输到新服务器"
echo "2. 在新服务器上解压: tar -xzf $(basename "$OUTPUT_FILE")"
echo "3. 进入目录: cd $(basename "$PROJECT_DIR")"
echo "4. 运行部署: sudo bash deploy.sh"
echo ""
