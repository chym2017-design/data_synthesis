"""
质检任务 API

支持：合成前质检、合成后质检、查询进度、列出历史任务。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from synth_engine.core.models import RunStatus
from synth_engine.limits import LIMITS
from synth_engine.qc.pre_check import pre_synthesis_qc
from synth_engine.qc.post_check import embedding_similarity_check, llm_qc_with_voting
from synth_engine.task_queue import task_queue
from synth_engine.task_ids import generate_task_id
from synth_engine.tenant import current_workspace

router = APIRouter()

import threading

_qc_lock = threading.Lock()
_active_qc_runs: Dict[str, Dict] = {}  # run_id -> {"status": RunStatus, "start_time": str}
_qc_cancel_flags: Dict[str, bool] = {}
def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _workspace_file(path_value: str, workspace_root: Path) -> Path:
    path = Path(path_value).resolve()
    root = workspace_root.resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(status_code=400, detail="所选文件不属于当前工作空间")
    return path


def _set_qc_run_status(run_id: str, status: RunStatus):
    """更新运行状态，保留 start_time（线程安全）"""
    with _qc_lock:
        if run_id in _active_qc_runs:
            _active_qc_runs[run_id]["status"] = status
        else:
            _active_qc_runs[run_id] = {"status": status, "start_time": _now_str()}


def _get_dir_mtime(dir_path: Path) -> str:
    """获取目录的修改时间字符串"""
    try:
        import time
        mtime = dir_path.stat().st_mtime
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def _load_llm_configs(config_path: Path) -> List[Dict]:
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            if isinstance(cfg, list):
                return cfg
    return []


def _load_embedding_config(config_path: Path) -> Optional[Dict]:
    """从配置文件加载 Embedding 配置"""
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            if isinstance(cfg, dict) and cfg.get("api_key") and cfg.get("url"):
                return cfg
    return None


def _save_meta(runs_dir: Path, run_id: str, qc_type: str, status: str, params: Dict, results: Dict):
    """持久化 QC 任务元数据到磁盘"""
    meta_path = runs_dir / "qc_results" / run_id / "meta.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    start_time = _active_qc_runs.get(run_id, {}).get("start_time", "")
    meta = {
        "run_id": run_id,
        "type": qc_type,
        "status": status,
        "start_time": start_time,
        "params": params,
        "results": results,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


@router.get("/available_files")
async def get_available_files():
    """列出可用于质检的文件（所有运行输出中的 CSV 和 intent.json）"""
    ws = current_workspace()
    files = {"data_csv": [], "intent_json": []}

    outputs_dir = ws.runs_dir / "outputs"
    if outputs_dir.exists():
        for d in outputs_dir.iterdir():
            if d.is_dir():
                csv = d / "data.csv"
                if csv.exists():
                    files["data_csv"].append({"run_id": d.name, "path": str(csv)})

    # 扫描模板中的 intent.json
    if ws.templates_dir.exists():
        for d in ws.templates_dir.iterdir():
            if d.is_dir():
                intent = d / "intent.json"
                if intent.exists():
                    files["intent_json"].append({"template": d.name, "path": str(intent)})

    return files


class QCPreRequest(BaseModel):
    """合成前质检 - 验证意图配置质量"""
    intent_file: str
    para: int = Field(default=LIMITS.model_parallelism.default, ge=1, le=LIMITS.model_parallelism.max)
    sample_size: int = Field(default=LIMITS.task_items.qc_pre, ge=1, le=LIMITS.task_items.qc_pre)
    similarity_threshold: float = 0.90


class QCPostRequest(BaseModel):
    """合成后质检 - 验证生成数据质量"""
    data_file: str
    intent_file: str
    skip_embedding: bool = False
    skip_llm: bool = False
    para: int = Field(default=LIMITS.model_parallelism.default, ge=1, le=LIMITS.model_parallelism.max)
    sample_size: int = Field(default=LIMITS.task_items.qc_post, ge=1, le=LIMITS.task_items.qc_post)
    similarity_threshold: float = 0.95


@router.post("/pre_check")
async def start_pre_qc(req: QCPreRequest):
    """启动合成前质检（异步）"""
    ws = current_workspace()
    intent_file = _workspace_file(req.intent_file, ws.root)
    run_id = generate_task_id(ws.username, "quality_bef")
    save_dir = str(ws.runs_dir / "qc_results" / run_id)
    Path(save_dir).mkdir(parents=True, exist_ok=True)

    llm_configs = _load_llm_configs(ws.configs_dir / "llm_config.yaml")
    emb_config = _load_embedding_config(ws.configs_dir / "embedding_config.yaml")

    _active_qc_runs[run_id] = {"status": RunStatus(
        run_id=run_id, stage="queued", message="任务已提交，等待处理...",
    ), "start_time": _now_str(), "workspace_id": ws.workspace_id, "username": ws.username, "type": "pre"}

    import threading

    def run_pre_qc():
        try:
            def status_callback(status: RunStatus):
                status.run_id = run_id  # 确保 run_id 正确
                _set_qc_run_status(run_id, status)

            status_callback(RunStatus(run_id=run_id, stage="quality_check", total=0, current=0, message="正在执行菜单质检..."))
            results = pre_synthesis_qc(
                intent_file=str(intent_file),
                llm_configs=llm_configs,
                save_dir=save_dir,
                para=req.para,
                embedding_config=emb_config,
                similarity_threshold=req.similarity_threshold,
                max_items=req.sample_size,
                status_callback=status_callback,
            )

            _set_qc_run_status(run_id, RunStatus(
                run_id=run_id, stage="done", total=1, current=1,
                message=f"合成前质检已完成，生成 {len(results)} 个结果文件",
            ))
            _save_meta(ws.runs_dir, run_id, "pre", "done", req.model_dump(), results)
        except Exception as e:
            _set_qc_run_status(run_id, RunStatus(
                run_id=run_id, stage="error",
                error=str(e), message=f"质检失败: {str(e)}",
            ))
            _save_meta(ws.runs_dir, run_id, "pre", "error", req.model_dump(), {"error": str(e)})
            raise

    def on_start():
        _set_qc_run_status(run_id, RunStatus(
            run_id=run_id, stage="starting", total=req.sample_size, current=0,
            message="任务已出队，正在启动...",
        ))

    queue_info = task_queue.submit(
        job_id=run_id,
        username=ws.username,
        workspace_id=ws.workspace_id,
        task_type="qc_pre",
        function=run_pre_qc,
        on_start=on_start,
    )
    position = queue_info.get("queue_position", 0)
    if queue_info.get("state") == "queued":
        _set_qc_run_status(run_id, RunStatus(
            run_id=run_id, stage="queued", total=req.sample_size, current=0,
            message=f"任务已排队，当前位置 {position}",
        ))

    return {"run_id": run_id, "status": "queued", "message": f"质检任务已提交，排队位置 {position}"}


@router.post("/post_check")
async def start_post_qc(req: QCPostRequest):
    """启动合成后质检（异步）"""
    ws = current_workspace()
    data_file = _workspace_file(req.data_file, ws.root)
    intent_file = _workspace_file(req.intent_file, ws.root)
    run_id = generate_task_id(ws.username, "quality_after")
    save_dir = str(ws.runs_dir / "qc_results" / run_id)
    Path(save_dir).mkdir(parents=True, exist_ok=True)

    llm_configs = _load_llm_configs(ws.configs_dir / "llm_config.yaml")
    emb_config = _load_embedding_config(ws.configs_dir / "embedding_config.yaml")

    with open(intent_file, "r", encoding="utf-8") as f:
        intent_config = json.load(f)

    _active_qc_runs[run_id] = {"status": RunStatus(
        run_id=run_id, stage="queued", message="任务已提交，等待处理...",
    ), "start_time": _now_str(), "workspace_id": ws.workspace_id, "username": ws.username, "type": "post"}

    import threading

    def run_post_qc():
        try:
            def status_callback(status: RunStatus):
                status.run_id = run_id  # 确保 run_id 正确
                _set_qc_run_status(run_id, status)

            results = {}

            if not req.skip_embedding:
                status_callback(RunStatus(run_id=run_id, stage="embedding", total=0, current=0, message="正在执行 Embedding 相似度检测..."))
                emb_path = embedding_similarity_check(
                    data_file=str(data_file),
                    embedding_config=emb_config or {},
                    save_dir=save_dir,
                    threshold=req.similarity_threshold,
                    sample_size=req.sample_size,
                    status_callback=status_callback,
                )
                results["embedding"] = emb_path

            if not req.skip_llm and llm_configs:
                status_callback(RunStatus(run_id=run_id, stage="llm_level1", total=0, current=0, message="正在准备一级意图判定..."))
                llm_results = llm_qc_with_voting(
                    data_file=str(data_file),
                    intent_config=intent_config,
                    llm_configs=llm_configs,
                    save_dir=save_dir,
                    para=req.para,
                    sample_size=req.sample_size,
                    status_callback=status_callback,
                )
                results.update(llm_results)

            _set_qc_run_status(run_id, RunStatus(
                run_id=run_id, stage="done", total=1, current=1,
                message=f"合成后质检已完成，生成 {len(results)} 个结果文件",
            ))
            _save_meta(ws.runs_dir, run_id, "post", "done", req.model_dump(), results)
        except Exception as e:
            _set_qc_run_status(run_id, RunStatus(
                run_id=run_id, stage="error",
                error=str(e), message=f"质检失败: {str(e)}",
            ))
            _save_meta(ws.runs_dir, run_id, "post", "error", req.model_dump(), {"error": str(e)})
            raise

    def on_start():
        _set_qc_run_status(run_id, RunStatus(
            run_id=run_id, stage="starting", total=req.sample_size, current=0,
            message="任务已出队，正在启动...",
        ))

    queue_info = task_queue.submit(
        job_id=run_id,
        username=ws.username,
        workspace_id=ws.workspace_id,
        task_type="qc_post",
        function=run_post_qc,
        on_start=on_start,
    )
    position = queue_info.get("queue_position", 0)
    if queue_info.get("state") == "queued":
        _set_qc_run_status(run_id, RunStatus(
            run_id=run_id, stage="queued", total=req.sample_size, current=0,
            message=f"任务已排队，当前位置 {position}",
        ))

    return {"run_id": run_id, "status": "queued", "message": f"质检任务已提交，排队位置 {position}"}


@router.get("/status/{run_id}")
async def get_qc_status(run_id: str):
    """获取质检任务状态"""
    ws = current_workspace()
    qc_results_dir = ws.runs_dir / "qc_results"

    if run_id in _active_qc_runs and _active_qc_runs[run_id].get("workspace_id") != ws.workspace_id:
        raise HTTPException(status_code=404, detail=f"质检任务 {run_id} 不存在")

    if run_id not in _active_qc_runs:
        # 尝试从磁盘恢复状态
        meta_path = qc_results_dir / run_id / "meta.json"
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            return {
                "run_id": run_id,
                "stage": meta.get("status", "unknown"),
                "type": meta.get("type", ""),
                "params": meta.get("params", {}),
                "results": meta.get("results", {}),
                "message": "历史任务",
                "start_time": meta.get("start_time", ""),
            }
        raise HTTPException(status_code=404, detail=f"质检任务 {run_id} 不存在")

    status = _active_qc_runs[run_id]["status"]
    active_entry = _active_qc_runs[run_id]
    start_time = active_entry.get("start_time", "")

    result = {
        "run_id": status.run_id,
        "type": active_entry.get("type", ""),
        "stage": status.stage,
        "total": status.total,
        "current": status.current,
        "progress": status.progress,
        "message": status.message,
        "error": status.error,
        "start_time": start_time,
    }
    queue_info = task_queue.status(run_id)
    if queue_info:
        result.update({
            "queue_position": queue_info.get("queue_position", 0),
            "queued_count": queue_info.get("queued_count", 0),
            "running_count": queue_info.get("running_count", 0),
            "max_concurrent": queue_info.get("max_concurrent", LIMITS.max_concurrent_tasks),
        })
        if status.stage == "queued":
            result["message"] = f"排队中，当前位置 {queue_info.get('queue_position', 0)}，全局等待 {queue_info.get('queued_count', 0)} 个"

    # 如果已完成，附带结果文件列表
    if status.stage == "done":
        result_dir = qc_results_dir / run_id
        if result_dir.exists():
            result["files"] = [f.name for f in result_dir.glob("*.csv")]

    return result


@router.get("/list")
async def list_qc_runs():
    """列出所有质检任务"""
    ws = current_workspace()
    qc_results_dir = ws.runs_dir / "qc_results"

    runs = []
    seen_ids = set()

    # 从内存获取活跃任务
    qc_running_stages = {
        "queued", "starting", "quality_check", "similarity_check", "embedding",
        "llm_qc", "llm_level1", "llm_level2", "llm_summary",
    }
    for run_id_entry, entry in _active_qc_runs.items():
        if entry.get("workspace_id") != ws.workspace_id:
            continue
        s = entry["status"]
        start_time = entry.get("start_time", "")
        run_dir = qc_results_dir / s.run_id
        dir_exists = run_dir.exists()
        has_output = dir_exists and any(run_dir.glob("*.csv"))

        if s.stage in qc_running_stages:
            stage = s.stage
        elif has_output and s.stage not in ("done", "error"):
            stage = "done"
        else:
            stage = s.stage

        # 活跃任务在提交时就记录类型；meta.json 只在任务结束后才存在。
        qc_type = entry.get("type", "")
        meta_path = run_dir / "meta.json"
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
                qc_type = meta.get("type", qc_type)

        result_files = [f.name for f in run_dir.glob("*.csv")] if dir_exists else []

        item = {
            "run_id": s.run_id,
            "type": qc_type,
            "stage": stage,
            "message": s.message,
            "files": result_files,
            "start_time": start_time,
        }
        queue_info = task_queue.status(s.run_id)
        if queue_info:
            item["queue_position"] = queue_info.get("queue_position", 0)
            item["queued_count"] = queue_info.get("queued_count", 0)
        runs.append(item)
        seen_ids.add(s.run_id)

    # 扫描磁盘上已有但未在内存中的 QC 结果目录
    if qc_results_dir.exists():
        for d in qc_results_dir.iterdir():
            if d.is_dir() and d.name not in seen_ids:
                meta_path = d / "meta.json"
                qc_type = ""
                status = "unknown"
                start_time = ""
                if meta_path.exists():
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        qc_type = meta.get("type", "")
                        status = meta.get("status", "unknown")
                        start_time = meta.get("start_time", "")
                if not start_time:
                    start_time = _get_dir_mtime(d)

                result_files = [f.name for f in d.glob("*.csv")]
                runs.append({
                    "run_id": d.name,
                    "type": qc_type,
                    "stage": status,
                    "message": "历史任务",
                    "files": result_files,
                    "start_time": start_time,
                })

    return {"runs": sorted(runs, key=lambda r: r["start_time"], reverse=True)}


@router.post("/cancel/{run_id}")
async def cancel_qc(run_id: str):
    """取消正在运行的质检任务"""
    if run_id not in _active_qc_runs:
        raise HTTPException(status_code=404, detail=f"质检任务 {run_id} 不存在")
    s = _active_qc_runs[run_id]["status"]
    if s.stage in ("done", "error", "cancelled"):
        raise HTTPException(status_code=400, detail=f"任务已结束，无法取消")
    if task_queue.cancel(run_id):
        _set_qc_run_status(run_id, RunStatus(run_id=run_id, stage="cancelled", message="排队任务已取消"))
        return {"status": "ok", "message": "排队任务已取消"}
    raise HTTPException(status_code=400, detail="任务已经开始运行，当前版本不能安全中止")


@router.post("/retry/{run_id}")
async def retry_qc(run_id: str):
    """重试失败的质检任务"""
    qc_results_dir = current_workspace().runs_dir / "qc_results"
    meta_path = qc_results_dir / run_id / "meta.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail=f"质检任务 {run_id} 不存在")

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    params = meta.get("params", {})
    qc_type = meta.get("type", "")

    task_type = "quality_bef" if qc_type == "pre" else "quality_after"
    new_run_id = generate_task_id(current_workspace().username, task_type)

    if qc_type == "pre":
        from synth_engine.api.routes.qc import QCPreRequest
        req = QCPreRequest(
            intent_file=params.get("intent_file", ""),
            para=params.get("para", LIMITS.model_parallelism.default),
            sample_size=params.get("sample_size", LIMITS.task_items.qc_pre),
            similarity_threshold=params.get("similarity_threshold", 0.90),
        )
    else:
        from synth_engine.api.routes.qc import QCPostRequest
        req = QCPostRequest(
            data_file=params.get("data_file", ""),
            intent_file=params.get("intent_file", ""),
            skip_embedding=params.get("skip_embedding", False),
            skip_llm=params.get("skip_llm", False),
            para=params.get("para", LIMITS.model_parallelism.default),
            sample_size=params.get("sample_size", LIMITS.task_items.qc_post),
            similarity_threshold=params.get("similarity_threshold", 0.95),
        )

    return {
        "status": "ok",
        "message": "请使用原参数重新发起任务",
        "new_run_id": new_run_id,
        "params": params,
        "type": qc_type,
    }


@router.get("/stats/{run_id}")
async def get_qc_stats(run_id: str):
    """获取质检任务的统计信息"""
    qc_results_dir = current_workspace().runs_dir / "qc_results"
    meta_path = qc_results_dir / run_id / "meta.json"

    stats = {"run_id": run_id}

    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        stats["type"] = meta.get("type", "")
        stats["start_time"] = meta.get("start_time", "")

    summary_path = qc_results_dir / run_id / "qc_summary_voting.csv"
    if summary_path.exists():
        import pandas as pd
        df = pd.read_csv(summary_path)
        total = len(df)
        l1_pass = int(df["level1_pass"].sum()) if "level1_pass" in df.columns else 0
        l2_pass = int(df["level2_pass"].sum()) if "level2_pass" in df.columns else 0
        overall_pass = int(df["overall_pass"].sum()) if "overall_pass" in df.columns else 0
        stats.update({
            "total_samples": total,
            "level1_pass_count": l1_pass,
            "level1_pass_rate": round(l1_pass / total, 4) if total > 0 else 0,
            "level2_pass_count": l2_pass,
            "level2_pass_rate": round(l2_pass / total, 4) if total > 0 else 0,
            "overall_pass_count": overall_pass,
            "overall_pass_rate": round(overall_pass / total, 4) if total > 0 else 0,
        })

    quality_path = qc_results_dir / run_id / "quality_check_results.csv"
    if quality_path.exists():
        import pandas as pd
        df = pd.read_csv(quality_path)
        sev_counts = df["severity"].value_counts().to_dict() if "severity" in df.columns else {}
        stats["severity_distribution"] = sev_counts

    return stats
    ws = current_workspace()
