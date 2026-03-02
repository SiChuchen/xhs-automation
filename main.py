#!/usr/bin/env python3
"""
小红书自动化运营 - 主入口脚本
提供命令行接口用于发布、互动、数据分析等操作
"""

import argparse
import sys
import os
import json
import logging
from logging.handlers import RotatingFileHandler

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 确保日志目录存在
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

# 配置日志 - 单文件上限 10MB，最多保留 5 个历史文件
log_file = os.path.join(log_dir, 'xhs_automation.log')
handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

logging.basicConfig(
    handlers=[handler],
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from src.database import get_database
from src.xhs_api_client import get_xhs_client
from src.mcp_client import get_mcp_client
from src.auto_interact import AutoInteract


def cmd_login_status(args):
    """检查登录状态"""
    client = get_xhs_client()
    is_logged_in, data = client.check_login_status()
    
    if is_logged_in:
        print(f"✅ 已登录: {data.get('username', 'unknown')}")
        return 0
    else:
        print(f"❌ 未登录: {data.get('error', '未知错误')}")
        return 1


def cmd_publish(args):
    """发布笔记"""
    client = get_xhs_client()
    db = get_database()
    
    # 检查登录
    is_logged_in, _ = client.check_login_status()
    if not is_logged_in:
        print("❌ 未登录，请先扫码登录")
        return 1
    
    # 读取内容
    title = args.title
    content = args.content
    image_path = args.image
    tags = args.tags.split(',') if args.tags else None
    
    # 如果没有提供内容，尝试读取文件
    if args.content_file and os.path.exists(args.content_file):
        with open(args.content_file, 'r', encoding='utf-8') as f:
            content = f.read()
    
    if not title or not content:
        print("❌ 标题和内容不能为空")
        return 1
    
    # 发布
    print(f"📝 发布笔记: {title}")
    result = client.publish_note(title, content, image_path, tags or [])
    
    if result.get('success'):
        post_id = result.get('post_id')
        print(f"✅ 发布成功! Post ID: {post_id}")
        
        # 保存到数据库
        db.add_post(
            title=title,
            content=content[:500],
            image_path=image_path,
            tags=tags or [],
            post_id=post_id or '',
            status='success'
        )
        return 0
    else:
        error = result.get('error', '未知错误')
        print(f"❌ 发布失败: {error}")
        
        # 保存失败记录
        db.add_post(
            title=title,
            content=content[:500],
            image_path=image_path,
            tags=tags or [],
            status='failed'
        )
        return 1


def cmd_search(args):
    """搜索内容"""
    client = get_xhs_client()
    mcp_client = get_mcp_client()
    db = get_database()
    
    # 检查缓存
    cached = db.get_cached_search(args.keyword, max_age_hours=args.cache_hours)
    if cached and not args.no_cache:
        print(f"📦 使用缓存结果 ({len(cached)} 条)")
        results = cached
    else:
        # 执行搜索
        print(f"🔍 搜索: {args.keyword}")
        results = mcp_client.search(args.keyword)
        
        # 缓存结果
        if results:
            db.cache_search_results(args.keyword, results)
    
    # 打印结果
    print(f"\n找到 {len(results)} 条结果:\n")
    for i, item in enumerate(results[:args.limit], 1):
        note_card = item.get('noteCard', {})
        title = note_card.get('displayTitle', '无标题')
        post_id = item.get('id', '')
        print(f"{i}. {title}")
        print(f"   ID: {post_id}")
        print()
    
    return 0


def cmd_interact(args):
    """自动互动"""
    # 加载配置
    config_path = args.config or "config/auto_interact_config.json"
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    else:
        print(f"❌ 配置文件不存在: {config_path}")
        return 1
    
    # 执行互动
    print("🚀 开始自动互动任务...")
    auto_interact = AutoInteract(config)
    result = auto_interact.run_daily_task()
    
    print(f"\n📊 互动结果:")
    print(f"   状态: {result.get('status')}")
    print(f"   关键词: {result.get('keywords', [])}")
    print(f"   成功: {result.get('total_success', 0)}")
    print(f"   失败: {result.get('total_failed', 0)}")
    
    return 0


def cmd_stats(args):
    """查看统计数据"""
    db = get_database()
    
    days = args.days
    
    # 账号摘要
    summary = db.get_account_summary(days)
    print(f"\n📊 账号运营摘要 (最近 {days} 天)")
    print(f"   发布数量: {summary['publish_count']}")
    print(f"   总点赞: {summary['total_likes']}")
    print(f"   总收藏: {summary['total_collects']}")
    print(f"   总评论: {summary['total_comments']}")
    
    # 热门帖子
    if args.top:
        top_posts = db.get_top_posts(limit=args.top, days=days)
        print(f"\n🔥 热门帖子 (Top {len(top_posts)}):")
        for i, post in enumerate(top_posts, 1):
            print(f"   {i}. {post.get('title', '无标题')[:40]}")
            print(f"      赞:{post.get('likes', 0)} 藏:{post.get('collects', 0)} 评:{post.get('comments', 0)}")
    
    # 互动统计
    comment_count = db.get_interaction_count('comment')
    like_count = db.get_interaction_count('like')
    collect_count = db.get_interaction_count('collect')
    print(f"\n📈 今日互动:")
    print(f"   评论: {comment_count}")
    print(f"   点赞: {like_count}")
    print(f"   收藏: {collect_count}")
    
    return 0


def cmd_db_cleanup(args):
    """清理数据库"""
    db = get_database()
    
    retention_days = args.days
    print(f"🧹 清理 {retention_days} 天前的数据...")
    
    result = db.cleanup_old_data(retention_days)
    print(f"   删除互动记录: {result['interactions']}")
    print(f"   删除分析数据: {result['analytics']}")
    print(f"   删除缓存: {result['cache']}")
    
    # 整理数据库
    if args.vacuum:
        print("📦 整理数据库...")
        db.vacuum()
    
    db_size = db.get_db_size()
    print(f"   当前数据库大小: {db_size / 1024 / 1024:.2f} MB")
    
    return 0


def cmd_setup(args):
    """运行交互式配置向导"""
    import subprocess
    result = subprocess.run([sys.executable, "scripts/setup.py"])
    return result.returncode


def cmd_trending(args):
    """获取热门话题"""
    import subprocess
    cmd = [sys.executable, "scripts/trending_fetcher.py"]
    if args.source:
        cmd.extend(["--source", args.source])
    if args.limit:
        cmd.extend(["--limit", str(args.limit)])
    if args.keyword:
        cmd.extend(["--keyword", args.keyword])
    if args.output:
        cmd.extend(["--output", args.output])
    
    result = subprocess.run(cmd)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description='小红书自动化运营工具',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 配置向导
    parser_setup = subparsers.add_parser('setup', help='交互式配置向导')
    parser_setup.set_defaults(func=cmd_setup)
    
    # 热门话题
    parser_trending = subparsers.add_parser('trending', help='获取热门话题')
    parser_trending.add_argument('--source', choices=['weibo', 'xiaohongshu', 'all'])
    parser_trending.add_argument('--limit', type=int, default=10)
    parser_trending.add_argument('--keyword', '-k')
    parser_trending.add_argument('--output', '-o')
    parser_trending.set_defaults(func=cmd_trending)
    
    # 登录状态
    parser_status = subparsers.add_parser('status', help='检查登录状态')
    parser_status.set_defaults(func=cmd_login_status)
    
    # 发布
    parser_publish = subparsers.add_parser('publish', help='发布笔记')
    parser_publish.add_argument('--title', '-t', required=True, help='标题')
    parser_publish.add_argument('--content', '-c', help='内容')
    parser_publish.add_argument('--content-file', '-f', help='内容文件路径')
    parser_publish.add_argument('--image', '-i', help='图片路径')
    parser_publish.add_argument('--tags', help='标签（逗号分隔）')
    parser_publish.set_defaults(func=cmd_publish)
    
    # 搜索
    parser_search = subparsers.add_parser('search', help='搜索内容')
    parser_search.add_argument('keyword', help='搜索关键词')
    parser_search.add_argument('--limit', '-l', type=int, default=10, help='结果数量')
    parser_search.add_argument('--cache-hours', type=int, default=24, help='缓存时间（小时）')
    parser_search.add_argument('--no-cache', action='store_true', help='不使用缓存')
    parser_search.set_defaults(func=cmd_search)
    
    # 自动互动
    parser_interact = subparsers.add_parser('interact', help='自动互动')
    parser_interact.add_argument('--config', '-c', help='配置文件路径')
    parser_interact.set_defaults(func=cmd_interact)
    
    # 统计
    parser_stats = subparsers.add_parser('stats', help='查看统计数据')
    parser_stats.add_argument('--days', '-d', type=int, default=7, help='统计天数')
    parser_stats.add_argument('--top', '-t', type=int, default=5, help='显示热门帖子数')
    parser_stats.set_defaults(func=cmd_stats)
    
    # 清理
    parser_cleanup = subparsers.add_parser('cleanup', help='清理数据库')
    parser_cleanup.add_argument('--days', '-d', type=int, default=30, help='保留天数')
    parser_cleanup.add_argument('--vacuum', '-v', action='store_true', help='整理数据库')
    parser_cleanup.set_defaults(func=cmd_db_cleanup)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
