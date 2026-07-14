"""
抽象模板基类

定义合成模板的接口，各领域的具体模板实现此接口。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from synth_engine.core.models import SynthSample


class SynthTemplate(ABC):
    """抽象合成模板"""

    @property
    @abstractmethod
    def name(self) -> str:
        """模板名称"""

    @abstractmethod
    def load_intent_config(self, config_path: str) -> Dict[str, Any]:
        """加载意图/领域配置"""

    @abstractmethod
    def load_synth_config(self, config_path: str) -> Dict[str, Any]:
        """加载合成概率配置"""

    @abstractmethod
    def build_prompt(self, sample: SynthSample, template_path: str) -> str:
        """根据模板构建 LLM prompt"""

    @abstractmethod
    def validate_response(self, response: str) -> bool:
        """验证 LLM 响应格式"""

    @abstractmethod
    def extract_query(self, response: str) -> str:
        """从 LLM 响应中提取最终 query"""

    @abstractmethod
    def gen_controller_data(self, sample: SynthSample) -> Dict[str, Any]:
        """生成 SFT 控制器数据"""
