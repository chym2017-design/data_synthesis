"""
合成任务 API

支持：启动合成、查询进度、列出历史任务。
模板目录由后端自动定位，无需前端传入。
LLM 配置从全局配置读取。
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from synth_engine.core.pipeline import SynthesisPipeline
from synth_engine.core.config import SynthConfigModel
from synth_engine.core.models import RunStatus
from synth_engine import templates  # noqa: F401 (触发模板自动注册)
from synth_engine.templates.registry import TemplateRegistry

router = APIRouter()

import threading

_synth_lock = threading.Lock()
_active_runs: Dict[str, Dict] = {}  # run_id -> {"status": RunStatus, "start_time": str}

# 模板目录由后端自动发现
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
# 全局 LLM 配置路径
LLM_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "configs" / "llm_config.yaml"


def _load_llm_configs() -> List[Dict]:
    """从全局配置加载 LLM 配置"""
    if LLM_CONFIG_PATH.exists():
        with open(LLM_CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            if isinstance(cfg, list):
                return cfg
    return []


def _get_template_dir(template_name: str) -> Path:
    """自动定位模板目录"""
    tmpl_dir = TEMPLATES_DIR / template_name
    if not tmpl_dir.exists():
        raise HTTPException(status_code=404, detail=f"模板 '{template_name}' 不存在")
    return tmpl_dir


def _now_str() -> str:
    """当前时间字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class SynthesisRequest(BaseModel):
    template_name: str
    num_samples: int = 100
    para: int = 3
    synth_config_override: Optional[Dict] = None


class SynthesisResponse(BaseModel):
    run_id: str
    status: str
    message: str


def _set_run_status(run_id: str, status: RunStatus):
    """更新运行状态，保留 start_time（线程安全）"""
    with _synth_lock:
        if run_id in _active_runs:
            _active_runs[run_id]["status"] = status
        else:
            _active_runs[run_id] = {"status": status, "start_time": _now_str()}


@router.post("/start", response_model=SynthesisResponse)
async def start_synthesis(req: SynthesisRequest):
    """启动合成任务"""
    if not TemplateRegistry.has(req.template_name):
        raise HTTPException(status_code=404, detail=f"模板 '{req.template_name}' 不存在")

    llm_configs = _load_llm_configs()
    if not llm_configs:
        raise HTTPException(
            status_code=400,
            detail="未配置 LLM。请先在「配置管理」页面设置 LLM API 地址和密钥。",
        )

    template_dir = _get_template_dir(req.template_name)
    run_id = str(uuid.uuid4())[:8]
    run_dir = Path(__file__).parent.parent.parent.parent / "runs" / "outputs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # 解析配置覆盖
    synth_config = None
    if req.synth_config_override:
        synth_config = SynthConfigModel(**req.synth_config_override)

    _active_runs[run_id] = {
        "status": RunStatus(run_id=run_id, stage="starting", message="任务已提交，等待处理..."),
        "start_time": _now_str(),
    }

    import threading

    def status_callback(status: RunStatus):
        _set_run_status(run_id, status)

    def run_pipeline():
        try:
            pipeline = SynthesisPipeline(
                template_name=req.template_name,
                template_dir=str(template_dir),
                run_dir=str(run_dir),
                synth_config=synth_config,
                status_callback=status_callback,
            )
            output_path = pipeline.run(
                num_samples=req.num_samples,
                llm_configs=llm_configs,
                para=req.para,
            )
            _set_run_status(run_id, RunStatus(
                run_id=run_id, stage="done",
                message=f"完成，输出: {output_path}",
                total=req.num_samples, current=req.num_samples,
            ))
        except Exception as e:
            _set_run_status(run_id, RunStatus(
                run_id=run_id, stage="error",
                error=str(e), message=f"失败: {str(e)}",
            ))

    threading.Thread(target=run_pipeline, daemon=True).start()

    return SynthesisResponse(run_id=run_id, status="starting", message="任务已提交")


@router.get("/status/{run_id}")
async def get_synthesis_status(run_id: str):
    """获取合成任务状态"""
    runs_dir = Path(__file__).parent.parent.parent.parent / "runs" / "outputs"

    if run_id not in _active_runs:
        # 内存中没有，尝试从磁盘恢复状态
        run_dir = runs_dir / run_id
        if run_dir.exists():
            csv_exists = (run_dir / "data.csv").exists()
            jsonl_exists = (run_dir / "sft.jsonl").exists()
            if csv_exists:
                return {
                    "run_id": run_id,
                    "stage": "done",
                    "total": 0, "current": 0,
                    "progress": 1.0,
                    "message": "历史任务（服务重启前完成）",
                    "error": "",
                    "start_time": _get_dir_mtime(run_dir),
                }
            else:
                return {
                    "run_id": run_id,
                    "stage": "running",
                    "total": 0, "current": 0,
                    "progress": 0.0,
                    "message": "任务可能在服务重启时中断",
                    "error": "",
                    "start_time": _get_dir_mtime(run_dir),
                }
        raise HTTPException(status_code=404, detail=f"运行 ID {run_id} 不存在")

    entry = _active_runs[run_id]
    status = entry["status"]
    start_time = entry.get("start_time", "")

    # 磁盘状态恢复：只对非运行中的任务生效
    running_stages = {"starting", "initialized", "generating", "calling_llm", "filtering", "exporting"}
    if status.stage not in running_stages and status.stage not in ("done", "error") and (runs_dir / run_id).exists():
        if (runs_dir / run_id / "data.csv").exists():
            status.stage = "done"
            status.total = status.current = max(status.total, 1)
            status.message = "历史任务（服务重启前完成）"
        else:
            status.stage = "interrupted"
            status.current = 0
            status.message = "任务被中断"

    return {
        "run_id": status.run_id,
        "stage": status.stage,
        "total": status.total,
        "current": status.current,
        "progress": status.progress,
        "message": status.message,
        "error": status.error,
        "start_time": start_time,
    }


def _get_dir_mtime(dir_path: Path) -> str:
    """获取目录的修改时间字符串"""
    try:
        import time
        mtime = dir_path.stat().st_mtime
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


@router.get("/list")
async def list_synthesis_runs():
    """列出所有合成任务"""
    runs_dir = Path(__file__).parent.parent.parent.parent / "runs" / "outputs"

    runs = []
    seen_ids = set()

    # 从内存获取活跃任务
    running_stages = {"starting", "initialized", "generating", "calling_llm", "filtering", "exporting"}
    for run_id, entry in _active_runs.items():
        s = entry["status"]
        start_time = entry.get("start_time", "")
        run_dir = runs_dir / run_id
        dir_exists = run_dir.exists()
        has_output = dir_exists and (run_dir / "data.csv").exists()

        if s.stage in running_stages:
            # 正在运行的任务，以内存状态为准
            stage = s.stage
            progress = s.progress
            message = s.message
        elif has_output and s.stage not in ("done", "error"):
            stage = "done"
            progress = 1.0
            message = "历史任务（服务重启前完成）"
        elif dir_exists and not has_output and s.stage not in ("done", "error"):
            stage = "interrupted"
            progress = 0.0
            message = "任务被中断（服务重启或异常退出）"
        else:
            stage = s.stage
            progress = s.progress
            message = s.message

        runs.append({
            "run_id": run_id,
            "stage": stage,
            "progress": progress,
            "message": message,
            "has_files": has_output,
            "start_time": start_time,
        })
        seen_ids.add(run_id)

    # 扫描磁盘上已有但未在内存中的运行目录
    if runs_dir.exists():
        for d in runs_dir.iterdir():
            if d.is_dir() and d.name not in seen_ids:
                csv_exists = (d / "data.csv").exists()
                jsonl_exists = (d / "sft.jsonl").exists()
                if csv_exists:
                    stage = "done"
                    progress = 1.0
                    message = "历史任务（服务重启前完成）"
                else:
                    stage = "interrupted"
                    progress = 0.0
                    message = "任务被中断（空目录）"
                runs.append({
                    "run_id": d.name,
                    "stage": stage,
                    "progress": progress,
                    "message": message,
                    "has_files": csv_exists,
                    "start_time": _get_dir_mtime(d),
                })

    return {"runs": sorted(runs, key=lambda r: r["start_time"], reverse=True)}
