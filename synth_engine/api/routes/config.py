"""
配置管理 API

支持：列出模板配置、读取/写入模板 YAML、管理全局 LLM 配置、生成示例画像。
"""

import json
import os
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import yaml
from fastapi import APIRouter, File, HTTPException, UploadFile

from synth_engine.core.config import deep_merge

router = APIRouter()

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
CONFIGS_DIR = Path(__file__).parent.parent.parent.parent / "configs"
LLM_CONFIG_PATH = CONFIGS_DIR / "llm_config.yaml"
EMBEDDING_CONFIG_PATH = CONFIGS_DIR / "embedding_config.yaml"


def _load_profile_config(template_name: str) -> Dict[str, Any]:
    """加载指定模板的 profile_config"""
    tmpl_dir = TEMPLATES_DIR / template_name
    cfg_path = tmpl_dir / "profile_config.yaml"
    if not cfg_path.exists():
        raise HTTPException(status_code=404, detail=f"profile_config.yaml 不存在: {template_name}")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@router.get("/list")
async def list_configs():
    """列出所有模板的配置类型"""
    configs = []
    if TEMPLATES_DIR.exists():
        for tmpl_dir in sorted(TEMPLATES_DIR.iterdir()):
            if tmpl_dir.is_dir() and not tmpl_dir.name.startswith("_"):
                for cfg_file in sorted(tmpl_dir.iterdir()):
                    if cfg_file.suffix in (".yaml", ".yml", ".json"):
                        configs.append({
                            "template_name": tmpl_dir.name,
                            "config_type": cfg_file.stem,
                            "file": str(cfg_file),
                        })
    return {"configs": configs}


RESOURCES_DIR = Path(__file__).parent.parent.parent / "resources"


@router.get("/resources")
async def list_resources():
    """列出可用的资源 CSV 文件（基金/理财产品池）"""
    resources = {}
    if RESOURCES_DIR.exists():
        for f in sorted(RESOURCES_DIR.iterdir()):
            if f.suffix == ".csv":
                resources[f.stem] = {
                    "filename": f.name,
                    "path": f"../../resources/{f.name}",
                    "rows": len(pd.read_csv(str(f), encoding="utf-8")),
                }
    return {"resources": resources}


@router.post("/upload_csv")
async def upload_csv(file: UploadFile = File(...)):
    """上传 CSV 文件到 resources 目录"""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="仅支持 CSV 文件")
    RESOURCES_DIR.mkdir(parents=True, exist_ok=True)
    dest = RESOURCES_DIR / file.filename
    contents = await file.read()
    with open(dest, "wb") as f:
        f.write(contents)
    row_count = len(pd.read_csv(str(dest), encoding="utf-8"))
    return {
        "status": "ok",
        "filename": file.filename,
        "path": f"../../resources/{file.filename}",
        "rows": row_count,
    }


@router.get("/csv_preview")
async def csv_preview(path: str, limit: int = 50):
    """预览 CSV 文件前 N 行"""
    tmpl_dir = TEMPLATES_DIR / "bank_intent"
    csv_path = (tmpl_dir / path).resolve()
    if not csv_path.exists():
        # 尝试相对于项目根目录
        project_root = Path(__file__).parent.parent.parent.parent
        csv_path = (project_root / path).resolve()
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"CSV 文件不存在: {path}")
    df = pd.read_csv(str(csv_path), nrows=limit, encoding="utf-8")
    return {
        "total_rows": len(pd.read_csv(str(csv_path), usecols=[0], encoding="utf-8")),
        "preview": df.head(limit).to_dict(orient="records"),
    }


@router.get("/llm")
async def get_llm_config():
    """获取全局 LLM 配置"""
    if LLM_CONFIG_PATH.exists():
        with open(LLM_CONFIG_PATH, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f) or []
        return {"config": content}
    return {"config": []}


@router.put("/llm")
async def update_llm_config(data: Dict[str, Any]):
    """更新全局 LLM 配置。data 应为 list[dict] 格式"""
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    cfg = data.get("config", data)
    if not isinstance(cfg, list):
        cfg = [cfg]
    with open(LLM_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return {"status": "ok", "message": "LLM 配置已更新"}


@router.get("/embedding")
async def get_embedding_config():
    """获取全局 Embedding 配置"""
    if EMBEDDING_CONFIG_PATH.exists():
        with open(EMBEDDING_CONFIG_PATH, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f) or {}
        return {"config": content}
    return {"config": {}}


@router.put("/embedding")
async def update_embedding_config(data: Dict[str, Any]):
    """更新全局 Embedding 配置"""
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    cfg = data.get("config", data)
    with open(EMBEDDING_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return {"status": "ok", "message": "Embedding 配置已更新"}


@router.post("/parse_yaml")
async def parse_yaml_file(file: UploadFile = File(...)):
    """解析上传的 YAML 文件，返回 JSON"""
    content = await file.read()
    try:
        data = yaml.safe_load(content.decode("utf-8"))
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"YAML 解析失败: {e}")


@router.post("/{template_name}/generate_sample_profile")
async def generate_sample_profile(template_name: str, data: Dict[str, Any] = {}):
    """生成一条示例用户画像（与合成流水线使用同一生成逻辑）

    data 可选字段：
    - fund_csv: 自定义基金产品 CSV 路径
    - wealth_csv: 自定义理财产品 CSV 路径
    """
    tmpl_dir = TEMPLATES_DIR / template_name
    if not tmpl_dir.exists():
        raise HTTPException(status_code=404, detail=f"模板不存在: {template_name}")

    cfg_path = tmpl_dir / "profile_config.yaml"
    if not cfg_path.exists():
        raise HTTPException(status_code=404, detail=f"profile_config.yaml 不存在: {template_name}")

    from synth_engine.core.config import ConfigLoader
    from synth_engine.core.profile_gen import ConfigDrivenProfileGenerator

    loader = ConfigLoader()
    profile_cfg = loader.load_yaml(str(cfg_path))

    # 设置配置目录用于解析相对路径
    profile_cfg["__config_dir__"] = str(tmpl_dir)

    # 如果前端传了自定义 CSV 路径，覆盖默认值
    fund_csv = data.get("fund_csv")
    wealth_csv = data.get("wealth_csv")
    if fund_csv:
        profile_cfg.setdefault("product_pools", {})["fund_csv"] = fund_csv
    if wealth_csv:
        profile_cfg.setdefault("product_pools", {})["wealth_csv"] = wealth_csv

    # 如果传了自定义 CSV，加载为 DataFrame 传入生成器
    df_fund = None
    df_wealth = None
    if fund_csv:
        csv_path = (tmpl_dir / fund_csv).resolve()
        if csv_path.exists():
            df_fund = pd.read_csv(str(csv_path))
    if wealth_csv:
        csv_path = (tmpl_dir / wealth_csv).resolve()
        if csv_path.exists():
            df_wealth = pd.read_csv(str(csv_path))

    generator = ConfigDrivenProfileGenerator(
        config=profile_cfg, df_fund=df_fund, df_wealth=df_wealth
    )
    profile = generator.generate_user_profile()

    return {"profile": profile}


@router.get("/{template_name}/{config_type}")
async def get_config(template_name: str, config_type: str):
    """获取指定模板的配置"""
    tmpl_dir = TEMPLATES_DIR / template_name
    if not tmpl_dir.exists():
        raise HTTPException(status_code=404, detail=f"模板不存在: {template_name}")

    cfg_path = tmpl_dir / f"{config_type}.yaml"
    if not cfg_path.exists():
        cfg_path = tmpl_dir / f"{config_type}.yml"
    if not cfg_path.exists():
        cfg_path = tmpl_dir / f"{config_type}.json"
    if not cfg_path.exists():
        raise HTTPException(status_code=404, detail=f"配置文件不存在: {template_name}/{config_type}")

    if cfg_path.suffix == ".json":
        with open(cfg_path, "r", encoding="utf-8") as f:
            content = json.load(f)
    else:
        with open(cfg_path, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f) or {}

    user_path = tmpl_dir / f"{config_type}.user.yaml"
    if user_path.exists():
        with open(user_path, "r", encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
        content = deep_merge(content, user_cfg)

    return {"template_name": template_name, "config_type": config_type, "content": content}


@router.put("/{template_name}/{config_type}")
async def update_config(template_name: str, config_type: str, data: Dict[str, Any]):
    """更新模板配置"""
    tmpl_dir = TEMPLATES_DIR / template_name
    if not tmpl_dir.exists():
        raise HTTPException(status_code=404, detail=f"模板目录不存在: {template_name}")

    user_path = tmpl_dir / f"{config_type}.user.yaml"
    with open(user_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    return {"status": "ok", "message": f"配置已更新: {template_name}/{config_type}"}
