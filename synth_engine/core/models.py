"""
通用数据模型

定义合成流水线中各环节使用的数据结构。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SynthSample:
    """一条合成样本的中间表示"""
    sample_id: int
    # 意图信息
    intent_1: str
    intent_2: str
    sub_intent_1: str
    sub_intent_2: str
    sub_intent_desc_1: str
    sub_intent_desc_2: str
    # 目标标签
    target: Dict[str, str]
    # 用户画像
    user_profile: str
    # 对话参数
    round_num: int
    num_sen: int
    yuqi: str
    xinqing: str
    # 可选
    menu_list: str = ""
    intent_transition_constraint: str = ""
    single_round: bool = False
    # LLM 响应
    response: str = ""
    query: str = ""
    # 元数据
    model: str = ""
    duration: float = 0.0
    status_code: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_1": self.intent_1,
            "intent_2": self.intent_2,
            "sub_intent_1": self.sub_intent_1,
            "sub_intent_2": self.sub_intent_2,
            "sub_intent_desc_1": self.sub_intent_desc_1,
            "sub_intent_desc_2": self.sub_intent_desc_2,
            "target": self.target,
            "user_profile": self.user_profile,
            "round": str(self.round_num),
            "num_sen": str(self.num_sen),
            "yuqi": self.yuqi,
            "xinqing": self.xinqing,
            "menu_list": self.menu_list,
            "intent_transition_constraint": self.intent_transition_constraint,
            "single_round": self.single_round,
            "response": self.response,
            "query": self.query,
        }


@dataclass
class LLMResult:
    """LLM 调用结果"""
    idx: int
    question: str
    response: str
    model: str = ""
    duration: float = 0.0
    status_code: int = 0
    err_msg: str = ""
    reasoning_content: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class QCResult:
    """质检结果"""
    sample_idx: int
    query: str
    true_level1: str
    true_level2: str
    pred_level1: str = ""
    pred_level2: str = ""
    level1_correct: bool = False
    level2_correct: bool = False
    overall_correct: bool = False
    model: str = ""
    severity: str = "unknown"
    suggestion: str = ""


@dataclass
class RunStatus:
    """运行状态（用于前端进度推送）"""
    run_id: str
    stage: str = ""  # "generating", "calling_llm", "filtering", "exporting", "done", "error"
    total: int = 0
    current: int = 0
    message: str = ""
    error: str = ""

    @property
    def progress(self) -> float:
        if self.total == 0:
            return 0.0
        return self.current / self.total
