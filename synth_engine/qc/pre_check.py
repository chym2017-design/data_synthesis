"""
合成前质检模块

基于 LLM-as-Judge 对意图配置进行质量检查。
"""

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from synth_engine.core.models import RunStatus
from synth_engine.llm.parallel import run_llm_para
from synth_engine.llm.embedding import get_embedding, compute_cosine_similarity_matrix


MENU_QUALITY_PROMPT = """你是一位专业的银行菜单定义质检专家。请对以下菜单定义进行质量检查。

## 待检查菜单

**菜单名称**: {menu_name}
**子意图名称**: {sub_intent_name}
**描述内容**:
```
{description}
```

## 检查维度

请逐项检查，并在 reasoning 字段中记录你的思考过程：

### 1. 错别字检查
- 拼写错误、标点不规范、语法错误

### 2. 一致性检查（菜单名与描述匹配）
- 菜单名与描述是否匹配？是否存在张冠李戴？
- 同一菜单下的不同子意图之间是否有重复或重叠？

### 3. 描述质量检查
- 清晰度：描述是否能明确区分此菜单意图？是否对非金融专业人士易理解？
- 长度：描述是否足够详细但又不过于冗长？
- 歧义性：是否存在可能导致歧义的用语？
- 业务场景示例：描述是否包含具体的金融业务上下文？

### 4. 判断可行性检查
- 用户能否仅凭这条菜单描述，正确判断一个查询是否属于此类别？
- 描述是否包含了所有必要的区分信息？
- 如果缺乏关键区分信息，请在 missing_info 中说明缺少什么。

请输出严格的 JSON 格式：
```json
{{
    "reasoning": "你对各项检查的综合分析",
    "typo_check": {{"has_issue": true/false, "issues": []}},
    "consistency_check": {{"has_issue": true/false, "issues": []}},
    "quality_check": {{"has_issue": true/false, "issues": [], "clarity_score": 5}},
    "judgment_feasibility_check": {{"has_issue": true/false, "issues": [], "can_judge_user_intent": true/false, "missing_info": ""}},
    "overall_assessment": {{"severity": "none|minor|major|critical", "suggestion": ""}}
}}
```

请只输出 JSON："""


SIMILAR_MENU_PROMPT = """你是一位银行菜单设计专家。请判断以下两个菜单是否存在定义混淆风险。

## 菜单 A
**菜单名称**: {menu_name_a}
**子意图名称**: {sub_intent_name_a}
**描述**: {description_a}

## 菜单 B
**菜单名称**: {menu_name_b}
**子意图名称**: {sub_intent_name_b}
**描述**: {description_b}

请输出 JSON：
```json
{{"is_confusable": true/false, "confusion_score": 0, "reason": "", "suggestion": ""}}
```

请只输出 JSON："""


def pre_synthesis_qc(
    intent_file: str,
    llm_configs: List[Dict],
    save_dir: str,
    para: int = 3,
    embedding_config: Optional[Dict] = None,
    similarity_threshold: float = 0.7,
    status_callback: Optional[Callable[[RunStatus], None]] = None,
) -> Dict[str, str]:
    """
    合成前意图配置质检。

    Returns:
        {"quality": path, "similarity": path} 结果文件路径
    """
    Path(save_dir).mkdir(parents=True, exist_ok=True)

    with open(intent_file, "r", encoding="utf-8") as f:
        intent_data = json.load(f)

    intent = intent_data.get("intent", {})
    menu_items = []
    for menu_name, menu_data in intent.items():
        for sub in menu_data.get("sub_intent", []):
            menu_items.append({
                "menu_name": menu_name,
                "sub_intent_name": sub.get("name", ""),
                "description": sub.get("description", ""),
            })

    results = {}

    # 任务1：菜单质检
    queries = []
    for item in menu_items:
        prompt = MENU_QUALITY_PROMPT.format(**item)
        queries.append(prompt)

    if status_callback:
        status_callback(RunStatus(run_id="", stage="quality_check", total=len(queries), current=0, message="正在执行菜单质检..."))

    cfg_with_json = []
    for cfg in llm_configs:
        c = cfg.copy()
        c["response_format"] = {"type": "json_object"}
        cfg_with_json.append(c)

    df_qc = run_llm_para(queries, para, cfg_with_json)
    if df_qc is not None:
        qc_records = []
        for i, (_, row) in enumerate(df_qc.iterrows()):
            item = menu_items[i]
            response = row.get("response", "")
            try:
                json_match = re.search(r"\{.*\}", response, re.DOTALL)
                result_data = json.loads(json_match.group()) if json_match else {}
            except json.JSONDecodeError:
                result_data = {}

            def _get_issues(data, key):
                val = data.get(key)
                if isinstance(val, dict):
                    return val.get("issues", [])
                return []

            def _get_nested(data, key, subkey, default=None):
                val = data.get(key)
                if isinstance(val, dict):
                    return val.get(subkey, default)
                return default

            qc_records.append({
                "menu_name": item["menu_name"],
                "sub_intent_name": item["sub_intent_name"],
                "description": item["description"],
                "model": row.get("model", ""),
                "reasoning": _get_nested(result_data, "", "reasoning", ""),
                "typo_issues": "|".join(_get_issues(result_data, "typo_check")),
                "consistency_issues": "|".join(_get_issues(result_data, "consistency_check")),
                "quality_issues": "|".join(_get_issues(result_data, "quality_check")),
                "clarity_score": _get_nested(result_data, "quality_check", "clarity_score", 0),
                "judgment_issues": "|".join(_get_issues(result_data, "judgment_feasibility_check")),
                "can_judge_user_intent": _get_nested(result_data, "judgment_feasibility_check", "can_judge_user_intent", False),
                "missing_info": _get_nested(result_data, "judgment_feasibility_check", "missing_info", ""),
                "severity": _get_nested(result_data, "overall_assessment", "severity", "unknown"),
                "suggestion": _get_nested(result_data, "overall_assessment", "suggestion", ""),
            })

        quality_path = str(Path(save_dir) / "quality_check_results.csv")
        pd.DataFrame(qc_records).to_csv(quality_path, index=False)
        results["quality"] = quality_path

    if status_callback:
        status_callback(RunStatus(run_id="", stage="similarity_check", message="正在检测相似菜单..."))

    # 任务2：相似菜单检测
    if embedding_config and len(menu_items) > 1:
        base_url = embedding_config.get("url", "").replace("/chat/completions", "").replace("/embeddings", "")
        api_key = embedding_config.get("api_key", "")
        model = embedding_config.get("model", "text-embedding-v3")

        embeddings = []
        for item in menu_items:
            emb = get_embedding(item["description"], base_url=base_url, api_key=api_key, model=model)
            embeddings.append(emb)

        sim_matrix = compute_cosine_similarity_matrix(embeddings)
        similar_pairs = []
        for i in range(len(menu_items)):
            for j in range(i + 1, len(menu_items)):
                sim = sim_matrix[i][j]
                if sim >= similarity_threshold:
                    similar_pairs.append((i, j, sim))

        if similar_pairs:
            sim_queries = []
            sim_info = []
            for i, j, score in similar_pairs:
                a, b = menu_items[i], menu_items[j]
                prompt = SIMILAR_MENU_PROMPT.format(
                    menu_name_a=a["menu_name"], sub_intent_name_a=a["sub_intent_name"],
                    description_a=a["description"],
                    menu_name_b=b["menu_name"], sub_intent_name_b=b["sub_intent_name"],
                    description_b=b["description"],
                )
                sim_queries.append(prompt)
                sim_info.append((a, b, score))

            df_sim = run_llm_para(sim_queries, para, llm_configs)
            if df_sim is not None:
                sim_records = []
                for idx, (_, row) in enumerate(df_sim.iterrows()):
                    if idx < len(sim_info):
                        a, b, score = sim_info[idx]
                        response = row.get("response", "")
                        try:
                            json_match = re.search(r"\{.*\}", response, re.DOTALL)
                            rd = json.loads(json_match.group()) if json_match else {}
                        except json.JSONDecodeError:
                            rd = {}
                        sim_records.append({
                            "menu_a": f"{a['menu_name']}/{a['sub_intent_name']}",
                            "menu_b": f"{b['menu_name']}/{b['sub_intent_name']}",
                            "similarity_score": score,
                            "is_confusable": bool(rd.get("is_confusable", False)),
                            "confusion_score": float(rd.get("confusion_score", 0)),
                            "reason": str(rd.get("reason", "")),
                            "suggestion": str(rd.get("suggestion", "")),
                        })

                sim_path = str(Path(save_dir) / "similarity_check_results.csv")
                pd.DataFrame(sim_records).to_csv(sim_path, index=False)
                results["similarity"] = sim_path

    if status_callback:
        status_callback(RunStatus(run_id="", stage="done", message="质检完成"))

    return results
