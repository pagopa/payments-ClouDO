import json
import logging
import os
import subprocess
from datetime import datetime, timezone

import azure.functions as func
import requests

# Configuration constants
RECEIVER_URL = "http://localhost:7072/api/Receiver"
QUEUE_NAME = "runbooktest-work"
STORAGE_CONNECTION = "AzureWebJobsStorage"

app = func.FunctionApp()


def _utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO 8601 format without microseconds."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _build_status_headers(payload: dict, status: str, log_message: str) -> dict:
    """Build headers for the Receiver call from payload and execution status."""
    return {
        "runbook": payload.get("runbook"),
        "Id": payload.get("id"),
        "Name": payload.get("name"),
        "ExecId": payload.get("exec_id"),
        "Content-Type": "application/json",
        "Status": status,
        "Log": log_message,
    }


def _post_status(payload: dict, status: str, log_message: str) -> requests.Response:
    """Send execution status to the Receiver and return the HTTP response."""
    headers = _build_status_headers(payload, status, log_message)
    try:
        return requests.post(RECEIVER_URL, headers=headers, timeout=10)
    except requests.RequestException as err:
        logging.error("Failed to send status to Receiver: %s", err)
        raise


def _run_script(script_name: str) -> subprocess.CompletedProcess:
    """Run the requested script and return the subprocess result"""
    if not script_name:
        raise ValueError("Missing runbook/script name")
    script_path = os.path.join("..", "scripts", script_name)
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Script not found: {script_path}")
    return subprocess.run([script_path], capture_output=True, text=True, check=True)


@app.route(route="RunbookTest", auth_level=func.AuthLevel.FUNCTION)
@app.queue_output(
    arg_name="out_msg", queue_name=QUEUE_NAME, connection=STORAGE_CONNECTION
)
def runbook_test(req: func.HttpRequest, out_msg: func.Out[str]) -> func.HttpResponse:
    logging.info("RunbookTest params: %s", req.params)
    payload = {
        "requestedAt": _utc_now_iso(),
        "id": req.headers.get("Id"),
        "name": req.headers.get("Name"),
        "runbook": req.headers.get("runbook"),
        "exec_id": req.headers.get("ExecId"),
        "oncall": req.headers.get("OnCall"),
    }
    out_msg.set(json.dumps(payload, ensure_ascii=False))
    body = json.dumps(
        {"status": "accepted", "message": "processing scheduled"}, ensure_ascii=False
    )
    return func.HttpResponse(body, status_code=202, mimetype="application/json")


@app.queue_trigger(arg_name="msg", queue_name=QUEUE_NAME, connection=STORAGE_CONNECTION)
def process_runbooktest(msg: func.QueueMessage) -> None:
    payload = json.loads(msg.get_body().decode("utf-8"))
    logging.info("Job started: %s", payload)
    try:
        result = _run_script(payload.get("runbook"))
        log_msg = f"Script succeeded. stdout: {result.stdout.strip()}"
        response = _post_status(payload, status="completed", log_message=log_msg)
        logging.info("Receiver response: %s", getattr(response, "text", ""))
    except subprocess.CalledProcessError as e:
        error_message = (
            f"Script failed. returncode={e.returncode} stderr={e.stderr.strip()}"
        )
        try:
            _post_status(payload, status="failed", log_message=error_message)
        finally:
            logging.error(error_message)
    except Exception as e:
        err_msg = f"{type(e).__name__}: {str(e)}"
        try:
            _post_status(payload, status="failed", log_message=err_msg)
        finally:
            logging.error("Unexpected error: %s", err_msg)
    finally:
        logging.info(
            "[%s] Job complete (requested at %s)",
            payload.get("id"),
            payload.get("requestedAt"),
        )
