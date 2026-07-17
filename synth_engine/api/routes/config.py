"""
配置管理 API

支持：列出模板配置、读取/写入模板 YAML、管理全局 LLM 配置、生成示例画像。
"""

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import yaml
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from synth_engine.core.config import deep_merge
from synth_engine import tenant
from synth_engine.llm.client import run_llm_non_stream
from synth_engine.llm.embedding import get_embedding
from synth_engine.tenant import current_workspace

router = APIRouter()
logger = logging.getLogger(__name__)

def _load_profile_config(template_name: str) -> Dict[str, Any]:
    """加载指定模板的 profile_config"""
    tmpl_dir = current_workspace().templates_dir / template_name
    cfg_path = tmpl_dir / "profile_config.yaml"
    if not cfg_path.exists():
        raise HTTPException(status_code=404, detail=f"profile_config.yaml 不存在: {template_name}")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@router.get("/list")
async def list_configs():
    """列出所有模板的配置类型"""
    configs = []
    templates_dir = current_workspace().templates_dir
    if templates_dir.exists():
        for tmpl_dir in sorted(templates_dir.iterdir()):
            if tmpl_dir.is_dir() and not tmpl_dir.name.startswith("_"):
                for cfg_file in sorted(tmpl_dir.iterdir()):
                    if cfg_file.suffix in (".yaml", ".yml", ".json"):
                        configs.append({
                            "template_name": tmpl_dir.name,
                            "config_type": cfg_file.stem,
                            "file": str(cfg_file),
                        })
    return {"configs": configs}


@router.get("/resources")
async def list_resources():
    """列出可用的资源 CSV 文件（基金/理财产品池）"""
    resources = {}
    resources_dir = current_workspace().resources_dir
    if resources_dir.exists():
        for f in sorted(resources_dir.iterdir()):
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
    filename = Path(file.filename or "").name
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="仅支持 CSV 文件")
    resources_dir = current_workspace().resources_dir
    resources_dir.mkdir(parents=True, exist_ok=True)
    dest = resources_dir / filename
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="CSV 文件不能超过 10 MB")
    with open(dest, "wb") as f:
        f.write(contents)
    row_count = len(pd.read_csv(str(dest), encoding="utf-8"))
    return {
        "status": "ok",
        "filename": filename,
        "path": f"../../resources/{filename}",
        "rows": row_count,
    }


@router.get("/csv_preview")
async def csv_preview(path: str, limit: int = 50):
    """预览 CSV 文件前 N 行"""
    ws = current_workspace()
    tmpl_dir = ws.templates_dir / "bank_intent"
    csv_path = (tmpl_dir / path).resolve()
    allowed_root = ws.root.resolve()
    if allowed_root not in csv_path.parents or not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"CSV 文件不存在: {path}")
    df = pd.read_csv(str(csv_path), nrows=limit, encoding="utf-8")
    return {
        "total_rows": len(pd.read_csv(str(csv_path), usecols=[0], encoding="utf-8")),
        "preview": df.head(limit).to_dict(orient="records"),
    }


@router.get("/llm")
async def get_llm_config():
    """获取全局 LLM 配置"""
    config_path = current_workspace().configs_dir / "llm_config.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f) or []
        return {"config": content}
    return {"config": []}


@router.put("/llm")
async def update_llm_config(data: Dict[str, Any]):
    """更新全局 LLM 配置。data 应为 list[dict] 格式"""
    configs_dir = current_workspace().configs_dir
    configs_dir.mkdir(parents=True, exist_ok=True)
    cfg = data.get("config", data)
    if not isinstance(cfg, list):
        cfg = [cfg]
    with open(configs_dir / "llm_config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return {"status": "ok", "message": "LLM 配置已更新"}


@router.get("/embedding")
async def get_embedding_config():
    """获取全局 Embedding 配置"""
    config_path = current_workspace().configs_dir / "embedding_config.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f) or {}
        return {"config": content}
    return {"config": {}}


@router.put("/embedding")
async def update_embedding_config(data: Dict[str, Any]):
    """更新全局 Embedding 配置"""
    configs_dir = current_workspace().configs_dir
    configs_dir.mkdir(parents=True, exist_ok=True)
    cfg = data.get("config", data)
    with open(configs_dir / "embedding_config.yaml", "w", encoding="utf-8") as f:
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
    tmpl_dir = current_workspace().templates_dir / template_name
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
    tmpl_dir = current_workspace().templates_dir / template_name
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
    tmpl_dir = current_workspace().templates_dir / template_name
    if not tmpl_dir.exists():
        raise HTTPException(status_code=404, detail=f"模板目录不存在: {template_name}")

    json_path = tmpl_dir / f"{config_type}.json"
    if json_path.exists():
        # JSON 模板（目前主要是 intent.json）是合成和质检直接读取的业务源文件。
        # 不能写入 YAML 覆盖文件，否则页面显示已保存，但运行时仍使用旧 JSON。
        temp_path = json_path.with_suffix(f"{json_path.suffix}.tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            f.write("\n")
        temp_path.replace(json_path)

        # 清除旧版本遗留的覆盖文件，避免读取时再次覆盖刚写入的 JSON。
        legacy_user_path = tmpl_dir / f"{config_type}.user.yaml"
        legacy_user_path.unlink(missing_ok=True)
        return {"status": "ok", "message": f"配置已更新: {template_name}/{config_type}.json"}

    user_path = tmpl_dir / f"{config_type}.user.yaml"
    with open(user_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    return {"status": "ok", "message": f"配置已更新: {template_name}/{config_type}"}


@router.post("/{template_name}/{config_type}/restore_default")
async def restore_default_config(template_name: str, config_type: str):
    """将当前用户的一类模板配置恢复为项目内置默认值。"""
    filenames = {
        "intent": "intent.json",
        "synth_config": "synth_config.yaml",
        "profile_config": "profile_config.yaml",
    }
    filename = filenames.get(config_type)
    if not filename:
        raise HTTPException(status_code=400, detail="该配置不支持恢复默认")

    source_path = tenant.DEFAULT_TEMPLATES_DIR / template_name / filename
    if not source_path.is_file():
        raise HTTPException(status_code=404, detail=f"默认配置不存在: {template_name}/{filename}")

    template_dir = current_workspace().templates_dir / template_name
    if not template_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"模板目录不存在: {template_name}")

    destination = template_dir / filename
    temp_path = destination.with_suffix(f"{destination.suffix}.restore.tmp")
    shutil.copy2(source_path, temp_path)
    temp_path.replace(destination)

    # YAML 页面修改保存在覆盖文件中；恢复默认时必须同时移除覆盖。
    user_path = template_dir / f"{config_type}.user.yaml"
    user_path.unlink(missing_ok=True)
    return {
        "status": "ok",
        "message": f"已恢复默认配置: {template_name}/{filename}",
        "filename": filename,
    }


class ModelTestRequest(BaseModel):
    config: Dict[str, Any]
    text: str = "请用一句话回复：模型连接测试成功。"


@router.post("/test/llm")
async def test_llm_config(req: ModelTestRequest):
    cfg = dict(req.config)
    if not cfg.get("model") or not cfg.get("url") or not cfg.get("api_key"):
        raise HTTPException(status_code=400, detail="模型名称、API 地址和 API Key 不能为空")
    cfg["stream"] = False
    cfg["timeout"] = min(int(cfg.get("timeout", 30)), 60)
    try:
        result = run_llm_non_stream(req.text[:500], **cfg)
    except Exception as exc:
        logger.warning("LLM 连接测试失败 model=%s error=%s", cfg.get("model"), exc)
        raise HTTPException(status_code=400, detail=f"模型连接失败: {exc}") from exc
    if result.get("status_code") != 200 or result.get("err_msg"):
        logger.warning(
            "LLM 连接测试失败 model=%s status=%s error=%s",
            cfg.get("model"),
            result.get("status_code"),
            result.get("err_msg"),
        )
        raise HTTPException(
            status_code=400,
            detail=f"模型连接失败: {result.get('err_msg') or result.get('status_code')}",
        )
    logger.info(
        "LLM 连接测试成功 model=%s duration=%s",
        result.get("model", cfg.get("model")),
        result.get("duration", 0),
    )
    return {
        "status": "ok",
        "message": "模型配置正确，可以正常调用",
        "model": result.get("model", cfg.get("model")),
        "response_preview": str(result.get("response", ""))[:300],
        "duration": result.get("duration", 0),
    }


@router.post("/test/embedding")
async def test_embedding_config(req: ModelTestRequest):
    cfg = req.config
    if not cfg.get("model") or not cfg.get("url") or not cfg.get("api_key"):
        raise HTTPException(status_code=400, detail="模型名称、API 地址和 API Key 不能为空")
    base_url = str(cfg["url"]).replace("/chat/completions", "").replace("/embeddings", "")
    try:
        vector = get_embedding(
            req.text[:500],
            base_url=base_url,
            api_key=str(cfg["api_key"]),
            model=str(cfg["model"]),
            timeout=min(int(cfg.get("timeout", 30)), 60),
            raise_on_error=True,
        )
    except Exception as exc:
        logger.warning("Embedding 连接测试失败 model=%s error=%s", cfg.get("model"), exc)
        raise HTTPException(status_code=400, detail=f"Embedding 连接失败: {exc}") from exc
    if vector is None:
        raise HTTPException(status_code=400, detail="Embedding 连接失败，请检查地址、模型和 API Key")
    logger.info("Embedding 连接测试成功 model=%s dimensions=%s", cfg.get("model"), len(vector))
    return {
        "status": "ok",
        "message": "Embedding 配置正确，可以正常调用",
        "dimensions": int(len(vector)),
    }
