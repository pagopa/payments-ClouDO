# python
import json
import os
from unittest.mock import MagicMock, patch

import azure.functions as func


def make_request(
    method="POST", url="https://x/api/Trigger", params=None, headers=None, body=b""
):
    # Inject team via querystring to avoid setting route_params (which is read-only)
    params = params or {}
    sep = "&" if "?" in url else "?"
    url = f"{url}{sep}team=core"
    return func.HttpRequest(
        method=method,
        url=url,
        params=params,
        headers=headers or {},
        body=body,
    )


class FakeOut(func.Out):
    # Minimal table output stub that captures the last value passed to set()
    def __init__(self):
        self.value = None

    def set(self, v):
        self.value = v

    def get(self):
        return self.value


def test_trigger_happy_path(monkeypatch):
    # Ensure anonymous auth in tests
    os.environ["FEATURE_DEV"] = "true"

    # Table binding mocked content: a single schema row
    schema_row = {
        "id": "schema-1",
        "Id": "schema-1",
        "name": "My Rule",
        "url": "https://runbook.example/exec",
        "runbook": "rb.sh",
        "run_args": "--x 1",
        "oncall": "false",
        "require_approval": "false",
    }
    entities = json.dumps([schema_row])

    # Mock downstream runbook HTTP call
    fake_resp = MagicMock()
    fake_resp.status_code = 202
    fake_resp.json.return_value = {"ok": True}

    # Patch external dependencies before importing the function to test
    with patch("function_app.request", return_value=fake_resp):
        # Routing is not executed for status 202 ("accepted"), but we patch defensively
        with patch("function_app.route_alert", return_value=MagicMock(actions=[])):
            with patch("function_app.execute_actions") as exec_actions:
                from function_app import Trigger

                # Build request and fake table output
                req = make_request(params={"id": "schema-1"})
                out = FakeOut()

                # Invoke function
                res = Trigger(req, out, entities)

                # Assert HTTP response
                assert res.status_code == 202
                body = json.loads(res.get_body())
                assert body["status"] == 202
                assert body["schema"]["id"] == "schema-1"

                # Assert a coherent log entity is written
                log = json.loads(out.get())
                assert log["Status"] == "accepted"
                assert log["Id"] == "schema-1"
                assert log["Runbook"] == "rb.sh"

                # Ensure routing actions are not executed on "accepted"
                exec_actions.assert_not_called()
