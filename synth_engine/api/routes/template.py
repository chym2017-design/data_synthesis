"""
模板管理 API
"""

import json
import shutil
from pathlib import Path
from typing import List

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from synth_engine import templates  # noqa: F401
from synth_engine.templates.registry import TemplateRegistry
from synth_engine.tenant import current_workspace

router = APIRouter()

class TemplateInfo(BaseModel):
    name: str
    has_intent_config: bool
    has_synth_config: bool
    has_profile_config: bool
    has_prompts: bool
    files: List[str]


@router.get("/list", response_model=List[TemplateInfo])
async def list_templates():
    """列出所有模板"""
    templates = []
    templates_dir = current_workspace().templates_dir
    if not templates_dir.exists():
        return templates

    for d in templates_dir.iterdir():
        if d.is_dir() and not d.name.startswith("_"):
            files = [f.name for f in d.iterdir() if not f.name.startswith("_")]
            templates.append(TemplateInfo(
                name=d.name,
                has_intent_config=(d / "intent.json").exists(),
                has_synth_config=(d / "synth_config.yaml").exists(),
                has_profile_config=(d / "profile_config.yaml").exists(),
                has_prompts=(d / "prompts").is_dir(),
                files=files,
            ))
    return templates


@router.get("/{template_name}")
async def get_template_info(template_name: str):
    """获取模板详情"""
    tmpl_dir = current_workspace().templates_dir / Path(template_name).name
    if not tmpl_dir.exists():
        raise HTTPException(status_code=404, detail=f"模板不存在: {template_name}")

    files = []
    for f in tmpl_dir.rglob("*"):
        if f.is_file() and not f.name.startswith("_"):
            files.append(str(f.relative_to(tmpl_dir)))

    return {"name": template_name, "files": files}


@router.post("/create")
async def create_template(template_name: str, source: str = None):
    """创建新模板（可复制已有模板）"""
    templates_dir = current_workspace().templates_dir
    safe_name = Path(template_name).name
    if safe_name != template_name or not safe_name:
        raise HTTPException(status_code=400, detail="模板名称不合法")
    tmpl_dir = templates_dir / safe_name
    if tmpl_dir.exists():
        raise HTTPException(status_code=400, detail=f"模板已存在: {template_name}")

    if source:
        src_dir = templates_dir / Path(source).name
        if not src_dir.exists():
            raise HTTPException(status_code=404, detail=f"源模板不存在: {source}")
        shutil.copytree(src_dir, tmpl_dir)
    else:
        tmpl_dir.mkdir(parents=True)
        (tmpl_dir / "prompts").mkdir()

    # 创建空配置
    synth_cfg = {
        "round_distribution": {
            "single_intent": [[1, 0.3], [2, 0.3], [3, 0.3], [4, 0.1]],
            "multi_intent": [[2, 0.25], [3, 0.5], [4, 0.1], [5, 0.1], [6, 0.05]],
        },
        "intent_transition": {
            "single_intent_prob": 0.3,
            "multi_intent_prob": 0.7,
            "same_intent_multi_subintent_ratio": 0.8,
            "cross_intent_jump": 0.2,
        },
        "single_round_ratio": 0.05,
        "tone_distribution": {"祈使句": 0.6, "问句": 0.15, "反问句": 0.1, "倒装句": 0.05, "长短复合句": 0.05, "带错别字的请求": 0.05},
        "mood": {"probability": 0.3, "emotions": ["兴奋", "开心", "愉快", "平静", "沮丧", "悲伤", "愤怒", "焦虑"]},
        "intent_transition_constraint": {"switch_at_terminal_turn_ratio": 0.2},
    }
    with open(tmpl_dir / "synth_config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(synth_cfg, f, allow_unicode=True, default_flow_style=False)

    # 创建空 intent.json
    with open(tmpl_dir / "intent.json", "w", encoding="utf-8") as f:
        json.dump({"intent": {}}, f, ensure_ascii=False, indent=4)

    return {"status": "ok", "message": f"模板已创建: {template_name}"}


@router.delete("/{template_name}")
async def delete_template(template_name: str):
    """删除模板"""
    tmpl_dir = current_workspace().templates_dir / Path(template_name).name
    if not tmpl_dir.exists():
        raise HTTPException(status_code=404, detail=f"模板不存在: {template_name}")
    shutil.rmtree(tmpl_dir)
    return {"status": "ok", "message": f"模板已删除: {template_name}"}


@router.get("/{template_name}/prompt/{prompt_name}")
async def get_prompt_template(template_name: str, prompt_name: str):
    """获取 Prompt 模板内容（支持 .md 后缀自动补全）"""
    tmpl_dir = current_workspace().templates_dir / Path(template_name).name
    if not tmpl_dir.exists():
        raise HTTPException(status_code=404, detail=f"模板不存在: {template_name}")

    # 尝试不同后缀
    safe_prompt = Path(prompt_name).name
    candidates = [safe_prompt, f"{safe_prompt}.md"]
    for name in candidates:
        p = tmpl_dir / "prompts" / name
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return {"content": f.read(), "file": name}

    raise HTTPException(status_code=404, detail=f"Prompt 模板不存在: {template_name}/prompts/{prompt_name}")
