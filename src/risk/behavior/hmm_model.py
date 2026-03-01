"""
隐马尔可夫模型 (HMM) - 仿生行为决策
动态生成操作序列，模拟真实用户行为
支持基于时间和权重的动态调整
"""

import random
import time
import logging
from typing import List, Dict, Tuple, Optional
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class ActionState(Enum):
    """行为状态"""
    IDLE = "idle"
    BROWSE = "browse"
    DEEP_READ = "deep_read"
    LIKE = "like"
    COLLECT = "collect"
    COMMENT = "comment"
    SHARE = "share"
    EXIT = "exit"


class HMMBehaviorModel:
    """基于 HMM 的行为模型"""
    
    # 基础状态转移概率矩阵
    BASE_TRANSITION_MATRIX = {
        ActionState.IDLE: {
            ActionState.BROWSE: 0.7,
            ActionState.EXIT: 0.3,
        },
        ActionState.BROWSE: {
            ActionState.BROWSE: 0.4,
            ActionState.DEEP_READ: 0.25,
            ActionState.LIKE: 0.15,
            ActionState.EXIT: 0.2,
        },
        ActionState.DEEP_READ: {
            ActionState.LIKE: 0.3,
            ActionState.COLLECT: 0.2,
            ActionState.COMMENT: 0.15,
            ActionState.BROWSE: 0.15,
            ActionState.EXIT: 0.2,
        },
        ActionState.LIKE: {
            ActionState.COLLECT: 0.2,
            ActionState.COMMENT: 0.15,
            ActionState.BROWSE: 0.3,
            ActionState.EXIT: 0.35,
        },
        ActionState.COLLECT: {
            ActionState.COMMENT: 0.2,
            ActionState.SHARE: 0.1,
            ActionState.BROWSE: 0.3,
            ActionState.EXIT: 0.4,
        },
        ActionState.COMMENT: {
            ActionState.LIKE: 0.15,
            ActionState.COLLECT: 0.1,
            ActionState.BROWSE: 0.35,
            ActionState.EXIT: 0.4,
        },
        ActionState.SHARE: {
            ActionState.BROWSE: 0.3,
            ActionState.EXIT: 0.7,
        },
    }
    
    # 各状态的停留时间分布 (秒)
    DURATION_PARAMS = {
        ActionState.IDLE: (0.5, 1.5),
        ActionState.BROWSE: (2, 8),
        ActionState.DEEP_READ: (10, 30),
        ActionState.LIKE: (1, 3),
        ActionState.COLLECT: (2, 5),
        ActionState.COMMENT: (5, 15),
        ActionState.SHARE: (2, 5),
        ActionState.EXIT: (0, 0),
    }
    
    # 观察概率
    EMISSION_PROBABILITIES = {
        ActionState.BROWSE: {
            "scroll": 0.8,
            "view_image": 0.15,
            "view_comment": 0.05,
        },
        ActionState.DEEP_READ: {
            "view_image": 0.4,
            "view_comment": 0.4,
            "scroll": 0.2,
        },
        ActionState.LIKE: {
            "click_like": 0.9,
            "cancel_like": 0.1,
        },
        ActionState.COLLECT: {
            "click_collect": 0.95,
            "cancel_collect": 0.05,
        },
    }
    
    def __init__(self, seed: Optional[int] = None):
        if seed is not None:
            random.seed(seed)
        self.current_state = ActionState.IDLE
        self.action_history: List[Tuple[ActionState, str, float]] = []
        self.TRANSITION_MATRIX = self._copy_matrix(self.BASE_TRANSITION_MATRIX)
    
    def _copy_matrix(self, matrix: Dict) -> Dict:
        """深拷贝转移矩阵"""
        return {k: dict(v) for k, v in matrix.items()}
    
    def _get_time_multiplier(self) -> Dict[str, float]:
        """获取时间系数 (模拟真实用户作息)"""
        hour = datetime.now().hour
        
        if 0 <= hour < 6:
            return {"browse": 0.3, "interact": 0.2, "exit": 1.5}
        elif 6 <= hour < 9:
            return {"browse": 0.8, "interact": 0.6, "exit": 1.2}
        elif 9 <= hour < 12:
            return {"browse": 1.2, "interact": 1.0, "exit": 0.9}
        elif 12 <= hour < 14:
            return {"browse": 1.3, "interact": 1.2, "exit": 0.8}
        elif 14 <= hour < 18:
            return {"browse": 1.1, "interact": 1.0, "exit": 1.0}
        elif 18 <= hour < 22:
            return {"browse": 1.5, "interact": 1.5, "exit": 0.7}
        else:
            return {"browse": 0.6, "interact": 0.5, "exit": 1.3}
    
    def _apply_time_multiplier(self, multiplier: Dict[str, float]):
        """应用时间系数到转移矩阵"""
        for state, transitions in self.TRANSITION_MATRIX.items():
            if state == ActionState.BROWSE:
                if ActionState.LIKE in transitions:
                    transitions[ActionState.LIKE] *= multiplier.get("interact", 1.0)
                if ActionState.DEEP_READ in transitions:
                    transitions[ActionState.DEEP_READ] *= multiplier.get("browse", 1.0)
            elif state == ActionState.DEEP_READ:
                if ActionState.LIKE in transitions:
                    transitions[ActionState.LIKE] *= multiplier.get("interact", 1.0)
                if ActionState.COLLECT in transitions:
                    transitions[ActionState.COLLECT] *= multiplier.get("interact", 1.0)
            
            if ActionState.EXIT in transitions:
                transitions[ActionState.EXIT] *= multiplier.get("exit", 1.0)
    
    def next_action(self) -> Tuple[ActionState, str, float]:
        """
        生成下一个动作
        
        Returns:
            (下一个状态, 动作类型, 停留时间)
        """
        # 应用时间动态调整
        self.TRANSITION_MATRIX = self._copy_matrix(self.BASE_TRANSITION_MATRIX)
        time_multiplier = self._get_time_multiplier()
        self._apply_time_multiplier(time_multiplier)
        
        # 根据转移概率选择下一个状态
        transitions = self.TRANSITION_MATRIX.get(self.current_state, {})
        next_state = self._choose_next_state(transitions)
        
        # 获取停留时间
        duration = self._generate_duration(next_state)
        
        # 获取具体动作
        action = self._generate_action(next_state)
        
        # 记录历史
        self.action_history.append((next_state, action, duration))
        
        # 更新当前状态
        self.current_state = next_state
        
        return next_state, action, duration
    
    def _choose_next_state(self, transitions: Dict[ActionState, float]) -> ActionState:
        """根据概率选择下一个状态"""
        states = list(transitions.keys())
        probs = list(transitions.values())
        
        # 归一化概率
        total = sum(probs)
        probs = [p / total for p in probs]
        
        return random.choices(states, weights=probs, k=1)[0]
    
    def _generate_duration(self, state: ActionState) -> float:
        """生成停留时间"""
        min_dur, max_dur = self.DURATION_PARAMS.get(state, (1, 3))
        return random.uniform(min_dur, max_dur)
    
    def _generate_action(self, state: ActionState) -> str:
        """生成具体动作"""
        emissions = self.EMISSION_PROBABILITIES.get(state, {})
        if not emissions:
            return state.value
        
        actions = list(emissions.keys())
        probs = list(emissions.values())
        
        return random.choices(actions, weights=probs, k=1)[0]
    
    def generate_session(self, max_actions: int = 20) -> List[Dict]:
        """
        生成完整的互动会话
        
        Args:
            max_actions: 最大动作数
        
        Returns:
            动作序列
        """
        session = []
        
        for _ in range(max_actions):
            state, action, duration = self.next_action()
            
            if state == ActionState.EXIT:
                break
            
            session.append({
                "state": state.value,
                "action": action,
                "duration": duration,
            })
        
        return session
    
    def reset(self):
        """重置状态"""
        self.current_state = ActionState.IDLE
        self.action_history.clear()


class RiskAwareBehaviorModel(HMMBehaviorModel):
    """风险感知 + 时间动态行为了模型"""
    
    def __init__(self, account_weight: float = 1.0, topic_relevance: float = 1.0, **kwargs):
        """
        初始化
        
        Args:
            account_weight: 账号权重 (0.5-2.0), 越高越激进
            topic_relevance: 话题相关度 (0.5-2.0), 越高越可能互动
        """
        super().__init__(**kwargs)
        self.account_weight = max(0.5, min(account_weight, 2.0))
        self.topic_relevance = max(0.5, min(topic_relevance, 2.0))
        
        self._apply_account_weight()
    
    def _apply_account_weight(self):
        """根据账号权重调整概率"""
        if self.account_weight >= 1.5:
            if ActionState.BROWSE in self.TRANSITION_MATRIX:
                self.TRANSITION_MATRIX[ActionState.BROWSE][ActionState.LIKE] += 0.1
                self.TRANSITION_MATRIX[ActionState.BROWSE][ActionState.DEEP_READ] -= 0.1
        elif self.account_weight <= 0.7:
            if ActionState.BROWSE in self.TRANSITION_MATRIX:
                self.TRANSITION_MATRIX[ActionState.BROWSE][ActionState.LIKE] -= 0.1
                self.TRANSITION_MATRIX[ActionState.BROWSE][ActionState.EXIT] += 0.1
    
    def boost_topic_interaction(self, boost_factor: float = 1.5):
        """临时提升话题互动概率"""
        for state in [ActionState.DEEP_READ, ActionState.BROWSE]:
            if state in self.TRANSITION_MATRIX:
                if ActionState.LIKE in self.TRANSITION_MATRIX[state]:
                    self.TRANSITION_MATRIX[state][ActionState.LIKE] *= boost_factor
                if ActionState.COLLECT in self.TRANSITION_MATRIX[state]:
                    self.TRANSITION_MATRIX[state][ActionState.COLLECT] *= boost_factor


def get_behavior_model(account_weight: float = 1.0, topic_relevance: float = 1.0) -> RiskAwareBehaviorModel:
    """获取行为模型实例"""
    return RiskAwareBehaviorModel(account_weight=account_weight, topic_relevance=topic_relevance)
