import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from threading import Lock

import azure.functions as func
import requests

# Configuration constants
RECEIVER_URL = os.environ.get("RECEIVER_URL", "http://localhost:7071/api/Receiver")
QUEUE_NAME = os.environ.get("QUEUE_NAME", "runbooktest-work")
STORAGE_CONNECTION = "AzureWebJobsStorage"

app = func.FunctionApp()

# In-memory registry of ongoing executions (per instance)
_ACTIVE_RUNS = {}
_ACTIVE_LOCK = Lock()


def _utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO 8601 format without microseconds."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _format_requested_at() -> str:
    # Human-readable UTC timestamp for logs (e.g., 2025-09-15 12:34:56)
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _sanitize_header_value(value: str | None, max_len: int = 4000) -> str:
    """Make a string safe for HTTP headers: remove CR/LF and control chars, collapse spaces, and truncate."""
    if not value:
        return ""
    v = value.replace("\r", " ").replace("\n", " ")
    v = " ".join(v.split())  # collapse whitespace
    try:
        # Keep only latin-1 representable chars to avoid encoding issues in headers
        v = v.encode("latin-1", "ignore").decode("latin-1")
    except Exception:
        v = v.encode("ascii", "ignore").decode("ascii")
    if len(v) > max_len:
        v = v[: max_len - 3] + "..."
    return v


def _build_status_headers(payload: dict, status: str, log_message: str) -> dict:
    """Build headers for the Receiver call from payload and execution status."""
    return {
        "runbook": payload.get("runbook"),
        "Id": payload.get("id"),
        "Name": payload.get("name"),
        "ExecId": payload.get("exec_id"),
        "Content-Type": "application/json",
        "Status": status,
        "Log": _sanitize_header_value(log_message),
        "OnCall": payload.get("oncall"),
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
    script_path = os.path.join("scripts", script_name)
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Script not found: {script_path}")

    # If it's a Python script, run it with the current interpreter; otherwise run it directly
    if script_path.lower().endswith(".py"):
        cmd = [sys.executable, script_path]
    else:
        cmd = [script_path]

    return subprocess.run(cmd, capture_output=True, text=True, check=True)


@app.route(route="RunbookTest", auth_level=func.AuthLevel.FUNCTION)
@app.queue_output(
    arg_name="out_msg", queue_name=QUEUE_NAME, connection=STORAGE_CONNECTION
)
def runbook_test(req: func.HttpRequest, out_msg: func.Out[str]) -> func.HttpResponse:
    payload = {
        "requestedAt": _format_requested_at(),
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

    started_at = _format_requested_at()
    exec_id = payload.get("exec_id") or ""

    # Check if this execution is already running
    with _ACTIVE_LOCK:
        items = list(_ACTIVE_RUNS.values())
        if any(item["id"] == payload.get("id") for item in items):
            log_msg = f"Execution {exec_id} already in progress, skipping"
            logging.info(log_msg)
            _post_status(payload, status="skipped", log_message=log_msg)
            return

    # Register the execution as "in progress"
    with _ACTIVE_LOCK:
        _ACTIVE_RUNS[exec_id] = {
            "exec_id": exec_id,
            "id": payload.get("id"),
            "name": payload.get("name"),
            "runbook": payload.get("runbook"),
            "requestedAt": payload.get("requestedAt"),
            "startedAt": started_at,
            "status": "running",
        }

    try:
        result = _run_script(payload.get("runbook"))
        log_msg = f"Script succeeded. stdout: {result.stdout.strip()}"
        logging.debug(log_msg)
        response = _post_status(payload, status="completed", log_message=log_msg)
        logging.info("Receiver response: %s", getattr(response, "text", ""))
    except subprocess.CalledProcessError as e:
        error_message = (
            f"Script failed. returncode={e.returncode} stderr={e.stderr.strip()}"
        )
        try:
            response = _post_status(payload, status="failed", log_message=error_message)
            logging.error("Receiver response: %s", getattr(response, "text", ""))
        finally:
            logging.error(error_message)
    except Exception as e:
        err_msg = f"{type(e).__name__}: {str(e)}"
        try:
            response = _post_status(payload, status="error", log_message=err_msg)
            logging.error("Receiver response: %s", getattr(response, "text", ""))
        finally:
            logging.error("Unexpected error: %s", err_msg)
    finally:
        # Remove from the registry: no longer "in progress"
        with _ACTIVE_LOCK:
            _ACTIVE_RUNS.pop(exec_id, None)
        logging.info(
            "[%s] Job complete (requested at %s)",
            payload.get("ExecId"),
            payload.get("requestedAt"),
        )


# =========================
# Heartbeat
# =========================


@app.route(route="healthz", auth_level=func.AuthLevel.ANONYMOUS)
def heartbeat(req: func.HttpRequest) -> func.HttpResponse:
    now_utc = _utc_now_iso()
    body = json.dumps(
        {
            "status": "ok",
            "time": now_utc,
            "service": "RunbookTest",
        },
        ensure_ascii=False,
    )
    return func.HttpResponse(
        body,
        status_code=200,
        mimetype="application/json",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@app.route(route="processes", auth_level=func.AuthLevel.FUNCTION)
def list_processes(req: func.HttpRequest) -> func.HttpResponse:
    """
    Lists the "in progress" runs of the RunbookTest endpoint (jobs not yet completed).
    Parameters:
    - q: text filter on exec_id, id, name, runbook (optional)

    Example:
    - GET /api/processes — returns only the “running” runs of RunbookTest on this instance
    - GET /api/processes?q=python — Filter by text on exec_id, id, name, runbook

    """
    q = (req.params.get("q") or "").lower().strip()
    with _ACTIVE_LOCK:
        items = list(_ACTIVE_RUNS.values())

    if q:

        def match(item: dict) -> bool:
            return any(
                (str(item.get(k) or "").lower().find(q) != -1)
                for k in ("exec_id", "id", "name", "runbook")
            )

        items = [i for i in items if match(i)]

    # Order by startedAt desc
    items.sort(key=lambda x: x.get("startedAt") or "", reverse=True)

    body = json.dumps(
        {
            "status": "ok",
            "time": _utc_now_iso(),
            "count": len(items),
            "runs": items,
        },
        ensure_ascii=False,
    )
    return func.HttpResponse(
        body,
        status_code=200,
        mimetype="application/json",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )
