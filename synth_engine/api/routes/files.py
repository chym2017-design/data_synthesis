"""
结果文件 API

支持：列出所有运行结果、下载文件、预览文件。
"""

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

RUNS_DIR = Path(__file__).parent.parent.parent.parent / "runs"


def _dir_mtime(dir_path: Path) -> str:
    """获取目录的修改时间字符串"""
    try:
        mtime = dir_path.stat().st_mtime
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def _sanitize(obj: Any) -> Any:
    """递归替换 NaN/Inf 为 None"""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    elif pd.isna(obj):
        return None
    return obj


@router.get("/runs")
async def list_all_runs():
    """列出所有运行结果（自动扫描磁盘）"""
    runs = []
    outputs_dir = RUNS_DIR / "outputs"
    qc_dir = RUNS_DIR / "qc_results"

    for search_dir in [outputs_dir, qc_dir]:
        if search_dir.exists():
            for d in sorted(search_dir.iterdir()):
                if d.is_dir():
                    files = []
                    for f in d.iterdir():
                        if f.is_file():
                            files.append({
                                "name": f.name,
                                "size": f.stat().st_size,
                                "type": _guess_type(f.name),
                            })
                    runs.append({
                        "run_id": d.name,
                        "files": files,
                        "dir": str(d.relative_to(RUNS_DIR)),
                        "mtime": _dir_mtime(d),
                    })

    return {"runs": sorted(runs, key=lambda r: r["mtime"], reverse=True)}


@router.delete("/runs/{run_id}")
async def delete_run(run_id: str):
    """删除运行结果目录"""
    import shutil
    for search_dir in ["outputs", "qc_results"]:
        d = RUNS_DIR / search_dir / run_id
        if d.exists():
            shutil.rmtree(str(d))
            return {"status": "ok", "message": f"已删除 {run_id}"}
    raise HTTPException(status_code=404, detail=f"运行 {run_id} 不存在")


@router.get("/download/{run_id}/{filename}")
async def download_file(run_id: str, filename: str):
    """下载运行结果文件"""
    file_path = RUNS_DIR / "outputs" / run_id / filename
    if not file_path.exists():
        file_path = RUNS_DIR / "qc_results" / run_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {run_id}/{filename}")

    return FileResponse(
        str(file_path),
        filename=filename,
        media_type="application/octet-stream",
    )


@router.get("/preview/{run_id}/{filename}")
async def preview_file(run_id: str, filename: str, limit: int = 50):
    """预览结果文件内容（CSV/JSONL 前 N 条）"""
    file_path = RUNS_DIR / "outputs" / run_id / filename
    if not file_path.exists():
        file_path = RUNS_DIR / "qc_results" / run_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {run_id}/{filename}")

    if filename.endswith(".csv"):
        try:
            df = pd.read_csv(str(file_path), nrows=limit, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(str(file_path), nrows=limit, encoding="gbk")
        total = len(pd.read_csv(str(file_path), usecols=[0], encoding="utf-8"))
        return {
            "type": "csv",
            "total_rows": total,
            "columns": list(df.columns),
            "preview": _sanitize(df.head(limit).to_dict(orient="records")),
        }
    elif filename.endswith(".jsonl"):
        with open(file_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        total = len(all_lines)
        preview = []
        for line in all_lines[:limit]:
            try:
                preview.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                preview.append({"_raw": line.strip()})
        return {
            "type": "jsonl",
            "total_rows": total,
            "preview": preview,
        }
    elif filename.endswith(".json"):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "type": "json",
            "preview": data,
        }
    else:
        raise HTTPException(status_code=400, detail=f"不支持预览的文件类型: {filename}")


def _guess_type(filename: str) -> str:
    if filename.endswith(".csv"):
        return "csv"
    elif filename.endswith(".jsonl"):
        return "jsonl"
    elif filename.endswith(".json"):
        return "json"
    elif filename.endswith(".yaml") or filename.endswith(".yml"):
        return "yaml"
    return "other"
