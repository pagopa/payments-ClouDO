import base64
import json
import logging
import os
import shlex
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional
from zoneinfo import ZoneInfo

import azure.functions as func
import requests

# =========================
# Constants and Utilities
# =========================

# Configuration constants
RECEIVER_URL = os.environ.get("RECEIVER_URL", "http://localhost:7071/api/Receiver")
QUEUE_NAME = os.environ.get("QUEUE_NAME", "runbooktest-work")
STORAGE_CONNECTION = "AzureWebJobsStorage"

# GitHub fallback configuration
GITHUB_REPO = os.environ.get("GITHUB_REPO", "pagopa/payments-cloudo")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_PATH_PREFIX = os.environ.get("GITHUB_PATH_PREFIX", "src/runbooks")

if os.getenv("FEATURE_DEV", "false").lower() != "true":
    AUTH = func.AuthLevel.FUNCTION
else:
    AUTH = func.AuthLevel.ANONYMOUS


app = func.FunctionApp()

# In-memory registry of ongoing executions (per instance)
_ACTIVE_RUNS = {}
_ACTIVE_LOCK = Lock()


def _utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO 8601 format without microseconds."""
    return (
        datetime.now(timezone.utc)
        .astimezone(ZoneInfo("Europe/Rome"))
        .replace(microsecond=0)
        .isoformat()
    )


def _format_requested_at() -> str:
    # Human-readable UTC timestamp for logs (e.g., 2025-09-15 12:34:56)
    return (
        datetime.now(timezone.utc)
        .astimezone(ZoneInfo("Europe/Rome"))
        .strftime("%Y-%m-%d %H:%M:%S")
    )


def encode_logs(value: str | None) -> bytes:
    """
    Encode a string value to base64 bytes.
    If value is None or empty, returns empty bytes.
    """
    if not value:
        return b""
    return base64.b64encode(value.encode("utf-8"))


def _build_status_headers(payload: dict, status: str, log_message: str) -> dict:
    """Build headers for the Receiver call from payload and execution status."""
    return {
        "runbook": payload.get("runbook"),
        "run_args": payload.get("run_args"),
        "Id": payload.get("id"),
        "Name": payload.get("name"),
        "ExecId": payload.get("exec_id"),
        "Content-Type": "application/json",
        "Status": status,
        "Log": encode_logs(log_message),
        "OnCall": payload.get("oncall"),
        "MonitorCondition": payload.get("monitor_condition"),
        "Severity": payload.get("severity"),
    }


def _post_status(payload: dict, status: str, log_message: str) -> requests.Response:
    """Send execution status to the Receiver and return the HTTP response."""
    headers = _build_status_headers(payload, status, log_message)
    try:
        return requests.post(RECEIVER_URL, headers=headers, timeout=10)
    except requests.RequestException as err:
        logging.error(
            f"[{payload.get('id')}] Failed to send status to Receiver: %s", err
        )
        raise


def _github_auth_headers() -> list[dict]:
    """
    Build alternative auth headers for GitHub:
    - Prefer Bearer (fine-grained tokens)
    - Fallback to 'token' (classic PAT)
    Always include User-Agent and Accept.
    """
    base = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "azure-func-runbook/1.0",
    }
    headers_list: list[dict] = [base.copy()]
    if GITHUB_TOKEN:
        # Try Bearer first
        h1 = base.copy()
        h1["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        headers_list.insert(0, h1)
        # Then classic 'token' scheme
        h2 = base.copy()
        h2["Authorization"] = f"token {GITHUB_TOKEN}"
        headers_list.append(h2)
    return headers_list


def _download_from_github(script_name: str) -> str:
    """
    Download a script from GitHub using the Contents API with proper auth.
    Tries both Bearer and 'token' schemes and falls back to raw download.
    Returns the local temporary file path.
    """
    owner_repo = (GITHUB_REPO or "").strip()
    if not owner_repo or "/" not in owner_repo:
        raise RuntimeError(
            "GITHUB_REPO must be set as 'owner/repo' (e.g., 'pagopa/payments-cloudo')"
        )
    branch = (GITHUB_BRANCH or "main").strip()
    prefix = (GITHUB_PATH_PREFIX or "").strip().strip("/")

    path_parts = [p for p in [prefix, script_name] if p]
    repo_path = "/".join(path_parts)

    api_url = f"https://api.github.com/repos/{owner_repo}/contents/{repo_path}"
    params = {"ref": branch}

    last_resp = None
    data = None

    # Try Contents API with multiple auth headers
    for headers in _github_auth_headers():
        try:
            resp = requests.get(api_url, headers=headers, params=params, timeout=30)
            last_resp = resp
            logging.info("GitHub GET %s -> %s", resp.url, resp.status_code)
            if resp.status_code == 200:
                data = resp.json()
                break
            # If unauthorized/forbidden, try next header variant
            if resp.status_code in (401, 403):
                continue
            # For 404, don't immediately fail; we will also try raw fallback below
        except requests.RequestException as e:
            logging.warning("GitHub request error: %s", e)
            continue

    content_bytes: bytes | None = None
    if (
        isinstance(data, dict)
        and data.get("encoding") == "base64"
        and "content" in data
    ):
        try:
            b64 = data["content"].replace("\n", "")
            content_bytes = base64.b64decode(b64)
        except Exception as e:
            raise RuntimeError(f"Failed to decode GitHub content: {e}") from e

    if content_bytes is None:
        # Raw fallback: https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}
        raw_url = f"https://raw.githubusercontent.com/{owner_repo}/{branch}/{repo_path}"
        raw_ok = False
        for headers in _github_auth_headers():
            # Raw supports same auth headers
            try:
                raw_resp = requests.get(raw_url, headers=headers, timeout=30)
                logging.info("GitHub RAW %s -> %s", raw_url, raw_resp.status_code)
                if raw_resp.status_code == 200:
                    content_bytes = raw_resp.content
                    raw_ok = True
                    break
                if raw_resp.status_code in (401, 403):
                    continue
            except requests.RequestException as e:
                logging.warning("GitHub raw request error: %s", e)
                continue

        if not raw_ok:
            # Build meaningful error based on last response
            status = getattr(last_resp, "status_code", "n/a")
            url = getattr(last_resp, "url", api_url)
            raise FileNotFoundError(
                f"GitHub file not found or not accessible: {owner_repo}/{repo_path}@{branch} "
                f"(last status={status}, url={url}). "
                "Check token scopes (repo or fine-grained: Contents Read, Metadata Read) and SSO authorization."
            )

    suffix = ".py" if script_name.lower().endswith(".py") else ""
    fd, tmp_path = tempfile.mkstemp(prefix="runbook_", suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(content_bytes)

    try:
        st = os.stat(tmp_path)
        os.chmod(tmp_path, st.st_mode | stat.S_IEXEC)
    except Exception:
        pass

    return tmp_path


def _clean_path(p: str | None) -> str | None:
    if p is None:
        return None
    s = str(p).strip().strip('"').strip("'")
    if not s:
        return None
    s = os.path.expanduser(s)
    s = os.path.normpath(s)
    return s


def _run_aks_login(aks_resource_info: dict | str) -> None:
    """
    Runs the local AKS login script:
      src/core/worker/utils/aks-login.sh <rg> <name> <namespace>
    Accepts aks_resource_info as dict or JSON string.
    """
    if isinstance(aks_resource_info, str):
        try:
            aks_resource_info = json.loads(aks_resource_info)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"aks_resource_info is not valid JSON: {e}") from e
    if not isinstance(aks_resource_info, dict):
        raise RuntimeError("aks_resource_info must be a dict")

    rg = (aks_resource_info.get("aks_rg") or "").strip()
    name = (aks_resource_info.get("aks_name") or "").strip()
    ns = (aks_resource_info.get("aks_namespace") or "").strip()

    if not rg or not name:
        raise RuntimeError(
            "aks_resource_info requires non-empty 'aks_rg' and 'aks_name'"
        )

    script_path = os.path.normpath("utils/aks-login.sh")
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"AKS login script not found: {script_path}")

    cmd = [script_path, rg, name, ns] if ns else [script_path, rg, name]
    logging.info("Running AKS login: %s", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"AKS login failed: {e.stderr.strip() or e.stdout.strip()}"
        ) from e


def _run_script(
    script_name: str,
    run_args: Optional[str],
    script_path: str | None = None,
    aks_resource_info: dict | None = None,
    monitor_condition: Optional[str] = "",
) -> subprocess.CompletedProcess:
    """Run the requested script fetching it from Blob Storage, falling back to local folder, then GitHub."""
    tmp_path: str | None = None
    github_tmp_path: str | None = None
    github_error: Exception | None = None

    # Setting MONITOR_CONDITION env VAR
    os.environ["MONITOR_CONDITION"] = monitor_condition

    try:

        def normalize_aks_info(val) -> dict[str, Any]:
            if isinstance(val, dict):
                return val
            if isinstance(val, str):
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    logging.warning("AKS info string non JSON: %r", val)
            return {}

        def to_str(x) -> str:
            return "" if x is None else str(x)

        aks_info = normalize_aks_info(aks_resource_info)
        logging.info(f"AKS info: {aks_info}")

        os.environ["AKS_NAME"] = to_str(aks_info.get("aks_name"))
        os.environ["AKS_RG"] = to_str(aks_info.get("aks_rg"))
        os.environ["AKS_ID"] = to_str(aks_info.get("aks_id"))
        os.environ["AKS_NAMESPACE"] = to_str(aks_info.get("aks_namespace"))
        os.environ["AKS_POD"] = to_str(aks_info.get("aks_pod"))
        os.environ["AKS_DEPLOYMENT"] = to_str(aks_info.get("aks_deployment"))
        os.environ["AKS_JOB"] = to_str(aks_info.get("aks_job"))
    except Exception as e:
        logging.warning("AKS set env failed: %s", e)

    # GitHub if not found locally
    if script_path is None:
        try:
            github_tmp_path = _download_from_github(script_name)
            logging.info("Downloaded script from GitHub: %s", github_tmp_path)
            script_path = github_tmp_path
        except Exception as e:
            github_error = e
    else:
        base = (_clean_path(script_path) or "").strip()
        name = _clean_path(script_name) or script_name
        if os.path.isabs(name):
            script_path = name
        else:
            script_path = os.path.join(base, name)

    if script_path is None or not os.path.exists(script_path):
        details = []
        if github_error:
            details.append(f"GitHub: {type(github_error).__name__}: {github_error}")
        raise FileNotFoundError(
            f"Script '{script_name}' not found. Checked GitHub. "
            f"Details: {' | '.join(details) if details else 'no extra details'}"
        )

    # Execute
    cmd = (
        [sys.executable, script_path]
        if script_path.lower().endswith(".py")
        else [script_path]
    )
    try:
        if run_args is not None:
            cmd = cmd + shlex.split(run_args)

        logging.info("Running script: %s", cmd)
        return subprocess.run(cmd, capture_output=True, text=True, check=True)
    finally:
        # Clean up only if paths are valid files
        for p in (tmp_path, github_tmp_path):
            try:
                if isinstance(p, str) and p and os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass


@app.route(route="Runbook", auth_level=AUTH)
@app.queue_output(
    arg_name="out_msg", queue_name=QUEUE_NAME, connection=STORAGE_CONNECTION
)
def runbook(req: func.HttpRequest, out_msg: func.Out[str]) -> func.HttpResponse:
    payload = {
        "requestedAt": _format_requested_at(),
        "id": req.headers.get("Id"),
        "name": req.headers.get("Name"),
        "runbook": req.headers.get("runbook"),
        "run_args": req.headers.get("run_args"),
        "exec_id": req.headers.get("ExecId"),
        "oncall": req.headers.get("OnCall"),
        "monitor_condition": req.headers.get("MonitorCondition"),
        "severity": req.headers.get("Severity"),
    }
    if "aks_resource_info" in req.headers:
        aks_info = req.headers.get("aks_resource_info")
        if aks_info is not None:
            payload["aks_resource_info"] = aks_info
    out_msg.set(json.dumps(payload, ensure_ascii=False))
    body = json.dumps(
        {"status": "accepted", "message": "processing scheduled"}, ensure_ascii=False
    )
    return func.HttpResponse(body, status_code=202, mimetype="application/json")


@app.queue_trigger(arg_name="msg", queue_name=QUEUE_NAME, connection=STORAGE_CONNECTION)
def process_runbook(msg: func.QueueMessage) -> None:
    payload = json.loads(msg.get_body().decode("utf-8"))
    logging.info(f"[{payload.get('id')}] Job started: %s", payload)

    started_at = _format_requested_at()
    exec_id = payload.get("exec_id") or ""

    # Check if this execution is already running
    with _ACTIVE_LOCK:
        items = list(_ACTIVE_RUNS.values())
        if any(item["id"] == payload.get("id") for item in items):
            log_msg = f"Execution {exec_id} already in progress, skipping"
            logging.info(f"[{payload.get('id')}] {log_msg}")
            _post_status(payload, status="skipped", log_message=log_msg)
            return

    # Register the execution as "in progress"
    with _ACTIVE_LOCK:
        _ACTIVE_RUNS[exec_id] = {
            "exec_id": exec_id,
            "id": payload.get("id"),
            "name": payload.get("name"),
            "runbook": payload.get("runbook"),
            "run_args": payload.get("run_args"),
            "requestedAt": payload.get("requestedAt"),
            "startedAt": started_at,
            "status": "running",
        }

    try:
        if payload.get("aks_resource_info"):
            try:
                _run_aks_login(payload["aks_resource_info"])
                logging.info(f"[{payload.get('id')}] AKS login completed successfully")
            except Exception as e:
                # Report error and stop processing
                err_msg = f"AKS login failed: {type(e).__name__}: {e}"
                _post_status(payload, status="error", log_message=err_msg)
                logging.error(f"[{payload.get('id')}] {err_msg}")
                return

        if os.getenv("DEV_SCRIPT_PATH"):
            script_path = os.getenv("DEV_SCRIPT_PATH", "/work/runbooks/")
        else:
            script_path = None

        result = _run_script(
            script_name=payload.get("runbook"),
            script_path=script_path,
            run_args=payload.get("run_args"),
            aks_resource_info=payload.get("aks_resource_info"),
            monitor_condition=payload.get("monitor_condition"),
        )
        log_msg = f"Script succeeded. stdout: {result.stdout.strip()}"
        logging.info(f"[{payload.get('id')}] {log_msg}")
        response = _post_status(payload, status="completed", log_message=log_msg)
        logging.info(
            f"[{payload.get('id')}] Receiver response: %s",
            getattr(response, "text", ""),
        )
    except subprocess.CalledProcessError as e:
        error_message = f"Script failed. returncode={e.returncode} stderr={e.stderr.strip()} stdout={e.stdout.strip()}"
        try:
            response = _post_status(payload, status="failed", log_message=error_message)
            logging.error(
                f"[{payload.get('id')}] Receiver response: %s",
                getattr(response, "text", ""),
            )
        finally:
            logging.error(f"[{payload.get('id')}] {error_message}")
    except Exception as e:
        err_msg = f"{type(e).__name__}: {str(e)}"
        try:
            response = _post_status(payload, status="error", log_message=err_msg)
            logging.error(
                f"[{payload.get('id')}] Receiver response: %s",
                getattr(response, "text", ""),
            )
        finally:
            logging.error(f"[{payload.get('id')}] Unexpected error: %s", err_msg)
    finally:
        # Remove from the registry: no longer "in progress"
        logging.info(
            "[%s] Job complete (requested at %s)",
            payload.get("exec_id"),
            payload.get("requestedAt"),
        )
        with _ACTIVE_LOCK:
            _ACTIVE_RUNS.pop(exec_id, None)


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


# =========================
# HTTPS: Running Process
# =========================


@app.route(route="processes", auth_level=AUTH)
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


# =========================
# DEV: Test runbook
# =========================


@app.route(route="dev/runScript", auth_level=AUTH)
def dev_run_script(req: func.HttpRequest) -> func.HttpResponse:
    """
    Development endpoint to test _run_script.
    Optionally enabled via FEATURE_DEV=true.
    Parameters:
      - name (or 'script') query string, or 'runbook' header with the file name.
    Response: JSON with stdout/stderr/returncode.
    """
    # Feature flag for test and develop of runbooks
    if os.getenv("FEATURE_DEV", "false").lower() != "true":
        return func.HttpResponse("Not found", status_code=404)
    elif os.getenv("DEV_SCRIPT_PATH"):
        script_path = os.getenv("DEV_SCRIPT_PATH", "/work/runbooks/")
    else:
        script_path = None

    logging.info(f"Running _run_script on {script_path}")
    script_name = (
        req.params.get("name")
        or req.params.get("script")
        or req.headers.get("runbook")
        or ""
    ).strip()
    run_args = req.headers.get("run_args") or None
    if not script_name:
        return func.HttpResponse(
            json.dumps(
                {"error": "missing script name (use ?name= or header runbook)"},
                ensure_ascii=False,
            ),
            status_code=400,
            mimetype="application/json",
        )

    try:
        result = _run_script(
            script_name=script_name, script_path=script_path, run_args=run_args
        )
        body = json.dumps(
            {
                "status": "ok",
                "script": script_name,
                "run_args": run_args,
                "returncode": result.returncode,
                "stdout": (result.stdout or "").strip(),
                "stderr": (result.stderr or "").strip(),
            },
            ensure_ascii=False,
        )
        return func.HttpResponse(body, status_code=200, mimetype="application/json")
    except subprocess.CalledProcessError as e:
        body = json.dumps(
            {
                "status": "failed",
                "script": script_name,
                "run_args": run_args,
                "returncode": e.returncode,
                "stdout": (e.stdout or "").strip(),
                "stderr": (e.stderr or "").strip(),
            },
            ensure_ascii=False,
        )
        return func.HttpResponse(body, status_code=500, mimetype="application/json")
    except Exception as e:
        body = json.dumps(
            {
                "status": "error",
                "script": script_name,
                "error": f"{type(e).__name__}: {str(e)}",
            },
            ensure_ascii=False,
        )
        return func.HttpResponse(body, status_code=500, mimetype="application/json")
