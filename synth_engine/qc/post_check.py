"""
合成后质检模块

基于 LLM 多模型投票和 Embedding 相似度检测。
"""

import json
import random
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from synth_engine.core.models import RunStatus
from synth_engine.llm.parallel import run_llm_para_with_assign
from synth_engine.llm.embedding import get_embedding, compute_cosine_similarity_matrix, cosine_similarity


def build_intent_prompt(
    intent_config: Dict,
    level: int = 1,
    parent_intent: Optional[str] = None,
    reference_target: Optional[str] = None,
    reference_desc: Optional[str] = None,
) -> str:
    """构建意图判定 Prompt"""
    if level == 1:
        intent_list = []
        for iname, idata in intent_config.get("intent", {}).items():
            desc = idata.get("description", "")
            if not desc:
                sub_names = [s.get("name", "") for s in idata.get("sub_intent", [])]
                desc = "、".join(sub_names)
            intent_list.append(f"  - {iname}: {desc}")
        intent_label = "一级意图"
        intent_type = "一级意图类别"
    else:
        if parent_intent is None:
            return ""
        idata = intent_config.get("intent", {}).get(parent_intent, {})
        sub_intents = idata.get("sub_intent", [])
        intent_list = []
        for sub in sub_intents:
            name = sub.get("name", "")
            desc = sub.get("description", "").replace("\n", "\\n")
            intent_list.append(f"  - {name}: {desc}")
        intent_label = "二级意图"
        intent_type = "二级意图（子意图）"

    # 外部标注参考
    reference_info = ""
    if reference_target:
        try:
            target_data = json.loads(str(reference_target).replace('""', '"'))
            ref_intent = target_data.get("意图", "")
            ref_sub_intent = target_data.get("子意图", "")
            reference_info = f"\n【外部标注参考】（仅供参考，你仍需独立判断）\n该查询被标注为：意图「{ref_intent}」下的子意图「{ref_sub_intent}」"
            if reference_desc:
                reference_info += f"，该子意图的描述为：{reference_desc}"
            reference_info += "\n"
        except Exception:
            reference_info = f"\n【外部标注参考】（仅供参考，你仍需独立判断）\n标注的意图标签：{reference_target}\n"

    intent_options = "\n".join(intent_list)
    # Escape user-data curly braces to prevent .format() KeyError
    intent_options = intent_options.replace("{", "{{").replace("}", "}}")
    reference_info = reference_info.replace("{", "{{").replace("}", "}}")
    return f"""你是一个银行客服意图识别专家。

可选的{intent_type}：
{intent_options}

用户查询：{{query}}
{reference_info}

请输出以下格式的JSON：
{{{{
    "{intent_label}": "从上述列表中选择最匹配的一个",
    "置信度": 0.95
}}}}

注意：
1. {intent_label}必须从上述列表中精确选择，不要修改名称
2. 置信度范围0-1
3. 只输出JSON，不要有其他文字
4. 如果是多轮对话，判定的是用户最后一轮对话的意图
5. 外部标注结果仅供参考，你仍需根据用户查询内容独立判断"""


def match_intent(pred: str, true: str) -> bool:
    """匹配预测意图与真实意图"""
    if not pred or pd.isna(pred):
        return False
    pred = str(pred).strip()
    true = str(true).strip()

    try:
        json_start = pred.find("{")
        json_end = pred.rfind("}")
        if json_start >= 0 and json_end > json_start:
            data = json.loads(pred[json_start:json_end + 1])
            for key in ["一级意图", "二级意图", "意图", "intent", "category"]:
                if key in data:
                    pred_intent = str(data[key]).strip()
                    if true in pred_intent or pred_intent in true:
                        return True
    except Exception:
        pass

    if true in pred or pred in true:
        return True
    if pred.lower().replace(" ", "") == true.lower().replace(" ", ""):
        return True
    return False


def _sample_dataframe(df: pd.DataFrame, sample_size: Optional[int]) -> pd.DataFrame:
    """从 DataFrame 采样"""
    if sample_size and len(df) > sample_size:
        return df.sample(n=sample_size, random_state=42)
    return df


def embedding_similarity_check(
    data_file: str,
    embedding_config: Dict,
    save_dir: str,
    threshold: float = 0.95,
    sample_size: Optional[int] = None,
    status_callback: Optional[Callable[[RunStatus], None]] = None,
) -> str:
    """基于 embedding 的相似语料检查"""
    Path(save_dir).mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(data_file, index_col=0)
    df = _sample_dataframe(df, sample_size)
    df = df.reset_index(drop=True)

    def parse_target(s):
        try:
            t = json.loads(str(s).replace('""', '"'))
            return t.get("意图", ""), t.get("子意图", "")
        except Exception:
            return "", ""

    parsed = df["target"].apply(parse_target)
    df["true_intent"] = [p[0] for p in parsed]
    df["true_sub_intent"] = [p[1] for p in parsed]

    base_url = embedding_config.get("url", "").replace("/chat/completions", "").replace("/embeddings", "")
    api_key = embedding_config.get("api_key", "")
    model = embedding_config.get("model", "text-embedding-v3")

    if status_callback:
        status_callback(RunStatus(run_id="", stage="embedding", total=len(df), current=0, message="正在计算 Embedding..."))

    embeddings = {}  # {df_index: ndarray}
    valid_indices = []
    for idx, row in df.iterrows():
        query = row.get("query", "")
        if pd.isna(query) or not query:
            continue
        emb = get_embedding(str(query), base_url=base_url, api_key=api_key, model=model)
        if emb is not None:
            embeddings[idx] = emb
            valid_indices.append(idx)
        if status_callback and valid_indices:
            status_callback(RunStatus(
                run_id="", stage="embedding", total=len(df),
                current=valid_indices[-1],
                message=f"正在计算 Embedding... ({len(valid_indices)}/{len(df)})",
            ))

    pairs = []
    processed = set()
    n = len(valid_indices)
    for a in range(n):
        idx_i = valid_indices[a]
        if idx_i not in embeddings:
            continue
        for b in range(a + 1, n):
            idx_j = valid_indices[b]
            if idx_j not in embeddings:
                continue
            pair_key = tuple(sorted([idx_i, idx_j]))
            if pair_key in processed:
                continue
            processed.add(pair_key)
            sim = cosine_similarity(embeddings[idx_i], embeddings[idx_j])
            if sim >= threshold:
                row_i = df.loc[idx_i]
                row_j = df.loc[idx_j]
                intent_diff = (row_i.get("true_intent") != row_j.get("true_intent") or
                               row_i.get("true_sub_intent") != row_j.get("true_sub_intent"))
                if intent_diff:
                    pairs.append({
                        "index_a": idx_i, "index_b": idx_j,
                        "query_a": row_i.get("query", ""), "query_b": row_j.get("query", ""),
                        "intent_a": row_i.get("true_intent", ""), "intent_b": row_j.get("true_intent", ""),
                        "sub_intent_a": row_i.get("true_sub_intent", ""), "sub_intent_b": row_j.get("true_sub_intent", ""),
                        "similarity": sim,
                    })

    output_path = str(Path(save_dir) / "embedding_similarity_check.csv")
    if pairs:
        pd.DataFrame(pairs).sort_values("similarity", ascending=False).to_csv(output_path, index=False)
    else:
        pd.DataFrame(columns=["index_a", "index_b", "query_a", "query_b", "similarity"]).to_csv(output_path, index=False)
    return output_path


def llm_qc_with_voting(
    data_file: str,
    intent_config: Dict,
    llm_configs: List[Dict],
    save_dir: str,
    para: int = 3,
    sample_size: Optional[int] = None,
    status_callback: Optional[Callable[[RunStatus], None]] = None,
) -> Dict[str, str]:
    """多模型投票机制 LLM 质检"""
    Path(save_dir).mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(data_file, index_col=0)
    df = _sample_dataframe(df, sample_size)
    df = df.reset_index(drop=True)

    def parse_target(s):
        try:
            t = json.loads(str(s).replace('""', '"'))
            return t.get("意图", ""), t.get("子意图", "")
        except Exception:
            return "", ""

    parsed = df["target"].apply(parse_target)
    df["true_intent"] = [p[0] for p in parsed]
    df["true_sub_intent"] = [p[1] for p in parsed]

    random.seed(42)
    num_models = min(3, len(llm_configs))

    sample_model_assignments = []
    for si in range(len(df)):
        if len(llm_configs) > 3:
            selected = random.sample(range(len(llm_configs)), 3)
        else:
            selected = list(range(len(llm_configs)))
        sample_model_assignments.append((si, selected))

    # 构建一级查询
    level1_queries = []
    level1_metadata = []
    level1_prompt_templates = {}  # sample_idx -> prompt template text
    for si, model_indices in sample_model_assignments:
        row = df.iloc[si]
        prompt_template = build_intent_prompt(
            intent_config, level=1,
            reference_target=row.get("target"),
            reference_desc=row.get("sub_intent_desc_2"),
        )
        prompt = prompt_template.format(query=row["query"])
        level1_prompt_templates[si] = prompt_template
        for mi in model_indices:
            level1_queries.append((prompt, llm_configs[mi]))
            level1_metadata.append((si, mi))

    if status_callback:
        status_callback(RunStatus(run_id="", stage="llm_qc", total=len(df) * 2, current=0, message="正在执行一级意图判定..."))

    results1 = run_llm_para_with_assign(level1_queries, para=para)

    sample_model_results = {}
    level2_queries = []
    level2_metadata = []
    level2_prompt_templates = {}  # (sample_idx, model_idx) -> prompt template text

    for i, (si, mi) in enumerate(level1_metadata):
        response = results1.iloc[i].get("response", "") if results1 is not None and i < len(results1) else ""
        row = df.iloc[si]
        correct = match_intent(response, row["true_intent"])

        key = (si, mi)
        sample_model_results[key] = {
            "level1_response": response,
            "level1_correct": correct,
            "true_level1": row["true_intent"],
        }

        if correct:
            prompt_template2 = build_intent_prompt(
                intent_config, level=2, parent_intent=row["true_intent"],
                reference_target=row.get("target"),
                reference_desc=row.get("sub_intent_desc_2"),
            )
            level2_prompt_templates[key] = prompt_template2
            prompt2 = prompt_template2.format(query=row["query"])
            level2_queries.append((prompt2, llm_configs[mi]))
            level2_metadata.append((si, mi))

        if status_callback:
            status_callback(RunStatus(
                run_id="", stage="llm_qc", total=len(df) * 2,
                current=i + 1, message=f"正在执行一级意图判定... ({i + 1}/{len(level1_metadata)})",
            ))

    if level2_queries:
        if status_callback:
            status_callback(RunStatus(run_id="", stage="llm_qc", total=len(df) * 2, current=len(level1_metadata), message="正在执行二级意图判定..."))

        results2 = run_llm_para_with_assign(level2_queries, para=para)
        if results2 is not None:
            for i, (si, mi) in enumerate(level2_metadata):
                response = results2.iloc[i].get("response", "") if i < len(results2) else ""
                row = df.iloc[si]
                correct = match_intent(response, row["true_sub_intent"])
                key = (si, mi)
                sample_model_results[key]["level2_response"] = response
                sample_model_results[key]["level2_correct"] = correct
                sample_model_results[key]["true_level2"] = row["true_sub_intent"]

                if status_callback:
                    status_callback(RunStatus(
                        run_id="", stage="llm_qc", total=len(df) * 2,
                        current=len(level1_metadata) + i + 1,
                        message=f"正在执行二级意图判定... ({i + 1}/{len(level2_metadata)})",
                    ))

    # 投票汇总
    summary_records = []
    detail_records = []

    for si in range(len(df)):
        row = df.iloc[si]
        _, model_indices = sample_model_assignments[si]
        l1_correct_count = 0
        l2_correct_count = 0

        for mi in model_indices:
            key = (si, mi)
            result = sample_model_results.get(key, {})
            if result.get("level1_correct", False):
                l1_correct_count += 1
            if result.get("level2_correct", False):
                l2_correct_count += 1

            # 构建 prompt 文本
            l1_prompt = level1_prompt_templates.get(si, "").format(query=row["query"])
            l2_prompt = ""
            if result.get("level1_correct", False):
                l2_tpl = level2_prompt_templates.get(key)
                if l2_tpl:
                    l2_prompt = l2_tpl.format(query=row["query"])

            detail_records.append({
                "idx": row.name,
                "model": llm_configs[mi].get("model", f"model_{mi}"),
                "query": row["query"],
                "true_level1": row["true_intent"],
                "true_level2": row["true_sub_intent"],
                "pred_level1": result.get("level1_response", ""),
                "pred_level2": result.get("level2_response", ""),
                "level1_correct": result.get("level1_correct", False),
                "level2_correct": result.get("level2_correct", False),
                "overall_correct": result.get("level1_correct", False) and result.get("level2_correct", False),
                "prompt_lvl_1": l1_prompt,
                "prompt_lvl_2": l2_prompt,
            })

        total = len(model_indices)
        l1_pass = l1_correct_count >= (total / 2)
        l2_pass = l2_correct_count >= (total / 2) if l1_pass else False

        summary_records.append({
            "idx": row.name,
            "query": row["query"],
            "true_level1": row["true_intent"],
            "true_level2": row["true_sub_intent"],
            "level1_pass_votes": f"{l1_correct_count}/{total}",
            "level1_pass": l1_pass,
            "level2_pass_votes": f"{l2_correct_count}/{total}" if l1_pass else "0/0",
            "level2_pass": l2_pass,
            "overall_pass": l1_pass and l2_pass,
            "reason": "" if (l1_pass and l2_pass) else (
                f"一级意图判定失败({l1_correct_count}/{total})" if not l1_pass
                else f"二级意图判定失败({l2_correct_count}/{total})"
            ),
        })

    detail_path = str(Path(save_dir) / "qc_detail_by_model.csv")
    summary_path = str(Path(save_dir) / "qc_summary_voting.csv")
    pd.DataFrame(detail_records).to_csv(detail_path, index=False)
    pd.DataFrame(summary_records).to_csv(summary_path, index=False)

    return {"detail": detail_path, "summary": summary_path}
