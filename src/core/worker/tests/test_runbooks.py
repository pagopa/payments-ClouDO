# python
import importlib
import json
import os
from unittest.mock import MagicMock, patch

import azure.functions as func


def make_queue_message(payload: dict) -> func.QueueMessage:
    # Minimal QueueMessage stub using azure.functions QueueMessage signature
    class QM(func.QueueMessage):
        def __init__(self, body: bytes):
            self._body = body

        def get_body(self) -> bytes:
            return self._body

    return QM(json.dumps(payload).encode("utf-8"))


def test_process_runbook_happy_path(monkeypatch):
    os.environ["FEATURE_DEV"] = "true"
    worker = importlib.import_module("function_app")

    payload = {
        "requestedAt": "2025-01-01 10:00:00",
        "id": "schema-1",
        "name": "MyRule",
        "runbook": "script.py",
        "run_args": "--ok 1",
        "exec_id": "exec-abc",
        "oncall": "false",
        "monitor_condition": "Fired",
        "severity": "Sev2",
        "resource_info": json.dumps({"aks_namespace": "", "resource_name": "r1"}),
    }

    # Patch _post_status to record calls instead of doing HTTP
    status_calls = []

    def fake_post_status(d, status, log_message):
        status_calls.append((status, log_message))
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        return mock_resp

    # Patch _run_script to simulate success
    fake_completed = MagicMock()
    fake_completed.returncode = 0
    fake_completed.stdout = "all good\n"
    fake_completed.stderr = ""

    with patch.object(worker, "_post_status", side_effect=fake_post_status):
        with patch.object(worker, "_run_script", return_value=fake_completed):
            # Ensure internal registries are clean
            worker._ACTIVE_RUNS.clear()
            worker._PROCESS_BY_EXEC.clear()

            msg = make_queue_message(payload)
            worker.process_runbook(msg)

            # Verify status transitions: running -> completed
            assert status_calls[0][0] == "running"
            assert status_calls[-1][0] in ("completed",)  # final success

            # Ensure the run is no longer tracked
            assert payload["exec_id"] not in worker._ACTIVE_RUNS


def test_process_runbook_skips_if_already_running(monkeypatch):
    os.environ["FEATURE_DEV"] = "true"
    worker = importlib.import_module("function_app")

    payload = {
        "requestedAt": "2025-01-01 10:00:00",
        "id": "schema-dup",  # same id triggers skip logic
        "name": "MyRule",
        "runbook": "script.py",
        "run_args": "--ok 1",
        "exec_id": "exec-1",
    }

    # Pre-populate ACTIVE_RUNS with same id to trigger skip branch
    worker._ACTIVE_RUNS.clear()
    worker._ACTIVE_RUNS["some-other-exec"] = {"id": "schema-dup"}

    status_calls = []

    def fake_post_status(d, status, log_message):
        status_calls.append(status)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        return mock_resp

    with patch.object(worker, "_post_status", side_effect=fake_post_status):
        msg = make_queue_message(payload)
        worker.process_runbook(msg)

    # Should report "skipped" and not attempt to run
    assert "skipped" in status_calls


def test_run_aks_login_error_includes_full_output(tmp_path):
    os.environ["FEATURE_DEV"] = "true"
    worker = importlib.import_module("function_app")

    class FakePopen:
        def __init__(self, *args, **kwargs):
            self.stdout = iter(
                [
                    'WARNING: Merged "cluster" as current context\n',
                    "ERROR: forbidden: cannot create token\n",
                ]
            )

        def wait(self):
            return 1

    with patch("function_app.os.path.exists", return_value=True), patch(
        "function_app.subprocess.Popen", return_value=FakePopen()
    ):
        try:
            worker._run_aks_login(
                {
                    "resource_rg": "rg-demo",
                    "resource_name": "aks-demo",
                    "aks_namespace": "demo-ns",
                },
                payload={"exec_id": "exec-aks-1"},
                env={},
                temp_dir=str(tmp_path),
            )
            assert False, "Expected RuntimeError from AKS login"
        except RuntimeError as exc:
            message = str(exc)

    assert "AKS login error (rc=1). Full output:" in message
    assert 'WARNING: Merged "cluster" as current context' in message
    assert "ERROR: forbidden: cannot create token" in message
