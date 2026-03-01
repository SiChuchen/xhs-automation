"""
DFA 敏感词过滤器
使用确定有限状态机 (DFA) 算法进行高效敏感词匹配
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import List, Set, Optional, Dict, Any

logger = logging.getLogger(__name__)


class DFAFilter:
    """DFA 敏感词过滤器"""
    
    def __init__(self, sensitive_words: Optional[List[str]] = None, word_file: Optional[str] = None):
        """
        初始化 DFA 过滤器
        
        Args:
            sensitive_words: 敏感词列表
            word_file: 敏感词文件路径 (JSON/TXT)
        """
        self._word_tree = {}
        self._max_word_len = 0
        
        words = sensitive_words or []
        
        if word_file:
            words.extend(self._load_words_from_file(word_file))
        
        if words:
            self.build_word_tree(words)
        
        logger.info(f"DFA 过滤器初始化完成，敏感词数量: {len(words)}")
    
    def _load_words_from_file(self, filepath: str) -> List[str]:
        """从文件加载敏感词"""
        words = []
        
        if not os.path.exists(filepath):
            logger.warning(f"敏感词文件不存在: {filepath}")
            return words
        
        try:
            if filepath.endswith('.json'):
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        words = data
                    elif isinstance(data, dict):
                        words = data.get('words', [])
            else:
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        word = line.strip()
                        if word and not word.startswith('#'):
                            words.append(word)
        except Exception as e:
            logger.error(f"加载敏感词文件失败: {e}")
        
        return words
    
    def build_word_tree(self, words: List[str]):
        """构建词树"""
        self._word_tree = {}
        self._max_word_len = 0
        
        for word in words:
            word = word.strip()
            if not word:
                continue
            
            self._max_word_len = max(self._max_word_len, len(word))
            
            tree = self._word_tree
            for char in word:
                if char not in tree:
                    tree[char] = {}
                tree = tree[char]
            
            tree[0] = True  # 标记词尾
    
    def add_word(self, word: str):
        """添加敏感词"""
        word = word.strip()
        if not word:
            return
        
        self._max_word_len = max(self._max_word_len, len(word))
        
        tree = self._word_tree
        for char in word:
            if char not in tree:
                tree[char] = {}
            tree = tree[char]
        
        tree[0] = True
    
    def filter(self, text: str, replace_char: str = "*") -> str:
        """
        过滤文本中的敏感词
        
        Args:
            text: 待过滤文本
            replace_char: 替换字符
        
        Returns:
            过滤后的文本
        """
        if not text or not self._word_tree:
            return text
        
        result = list(text)
        
        for i in range(len(text)):
            if self._is_sensitive(i, text):
                for j in range(i, min(i + self._max_word_len, len(text))):
                    if self._is_sensitive(j, text):
                        result[j] = replace_char
                    else:
                        break
        
        return ''.join(result)
    
    def _is_sensitive(self, pos: int, text: str) -> bool:
        """检查位置是否是敏感词的一部分"""
        tree = self._word_tree
        
        for i in range(pos, len(text)):
            char = text[i]
            
            if char not in tree:
                return False
            
            tree = tree[char]
            
            if tree.get(0):
                return True
        
        return False
    
    def find_all(self, text: str) -> List[Dict[str, Any]]:
        """
        查找所有敏感词
        
        Returns:
            [{'word': '敏感词', 'start': 0, 'end': 2}, ...]
        """
        if not text or not self._word_tree:
            return []
        
        found = []
        
        for i in range(len(text)):
            tree = self._word_tree
            current_pos = i
            word = ""
            
            while current_pos < len(text):
                char = text[current_pos]
                
                if char not in tree:
                    break
                
                word += char
                tree = tree[char]
                
                if tree.get(0):
                    found.append({
                        'word': word,
                        'start': i,
                        'end': current_pos + 1
                    })
                
                current_pos += 1
        
        return found
    
    def contains_sensitive(self, text: str) -> bool:
        """检查是否包含敏感词"""
        return len(self.find_all(text)) > 0
    
    def get_sensitive_words(self, text: str) -> Set[str]:
        """获取文本中的敏感词集合"""
        return {f['word'] for f in self.find_all(text)}
    
    def get_max_word_len(self) -> int:
        """获取最长敏感词长度"""
        return self._max_word_len


class SensitiveWordFilter:
    """敏感词过滤器 - 整合 DFA 和其他功能"""
    
    DEFAULT_WORD_FILE = "config/sensitive_words.json"
    
    def __init__(self, word_file: Optional[str] = None):
        self.dfa = DFAFilter(word_file=word_file or self.DEFAULT_WORD_FILE)
        self._compile_patterns()
    
    def _compile_patterns(self):
        """编译额外的高级匹配模式"""
        self._patterns = [
            (re.compile(r'1[3-9]\d{9}'), '手机号'),
            (re.compile(r'\d{17}[\dXx]'), '身份证号'),
            (re.compile(r'\d{4}-\d{2}-\d{2}'), '日期'),
            (re.compile(r'http[s]?://[^\s]+'), 'URL'),
        ]
    
    def check(self, text: str) -> tuple[bool, List[Dict]]:
        """
        检查文本是否包含敏感内容
        
        Returns:
            (is_safe, issues)
            issues: [{'type': 'sensitive_word'|'pattern', 'content': 'xxx', 'position': 0}, ...]
        """
        issues = []
        
        if not text:
            return True, []
        
        sensitive_words = self.dfa.find_all(text)
        for sw in sensitive_words:
            issues.append({
                'type': 'sensitive_word',
                'content': sw['word'],
                'position': sw['start']
            })
        
        for pattern, label in self._patterns:
            for match in pattern.finditer(text):
                issues.append({
                    'type': 'pattern',
                    'pattern_type': label,
                    'content': match.group()[:20] + '...' if len(match.group()) > 20 else match.group(),
                    'position': match.start()
                })
        
        return len(issues) == 0, issues
    
    def filter(self, text: str, replace_char: str = "*") -> str:
        """过滤敏感词"""
        text = self.dfa.filter(text, replace_char)
        
        for pattern, label in self._patterns:
            text = pattern.sub(f'[{label}]', text)
        
        return text
    
    def add_sensitive_words(self, words: List[str]):
        """添加敏感词"""
        for word in words:
            self.dfa.add_word(word)
    
    def reload_words(self, word_file: str):
        """重新加载敏感词"""
        self.dfa = DFAFilter(word_file=word_file)
        logger.info(f"敏感词已重新加载: {word_file}")


_default_filter = None


def get_sensitive_word_filter(word_file: Optional[str] = None) -> SensitiveWordFilter:
    """获取全局敏感词过滤器"""
    global _default_filter
    if _default_filter is None:
        _default_filter = SensitiveWordFilter(word_file=word_file)
    return _default_filter


def check_text_safety(text: str) -> tuple[bool, List[Dict]]:
    """便捷函数: 检查文本安全性"""
    filter = get_sensitive_word_filter()
    return filter.check(text)


def filter_sensitive_words(text: str, replace_char: str = "*") -> str:
    """便捷函数: 过滤敏感词"""
    filter = get_sensitive_word_filter()
    return filter.filter(text, replace_char)
