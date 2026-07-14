"""
模板注册中心

管理所有已注册的合成模板。
"""

from typing import Dict, List, Type

from synth_engine.templates.base import SynthTemplate


class TemplateRegistry:
    _templates: Dict[str, Type[SynthTemplate]] = {}

    @classmethod
    def register(cls, name: str, template_class: Type[SynthTemplate]):
        """注册一个模板类"""
        cls._templates[name] = template_class

    @classmethod
    def get(cls, name: str) -> SynthTemplate:
        """获取模板实例"""
        if name not in cls._templates:
            available = list(cls._templates.keys())
            raise ValueError(f"模板 '{name}' 未注册。可用模板: {available}")
        return cls._templates[name]()

    @classmethod
    def list(cls) -> List[str]:
        """列出所有已注册的模板名称"""
        return list(cls._templates.keys())

    @classmethod
    def has(cls, name: str) -> bool:
        return name in cls._templates
