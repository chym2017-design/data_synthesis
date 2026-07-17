import threading
import time
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from synth_engine.api.main import app
from synth_engine import tenant
from synth_engine.api.routes import config as config_routes
from synth_engine.api.routes import qc as qc_routes
from synth_engine.api.routes import system as system_routes
from synth_engine.qc import pre_check as pre_check_module
from synth_engine.qc import post_check as post_check_module
from synth_engine.core import pipeline as pipeline_module
from synth_engine.core.pipeline import SynthesisPipeline
from synth_engine.core.models import RunStatus, SynthSample
from synth_engine.limits import LIMITS, load_system_limits
from synth_engine.task_ids import generate_task_id
from synth_engine.task_queue import TaskQueue


@pytest.fixture()
def isolated_tenants(tmp_path, monkeypatch):
    seed_configs = tmp_path / "seed-configs"
    seed_templates = tmp_path / "seed-templates"
    seed_resources = tmp_path / "seed-resources"
    seed_configs.mkdir()
    seed_templates.mkdir()
    seed_resources.mkdir()
    monkeypatch.setattr(tenant, "DATA_ROOT", tmp_path / "data")
    monkeypatch.setattr(tenant, "USERS_DB", tmp_path / "data" / "users.db")
    monkeypatch.setattr(tenant, "WORKSPACES_ROOT", tmp_path / "workspaces")
    monkeypatch.setattr(tenant, "DEFAULT_CONFIGS_DIR", seed_configs)
    monkeypatch.setattr(tenant, "DEFAULT_TEMPLATES_DIR", seed_templates)
    monkeypatch.setattr(tenant, "DEFAULT_RESOURCES_DIR", seed_resources)
    tenant.init_tenant_store()
    return tmp_path


def _headers(username):
    return {"X-Authenticated-User": username}


def test_users_receive_separate_workspaces_and_configs(isolated_tenants):
    alice = tenant.create_user("alice")
    bob = tenant.create_user("bob")
    assert alice.workspace_id.startswith("alice-")
    assert bob.workspace_id.startswith("bob-")
    assert alice.workspace_id != bob.workspace_id
    assert alice.root != bob.root

    with TestClient(app) as client:
        alice_cfg = [{"model": "alice-model", "url": "https://example.test/v1", "api_key": "alice-key"}]
        response = client.put("/api/config/llm", json={"config": alice_cfg}, headers=_headers("alice"))
        assert response.status_code == 200
        assert client.get("/api/config/llm", headers=_headers("alice")).json()["config"] == alice_cfg
        assert client.get("/api/config/llm", headers=_headers("bob")).json()["config"] == []


def test_system_limits_are_not_copied_into_user_workspace(isolated_tenants):
    (tenant.DEFAULT_CONFIGS_DIR / "system_limits.yaml").write_text(
        "max_concurrent_tasks: 99\n", encoding="utf-8"
    )
    (tenant.DEFAULT_CONFIGS_DIR / "llm_config.yaml").write_text("[]\n", encoding="utf-8")

    ctx = tenant.create_user("alice")

    assert (ctx.configs_dir / "llm_config.yaml").is_file()
    assert not (ctx.configs_dir / "system_limits.yaml").exists()


def test_intent_editor_updates_runtime_json_and_removes_legacy_overlay(isolated_tenants):
    seed_template = tenant.DEFAULT_TEMPLATES_DIR / "bank_intent"
    seed_template.mkdir(parents=True)
    original = {
        "intent": {
            "其他": {
                "weight": 1,
                "description": "其他业务",
                "sub_intent": [{"name": "缴费", "description": "旧描述"}],
                "example": [],
            }
        }
    }
    (seed_template / "intent.json").write_text(
        json.dumps(original, ensure_ascii=False), encoding="utf-8"
    )
    ctx = tenant.create_user("alice")
    legacy_overlay = ctx.templates_dir / "bank_intent" / "intent.user.yaml"
    legacy_overlay.write_text("intent: {}\n", encoding="utf-8")
    updated = json.loads(json.dumps(original, ensure_ascii=False))
    updated["intent"]["其他"]["sub_intent"][0]["description"] = "支持水电燃气等生活缴费"

    with TestClient(app) as client:
        response = client.put(
            "/api/config/bank_intent/intent",
            json=updated,
            headers=_headers("alice"),
        )

    saved_path = ctx.templates_dir / "bank_intent" / "intent.json"
    assert response.status_code == 200
    assert json.loads(saved_path.read_text(encoding="utf-8")) == updated
    assert not legacy_overlay.exists()


@pytest.mark.parametrize(
    ("config_type", "filename", "default_content", "changed_content"),
    [
        ("intent", "intent.json", {"intent": {"默认": {"weight": 1}}}, {"intent": {"修改": {"weight": 2}}}),
        ("synth_config", "synth_config.yaml", {"single_round_ratio": 0.05}, {"single_round_ratio": 0.9}),
        ("profile_config", "profile_config.yaml", {"basic_attributes": {"age_range": [18, 70]}}, {"basic_attributes": {"age_range": [30, 31]}}),
    ],
)
def test_template_configs_can_restore_defaults(
    isolated_tenants, config_type, filename, default_content, changed_content
):
    seed_template = tenant.DEFAULT_TEMPLATES_DIR / "bank_intent"
    seed_template.mkdir(parents=True, exist_ok=True)
    source = seed_template / filename
    if source.suffix == ".json":
        source.write_text(json.dumps(default_content, ensure_ascii=False), encoding="utf-8")
    else:
        import yaml
        source.write_text(yaml.safe_dump(default_content, allow_unicode=True), encoding="utf-8")

    ctx = tenant.create_user("alice")
    destination = ctx.templates_dir / "bank_intent" / filename
    if destination.suffix == ".json":
        destination.write_text(json.dumps(changed_content, ensure_ascii=False), encoding="utf-8")
    else:
        import yaml
        destination.write_text(yaml.safe_dump(changed_content, allow_unicode=True), encoding="utf-8")
    overlay = ctx.templates_dir / "bank_intent" / f"{config_type}.user.yaml"
    overlay.write_text("changed: true\n", encoding="utf-8")

    with TestClient(app) as client:
        response = client.post(
            f"/api/config/bank_intent/{config_type}/restore_default",
            headers=_headers("alice"),
        )

    assert response.status_code == 200
    assert destination.read_bytes() == source.read_bytes()
    assert not overlay.exists()


def test_user_cannot_read_another_workspace_result(isolated_tenants):
    alice = tenant.create_user("alice")
    tenant.create_user("bob")
    result_dir = alice.runs_dir / "outputs" / "private-run"
    result_dir.mkdir(parents=True)
    (result_dir / "data.csv").write_text("secret\nvalue\n", encoding="utf-8")

    with TestClient(app) as client:
        assert client.get("/api/files/preview/private-run/data.csv", headers=_headers("alice")).status_code == 200
        assert client.get("/api/files/preview/private-run/data.csv", headers=_headers("bob")).status_code == 404

        alice_files = client.get("/api/qc/available_files", headers=_headers("alice"))
        bob_files = client.get("/api/qc/available_files", headers=_headers("bob"))
        assert alice_files.status_code == 200
        assert [item["run_id"] for item in alice_files.json()["data_csv"]] == ["private-run"]
        assert bob_files.status_code == 200
        assert bob_files.json()["data_csv"] == []


@pytest.mark.parametrize(
    ("url", "payload"),
    [
        (
            "/api/synthesis/start",
            {
                "template_name": "bank_intent",
                "num_samples": LIMITS.task_items.synthesis + 1,
                "para": LIMITS.model_parallelism.default,
            },
        ),
        (
            "/api/qc/pre_check",
            {
                "intent_file": "x.json",
                "sample_size": LIMITS.task_items.qc_pre + 1,
                "para": LIMITS.model_parallelism.default,
            },
        ),
        (
            "/api/qc/post_check",
            {
                "data_file": "x.csv",
                "intent_file": "x.json",
                "sample_size": LIMITS.task_items.qc_post + 1,
                "para": LIMITS.model_parallelism.default,
            },
        ),
    ],
)
def test_configured_item_limits_are_enforced(isolated_tenants, url, payload):
    tenant.create_user("alice")
    with TestClient(app) as client:
        response = client.post(url, json=payload, headers=_headers("alice"))
    assert response.status_code == 422


def test_system_limits_endpoint_uses_shared_config(isolated_tenants):
    tenant.create_user("alice")
    with TestClient(app) as client:
        response = client.get("/api/system/limits", headers=_headers("alice"))

    assert response.status_code == 200
    assert response.json() == LIMITS.as_dict()


def test_system_limits_loader_reads_and_validates_one_yaml(tmp_path):
    config_path = tmp_path / "system_limits.yaml"
    config_path.write_text(
        """task_items:
  synthesis: 12
  qc_pre: 13
  qc_post: 14
model_parallelism:
  default: 2
  max: 4
max_concurrent_tasks: 6
""",
        encoding="utf-8",
    )

    loaded = load_system_limits(config_path)
    assert loaded.task_items.synthesis == 12
    assert loaded.task_items.qc_pre == 13
    assert loaded.task_items.qc_post == 14
    assert loaded.model_parallelism.default == 2
    assert loaded.model_parallelism.max == 4
    assert loaded.max_concurrent_tasks == 6

    config_path.write_text(config_path.read_text(encoding="utf-8").replace("default: 2", "default: 5"), encoding="utf-8")
    with pytest.raises(ValueError, match="default 不能大于"):
        load_system_limits(config_path)


def test_tasks_beyond_worker_limit_are_queued():
    queue = TaskQueue(max_workers=2)
    release = threading.Event()
    started = threading.Event()
    started_count = 0
    lock = threading.Lock()

    def blocking_task():
        nonlocal started_count
        with lock:
            started_count += 1
            if started_count == 2:
                started.set()
        release.wait(timeout=5)

    try:
        for index in range(3):
            queue.submit(
                job_id=f"job-{index}",
                username="alice",
                workspace_id="workspace-a",
                task_type="test",
                function=blocking_task,
            )
        assert started.wait(timeout=2)
        deadline = time.time() + 2
        while time.time() < deadline and queue.status("job-2")["state"] != "queued":
            time.sleep(0.01)
        third = queue.status("job-2")
        assert third["state"] == "queued"
        assert third["queue_position"] == 1
        assert third["running_count"] == 2
        assert third["max_concurrent"] == 2
    finally:
        release.set()


def test_model_connection_endpoints_use_unsaved_config(isolated_tenants, monkeypatch):
    tenant.create_user("alice")
    supplied = {}

    def fake_llm(question, **config):
        supplied.update(config)
        return {
            "status_code": 200,
            "err_msg": "",
            "model": config["model"],
            "response": "连接正常",
            "duration": 0.1,
        }

    monkeypatch.setattr(config_routes, "run_llm_non_stream", fake_llm)
    payload = {
        "config": {
            "model": "unsaved-model",
            "url": "https://example.test/v1/chat/completions",
            "api_key": "unsaved-key",
            "stream": True,
        }
    }
    with TestClient(app) as client:
        response = client.post("/api/config/test/llm", json=payload, headers=_headers("alice"))
    assert response.status_code == 200
    assert response.json()["response_preview"] == "连接正常"
    assert supplied["stream"] is False
    assert not (tenant.workspace_for_user("alice").configs_dir / "llm_config.yaml").exists()


def test_embedding_connection_endpoint_reports_dimensions(isolated_tenants, monkeypatch):
    tenant.create_user("alice")
    monkeypatch.setattr(config_routes, "get_embedding", lambda *args, **kwargs: [0.1, 0.2, 0.3])
    payload = {
        "config": {
            "model": "embedding-model",
            "url": "https://example.test/v1/embeddings",
            "api_key": "unsaved-key",
        }
    }
    with TestClient(app) as client:
        response = client.post("/api/config/test/embedding", json=payload, headers=_headers("alice"))
    assert response.status_code == 200
    assert response.json()["dimensions"] == 3


def test_old_uuid_workspace_can_be_renamed_without_losing_files(isolated_tenants):
    ctx = tenant.create_user("alice")
    old_id = "0123456789abcdef0123456789abcdef"
    old_root = tenant.WORKSPACES_ROOT / old_id
    ctx.root.rename(old_root)
    marker = old_root / "runs" / "outputs" / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    with tenant._connect() as conn:
        conn.execute(
            "UPDATE users SET workspace_id = ? WHERE username = ?",
            (old_id, "alice"),
        )

    result = tenant.migrate_workspace_names()
    migrated = tenant.workspace_for_user("alice")
    assert result == [{"username": "alice", "old": old_id, "new": "alice-01234567"}]
    assert migrated.workspace_id == "alice-01234567"
    assert (migrated.root / "runs" / "outputs" / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert not old_root.exists()


def test_dev_user_override_only_accepts_loopback(isolated_tenants, monkeypatch):
    tenant.create_user("localtest")
    monkeypatch.setenv("SYNTH_DEV_USER", "localtest")
    with TestClient(app) as client:
        response = client.get("/api/system/me")
    assert response.status_code == 200
    assert response.json()["username"] == "localtest"


@pytest.mark.parametrize(
    ("task_type", "expected"),
    [
        ("quality_bef", "alice_quality_bef_260717103015_0123456789abcdef0123456789abcdef"),
        ("quality_after", "alice_quality_after_260717103015_0123456789abcdef0123456789abcdef"),
        ("synth", "alice_synth_260717103015_0123456789abcdef0123456789abcdef"),
    ],
)
def test_task_id_is_the_single_readable_unique_id(task_type, expected):
    now = datetime(2026, 7, 17, 10, 30, 15, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert generate_task_id(
        "alice",
        task_type,
        now=now,
        uuid_hex="0123456789abcdef0123456789abcdef",
    ) == expected


def test_global_queue_is_visible_without_exposing_workspace_ids(isolated_tenants, monkeypatch):
    tenant.create_user("alice")
    tenant.create_user("bob")

    class FakeQueue:
        def summary(self):
            return {
                "running_count": 1,
                "queued_count": 1,
                "max_concurrent": 5,
                "jobs": [
                    {
                        "job_id": "alice_synth_260717103015_0123456789abcdef0123456789abcdef",
                        "username": "alice",
                        "workspace_id": "alice-private-space",
                        "task_type": "synthesis",
                        "state": "running",
                        "submitted_at": "2026-07-17 10:30:15",
                        "started_at": "2026-07-17 10:30:16",
                        "finished_at": "",
                        "error": "",
                        "queue_position": 0,
                    },
                    {
                        "job_id": "bob_quality_bef_260717103016_fedcba9876543210fedcba9876543210",
                        "username": "bob",
                        "workspace_id": "bob-private-space",
                        "task_type": "qc_pre",
                        "state": "queued",
                        "submitted_at": "2026-07-17 10:30:16",
                        "started_at": "",
                        "finished_at": "",
                        "error": "",
                        "queue_position": 1,
                    },
                ],
            }

    monkeypatch.setattr(system_routes, "task_queue", FakeQueue())
    with TestClient(app) as client:
        alice_view = client.get("/api/system/queue", headers=_headers("alice"))
        bob_view = client.get("/api/system/queue", headers=_headers("bob"))
    assert alice_view.status_code == bob_view.status_code == 200
    assert alice_view.json() == bob_view.json()
    assert {job["username"] for job in alice_view.json()["jobs"]} == {"alice", "bob"}
    assert all("workspace_id" not in job for job in alice_view.json()["jobs"])


def test_logout_returns_basic_auth_challenge_and_clear_header():
    with TestClient(app) as client:
        response = client.get("/logout")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Basic realm="Synth Engine"'
    assert "cookies" in response.headers["clear-site-data"]


def test_active_qc_with_partial_csv_is_not_reported_as_done(isolated_tenants):
    ctx = tenant.create_user("alice")
    run_id = "alice_quality_bef_260717114006_0123456789abcdef0123456789abcdef"
    result_dir = ctx.runs_dir / "qc_results" / run_id
    result_dir.mkdir(parents=True)
    (result_dir / "quality_check_results.csv").write_text("partial\n", encoding="utf-8")
    qc_routes._active_qc_runs[run_id] = {
        "status": RunStatus(
            run_id=run_id,
            stage="similarity_check",
            total=190,
            current=32,
            message="正在判断相似菜单... (32/190)",
        ),
        "start_time": "2026-07-17 11:40:06",
        "workspace_id": ctx.workspace_id,
        "username": "alice",
        "type": "pre",
    }
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/qc/status/{run_id}", headers=_headers("alice"))
        body = response.json()
        assert response.status_code == 200
        assert body["type"] == "pre"
        assert body["stage"] == "similarity_check"
        assert body["current"] == 32
        assert body["total"] == 190
        assert body["message"] == "正在判断相似菜单... (32/190)"
    finally:
        qc_routes._active_qc_runs.pop(run_id, None)


def test_pre_qc_reports_similarity_llm_progress(tmp_path, monkeypatch):
    intent_path = tmp_path / "intent.json"
    intent_path.write_text(
        json.dumps({
            "intent": {
                "其他": {
                    "sub_intent": [
                        {"name": "缴费", "description": "生活缴费"},
                        {"name": "充值", "description": "账户充值"},
                    ]
                }
            }
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    call_number = 0

    def fake_run_llm_para(queries, para, configs, progress_callback=None):
        nonlocal call_number
        call_number += 1
        for completed in range(1, len(queries) + 1):
            if progress_callback:
                progress_callback(completed, len(queries))
        if call_number == 1:
            responses = ['{"overall_assessment":{"severity":"none"}}'] * len(queries)
        else:
            responses = ['{"is_confusable":false,"confusion_score":0}'] * len(queries)
        return pd.DataFrame({"response": responses, "model": ["mock"] * len(queries)})

    monkeypatch.setattr(pre_check_module, "run_llm_para", fake_run_llm_para)
    monkeypatch.setattr(pre_check_module, "get_embedding", lambda *args, **kwargs: [1.0, 0.0])
    statuses = []
    pre_check_module.pre_synthesis_qc(
        intent_file=str(intent_path),
        llm_configs=[{"model": "mock"}],
        save_dir=str(tmp_path / "results"),
        embedding_config={"url": "https://example.test/v1/embeddings", "api_key": "key", "model": "mock"},
        similarity_threshold=0.9,
        status_callback=statuses.append,
    )

    similarity_updates = [
        status for status in statuses
        if status.stage == "similarity_check" and "正在判断相似菜单" in status.message
    ]
    assert any(status.current == 1 and status.total == 1 for status in similarity_updates)


def test_synthesis_llm_progress_is_forwarded_and_logs_are_appended(tmp_path, monkeypatch):
    class FakeTemplate:
        def build_prompt(self, sample, prompt_path):
            return f"prompt-{sample.sample_id}"

    def fake_run_llm_para(queries, para, configs, progress_callback=None):
        for completed in range(1, len(queries) + 1):
            if progress_callback:
                progress_callback(completed, len(queries))
        return pd.DataFrame({
            "question": queries,
            "response": ["用户：测试"] * len(queries),
            "model": ["mock"] * len(queries),
            "status_code": [200] * len(queries),
            "err_msg": [""] * len(queries),
            "duration": [0.1] * len(queries),
        })

    monkeypatch.setattr(pipeline_module, "run_llm_para", fake_run_llm_para)
    pipeline = object.__new__(SynthesisPipeline)
    pipeline.run_dir = tmp_path
    pipeline.template_dir = tmp_path
    pipeline.template = FakeTemplate()
    statuses = []
    pipeline.status_callback = statuses.append
    sample = SynthSample(
        sample_id=1,
        intent_1="其他", intent_2="其他",
        sub_intent_1="缴费", sub_intent_2="缴费",
        sub_intent_desc_1="缴费", sub_intent_desc_2="缴费",
        target={"意图": "其他", "子意图": "缴费"},
        user_profile="测试画像", round_num=1, num_sen=2,
        yuqi="问句", xinqing="",
    )

    pipeline.call_llm(
        [sample], [{"model": "mock"}], template_name="multi_round.md",
        progress_offset=2, progress_total=5,
    )
    pipeline.call_llm(
        [sample], [{"model": "mock"}], template_name="single_round.md",
        progress_offset=3, progress_total=5,
    )

    assert any(status.stage == "calling_llm" and status.current == 3 and status.total == 5 for status in statuses)
    assert any(status.stage == "calling_llm" and status.current == 4 and status.total == 5 for status in statuses)
    assert len((tmp_path / "llm_log.jsonl").read_text(encoding="utf-8").strip().splitlines()) == 2


def test_post_qc_reports_each_model_phase_and_summary_progress(tmp_path, monkeypatch):
    data_path = tmp_path / "data.csv"
    pd.DataFrame([{
        "query": "我要缴费",
        "target": json.dumps({"意图": "其他", "子意图": "缴费"}, ensure_ascii=False),
        "sub_intent_desc_2": "查询缴费信息",
    }]).to_csv(data_path)

    call_number = 0

    def fake_run_with_assign(queries, para, progress_callback=None):
        nonlocal call_number
        call_number += 1
        for completed in range(1, len(queries) + 1):
            if progress_callback:
                progress_callback(completed, len(queries))
        response = "其他" if call_number == 1 else "缴费"
        return pd.DataFrame({"response": [response] * len(queries)})

    monkeypatch.setattr(post_check_module, "run_llm_para_with_assign", fake_run_with_assign)
    statuses = []
    post_check_module.llm_qc_with_voting(
        data_file=str(data_path),
        intent_config={
            "intent": {
                "其他": {
                    "description": "其他金融业务",
                    "sub_intent": [{"name": "缴费", "description": "查询缴费信息"}],
                }
            }
        },
        llm_configs=[{"model": "mock"}],
        save_dir=str(tmp_path / "qc"),
        status_callback=statuses.append,
    )

    assert any(s.stage == "llm_level1" and s.current == s.total == 1 for s in statuses)
    assert any(s.stage == "llm_level2" and s.current == s.total == 1 for s in statuses)
    assert any(s.stage == "llm_summary" and s.current == s.total == 1 for s in statuses)
