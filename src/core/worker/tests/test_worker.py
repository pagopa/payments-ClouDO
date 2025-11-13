# python
import importlib
import json
import os

import azure.functions as func


# Minimal Out stub capturing value passed to set()
class FakeOut(func.Out):
    def __init__(self):
        self.value = None

    def set(self, v):
        self.value = v

    def get(self):
        return self.value


def test_runbook_accepts_and_queues(monkeypatch):
    # Ensure dev mode for anonymous auth if the function checks FEATURE_DEV
    os.environ["FEATURE_DEV"] = "true"

    # Import the module under test (adjust if your worker module has a different name)
    worker = importlib.import_module("function_app")

    headers = {
        "Id": "schema-1",
        "Name": "MyRule",
        "runbook": "script.py",
        "run_args": "--flag x",
        "ExecId": "exec-123",
        "OnCall": "false",
        "MonitorCondition": "Fired",
        "Severity": "Sev3",
        # Optional: pass resource/routing info as strings; function just forwards them
        "resource_info": json.dumps({"resource_name": "r1"}),
        "routing_info": json.dumps({"team": "core"}),
    }
    req = func.HttpRequest(
        method="POST",
        url="https://x/api/Runbook",
        headers=headers,
        params={},
        body=b"",
    )

    out = FakeOut()

    # Call the HTTP function
    res = worker.runbook(req, out)

    # Assert HTTP 202 response
    assert res.status_code == 202
    body = json.loads(res.get_body())
    assert body["status"] == "accepted"

    # Verify a message was queued with expected payload fields
    queued = json.loads(out.get())
    assert queued["id"] == "schema-1"
    assert queued["name"] == "MyRule"
    assert queued["runbook"] == "script.py"
    assert queued["run_args"] == "--flag x"
    assert queued["exec_id"] == "exec-123"
    assert "requestedAt" in queued
