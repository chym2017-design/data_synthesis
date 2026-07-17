"""进程内统一任务队列。

当前单 ECS/单应用进程默认同时执行五个合成或质检任务。队列记录仅用于
当前进程；服务重启时正在运行和排队的任务由各路由按中断任务处理。
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Callable, Deque, Dict, List, Optional

from synth_engine.limits import LIMITS


MAX_CONCURRENT_TASKS = LIMITS.max_concurrent_tasks


@dataclass
class QueueJob:
    job_id: str
    username: str
    workspace_id: str
    task_type: str
    state: str = "queued"
    submitted_at: str = ""
    started_at: str = ""
    finished_at: str = ""
    error: str = ""


class TaskQueue:
    def __init__(self, max_workers: int = MAX_CONCURRENT_TASKS):
        self.max_workers = max(1, max_workers)
        self._condition = threading.Condition(threading.RLock())
        self._pending: Deque[str] = deque()
        self._jobs: Dict[str, QueueJob] = {}
        self._functions: Dict[str, Callable[[], None]] = {}
        self._on_start: Dict[str, Callable[[], None]] = {}
        self._running: set[str] = set()
        for index in range(self.max_workers):
            threading.Thread(
                target=self._worker,
                name=f"synth-task-worker-{index + 1}",
                daemon=True,
            ).start()

    @staticmethod
    def _now() -> str:
        return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")

    def submit(
        self,
        *,
        job_id: str,
        username: str,
        workspace_id: str,
        task_type: str,
        function: Callable[[], None],
        on_start: Optional[Callable[[], None]] = None,
    ) -> Dict[str, object]:
        with self._condition:
            if job_id in self._jobs:
                raise ValueError(f"任务已存在: {job_id}")
            job = QueueJob(
                job_id=job_id,
                username=username,
                workspace_id=workspace_id,
                task_type=task_type,
                submitted_at=self._now(),
            )
            self._jobs[job_id] = job
            self._functions[job_id] = function
            if on_start:
                self._on_start[job_id] = on_start
            self._pending.append(job_id)
            self._condition.notify()
            return self.status(job_id) or {}

    def _worker(self) -> None:
        while True:
            with self._condition:
                while not self._pending:
                    self._condition.wait()
                job_id = self._pending.popleft()
                job = self._jobs[job_id]
                if job.state == "cancelled":
                    continue
                job.state = "running"
                job.started_at = self._now()
                self._running.add(job_id)
                function = self._functions[job_id]
                on_start = self._on_start.get(job_id)

            try:
                if on_start:
                    on_start()
                function()
                with self._condition:
                    if job.state != "cancelled":
                        job.state = "done"
            except Exception as exc:
                with self._condition:
                    job.state = "error"
                    job.error = str(exc)
            finally:
                with self._condition:
                    job.finished_at = self._now()
                    self._running.discard(job_id)
                    self._functions.pop(job_id, None)
                    self._on_start.pop(job_id, None)
                    self._condition.notify_all()

    def status(self, job_id: str) -> Optional[Dict[str, object]]:
        with self._condition:
            job = self._jobs.get(job_id)
            if not job:
                return None
            result = asdict(job)
            result.update(self._counts_locked())
            result["queue_position"] = self._queue_position_locked(job_id)
            return result

    def _queue_position_locked(self, job_id: str) -> int:
        try:
            return list(self._pending).index(job_id) + 1
        except ValueError:
            return 0

    def _counts_locked(self) -> Dict[str, int]:
        return {
            "running_count": len(self._running),
            "queued_count": len(self._pending),
            "max_concurrent": self.max_workers,
        }

    def summary(self, workspace_id: Optional[str] = None) -> Dict[str, object]:
        with self._condition:
            jobs = list(self._jobs.values())
            if workspace_id:
                jobs = [job for job in jobs if job.workspace_id == workspace_id]
            result: Dict[str, object] = self._counts_locked()
            result["jobs"] = [
                {
                    **asdict(job),
                    "queue_position": self._queue_position_locked(job.job_id),
                }
                for job in sorted(jobs, key=lambda item: item.submitted_at, reverse=True)[:100]
            ]
            return result

    def cancel(self, job_id: str) -> bool:
        with self._condition:
            job = self._jobs.get(job_id)
            if not job or job.state != "queued":
                return False
            try:
                self._pending.remove(job_id)
            except ValueError:
                return False
            job.state = "cancelled"
            job.finished_at = self._now()
            self._functions.pop(job_id, None)
            self._on_start.pop(job_id, None)
            return True


task_queue = TaskQueue()
