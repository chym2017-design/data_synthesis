"""当前用户、工作空间和队列信息。"""

from fastapi import APIRouter

from synth_engine.limits import LIMITS
from synth_engine.task_queue import task_queue
from synth_engine.tenant import current_workspace


router = APIRouter()


@router.get("/limits")
async def get_system_limits():
    """返回前后端共同使用的系统任务限制。"""
    current_workspace()
    return LIMITS.as_dict()


@router.get("/me")
async def get_current_user():
    ws = current_workspace()
    return {
        "username": ws.username,
        "workspace_id": ws.workspace_id,
    }


@router.get("/queue")
async def get_queue():
    current_workspace()
    summary = task_queue.summary()
    summary["jobs"] = [
        {
            "job_id": job["job_id"],
            "username": job["username"],
            "task_type": job["task_type"],
            "state": job["state"],
            "submitted_at": job["submitted_at"],
            "started_at": job["started_at"],
            "queue_position": job["queue_position"],
        }
        for job in summary["jobs"]
        if job["state"] in {"queued", "running"}
    ]
    return summary
