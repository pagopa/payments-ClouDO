# python
import importlib
import json
import os
from unittest.mock import MagicMock, patch

import azure.functions as func


def test_list_processes_returns_active_runs(monkeypatch):
    os.environ["FEATURE_DEV"] = "true"
    worker = importlib.import_module("function_app")

    # Seed ACTIVE_RUNS with two items
    worker._ACTIVE_RUNS.clear()
    worker._ACTIVE_RUNS["e1"] = {
        "exec_id": "e1",
        "id": "s1",
        "name": "N1",
        "runbook": "a.sh",
        "requestedAt": "2025-01-01 10:00:00",
        "startedAt": "2025-01-01 10:01:00",
        "status": "running",
    }
    worker._ACTIVE_RUNS["e2"] = {
        "exec_id": "e2",
        "id": "s2",
        "name": "N2",
        "runbook": "b.sh",
        "requestedAt": "2025-01-01 10:00:10",
        "startedAt": "2025-01-01 10:02:00",
        "status": "running",
    }

    req = func.HttpRequest(
        "GET", "https://x/api/processes?q=N", params={}, headers={}, body=b""
    )
    res = worker.list_processes(req)
    assert res.status_code == 200
    data = json.loads(res.get_body())
    assert data["status"] == "ok"
    assert data["count"] == 2
    assert len(data["runs"]) == 2


def test_stop_process_terminates_and_reports(monkeypatch):
    os.environ["FEATURE_DEV"] = "true"
    worker = importlib.import_module("function_app")

    # Fake running process mapped by exec id
    fake_proc = MagicMock()
    fake_proc.poll.return_value = None  # running
    worker._PROCESS_BY_EXEC.clear()
    worker._PROCESS_BY_EXEC["exec-999"] = fake_proc

    # Track run info to trigger _post_status on stop
    worker._ACTIVE_RUNS.clear()
    worker._ACTIVE_RUNS["exec-999"] = {
        "exec_id": "exec-999",
        "id": "s1",
        "name": "N1",
        "runbook": "a.sh",
        "run_args": "--x 1",
        "requestedAt": "2025-01-01 10:00:00",
        "startedAt": "2025-01-01 10:01:00",
        "status": "running",
    }

    # Stub post status so we don't do real HTTP
    with patch.object(
        worker, "_post_status", return_value=MagicMock(status_code=200)
    ) as post_status:
        req = func.HttpRequest(
            "DELETE",
            "https://x/api/processes/stop?exec_id=exec-999",
            params={"exec_id": "exec-999"},
            headers={},
            body=b"",
        )
        res = worker.stop_process(req)

    assert res.status_code == 200
    body = json.loads(res.get_body())
    assert body["status"] == "stopped"
    assert body["exec_id"] == "exec-999"

    # Process termination sequence attempted
    fake_proc.terminate.assert_called_once()
    fake_proc.wait.assert_called_once()

    # A status update should have been posted
    post_status.assert_called()
