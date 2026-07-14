"""
模板注册中心入口

导入时自动加载所有模板，触发自动注册。
"""

from synth_engine.templates import bank_intent  # noqa: F401
from synth_engine.templates.registry import TemplateRegistry
