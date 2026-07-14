"""
配置加载与验证模块

使用 Pydantic 模型验证配置结构，支持 YAML 配置加载。
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, model_validator


# ============ 合成配置模型 ============

class RoundDistribution(BaseModel):
    single_intent: List[List[Any]] = Field(default_factory=lambda: [[1, 0.3], [2, 0.3], [3, 0.3], [4, 0.1]])
    multi_intent: List[List[Any]] = Field(default_factory=lambda: [[2, 0.25], [3, 0.5], [4, 0.1], [5, 0.1], [6, 0.05]])


class IntentTransition(BaseModel):
    """意图跳转配置：单/多意图概率 + 多意图内细分条件概率"""
    single_intent_prob: float = 0.3                     # 单意图概率
    multi_intent_prob: float = 0.7                       # 多意图概率（= 1 - single_intent_prob）
    same_intent_multi_subintent_ratio: float = 0.8       # 多意图中同意图多子意图的条件概率
    cross_intent_jump: float = 0.2                       # 多意图中跨意图跳转的条件概率（= 1 - same_intent_multi_subintent_ratio）


class MoodConfig(BaseModel):
    probability: float = 0.3
    emotions: List[str] = Field(default_factory=lambda: ["兴奋", "开心", "愉快", "平静", "沮丧", "悲伤", "愤怒", "焦虑"])


class IntentTransitionConstraint(BaseModel):
    switch_at_terminal_turn_ratio: float = 0.2


class SynthConfigModel(BaseModel):
    """合成流程配置"""
    round_distribution: RoundDistribution = Field(default_factory=RoundDistribution)
    intent_transition: IntentTransition = Field(default_factory=IntentTransition)
    single_round_ratio: float = 0.05
    tone_distribution: Dict[str, float] = Field(default_factory=lambda: {
        "祈使句": 0.60,
        "问句": 0.15,
        "反问句": 0.10,
        "倒装句": 0.05,
        "长短复合句": 0.05,
        "带错别字的请求": 0.05,
    })
    mood: MoodConfig = Field(default_factory=MoodConfig)
    intent_transition_constraint: IntentTransitionConstraint = Field(default_factory=IntentTransitionConstraint)

    @model_validator(mode="after")
    def validate_probabilities(self):
        """验证概率总和为 1"""
        tone_sum = sum(self.tone_distribution.values())
        if abs(tone_sum - 1.0) > 1e-6:
            raise ValueError(f"tone_distribution 概率总和为 {tone_sum}，应为 1.0")
        return self


# ============ 画像配置模型 ============

class DebitCardConfig(BaseModel):
    level_weights: Dict[str, float] = Field(default_factory=lambda: {
        "普卡": 0.60, "金卡": 0.25, "白金卡": 0.12, "钻石卡": 0.03,
    })
    count: Dict[str, Any] = Field(default_factory=lambda: {"single_prob": 0.55, "multi_max": 4})


class CreditCardConfig(BaseModel):
    has_probability: float = 0.7


class HoldingsProbability(BaseModel):
    has_payees: float = 0.7
    has_fund: float = 0.6
    has_wealth: float = 0.5
    has_insurance: float = 0.5
    has_bond: float = 0.3
    has_metals: float = 0.2
    has_loan: float = 0.6


class ServiceProbability(BaseModel):
    has_udun: float = 0.5
    has_social_security: float = 0.8
    has_medical_insurance: float = 0.9
    has_housing_fund: float = 0.7
    has_personal_pension: float = 0.4
    has_digital_rmb: float = 0.6
    has_salary_card: float = 0.8
    has_payment_agreements: float = 0.7


class ProfileConfigModel(BaseModel):
    """画像生成配置"""
    debit_card: DebitCardConfig = Field(default_factory=DebitCardConfig)
    credit_card: CreditCardConfig = Field(default_factory=CreditCardConfig)
    holdings_probability: HoldingsProbability = Field(default_factory=HoldingsProbability)
    service_probability: ServiceProbability = Field(default_factory=ServiceProbability)
    balance_distribution: Dict[str, Dict[str, float]] = Field(default_factory=dict)


# ============ 配置加载器 ============

# 这些字段即使值是数字字符串也应保持字符串类型
_STRING_FIELDS = {"phone_prefixes"}


def _convert_numeric_strings(obj, parent_key=None):
    """递归将配置中可转为数字的字符串转换为 int/float，排除特定字段"""
    if isinstance(obj, dict):
        return {k: _convert_numeric_strings(v, parent_key=k) for k, v in obj.items()}
    elif isinstance(obj, list):
        if parent_key in _STRING_FIELDS:
            return obj  # 保持字符串类型
        return [_convert_numeric_strings(item, parent_key=parent_key) for item in obj]
    elif isinstance(obj, str):
        try:
            return int(obj)
        except ValueError:
            try:
                return float(obj)
            except ValueError:
                return obj
    return obj


class ConfigLoader:
    """统一配置加载器"""

    @staticmethod
    def load_yaml(path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return _convert_numeric_strings(data)

    @staticmethod
    def load_synth_config(path: str) -> SynthConfigModel:
        data = ConfigLoader.load_yaml(path)
        return SynthConfigModel(**data)

    @staticmethod
    def load_profile_config(path: str) -> ProfileConfigModel:
        data = ConfigLoader.load_yaml(path)
        return ProfileConfigModel(**data)

    @staticmethod
    def load_intent_config(path: str) -> Dict[str, Any]:
        return ConfigLoader.load_yaml(path)

    @staticmethod
    def load_prompt(path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """递归合并两个 dict，override 中的值覆盖 base 中的同名字段。"""
    result = base.copy()
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result
