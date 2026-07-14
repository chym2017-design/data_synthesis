"""
银行意图识别模板

第一个具体的合成模板，从 syn/ 目录的配置和代码中提取。
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from cn2an import an2cn

from synth_engine.templates.base import SynthTemplate
from synth_engine.core.models import SynthSample
from synth_engine.templates.registry import TemplateRegistry


class BankIntentTemplate(SynthTemplate):
    """银行意图识别数据合成模板"""

    @property
    def name(self) -> str:
        return "bank_intent"

    def load_intent_config(self, config_path: str) -> Dict[str, Any]:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_synth_config(self, config_path: str) -> Dict[str, Any]:
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def build_prompt(self, sample: SynthSample, template_path: str) -> str:
        """填充 prompt 模板变量"""
        with open(template_path, "r", encoding="utf-8") as f:
            prompt = f.read().strip()

        variables = {
            "user_profile": sample.user_profile,
            "intent_1": sample.intent_1,
            "intent_2": sample.intent_2,
            "sub_intent_1": sample.sub_intent_1,
            "sub_intent_2": sample.sub_intent_2,
            "sub_intent_desc_1": sample.sub_intent_desc_1,
            "sub_intent_desc_2": sample.sub_intent_desc_2,
            "round": an2cn(sample.round_num),
            "num_sen": an2cn(sample.num_sen),
            "yuqi": sample.yuqi,
            "menu_list": sample.menu_list,
            "intent_transition_constraint": sample.intent_transition_constraint,
        }

        for key, value in variables.items():
            prompt = prompt.replace("{{" + key + "}}", str(value))

        return prompt

    def validate_response(self, response: str) -> bool:
        """检查响应是否包含正确的对话格式"""
        if not response or response == "nan" or isinstance(response, float):
            return False
        r_lst = [rr for rr in str(response).split("\n") if rr]
        for rr in r_lst:
            if not re.search(r"^(用户：|客服：)", rr):
                return False
        return True

    def extract_query(self, response: str) -> str:
        """提取最后一轮用户请求"""
        r_lst = [r for r in str(response).split("\n") if r]
        while r_lst and not r_lst[-1].startswith("用户："):
            r_lst.pop()
        return "\n".join(r_lst)

    def gen_controller_data(self, sample: SynthSample) -> Dict[str, Any]:
        """生成 SFT 控制器数据"""
        history_lst = []
        for line in str(sample.query).split("\n"):
            if line.startswith("用户："):
                history_lst.append({"role": "user", "content": line[3:]})
            elif line.startswith("客服："):
                history_lst.append({"role": "assistant", "content": line[3:]})

        history_str = json.dumps(history_lst, ensure_ascii=False)
        current_query = history_lst[-1]["content"] if history_lst and history_lst[-1]["role"] == "user" else ""

        intent_1_json = json.dumps({"class": sample.intent_1}, ensure_ascii=False)
        intent_2_json = json.dumps({"class": sample.intent_2}, ensure_ascii=False)

        if sample.intent_1 == sample.intent_2:
            target_json = json.dumps({"class": sample.sub_intent_2}, ensure_ascii=False)
        else:
            target_json = json.dumps({"class": "默认分类"}, ensure_ascii=False)

        return {
            "intent_descr": f"- {sample.sub_intent_1}: {sample.sub_intent_desc_1}\n\n- {sample.sub_intent_2}: {sample.sub_intent_desc_2}",
            "history": history_str,
            "query": current_query,
            "intent_1": intent_1_json,
            "intent_2": intent_2_json,
            "target": target_json,
        }


# 自动注册
TemplateRegistry.register("bank_intent", BankIntentTemplate)
