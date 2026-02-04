#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WeChat-Archiver 主程序（支持分组版本）
功能：从 RSS 源抓取微信公众号文章，转换为 Markdown，下载图片，提交到 Git
支持：按分组存储文章
"""

import os
import re
import sys
import hashlib
import logging
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import yaml
import feedparser
import requests
import html2text
from bs4 import BeautifulSoup
from git import Repo, GitCommandError


# ==================== 配置加载 ====================

def load_config(config_path: str = "config.yaml") -> dict:
    """加载配置文件"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config
    except FileNotFoundError:
        logging.error(f"配置文件不存在: {config_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        logging.error(f"配置文件解析错误: {e}")
        sys.exit(1)


# ==================== 工具函数 ====================

def sanitize_filename(filename: str) -> str:
    """清理文件名中的特殊字符"""
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = filename.strip()
    if len(filename) > 200:
        filename = filename[:200]
    return filename


def setup_logging(level: str = "INFO"):
    """配置日志"""
    logging.basicConfig(
        level=getattr(logging, level),
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


# ==================== 图片下载器 ====================

class ImageDownloader:
    """图片下载器 - 处理微信防盗链"""

    def __init__(self, assets_dir: Path, article_url: str, config: dict):
        self.assets_dir = assets_dir
        self.article_url = article_url
        self.max_size = config.get('image', {}).get('max_size_mb', 10) * 1024 * 1024
        self.timeout = config.get('image', {}).get('download_timeout', 30)
        self.session = requests.Session()

        # 标准浏览器 UA
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

    def get_image_extension(self, url: str) -> str:
        """根据 URL 参数或 Content-Type 获取图片扩展名"""
        # 从 URL 参数中提取
        if 'wx_fmt=' in url:
            fmt = url.split('wx_fmt=')[-1].split('&')[0]
            fmt_map = {
                'jpeg': '.jpg',
                'jpg': '.jpg',
                'png': '.png',
                'gif': '.gif',
                'webp': '.webp',
                'bmp': '.bmp'
            }
            return fmt_map.get(fmt, '.jpg')

        # 从 URL 路径提取
        parsed = urlparse(url)
        path = parsed.path.lower()
        if path.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')):
            return Path(path).suffix

        return '.jpg'  # 默认

    def download(self, img_url: str) -> str:
        """
        下载单张图片

        Returns:
            本地相对路径，如 ../assets/image_123456.jpg
        """
        try:
            # 处理相对 URL
            if img_url.startswith('//'):
                img_url = 'https:' + img_url

            # 构造请求头（关键：防盗链处理）
            headers = {
                'User-Agent': self.user_agent,
                'Referer': self.article_url  # 必须携带 Referer
            }

            response = self.session.get(img_url, headers=headers, timeout=self.timeout, stream=True)
            response.raise_for_status()

            # 检查文件大小
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > self.max_size:
                logging.warning(f"图片过大，跳过下载: {img_url}")
                return img_url  # 返回原 URL

            # 生成唯一文件名
            url_hash = hashlib.md5(img_url.encode('utf-8')).hexdigest()[:8]
            timestamp = datetime.now().strftime('%H%M%S')
            ext = self.get_image_extension(img_url)
            filename = f"img_{timestamp}_{url_hash}{ext}"
            filepath = self.assets_dir / filename

            # 保存图片
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            logging.debug(f"图片下载成功: {filepath}")
            return f"../assets/{filename}"

        except Exception as e:
            logging.warning(f"图片下载失败 {img_url}: {e}")
            return img_url  # 失败返回原 URL


# ==================== 文章处理器 ====================

class ArticleProcessor:
    """文章处理器 - 抓取、转换、保存"""

    def __init__(self, config: dict, group_name: str):
        self.config = config
        self.group_name = group_name
        self.data_dir = Path(config['storage']['data_dir'])

        # 按分组创建目录
        self.group_dir = self.data_dir / group_name
        self.posts_dir = self.group_dir / config['storage']['posts_dir']
        self.assets_dir = self.group_dir / config['storage']['assets_dir']
        self.date_format = config['storage']['date_format']

        # 确保目录存在
        self.group_dir.mkdir(parents=True, exist_ok=True)
        self.posts_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)

        # HTML 转 Markdown 配置
        self.h2t = html2text.HTML2Text()
        self.h2t.ignore_links = False
        self.h2t.ignore_images = False
        self.h2t.body_width = 0  # 不自动换行
        self.h2t.unicode_snob = True

        # HTTP 会话
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def is_already_archived(self, title: str, pub_date: str) -> bool:
        """检查文章是否已归档（幂等性）"""
        date_str = datetime.strptime(pub_date, self.date_format).strftime(self.date_format)
        filename = f"{date_str}-{sanitize_filename(title)}.md"
        filepath = self.posts_dir / filename
        return filepath.exists()

    def extract_images(self, html_content: str, article_url: str) -> str:
        """
        提取并下载所有图片，替换 HTML 中的链接

        Returns:
            处理后的 HTML（图片链接已替换为本地路径）
        """
        soup = BeautifulSoup(html_content, 'lxml')
        downloader = ImageDownloader(self.assets_dir, article_url, self.config)

        for img in soup.find_all('img'):
            # 优先提取 data-src（微信懒加载）
            src = img.get('data-src') or img.get('src')
            if not src:
                continue

            # 下载图片并获取本地路径
            local_path = downloader.download(src)

            # 替换 src 属性
            img['src'] = local_path

            # 清除其他属性
            for attr in list(img.attrs):
                if attr != 'src':
                    del img[attr]

        return str(soup)

    def fetch_article_html(self, url: str) -> str:
        """抓取文章 HTML 内容"""
        max_retries = self.config['fetch']['max_retries']
        retry_delay = self.config['fetch']['retry_delay']
        timeout = self.config['fetch']['timeout']

        for attempt in range(max_retries):
            try:
                logging.debug(f"抓取文章 HTML: {url} (尝试 {attempt + 1}/{max_retries})")
                response = self.session.get(url, timeout=timeout)
                response.raise_for_status()
                response.encoding = 'utf-8'
                return response.text
            except requests.RequestException as e:
                logging.warning(f"请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)

        logging.error(f"文章 HTML 抓取失败，已达最大重试次数: {url}")
        return None

    def process_entry(self, entry, feed_name: str) -> bool:
        """
        处理单个 RSS 条目

        Returns:
            是否成功归档
        """
        try:
            # 提取基本信息
            title = entry.get('title', '无标题')
            link = entry.get('link', '')
            pub_date = entry.get('published_parsed')

            if not link:
                logging.warning(f"文章无链接，跳过: {title}")
                return False

            # 解析发布日期
            if pub_date:
                pub_date_str = datetime(*pub_date[:6]).strftime(self.date_format)
            else:
                pub_date_str = datetime.now().strftime(self.date_format)

            # 幂等性检查
            if self.is_already_archived(title, pub_date_str):
                logging.info(f"文章已存在，跳过: {title}")
                return False

            logging.info(f"处理文章: {title}")

            # 抓取文章 HTML
            html_content = self.fetch_article_html(link)
            if not html_content:
                return False

            # 提取并处理图片
            html_with_local_images = self.extract_images(html_content, link)

            # 转换为 Markdown
            markdown_content = self.h2t.handle(html_with_local_images)

            # 生成 Front Matter
            frontmatter = f"""---
title: {title}
source: {feed_name}
group: {self.group_name}
date: {pub_date_str}
original_url: {link}
archived_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

"""

            # 生成文件名
            filename = f"{pub_date_str}-{sanitize_filename(title)}.md"
            filepath = self.posts_dir / filename

            # 保存文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(frontmatter + markdown_content)

            logging.info(f"文章保存成功: {filepath}")
            return True

        except Exception as e:
            logging.error(f"处理文章失败: {e}")
            import traceback
            traceback.print_exc()
            return False


# ==================== Git 管理器 ====================

class GitManager:
    """Git 管理器 - 自动提交和推送"""

    def __init__(self, config: dict):
        self.config = config
        self.repo_path = Path(config['github_repo_path'])
        self.remote_url = config['github_remote_url']
        self.branch = config.get('github_branch', 'main')
        self.user_name = config['git_user_name']
        self.user_email = config['git_user_email']

    def init_repo(self):
        """初始化 Git 仓库"""
        try:
            if not (self.repo_path / '.git').exists():
                logging.info("初始化 Git 仓库...")
                repo = Repo.init(self.repo_path)

                # 配置用户信息
                repo.config_writer().set_value("user", "name", self.user_name).release()
                repo.config_writer().set_value("user", "email", self.user_email).release()

                # 添加远程仓库
                if self.remote_url:
                    repo.create_remote('origin', self.remote_url)

                logging.info("Git 仓库初始化完成")
            else:
                repo = Repo(self.repo_path)
                logging.info("Git 仓库已存在")

            return repo

        except GitCommandError as e:
            logging.error(f"Git 仓库初始化失败: {e}")
            sys.exit(1)

    def commit_and_push(self, repo: Repo):
        """提交并推送更改"""
        try:
            # 检查是否有更改
            if repo.is_dirty(untracked_files=True):
                # 添加所有更改
                repo.git.add(A=True)

                # 创建提交
                commit_msg = f"Auto-archive: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                repo.index.commit(commit_msg)

                logging.info(f"Git 提交成功: {commit_msg}")

                # 推送到远程
                if self.remote_url:
                    origin = repo.remote(name='origin')
                    origin.push(self.branch)
                    logging.info(f"推送到远程仓库成功: {self.branch}")
                else:
                    logging.warning("未配置远程仓库 URL，跳过推送")
            else:
                logging.info("没有新的更改，跳过提交")

        except GitCommandError as e:
            logging.error(f"Git 操作失败: {e}")


# ==================== 主程序 ====================

def main():
    """主函数"""
    # 加载配置
    config = load_config()
    setup_logging(config.get('logging', {}).get('level', 'INFO'))

    logging.info("=" * 60)
    logging.info("WeChat-Archiver 启动（支持分组版本）")
    logging.info("=" * 60)

    # 初始化 Git 仓库
    git_manager = GitManager(config)
    repo = git_manager.init_repo()

    # 获取分组配置
    groups = config.get('groups', [])
    if not groups:
        logging.warning("没有配置分组，请检查 config.yaml 中的 groups 配置")
        return

    total_processed = 0

    # 遍历每个分组
    for group in groups:
        group_name = group.get('name', '未命名')
        feeds = group.get('feeds', [])

        if not feeds:
            logging.warning(f"分组 {group_name} 没有配置 RSS 源")
            continue

        logging.info(f"\n{'=' * 40}")
        logging.info(f"处理分组: {group_name}")
        logging.info(f"{'=' * 40}")

        # 初始化该分组的文章处理器
        processor = ArticleProcessor(config, group_name)

        # 遍历该分组的所有 RSS 源
        for feed_config in feeds:
            feed_name = feed_config.get('name', 'Unknown')
            feed_url = feed_config.get('url')

            if not feed_url:
                logging.warning(f"RSS 源 {feed_name} 缺少 URL，跳过")
                continue

            logging.info(f"\n处理 RSS 源: {feed_name}")

            # 解析 RSS
            try:
                feed = feedparser.parse(feed_url)
                if not feed.entries:
                    logging.warning(f"RSS 源 {feed_name} 没有文章")
                    continue

                # 处理文章
                max_articles = config['fetch']['max_articles']
                entries = feed.entries[:max_articles]

                for entry in entries:
                    if processor.process_entry(entry, feed_name):
                        total_processed += 1

            except Exception as e:
                logging.error(f"处理 RSS 源 {feed_name} 失败: {e}")
                import traceback
                traceback.print_exc()

    # Git 提交和推送
    if total_processed > 0:
        logging.info(f"\n总共归档 {total_processed} 篇文章")
        git_manager.commit_and_push(repo)
    else:
        logging.info("\n没有新增文章")

    logging.info("=" * 60)
    logging.info("WeChat-Archiver 完成")
    logging.info("=" * 60)


if __name__ == '__main__':
    main()
