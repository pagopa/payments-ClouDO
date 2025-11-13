# python
import json

import azure.functions as func


class FakeOut(func.Out):
    # Minimal table output stub that captures writes and allows reading back
    def __init__(self):
        self.value = None

    def set(self, v):
        self.value = v

    def get(self):
        return self.value


def test_receiver_min_ok():
    # Import after potential global patches (if any in suite)
    from function_app import Receiver

    # Minimal base64 body (e.g., {"log":"base64"})
    body = b"eyJsb2ciOiAiYmFzZTY0In0="

    # Required headers. Include Severity because Opsgenie priority derives from it.
    headers = {
        "ExecId": "123",
        "Status": "Completed",  # will be normalized to "succeeded"
        "Name": "Rule",
        "Id": "schema-1",
        "runbook": "rb.sh",
        "Severity": "Sev3",
    }

    # Build request and output binding stub
    req = func.HttpRequest("POST", "https://x/api/Receiver", headers=headers, body=body)
    out = FakeOut()

    # Call the function
    res = Receiver(req, out)

    # Assert HTTP response
    assert res.status_code == 200

    # Assert log entity content
    log = json.loads(out.get())
    assert log["Status"] == "succeeded"
    assert log["ExecId"] == "123"
    # Some implementations may store schema id under "Id"
    assert log.get("Id") == "schema-1"
