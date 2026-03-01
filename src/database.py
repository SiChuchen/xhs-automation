"""
小红书自动化运营 - 数据库模块
使用 SQLite WAL 模式支持并发
"""

import sqlite3
import json
import os
import logging
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from contextlib import contextmanager
from queue import Queue, Empty

logger = logging.getLogger(__name__)


class ConnectionPool:
    """SQLite 连接池 (简化版，适用于 WAL 模式)"""
    
    def __init__(self, db_path: str, max_connections: int = 5):
        self.db_path = db_path
        self.max_connections = max_connections
        self._local = threading.local()
        self._lock = threading.Lock()
    
    def _create_connection(self) -> sqlite3.Connection:
        """创建新连接"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn
    
    def get_connection(self) -> sqlite3.Connection:
        """获取连接"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = self._create_connection()
        return self._local.conn
    
    def close_all(self):
        """关闭所有连接"""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


class XHSDatabase:
    """小红书数据库操作类"""
    
    def __init__(self, db_path: str = "data/xhs_data.db"):
        self.db_path = db_path
        self._ensure_db_dir()
        self._pool = ConnectionPool(db_path)
        self._init_database()
        logger.info(f"数据库初始化完成 (WAL模式): {db_path}")
    
    def _ensure_db_dir(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
    
    @contextmanager
    def _get_connection(self):
        """获取数据库连接上下文管理器"""
        conn = self._pool.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
    
    def _init_database(self):
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 发布记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id TEXT,
                    title TEXT NOT NULL,
                    content TEXT,
                    image_path TEXT,
                    tags TEXT,
                    module TEXT,
                    topic TEXT,
                    published_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending'
                )
            """)
            
            # 帖子互动数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS post_analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id TEXT NOT NULL,
                    fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    likes INTEGER DEFAULT 0,
                    collects INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    shares INTEGER DEFAULT 0,
                    UNIQUE(post_id, fetched_at)
                )
            """)
            
            # 互动历史表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_post_id TEXT NOT NULL,
                    target_keyword TEXT,
                    action TEXT NOT NULL,
                    content TEXT,
                    status TEXT DEFAULT 'pending',
                    interacted_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 搜索缓存表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS search_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT UNIQUE NOT NULL,
                    results_json TEXT,
                    searched_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_published ON posts(published_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_post_analytics_post ON post_analytics(post_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_interactions_post ON interactions(target_post_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_interactions_keyword ON interactions(target_keyword)")
            
            logger.info("数据库初始化完成")
    
    def get_wal_status(self) -> Dict:
        """获取 WAL 模式状态"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode")
            journal_mode = cursor.fetchone()[0]
            cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            checkpoint = cursor.fetchone()
            return {
                "journal_mode": journal_mode,
                "wal_size": os.path.getsize(self.db_path + "-wal") if os.path.exists(self.db_path + "-wal") else 0,
                "shm_size": os.path.getsize(self.db_path + "-shm") if os.path.exists(self.db_path + "-shm") else 0,
                "checkpoint": checkpoint
            }
    
    def checkpoint(self):
        """执行 WAL 检查点"""
        with self._get_connection() as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    
    # ==================== 发布记录操作 ====================
    
    def add_post(self, title: str, content: str, image_path: Optional[str] = None, 
                 tags: Optional[List[str]] = None, module: Optional[str] = None, topic: Optional[str] = None,
                 post_id: Optional[str] = None, status: str = 'success') -> int:
        """添加发布记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO posts (post_id, title, content, image_path, tags, module, topic, published_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (post_id, title, content, image_path, json.dumps(tags) if tags else None,
                  module, topic, datetime.now().isoformat(), status))
            return cursor.lastrowid or 0
    
    def update_post_status(self, post_id: int, status: str, xhs_post_id: Optional[str] = None):
        """更新发布状态"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if xhs_post_id:
                cursor.execute("""
                    UPDATE posts SET status = ?, post_id = ? WHERE id = ?
                """, (status, xhs_post_id, post_id))
            else:
                cursor.execute("UPDATE posts SET status = ? WHERE id = ?", (status, post_id))
    
    def get_posts(self, limit: int = 50, status: Optional[str] = None) -> List[Dict]:
        """获取发布记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("""
                    SELECT * FROM posts WHERE status = ? ORDER BY published_at DESC LIMIT ?
                """, (status, limit))
            else:
                cursor.execute("SELECT * FROM posts ORDER BY published_at DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_post_by_xhs_id(self, xhs_post_id: str) -> Optional[Dict]:
        """根据小红书ID获取帖子"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM posts WHERE post_id = ?", (xhs_post_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    # ==================== 互动数据分析 ====================
    
    def add_post_analytics(self, post_id: str, likes: int = 0, collects: int = 0, 
                          comments: int = 0, shares: int = 0):
        """添加帖子互动数据"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO post_analytics 
                (post_id, fetched_at, likes, collects, comments, shares)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (post_id, datetime.now().isoformat(), likes, collects, comments, shares))
    
    def get_post_analytics_history(self, post_id: str, days: int = 30) -> List[Dict]:
        """获取帖子互动数据历史"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM post_analytics 
                WHERE post_id = ? AND fetched_at > datetime('now', '-{} days')
                ORDER BY fetched_at DESC
            """.format(days), (post_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_account_summary(self, days: int = 7) -> Dict:
        """获取账号运营摘要"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取发布数量
            cursor.execute("""
                SELECT COUNT(*) as total FROM posts 
                WHERE status = 'success' AND published_at > datetime('now', '-{} days')
            """.format(days))
            publish_count = cursor.fetchone()['total']
            
            # 获取最新互动数据
            cursor.execute("""
                SELECT SUM(likes) as total_likes, SUM(collects) as total_collects,
                       SUM(comments) as total_comments
                FROM post_analytics pa
                JOIN posts p ON p.post_id = pa.post_id
                WHERE p.published_at > datetime('now', '-{} days')
            """.format(days))
            stats = cursor.fetchone()
            
            return {
                'publish_count': publish_count or 0,
                'total_likes': stats['total_likes'] or 0,
                'total_collects': stats['total_collects'] or 0,
                'total_comments': stats['total_comments'] or 0,
                'period_days': days
            }
    
    def get_top_posts(self, limit: int = 10, days: int = 30) -> List[Dict]:
        """获取热门帖子排行"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.*, 
                       COALESCE(pa.likes, 0) as likes,
                       COALESCE(pa.collects, 0) as collects,
                       COALESCE(pa.comments, 0) as comments
                FROM posts p
                LEFT JOIN (
                    SELECT post_id, likes, collects, comments,
                           ROW_NUMBER() OVER (PARTITION BY post_id ORDER BY fetched_at DESC) as rn
                    FROM post_analytics
                ) pa ON p.post_id = pa.post_id AND pa.rn = 1
                WHERE p.status = 'success' AND p.published_at > datetime('now', '-{} days')
                ORDER BY (pa.likes + pa.collects * 2 + pa.comments * 3) DESC
                LIMIT ?
            """.format(days), (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    # ==================== 互动历史操作 ====================
    
    def add_interaction(self, target_post_id: str, target_keyword: str,
                       action: str, content: Optional[str] = None, status: str = 'success') -> int:
        """添加互动记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO interactions (target_post_id, target_keyword, action, content, status)
                VALUES (?, ?, ?, ?, ?)
            """, (target_post_id, target_keyword, action, content, status))
            return cursor.lastrowid or 0
    
    def update_interaction_status(self, interaction_id: int, status: str):
        """更新互动状态"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE interactions SET status = ? WHERE id = ?
            """, (status, interaction_id))
    
    def is_interacted(self, target_post_id: str, action: Optional[str] = None) -> bool:
        """检查是否已互动"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if action:
                cursor.execute("""
                    SELECT COUNT(*) FROM interactions 
                    WHERE target_post_id = ? AND action = ?
                """, (target_post_id, action))
            else:
                cursor.execute("SELECT COUNT(*) FROM interactions WHERE target_post_id = ?",
                             (target_post_id,))
            return cursor.fetchone()[0] > 0
    
    def get_interaction_count(self, action: Optional[str] = None, days: int = 1) -> int:
        """获取互动次数"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if action:
                cursor.execute("""
                    SELECT COUNT(*) FROM interactions 
                    WHERE action = ? AND interacted_at > datetime('now', '-{} days')
                """.format(days), (action,))
            else:
                cursor.execute("""
                    SELECT COUNT(*) FROM interactions 
                    WHERE interacted_at > datetime('now', '-{} days')
                """.format(days))
            return cursor.fetchone()[0]
    
    def get_recent_interactions(self, limit: int = 50) -> List[Dict]:
        """获取最近互动记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM interactions ORDER BY interacted_at DESC LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    # ==================== 搜索缓存操作 ====================
    
    def cache_search_results(self, keyword: str, results: List[Dict]):
        """缓存搜索结果"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO search_cache (keyword, results_json, searched_at)
                VALUES (?, ?, ?)
            """, (keyword, json.dumps(results), datetime.now().isoformat()))
    
    def get_cached_search(self, keyword: str, max_age_hours: int = 24) -> Optional[List[Dict]]:
        """获取缓存的搜索结果"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT results_json, searched_at FROM search_cache 
                WHERE keyword = ? AND searched_at > datetime('now', '-{} hours')
            """.format(max_age_hours), (keyword,))
            row = cursor.fetchone()
            if row:
                return json.loads(row['results_json'])
            return None
    
    # ==================== 清理操作 ====================
    
    def cleanup_old_data(self, retention_days: int = 30):
        """清理过期数据"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 清理旧的互动数据
            cursor.execute("""
                DELETE FROM interactions 
                WHERE interacted_at < datetime('now', '-{} days')
            """.format(retention_days))
            interactions_deleted = cursor.rowcount
            
            # 清理旧的帖子分析数据
            cursor.execute("""
                DELETE FROM post_analytics 
                WHERE fetched_at < datetime('now', '-{} days')
            """.format(retention_days))
            analytics_deleted = cursor.rowcount
            
            # 清理旧的搜索缓存
            cursor.execute("""
                DELETE FROM search_cache 
                WHERE searched_at < datetime('now', '-1 days')
            """)
            cache_deleted = cursor.rowcount
            
            logger.info(f"清理完成: 互动记录-{interactions_deleted}, 分析数据-{analytics_deleted}, 缓存-{cache_deleted}")
            return {
                'interactions': interactions_deleted,
                'analytics': analytics_deleted,
                'cache': cache_deleted
            }
    
    def get_db_size(self) -> int:
        """获取数据库大小(字节)"""
        if os.path.exists(self.db_path):
            return os.path.getsize(self.db_path)
        return 0
    
    def vacuum(self):
        """整理数据库"""
        with self._get_connection() as conn:
            conn.execute("VACUUM")
            logger.info("数据库整理完成")


# 全局数据库实例
_db_instance = None

def get_database(db_path: str = "data/xhs_data.db") -> XHSDatabase:
    """获取数据库单例"""
    global _db_instance
    if _db_instance is None:
        _db_instance = XHSDatabase(db_path)
    return _db_instance
