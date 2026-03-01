#!/usr/bin/env python3
"""
存储清理脚本 - 定期清理旧日志、图片和临时文件
"""

import os
import sys
import json
import shutil
import logging
from datetime import datetime, timedelta
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/ubuntu/xhs-automation/logs/cleanup.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class StorageCleaner:
    """存储清理器"""
    
    def __init__(self, config_path: str = None):
        """初始化清理器"""
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'config',
                'monitoring_config.json'
            )
        
        self.config_path = config_path
        self.config = self._load_config()
        
    def _load_config(self):
        """加载配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('storage_management', {})
        except FileNotFoundError:
            logger.warning(f"配置文件不存在: {self.config_path}")
            return self._get_default_config()
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return self._get_default_config()
    
    def _get_default_config(self):
        """获取默认配置"""
        return {
            "enabled": True,
            "log_retention_days": 30,
            "image_retention_days": 7,
            "max_log_size_mb": 100,
            "max_image_dir_size_mb": 1024
        }
    
    def cleanup_old_logs(self):
        """清理旧日志文件"""
        if not self.config.get('enabled', True):
            logger.info("存储清理功能已禁用")
            return
        
        log_dir = Path('/home/ubuntu/xhs-automation/logs')
        retention_days = self.config.get('log_retention_days', 30)
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        deleted_count = 0
        freed_bytes = 0
        
        logger.info(f"开始清理{retention_days}天前的日志文件...")
        
        # 清理旧的日志文件（按修改时间）
        for log_file in log_dir.glob('*.log'):
            try:
                # 跳过当前正在使用的日志文件
                if log_file.name in ['automation.log', 'cleanup.log']:
                    continue
                
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime < cutoff_date:
                    file_size = log_file.stat().st_size
                    log_file.unlink()
                    deleted_count += 1
                    freed_bytes += file_size
                    logger.info(f"删除旧日志: {log_file.name} (修改时间: {mtime})")
            except Exception as e:
                logger.error(f"删除日志文件失败 {log_file}: {e}")
        
        # 清理旧的JSON记录文件（publish_records.json保留）
        for json_file in log_dir.glob('*.json'):
            if json_file.name == 'publish_records.json':
                continue
                
            try:
                mtime = datetime.fromtimestamp(json_file.stat().st_mtime)
                if mtime < cutoff_date:
                    file_size = json_file.stat().st_size
                    json_file.unlink()
                    deleted_count += 1
                    freed_bytes += file_size
                    logger.info(f"删除旧JSON文件: {json_file.name} (修改时间: {mtime})")
            except Exception as e:
                logger.error(f"删除JSON文件失败 {json_file}: {e}")
        
        logger.info(f"日志清理完成: 删除{deleted_count}个文件，释放{freed_bytes}字节")
        return deleted_count, freed_bytes
    
    def cleanup_old_images(self):
        """清理旧图片文件"""
        if not self.config.get('enabled', True):
            return
        
        image_dir = Path('/tmp/xhs-official/images')
        if not image_dir.exists():
            logger.info(f"图片目录不存在: {image_dir}")
            return 0, 0
        
        retention_days = self.config.get('image_retention_days', 7)
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        deleted_count = 0
        freed_bytes = 0
        
        logger.info(f"开始清理{retention_days}天前的图片文件...")
        
        # 支持的图片扩展名
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
        
        for image_file in image_dir.iterdir():
            try:
                # 检查扩展名
                if image_file.suffix.lower() not in image_extensions:
                    continue
                
                # 保留测试文件（以test_开头的文件）
                if image_file.name.startswith('test_'):
                    continue
                
                # 保留人物形象文件（以character_开头的文件）
                if image_file.name.startswith('character_'):
                    continue
                
                mtime = datetime.fromtimestamp(image_file.stat().st_mtime)
                if mtime < cutoff_date:
                    file_size = image_file.stat().st_size
                    image_file.unlink()
                    deleted_count += 1
                    freed_bytes += file_size
                    logger.info(f"删除旧图片: {image_file.name} (修改时间: {mtime})")
            except Exception as e:
                logger.error(f"删除图片文件失败 {image_file}: {e}")
        
        logger.info(f"图片清理完成: 删除{deleted_count}个文件，释放{freed_bytes}字节")
        return deleted_count, freed_bytes
    
    def cleanup_temp_files(self):
        """清理临时文件"""
        temp_dirs = [
            '/tmp/xhs-official/temp',
            '/tmp/xhs-automation-temp'
        ]
        
        deleted_count = 0
        freed_bytes = 0
        
        logger.info("开始清理临时文件...")
        
        for temp_dir in temp_dirs:
            temp_path = Path(temp_dir)
            if not temp_path.exists():
                continue
            
            cutoff_date = datetime.now() - timedelta(hours=24)  # 24小时前的临时文件
            
            for temp_file in temp_path.iterdir():
                try:
                    mtime = datetime.fromtimestamp(temp_file.stat().st_mtime)
                    if mtime < cutoff_date:
                        if temp_file.is_file():
                            file_size = temp_file.stat().st_size
                            temp_file.unlink()
                            deleted_count += 1
                            freed_bytes += file_size
                            logger.info(f"删除临时文件: {temp_file} (修改时间: {mtime})")
                        elif temp_file.is_dir():
                            shutil.rmtree(temp_file)
                            deleted_count += 1
                            logger.info(f"删除临时目录: {temp_file} (修改时间: {mtime})")
                except Exception as e:
                    logger.error(f"删除临时文件失败 {temp_file}: {e}")
        
        logger.info(f"临时文件清理完成: 删除{deleted_count}个项目，释放{freed_bytes}字节")
        return deleted_count, freed_bytes
    
    def check_disk_usage(self):
        """检查目录磁盘使用情况"""
        directories = [
            ('日志目录', '/home/ubuntu/xhs-automation/logs'),
            ('图片目录', '/tmp/xhs-official/images'),
            ('数据目录', '/tmp/xhs-official/data')
        ]
        
        results = {}
        
        for name, path in directories:
            dir_path = Path(path)
            if not dir_path.exists():
                results[name] = {"exists": False, "size_mb": 0}
                continue
            
            total_size = 0
            file_count = 0
            
            for file_path in dir_path.rglob('*'):
                if file_path.is_file():
                    try:
                        total_size += file_path.stat().st_size
                        file_count += 1
                    except Exception:
                        pass
            
            size_mb = total_size / (1024 * 1024)
            results[name] = {
                "exists": True,
                "size_mb": round(size_mb, 2),
                "file_count": file_count
            }
            
            # 检查是否超过限制
            if name == '日志目录':
                max_size = self.config.get('max_log_size_mb', 100)
                if size_mb > max_size:
                    logger.warning(f"警告: {name}大小({size_mb:.1f}MB)超过限制({max_size}MB)")
            elif name == '图片目录':
                max_size = self.config.get('max_image_dir_size_mb', 1024)
                if size_mb > max_size:
                    logger.warning(f"警告: {name}大小({size_mb:.1f}MB)超过限制({max_size}MB)")
        
        return results
    
    def run_comprehensive_cleanup(self):
        """运行全面清理"""
        logger.info("开始全面存储清理...")
        
        # 检查磁盘使用情况
        disk_usage = self.check_disk_usage()
        logger.info(f"磁盘使用情况: {json.dumps(disk_usage, indent=2, ensure_ascii=False)}")
        
        # 清理旧日志
        log_deleted, log_freed = self.cleanup_old_logs()
        
        # 清理旧图片
        img_deleted, img_freed = self.cleanup_old_images()
        
        # 清理临时文件
        temp_deleted, temp_freed = self.cleanup_temp_files()
        
        total_deleted = log_deleted + img_deleted + temp_deleted
        total_freed = log_freed + img_freed + temp_freed
        
        # 再次检查磁盘使用情况
        final_disk_usage = self.check_disk_usage()
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "log_files_deleted": log_deleted,
            "log_bytes_freed": log_freed,
            "image_files_deleted": img_deleted,
            "image_bytes_freed": img_freed,
            "temp_items_deleted": temp_deleted,
            "temp_bytes_freed": temp_freed,
            "total_deleted": total_deleted,
            "total_freed": total_freed,
            "initial_disk_usage": disk_usage,
            "final_disk_usage": final_disk_usage
        }
        
        logger.info(f"全面清理完成: 总计删除{total_deleted}个文件，释放{total_freed}字节")
        
        # 保存清理报告
        report_path = Path('/home/ubuntu/xhs-automation/logs/cleanup_report.json')
        reports = []
        
        if report_path.exists():
            try:
                with open(report_path, 'r', encoding='utf-8') as f:
                    reports = json.load(f)
            except Exception:
                reports = []
        
        reports.append(summary)
        
        # 只保留最近30次报告
        if len(reports) > 30:
            reports = reports[-30:]
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(reports, f, ensure_ascii=False, indent=2)
        
        return summary

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='存储清理工具')
    parser.add_argument('--cleanup-logs', action='store_true', help='清理旧日志')
    parser.add_argument('--cleanup-images', action='store_true', help='清理旧图片')
    parser.add_argument('--cleanup-temp', action='store_true', help='清理临时文件')
    parser.add_argument('--check-disk', action='store_true', help='检查磁盘使用情况')
    parser.add_argument('--full', action='store_true', help='运行全面清理')
    parser.add_argument('--config', help='配置文件路径')
    
    args = parser.parse_args()
    
    cleaner = StorageCleaner(args.config)
    
    if args.cleanup_logs:
        deleted, freed = cleaner.cleanup_old_logs()
        print(f"清理日志: 删除{deleted}个文件，释放{freed}字节")
    
    elif args.cleanup_images:
        deleted, freed = cleaner.cleanup_old_images()
        print(f"清理图片: 删除{deleted}个文件，释放{freed}字节")
    
    elif args.cleanup_temp:
        deleted, freed = cleaner.cleanup_temp_files()
        print(f"清理临时文件: 删除{deleted}个项目，释放{freed}字节")
    
    elif args.check_disk:
        usage = cleaner.check_disk_usage()
        print(json.dumps(usage, indent=2, ensure_ascii=False))
    
    elif args.full:
        summary = cleaner.run_comprehensive_cleanup()
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    
    else:
        # 默认运行全面清理
        summary = cleaner.run_comprehensive_cleanup()
        print(json.dumps(summary, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()