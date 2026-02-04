#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WeChat-Archiver Web 管理界面
提供动态分组管理、RSS 源管理功能
"""

from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import yaml
import json
from pathlib import Path
import logging

app = Flask(__name__)
CORS(app)

CONFIG_FILE = Path("/root/weichat/config.yaml")
DATA_DIR = Path("/root/weichat/data")

# HTML 模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WeChat-Archiver 管理界面</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .header h1 {
            color: #333;
            font-size: 28px;
            margin-bottom: 10px;
        }
        .header p {
            color: #666;
            font-size: 14px;
        }
        .main-content {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        .panel {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }
        .panel h2 {
            color: #333;
            font-size: 20px;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }
        .form-group {
            margin-bottom: 15px;
        }
        .form-group label {
            display: block;
            color: #555;
            font-weight: 500;
            margin-bottom: 5px;
            font-size: 14px;
        }
        .form-group input, .form-group select {
            width: 100%;
            padding: 10px 12px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            font-size: 14px;
            transition: border-color 0.3s;
        }
        .form-group input:focus, .form-group select:focus {
            outline: none;
            border-color: #667eea;
        }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn-primary {
            background: #667eea;
            color: white;
        }
        .btn-primary:hover {
            background: #5568d3;
            transform: translateY(-1px);
        }
        .btn-danger {
            background: #ef4444;
            color: white;
        }
        .btn-danger:hover {
            background: #dc2626;
        }
        .btn-success {
            background: #10b981;
            color: white;
        }
        .btn-success:hover {
            background: #059669;
        }
        .group-list, .feed-list {
            margin-top: 20px;
        }
        .group-item, .feed-item {
            background: #f9fafb;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-left: 4px solid #667eea;
        }
        .group-item:hover, .feed-item:hover {
            background: #f3f4f6;
        }
        .group-name, .feed-name {
            font-weight: 500;
            color: #333;
        }
        .group-info, .feed-info {
            font-size: 12px;
            color: #666;
            margin-top: 4px;
        }
        .actions {
            display: flex;
            gap: 8px;
        }
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #999;
            font-size: 14px;
        }
        .toast {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 25px;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            z-index: 1000;
            animation: slideIn 0.3s ease;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .toast.success {
            background: #10b981;
        }
        .toast.error {
            background: #ef4444;
        }
        @keyframes slideIn {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        .select-group {
            margin-bottom: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📚 WeChat-Archiver 管理界面</h1>
            <p>动态管理分组和 RSS 订阅源，完全自定义你的文章归档分类</p>
        </div>

        <div class="main-content">
            <!-- 左侧：分组管理 -->
            <div class="panel">
                <h2>📁 分组管理</h2>

                <div class="form-group">
                    <label>创建新分组</label>
                    <div style="display: flex; gap: 10px;">
                        <input type="text" id="groupName" placeholder="输入分组名称，如：科技类">
                        <button class="btn btn-primary" onclick="createGroup()">创建</button>
                    </div>
                </div>

                <div class="group-list" id="groupList">
                    <div class="empty-state">加载中...</div>
                </div>
            </div>

            <!-- 右侧：RSS 源管理 -->
            <div class="panel">
                <h2>📡 RSS 源管理</h2>

                <div class="form-group select-group">
                    <label>选择分组</label>
                    <select id="groupSelect" onchange="loadFeeds()">
                        <option value="">-- 请选择分组 --</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>RSS 源名称</label>
                    <input type="text" id="feedName" placeholder="如：差评、爱范儿">
                </div>

                <div class="form-group">
                    <label>RSS URL</label>
                    <input type="text" id="feedUrl" placeholder="http://127.0.0.1:4000/feeds/xxxxx.atom">
                </div>

                <button class="btn btn-success" onclick="addFeed()" style="width: 100%;">添加 RSS 源</button>

                <div class="feed-list" id="feedList">
                    <div class="empty-state">请先选择一个分组</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let selectedGroup = null;

        // 显示提示消息
        function showToast(message, type = 'success') {
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        }

        // 加载所有分组
        async function loadGroups() {
            try {
                const response = await fetch('/api/groups');
                const data = await response.json();

                const groupList = document.getElementById('groupList');
                const groupSelect = document.getElementById('groupSelect');

                if (data.groups.length === 0) {
                    groupList.innerHTML = '<div class="empty-state">暂无分组，请创建一个</div>';
                    groupSelect.innerHTML = '<option value="">-- 请先创建分组 --</option>';
                    return;
                }

                // 更新分组列表
                groupList.innerHTML = data.groups.map(group => `
                    <div class="group-item">
                        <div>
                            <div class="group-name">${group.name}</div>
                            <div class="group-info">${group.feed_count || 0} 个 RSS 源</div>
                        </div>
                        <div class="actions">
                            <button class="btn btn-danger" onclick="deleteGroup('${group.name}')">删除</button>
                        </div>
                    </div>
                `).join('');

                // 更新下拉选择框
                groupSelect.innerHTML = '<option value="">-- 请选择分组 --</option>' +
                    data.groups.map(group => `<option value="${group.name}">${group.name}</option>`).join('');
            } catch (error) {
                showToast('加载分组失败: ' + error.message, 'error');
            }
        }

        // 创建分组
        async function createGroup() {
            const name = document.getElementById('groupName').value.trim();
            if (!name) {
                showToast('请输入分组名称', 'error');
                return;
            }

            try {
                const response = await fetch('/api/groups', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name })
                });

                if (response.ok) {
                    showToast('分组创建成功');
                    document.getElementById('groupName').value = '';
                    loadGroups();
                } else {
                    const data = await response.json();
                    showToast(data.error || '创建失败', 'error');
                }
            } catch (error) {
                showToast('创建失败: ' + error.message, 'error');
            }
        }

        // 删除分组
        async function deleteGroup(name) {
            if (!confirm(`确定要删除分组 "${name}" 吗？这将同时删除该分组下的所有 RSS 源。`)) {
                return;
            }

            try {
                const response = await fetch(`/api/groups/${encodeURIComponent(name)}`, {
                    method: 'DELETE'
                });

                if (response.ok) {
                    showToast('分组删除成功');
                    if (selectedGroup === name) {
                        selectedGroup = null;
                        document.getElementById('feedList').innerHTML = '<div class="empty-state">请先选择一个分组</div>';
                    }
                    loadGroups();
                } else {
                    const data = await response.json();
                    showToast(data.error || '删除失败', 'error');
                }
            } catch (error) {
                showToast('删除失败: ' + error.message, 'error');
            }
        }

        // 选择分组
        function loadFeeds() {
            const select = document.getElementById('groupSelect');
            selectedGroup = select.value;

            if (!selectedGroup) {
                document.getElementById('feedList').innerHTML = '<div class="empty-state">请先选择一个分组</div>';
                return;
            }

            loadFeedsForGroup(selectedGroup);
        }

        // 加载指定分组的 RSS 源
        async function loadFeedsForGroup(groupName) {
            try {
                const response = await fetch(`/api/groups/${encodeURIComponent(groupName)}/feeds`);
                const data = await response.json();

                const feedList = document.getElementById('feedList');

                if (!data.feeds || data.feeds.length === 0) {
                    feedList.innerHTML = '<div class="empty-state">该分组暂无 RSS 源</div>';
                    return;
                }

                feedList.innerHTML = data.feeds.map(feed => `
                    <div class="feed-item">
                        <div>
                            <div class="feed-name">${feed.name}</div>
                            <div class="feed-info">${feed.url}</div>
                        </div>
                        <div class="actions">
                            <button class="btn btn-danger" onclick="deleteFeed('${groupName}', '${feed.name}')">删除</button>
                        </div>
                    </div>
                `).join('');
            } catch (error) {
                showToast('加载 RSS 源失败: ' + error.message, 'error');
            }
        }

        // 添加 RSS 源
        async function addFeed() {
            const groupName = document.getElementById('groupSelect').value;
            const name = document.getElementById('feedName').value.trim();
            const url = document.getElementById('feedUrl').value.trim();

            if (!groupName) {
                showToast('请选择分组', 'error');
                return;
            }
            if (!name) {
                showToast('请输入 RSS 源名称', 'error');
                return;
            }
            if (!url) {
                showToast('请输入 RSS URL', 'error');
                return;
            }

            try {
                const response = await fetch(`/api/groups/${encodeURIComponent(groupName)}/feeds`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, url })
                });

                if (response.ok) {
                    showToast('RSS 源添加成功');
                    document.getElementById('feedName').value = '';
                    document.getElementById('feedUrl').value = '';
                    loadFeedsForGroup(groupName);
                    loadGroups(); // 更新分组列表中的源数量
                } else {
                    const data = await response.json();
                    showToast(data.error || '添加失败', 'error');
                }
            } catch (error) {
                showToast('添加失败: ' + error.message, 'error');
            }
        }

        // 删除 RSS 源
        async function deleteFeed(groupName, feedName) {
            if (!confirm(`确定要删除 RSS 源 "${feedName}" 吗？`)) {
                return;
            }

            try {
                const response = await fetch(`/api/groups/${encodeURIComponent(groupName)}/feeds/${encodeURIComponent(feedName)}`, {
                    method: 'DELETE'
                });

                if (response.ok) {
                    showToast('RSS 源删除成功');
                    loadFeedsForGroup(groupName);
                    loadGroups();
                } else {
                    const data = await response.json();
                    showToast(data.error || '删除失败', 'error');
                }
            } catch (error) {
                showToast('删除失败: ' + error.message, 'error');
            }
        }

        // 页面加载时初始化
        window.onload = function() {
            loadGroups();
        };
    </script>
</body>
</html>
"""

# 配置管理工具
class ConfigManager:
    def __init__(self):
        self.config_file = CONFIG_FILE
        self.config = self._load_config()

    def _load_config(self):
        """加载配置"""
        if not self.config_file.exists():
            return self._create_default_config()

        with open(self.config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _create_default_config(self):
        """创建默认配置"""
        default_config = {
            'github_repo_path': '/root/weichat/data',
            'github_remote_url': 'git@github.com:sherkevin/weichat.git',
            'github_branch': 'main',
            'git_user_name': 'WeChat Archiver',
            'git_user_email': 'archiver@localhost',
            'groups': [],
            'fetch': {
                'max_articles': 10,
                'timeout': 30,
                'max_retries': 3,
                'retry_delay': 5
            },
            'storage': {
                'data_dir': '/root/weichat/data',
                'posts_dir': 'posts',
                'assets_dir': 'assets',
                'date_format': '%Y-%m-%d'
            },
            'image': {
                'download_enabled': True,
                'download_timeout': 30,
                'max_size_mb': 10
            },
            'logging': {
                'level': 'INFO'
            }
        }
        self._save_config(default_config)
        return default_config

    def _save_config(self, config):
        """保存配置"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        self.config = config

    def get_groups(self):
        """获取所有分组"""
        groups = self.config.get('groups', [])
        return {
            'groups': [
                {
                    'name': g['name'],
                    'feed_count': len(g.get('feeds') or [])
                }
                for g in groups
            ]
        }

    def create_group(self, name):
        """创建分组"""
        groups = self.config.get('groups', [])

        # 检查是否已存在
        for g in groups:
            if g['name'] == name:
                return {'error': '分组已存在'}

        groups.append({'name': name, 'feeds': []})
        self.config['groups'] = groups
        self._save_config(self.config)
        return {'success': True}

    def delete_group(self, name):
        """删除分组"""
        groups = self.config.get('groups', [])

        # 过滤掉要删除的分组
        new_groups = [g for g in groups if g['name'] != name]

        if len(new_groups) == len(groups):
            return {'error': '分组不存在'}

        self.config['groups'] = new_groups
        self._save_config(self.config)
        return {'success': True}

    def get_feeds(self, group_name):
        """获取指定分组的 RSS 源"""
        groups = self.config.get('groups', [])

        for g in groups:
            if g['name'] == group_name:
                return {'feeds': g.get('feeds', [])}

        return {'error': '分组不存在'}

    def add_feed(self, group_name, feed_name, feed_url):
        """添加 RSS 源到指定分组"""
        groups = self.config.get('groups', [])

        for g in groups:
            if g['name'] == group_name:
                feeds = g.get('feeds', [])

                # 检查是否已存在
                for f in feeds:
                    if f['name'] == feed_name or f['url'] == feed_url:
                        return {'error': 'RSS 源已存在'}

                feeds.append({'name': feed_name, 'url': feed_url})
                g['feeds'] = feeds
                self._save_config(self.config)
                return {'success': True}

        return {'error': '分组不存在'}

    def delete_feed(self, group_name, feed_name):
        """删除指定分组的 RSS 源"""
        groups = self.config.get('groups', [])

        for g in groups:
            if g['name'] == group_name:
                feeds = g.get('feeds', [])
                new_feeds = [f for f in feeds if f['name'] != feed_name]

                if len(new_feeds) == len(feeds):
                    return {'error': 'RSS 源不存在'}

                g['feeds'] = new_feeds
                self._save_config(self.config)
                return {'success': True}

        return {'error': '分组不存在'}


# 初始化配置管理器
config_manager = ConfigManager()

# ==================== API 路由 ====================

@app.route('/')
def index():
    """管理界面首页"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/groups', methods=['GET'])
def get_groups():
    """获取所有分组"""
    return jsonify(config_manager.get_groups())

@app.route('/api/groups', methods=['POST'])
def create_group():
    """创建分组"""
    data = request.json
    name = data.get('name', '').strip()

    if not name:
        return jsonify({'error': '分组名称不能为空'}), 400

    result = config_manager.create_group(name)

    if 'error' in result:
        return jsonify(result), 400

    return jsonify(result)

@app.route('/api/groups/<group_name>', methods=['DELETE'])
def delete_group(group_name):
    """删除分组"""
    result = config_manager.delete_group(group_name)

    if 'error' in result:
        return jsonify(result), 404

    return jsonify(result)

@app.route('/api/groups/<group_name>/feeds', methods=['GET'])
def get_feeds(group_name):
    """获取指定分组的 RSS 源"""
    result = config_manager.get_feeds(group_name)

    if 'error' in result:
        return jsonify(result), 404

    return jsonify(result)

@app.route('/api/groups/<group_name>/feeds', methods=['POST'])
def add_feed(group_name):
    """添加 RSS 源到指定分组"""
    data = request.json
    name = data.get('name', '').strip()
    url = data.get('url', '').strip()

    if not name:
        return jsonify({'error': 'RSS 源名称不能为空'}), 400
    if not url:
        return jsonify({'error': 'RSS URL 不能为空'}), 400

    result = config_manager.add_feed(group_name, name, url)

    if 'error' in result:
        return jsonify(result), 400

    return jsonify(result)

@app.route('/api/groups/<group_name>/feeds/<feed_name>', methods=['DELETE'])
def delete_feed(group_name, feed_name):
    """删除指定分组的 RSS 源"""
    result = config_manager.delete_feed(group_name, feed_name)

    if 'error' in result:
        return jsonify(result), 404

    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
