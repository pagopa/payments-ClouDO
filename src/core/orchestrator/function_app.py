import base64
import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import azure.functions as func
import utils
from escalation import send_opsgenie_alert, send_slack_execution
from requests import request

app = func.FunctionApp()


# =========================
# Constants and Utilities
# =========================

# Centralize configuration strings to avoid "magic strings"
TABLE_NAME = "RunbookLogs"
TABLE_SCHEMAS = "RunbookSchemas"
STORAGE_CONN = "AzureWebJobsStorage"
MAX_TABLE_CHARS = int(os.getenv("MAX_TABLE_LOG_CHARS", "32000"))

if os.getenv("FEATURE_DEV", "false").lower() != "true":
    AUTH = func.AuthLevel.FUNCTION
else:
    AUTH = func.AuthLevel.ANONYMOUS


def format_requested_at() -> str:
    # Human-readable UTC timestamp for logs (e.g., 2025-09-15 12:34:56)
    return (
        datetime.now(timezone.utc)
        .astimezone(ZoneInfo("Europe/Rome"))
        .strftime("%Y-%m-%d %H:%M:%S")
    )


def today_partition_key() -> str:
    # Compact UTC date used as PartitionKey (e.g., 20250915)
    return (
        datetime.now(timezone.utc)
        .astimezone(ZoneInfo("Europe/Rome"))
        .strftime("%Y%m%d")
    )


def utc_now_iso() -> str:
    # ISO-like UTC timestamp used in health endpoint
    return (
        datetime.now(timezone.utc)
        .astimezone(ZoneInfo("Europe/Rome"))
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def utc_now_iso_seconds() -> str:
    # Generate a UTC timestamp in ISO 8601 format with seconds precision
    return (
        datetime.now(timezone.utc)
        .astimezone(ZoneInfo("Europe/Rome"))
        .isoformat(timespec="seconds")
    )


def utc_partition_key() -> str:
    # Generate a compact UTC date for PartitionKey (e.g., 20250915)
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _truncate_for_table(s: str | None, max_chars: int) -> str:
    if not s:
        return "", False
    return (s) if len(s) <= max_chars else (s[:max_chars])


def decode_base64(data: str) -> str:
    """Decode base64 encoded string to utf-8 string"""
    try:
        return base64.b64decode(data).decode("utf-8")
    except Exception as e:
        logging.warning(f"Failed to decode base64 encoded string: {e}")
        return data


def get_header(
    req: func.HttpRequest, name: str, default: Optional[str] = None
) -> Optional[str]:
    # Safely read a header value with a default fallback
    return req.headers.get(name, default)


def resolve_status(header_status: Optional[str]) -> str:
    # Map incoming header status to a canonical label for logs
    normalized = (header_status or "").strip().lower()
    return "succeeded" if normalized == "completed" else normalized


def resolve_caller_url(req: func.HttpRequest) -> str:
    raw = (
        get_header(req, "X-Caller-Url")
        or get_header(req, "Referer")
        or get_header(req, "Origin")
        or req.url
    )
    parts = urlsplit(raw)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _strip_after_api(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path or ""
    idx = path.lower().find("/api")
    new_path = path[:idx] if idx != -1 else path
    if new_path in ("", "/"):
        new_path = ""
    return urlunsplit((parts.scheme, parts.netloc, new_path, "", ""))


def safe_json(response) -> dict | str | None:
    # Safely parse response body, falling back to text or None
    try:
        return response.json()
    except Exception:
        try:
            return response.text
        except Exception:
            return None


def build_headers(
    schema: "Schema",
    exec_id: str,
    aks_resource_info: dict | None,
    monitor_condition: str | None,
    severity: str | None,
) -> dict:
    # Standardize request headers sent to the downstream runbook endpoint
    headers = {
        "runbook": f"{schema.runbook}",
        "run_args": f"{schema.run_args}",
        "Id": schema.id,
        "Name": schema.name or "",
        "ExecId": exec_id,
        "OnCall": schema.oncall,
        "Content-Type": "application/json",
        "MonitorCondition": monitor_condition,
        "Severity": severity,
    }
    if aks_resource_info is not None:
        headers["aks_resource_info"] = json.dumps(aks_resource_info, ensure_ascii=False)
    return headers


def build_response_body(
    status_code: int,
    schema: "Schema",
    partition_key: str,
    exec_id: str,
    api_json: dict | str | None,
) -> str:
    # Build the HTTP response payload returned by this function
    return json.dumps(
        {
            "status": status_code,
            "schema": {
                "id": schema.id,
                "name": schema.name,
                "description": schema.description,
                "url": schema.url,
                "oncall": schema.oncall,
                "runbook": schema.runbook,
                "run_args": schema.run_args,
            },
            "response": api_json,
            "log": {"partitionKey": partition_key, "exec_id": exec_id},
        },
        ensure_ascii=False,
    )


def build_log_entry(
    *,
    status: str,
    partition_key: str,
    row_key: str,
    exec_id: Optional[str],
    requested_at: str,
    name: Optional[str],
    schema_id: Optional[str],
    url: Optional[str],
    runbook: Optional[str],
    run_args: Optional[str],
    log_msg: Optional[str],
    oncall: Optional[str],
    monitor_condition: Optional[str],
    severity: Optional[str],
) -> dict[str, Any]:
    # Build a normalized log entity for Azure Table Storage
    return {
        "PartitionKey": partition_key,
        "RowKey": row_key,
        "ExecId": exec_id,
        "Status": status,
        "RequestedAt": requested_at,
        "Name": name,
        "Id": schema_id,
        "Url": url,
        "Runbook": runbook,
        "Run_Args": run_args,
        "Log": log_msg,
        "OnCall": oncall,
        "MonitorCondition": monitor_condition,
        "Severity": severity,
    }


# =========================
# Schema Model
# =========================


@dataclass
class Schema:
    id: str
    entity: Optional[dict] = None
    name: str | None = None
    description: str | None = None
    url: str | None = None
    runbook: str | None = None
    run_args: str | None = None
    oncall: str | None = "false"
    monitor_condition: str | None = None
    severity: str | None = None

    def __post_init__(self):
        if not self.id or not isinstance(self.id, str):
            raise ValueError("Schema id must be a non-empty str")

        if not self.entity:
            raise ValueError(
                "Entity not provided: use table input binding to inject the table entity"
            )

        e = self.entity
        self.name = (e.get("name") or "").strip()
        self.description = (e.get("description") or "").strip() or None
        self.url = (e.get("url") or "").strip() or None
        self.runbook = (e.get("runbook") or "").strip() or None
        self.run_args = (e.get("run_args") or "").strip() or ""
        self.oncall = (
            str(e.get("oncall", e.get("oncall", "false"))).strip().lower() or "false"
        )


# =========================
# HTTP Function: Trigger
# =========================


@app.route(route="Trigger", auth_level=AUTH)
@app.table_output(
    arg_name="log_table",
    table_name=TABLE_NAME,
    connection=STORAGE_CONN,
)
@app.table_input(
    arg_name="entities",
    table_name=TABLE_SCHEMAS,
    connection=STORAGE_CONN,
)
def Trigger(
    req: func.HttpRequest, log_table: func.Out[str], entities: str
) -> func.HttpResponse:
    # Init payload variables to None
    resource_name = resource_group = resource_id = schema_id = monitor_condition = (
        severity
    ) = ""

    # Pre-compute logging fields
    requested_at = format_requested_at()
    partition_key = today_partition_key()
    exec_id = str(uuid.uuid4())

    # Resolve schema_id from route first; fallback to query/body (alertId/schemaId)
    if (req.params.get("id")) is not None:
        schema_id = utils.extract_schema_id_from_req(req)
        aks_resource_info = None
    else:
        (
            resource_name,
            resource_group,
            resource_id,
            schema_id,
            namespace,
            pod,
            deployment,
            job,
            monitor_condition,
            severity,
        ) = utils.parse_resource_fields(req).values()
        aks_resource_info = (
            {
                "aks_name": resource_name,
                "aks_rg": resource_group,
                "aks_id": resource_id,
                "aks_namespace": namespace,
                "aks_pod": pod,
                "aks_deployment": deployment,
                "aks_job": job,
            }
            if resource_name
            else None
        )
        logging.info(f"[{exec_id}] Resource info: %s", aks_resource_info)

    if not schema_id:
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Unable to resolve schema_id (missing route id and alertId/schemaId in request body)"
                },
                ensure_ascii=False,
            ),
            status_code=400,
            mimetype="application/json",
        )

    # Parse bound table entities (binding returns a JSON array)
    try:
        parsed = json.loads(entities) if isinstance(entities, str) else entities
    except Exception:
        parsed = None

    if not isinstance(parsed, list):
        return func.HttpResponse(
            json.dumps({"error": "Unexpected table result format"}, ensure_ascii=False),
            status_code=500,
            mimetype="application/json",
        )

    # Apply optional filter in code (case-insensitive fallback on 'Id'/'id')
    def get_id(e: dict) -> str:
        return str(e.get("Id") or e.get("id") or "").strip()

    schema_entity = next((e for e in parsed if get_id(e) in schema_id), None)

    if not schema_entity:
        return func.HttpResponse(
            json.dumps(
                {"error": f"Schema with Id '{schema_id}' not found in {TABLE_SCHEMAS}"},
                ensure_ascii=False,
            ),
            status_code=404,
            mimetype="application/json",
        )
    logging.info(f"[{exec_id}] Getting schema entity id '{schema_id}'")
    logging.info(f"[{exec_id}] Getting schema entity id '{schema_entity}'")
    # Build domain model
    schema = Schema(
        id=schema_entity.get("id"),
        entity=schema_entity,
        monitor_condition=monitor_condition,
        severity=severity,
    )
    logging.info(f"[{exec_id}] Set schema: '{schema}'")
    try:
        # Call downstream runbook endpoint
        response = request(
            "POST",
            schema.url,
            headers=build_headers(
                schema, exec_id, aks_resource_info, monitor_condition, severity
            ),
        )
        api_body = safe_json(response)

        # Status label for logs
        status_label = "accepted" if response.status_code == 202 else "error"

        # Write log entry to the table
        start_log = build_log_entry(
            status=status_label,
            partition_key=partition_key,
            exec_id=exec_id,
            row_key=exec_id,
            requested_at=requested_at,
            name=schema.name or "",
            schema_id=schema.id,
            url=schema.url,
            runbook=schema.runbook,
            run_args=schema.run_args,
            log_msg=api_body,
            oncall=schema.oncall,
            monitor_condition=monitor_condition,
            severity=severity,
        )
        log_table.set(json.dumps(start_log, ensure_ascii=False))

        # Return HTTP response mirroring downstream status
        response_body = build_response_body(
            status_code=response.status_code,
            schema=schema,
            partition_key=partition_key,
            exec_id=exec_id,
            api_json=api_body,
        )
        return func.HttpResponse(
            response_body,
            status_code=response.status_code,
            mimetype="application/json",
        )
    except Exception as e:
        # Build error response
        response_body = build_response_body(
            status_code=500,
            schema=schema,
            partition_key=partition_key,
            exec_id=exec_id,
            api_json={"error": str(e)},
        )

        # Log error to table
        error_log = build_log_entry(
            status="error",
            partition_key=partition_key,
            exec_id=exec_id,
            row_key=exec_id,
            requested_at=requested_at,
            name=schema.name or "",
            schema_id=schema.id,
            url=schema.url,
            runbook=schema.runbook,
            run_args=schema.run_args,
            log_msg=str(e),
            oncall=schema.oncall,
            monitor_condition=monitor_condition,
            severity=severity,
        )
        log_table.set(json.dumps(error_log, ensure_ascii=False))

        return func.HttpResponse(
            response_body,
            status_code=500,
            mimetype="application/json",
        )


# =========================
# HTTP Function: receiver
# =========================


@app.route(route="Receiver", auth_level=AUTH)
@app.table_output(
    arg_name="log_table",
    table_name=TABLE_NAME,
    connection=STORAGE_CONN,
)
def Receiver(req: func.HttpRequest, log_table: func.Out[str]) -> func.HttpResponse:
    # Validate required headers
    required_headers = ["ExecId", "Status", "Name", "Id", "runbook"]
    missing_headers = [h for h in required_headers if not get_header(req, h)]
    if missing_headers:
        return func.HttpResponse(
            json.dumps(
                {"error": f"Missing required headers: {missing_headers}"},
                ensure_ascii=False,
            ),
            status_code=400,
            mimetype="application/json",
        )

    # Log only relevant and serializable headers for observability
    logging.info(
        f"[{get_header(req, 'ExecId')}] Receiver invoked",
        extra={
            "headers": {
                "ExecId": get_header(req, "ExecId"),
                "Status": get_header(req, "Status"),
                "Name": get_header(req, "Name"),
                "Id": get_header(req, "Id"),
                "Runbook": get_header(req, "runbook"),
                "Run_Args": get_header(req, "run_args"),
                "OnCall": get_header(req, "OnCall"),
                "MonitorCondition": get_header(req, "MonitorCondition"),
                "Severity": get_header(req, "Severity"),
            }
        },
    )

    # Precompute keys and timestamps for log
    requested_at = format_requested_at()
    partition_key = today_partition_key()
    row_key = str(uuid.uuid4())  # stable hex representation for RowKey
    request_origin_url = resolve_caller_url(req)
    status_label = resolve_status(get_header(req, "Status"))

    # Build and write the log entity
    log_entity = build_log_entry(
        status=status_label,
        partition_key=partition_key,
        row_key=row_key,
        exec_id=get_header(req, "ExecId"),
        requested_at=requested_at,
        name=get_header(req, "Name"),
        schema_id=get_header(req, "Id"),
        url=request_origin_url,
        runbook=get_header(req, "runbook"),
        run_args=get_header(req, "run_args"),
        log_msg=_truncate_for_table(decode_base64(req.get_body()), MAX_TABLE_CHARS),
        oncall=get_header(req, "OnCall"),
        monitor_condition=get_header(req, "MonitorCondition"),
        severity=get_header(req, "Severity"),
    )
    log_table.set(json.dumps(log_entity, ensure_ascii=False))

    if status_label == "running":
        return func.HttpResponse(
            json.dumps({"message": "Annotation completed"}, ensure_ascii=False),
            status_code=200,
            mimetype="application/json",
        )
    slack_bot_token = (os.environ.get("SLACK_TOKEN") or "").strip()
    slack_channel = (os.environ.get("SLACK_CHANNEL") or "#cloudo-test").strip()
    if slack_bot_token:
        try:
            status_emoji = "✅" if status_label == "succeeded" else "❌"
            send_slack_execution(
                token=slack_bot_token,
                channel=slack_channel,
                message=f"[{get_header(req, 'ExecId')}] Status: {status_label}: {get_header(req, 'Name')}",
                blocks=[
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"Worker Notification {status_emoji}",
                            "emoji": True,
                        },
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Name:*\n{get_header(req, 'Name')}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Id:*\n{get_header(req, 'Id')}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*ExecId:*\n{get_header(req, 'ExecId')}",
                            },
                            {"type": "mrkdwn", "text": f"*Status:*\n{status_label}"},
                            {
                                "type": "mrkdwn",
                                "text": f"*Severity:*\n{get_header(req, 'Severity')}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*OnCall:*\n{get_header(req, 'OnCall')}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*MonitorCondition:*\n{get_header(req, 'MonitorCondition')}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Origin*:\n{request_origin_url}",
                            },
                        ],
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Runbook:*\n{get_header(req, 'Runbook')}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*MonitorCondition:*\n{get_header(req, 'MonitorCondition')}",
                            },
                        ],
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Run Args:*\n```{get_header(req, 'run_args')}```",
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Logs (truncated):*\n```{decode_base64(req.get_body())[:1500]}```",
                        },
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Severity:* {get_header(req, 'Severity')}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"Timestamp: <!date^{int(__import__('time').time())}^{{date_short}} {{time}}|now>",
                            },
                        ],
                    },
                    {"type": "divider"},
                ],
            )
        except Exception as e:
            logging.error(
                f"[{get_header(req, 'ExecId')}] escalation to SLACK failed: {e}"
            )
            logging.error(f"status: escalation_failed: {str(e)}")

    if req.headers.get("OnCall") == "true" and status_label != "succeeded":
        opsgenie_api_key = (os.environ.get("OPSGENIE_API_KEY") or "").strip()
        if opsgenie_api_key:
            try:
                send_opsgenie_alert(
                    api_key=opsgenie_api_key,
                    message=f"[{get_header(req, 'Id')}] [{get_header(req, 'Severity')}] {get_header(req, 'Name')}",
                    priority=f"P{int(str(get_header(req, 'Severity')).strip().lower().replace('sev', '')) + 1}",
                    alias=get_header(req, "ExecId"),
                    details={
                        "Name": get_header(req, "Name"),
                        "Id": get_header(req, "Id"),
                        "ExecId": get_header(req, "ExecId"),
                        "Status": get_header(req, "Status"),
                        "Runbook": get_header(req, "runbook"),
                        "Run_Args": get_header(req, "run_args"),
                        "OnCall": get_header(req, "OnCall"),
                        "MonitorCondition": get_header(req, "MonitorCondition"),
                        "Severity": get_header(req, "Severity"),
                    },
                    description=f"Execution failed for {get_header(req, 'ExecId')}:\n\n{_truncate_for_table(decode_base64(req.get_body()), MAX_TABLE_CHARS or '')}",
                )
            except Exception as e:
                logging.error(
                    f"[{get_header(req, 'ExecId')}] escalation to OPSGENIE failed: {e}"
                )
                logging.error(f"status: escalation_failed: {str(e)}")

        else:
            logging.warning("OPSGENIE API key not set")
        # Return a coherent JSON response
        return func.HttpResponse(
            json.dumps({"message": "Chiamo il reperibile!"}, ensure_ascii=False),
            status_code=200,
            mimetype="application/json",
        )
    else:
        # Return a coherent JSON response
        return func.HttpResponse(
            json.dumps({"message": "Received Boss!"}, ensure_ascii=False),
            status_code=200,
            mimetype="application/json",
        )


# =========================
# Heartbeat
# =========================


@app.route(route="healthz", auth_level=AUTH)
def heartbeat(req: func.HttpRequest) -> func.HttpResponse:
    now_utc = utc_now_iso()
    body = json.dumps(
        {
            "status": "ok",
            "time": now_utc,
            "service": "Trigger",
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
# Table Storage READ (input binding)
# =========================


@app.route(route="logs/{partitionKey}/{execId}", auth_level=AUTH)
@app.table_input(
    arg_name="log_entity",
    table_name="RunbookLogs",
    partition_key="{partitionKey}",
    filter="ExecId eq '{execId}'",
    connection="AzureWebJobsStorage",
)
def get_log(req: func.HttpRequest, log_entity: str) -> func.HttpResponse:
    """
    Returns the entity from the RunbookLogs table identified by PartitionKey and RowKey..
    Uso: GET /api/logs/{partitionKey}/{execId}
    """
    # If the entity does not exist, the binding returns None/empty.
    if not log_entity:
        return func.HttpResponse(
            json.dumps({"error": "Entity not found"}, ensure_ascii=False),
            status_code=404,
            mimetype="application/json",
        )

    # log_entity is a JSON string of the complete entity
    return func.HttpResponse(
        log_entity,
        status_code=200,
        mimetype="application/json",
    )


# =========================
# HTTP Function: Logs UI
# =========================


@app.route(route="logs", auth_level=AUTH)
# fmt: off
# ruff: noqa
def logs_frontend(req: func.HttpRequest) -> func.HttpResponse:
    key = req.headers.get("x-functions-key") or req.params.get("code")
    if not key:
        logging.warning("Missing key")
    func_key = key
    code_js = json.dumps(func_key or "")

    html: str = f"""
<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="utf-8"/>
  <title>ClouDO Log</title>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <style>
    :root{{--bg:#f9fafb;--fg:#111827;--muted:#6b7280;--card:#fff;--border:#e5e7eb;--primary:#2563eb}}
    body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:2rem;color:var(--fg);background:var(--bg)}}
    .box{{max-width:1200px;margin:auto;background:var(--card);border:1px solid var(--border);border-radius:12px;padding:24px;box-shadow:0 1px 2px rgba(0,0,0,.04)}}
    h1{{margin-top:0}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}}
    label{{font-size:.85rem;color:var(--muted);display:block;margin-bottom:4px}}
    input,select{{width:100%;padding:8px 10px;border:1px solid var(--border);border-radius:8px;background:#fff}}
    .row{{display:flex;gap:8px;flex-wrap:wrap;align-items:end;margin-top:8px}}
    button{{padding:8px 12px;border:1px solid var(--border);border-radius:8px;background:#fff;cursor:pointer}}
    button.primary{{background:var(--primary);color:#fff;border-color:var(--primary)}}
    table{{width:100%;border-collapse:collapse;margin-top:16px}}
    th,td{{border-bottom:1px solid var(--border);padding:8px 6px;text-align:left;vertical-align:top}}
    th.sticky{{position:sticky;top:0;background:#fff;z-index:1}}
    .muted{{color:var(--muted)}}
    .badge{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:.75rem;border:1px solid var(--border)}}
    .ok{{background:#ecfdf5;color:#15803d;border-color:#bbf7d0}}
    .warn{{background:#fffbeb;color:#b45309;border-color:#fde68a}}
    .err{{background:#fef2f2;color:#b91c1c;border-color:#fecaca}}
    .info{{background:#e6f0ff;color:#1e40af;border-color:#bfdbfe}}
    details>summary{{cursor:pointer;user-select:none;font-weight:600;margin:12px 0}}
    pre{{background:#0b1220;color:#eef2ff;padding:12px;border-radius:10px;overflow:auto}}
    .nowrap{{white-space:nowrap}}
    .modal{{position:fixed;inset:0;background:rgba(0,0,0,.5);display:none;align-items:center;justify-content:center;z-index:1000}}
    .modal-content{{background:#fff;max-width:80vw;max-height:80vh;overflow:auto;padding:16px;border-radius:8px;box-shadow:0 10px 30px rgba(0,0,0,.2)}}
    .close{{float:right;border:0;background:transparent;font-size:1.5rem;cursor:pointer;line-height:1}}
    .btn{{padding:6px 10px;border:1px solid var(--border,#ddd);background:#f7f7f7;border-radius:6px;cursor:pointer}}
    .btn:hover{{background:#eee}}
    #logModal{{position:fixed;inset:0;background:rgba(0,0,0,.5);display:none;align-items:center;justify-content:center;z-index:1000}}
    #logModal .modal-content{{background:#fff;max-width:80vw;width:80vw;max-height:80vh;overflow:auto;padding:16px;border-radius:8px;box-shadow:0 10px 30px rgba(0,0,0,.2)}}
    #logContent{{white-space:pre-wrap;margin:0;font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace}}
  </style>
</head>
<body>
  <div class="box">
    <h1>ClouDO Log</h1>
    <p class="muted">Interroga la tabella RunbookLogs. Suggerimento: PartitionKey tipicamente è la data YYYYMMDD.</p>
    <div class="grid">
      <div>
        <label for="partitionKey">PartitionKey</label>
        <input id="partitionKey" placeholder="es. 20251001"/>
      </div>
      <div>
        <label for="execId">ExecId</label>
        <input id="execId" placeholder="UUID esatto (opzionale)"/>
      </div>
      <div>
        <label for="status">Status</label>
        <select id="status">
          <option value="">All</option>
          <option value="accepted">accepted</option>
          <option value="succeeded">succeeded</option>
          <option value="running">running</option>
          <option value="failed">failed</option>
          <option value="error">error</option>
        </select>
      </div>
      <div>
        <label for="q">Testo (Name/Id/Runbook/Url/Log)</label>
        <input id="q" placeholder="contains... (case-insensitive)"/>
      </div>
      <div>
        <label for="from">Da (RequestedAt)</label>
        <input id="from" type="datetime-local"/>
      </div>
      <div>
        <label for="to">A (RequestedAt)</label>
        <input id="to" type="datetime-local"/>
      </div>
      <div>
        <label for="limit">Limite</label>
        <input id="limit" type="number" min="1" max="5000" value="200"/>
      </div>
      <div>
        <label for="order">Ordine</label>
        <select id="order">
          <option value="desc">RequestedAt desc</option>
          <option value="asc">RequestedAt asc</option>
        </select>
      </div>
    </div>
    <div class="row">
        <button id="run" class="primary">
          <span style="display:inline-block;width:0;height:0;border-left:8px solid currentColor;
            border-top:6px solid transparent;border-bottom:6px solid transparent;margin-right:6px;
            vertical-align:middle;">
          </span>
          Run
        </button>
        <button id="clear">Reset</button>
      <span id="info" class="muted" aria-live="polite"></span>
    </div>
    <div id="logModal" class="modal" style="display:none;">
      <div class="modal-content">
        <button class="close" onclick="closeLogModal()" aria-label="Chiudi">&times;</button>
        <pre id="logContent" style="white-space:pre-wrap;margin:0;"></pre>
      </div>
    </div>
    <details open>
      <summary>Risultati</summary>
      <table id="tbl">
        <thead>
          <tr>
            <th class="sticky">RequestedAt</th>
            <th class="sticky">Status</th>
            <th class="sticky">ExecId</th>
            <th class="sticky">Name</th>
            <th class="sticky">Id</th>
            <th class="sticky">Runbook</th>
            <th class="sticky">Azioni</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
    </details>

    <details>
      <summary>JSON raw</summary>
      <pre id="raw"></pre>
    </details>
  </div>

  <script>
    const FUNCTION_QUERY_CODE = {code_js};
    const el = id => document.getElementById(id);
    function rowBadge(st){{
      let cls = 'badge';
      if (st==='succeeded') cls+=' ok';
      else if (st==='accepted') cls+=' warn';
      else if (st === 'running') cls+= ' info';
      else cls+=' err';
      return '<span class="'+cls+'">'+(st||'')+'</span>';
    }}
    function esc(s){{
      return (''+s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
    }}
    function openLogModal(btn){{
      // legacy no-op to keep backward compatibility if referenced elsewhere
      openTraceModal(btn);
    }}
    function openTraceModal(btn){{
      const url = btn.getAttribute('data-url');
      const modal = document.getElementById('logModal');
      const pre = document.getElementById('logContent');
      pre.textContent = 'Caricamento...';
      modal.style.setProperty('display','flex','important');
      fetch(url, {{ cache: 'no-store' }})
        .then(r => r.text())
        .then(txt => {{
          try {{
            const data = JSON.parse(txt);
            if (Array.isArray(data)) {{
              data.sort((a,b) => (b.RequestedAt || '').localeCompare(a.RequestedAt || ''));
              pre.textContent = JSON.stringify(data, null, 2);
            }} else {{
              pre.textContent = JSON.stringify(data, null, 2);
            }}
          }} catch(_){{
            pre.textContent = txt; // fallback se non è JSON valido
          }}
        }})
        .catch(err => {{ pre.textContent = 'Errore: ' + err.message; }});
    }}
    function openOnlyLogModal(btn){{
      const url = btn.getAttribute('data-url');
      const modal = document.getElementById('logModal');
      const pre = document.getElementById('logContent');
      pre.textContent = 'Caricamento...';
      modal.style.setProperty('display','flex','important');
      fetch(url, {{ cache: 'no-store' }})
        .then(r => r.text())
        .then(txt => {{
          try {{
            const data = JSON.parse(txt);
            const extractLog = (e) => (e && (e.Log ?? e.log ?? '')) || '';
            if (Array.isArray(data)) {{
              const logs = data
                .sort((a,b) => (b.RequestedAt || '').localeCompare(a.RequestedAt || ''))
                .map(e => extractLog(e))
                .filter(s => s && s.length > 0);
              pre.textContent = logs.length ? logs.join('\\n\\n---\\n\\n') : 'Nessun campo Log disponibile.';
            }} else {{
              const only = extractLog(data);
              pre.textContent = only ? only : 'Nessun campo Log disponibile.';
            }}
          }} catch(_){{
            // se non è JSON valido mostro il testo grezzo
            pre.textContent = txt;
          }}
        }})
        .catch(err => {{ pre.textContent = 'Errore: ' + err.message; }});
    }}
    function closeLogModal(){{ document.getElementById('logModal').style.display = 'none'; }}
    document.addEventListener('keydown', e => {{ if(e.key==='Escape') closeLogModal(); }});
    document.addEventListener('click', e => {{
      const m = document.getElementById('logModal');
      if (m.style.display !== 'none' && e.target === m) closeLogModal();
    }});

    function closeLogModal(){{
      const modal = document.getElementById('logModal');
      modal.style.display = 'none';
    }}

    // chiusura con ESC e click fuori
    document.addEventListener('keydown', (e) => {{
      if (e.key === 'Escape') closeLogModal();
    }});
    document.addEventListener('click', (e) => {{
      const modal = document.getElementById('logModal');
      if (modal.style.display !== 'none' && e.target === modal) closeLogModal();
    }});
    async function runQuery(){{
      const params = new URLSearchParams();
      const pk = el('partitionKey').value.trim();
      if (!pk) {{ alert('PartitionKey è obbligatorio'); return; }}
      params.set('partitionKey', pk);
      const execId = el('execId').value.trim(); if (execId) params.set('execId', execId);
      const status = el('status').value; if (status) params.set('status', status);
      const q = el('q').value.trim(); if (q) params.set('q', q);
      const f = el('from').value; if (f) params.set('from', f);
      const t = el('to').value; if (t) params.set('to', t);
      const limit = el('limit').value; if (limit) params.set('limit', limit);
      const order = el('order').value; if (order) params.set('order', order);
      if (FUNCTION_QUERY_CODE) params.set('code', FUNCTION_QUERY_CODE);

      el('info').textContent = 'Caricamento...';
      const url = '/api/logs/query?' + params.toString();
      const res = await fetch(url);
      const data = await res.json().catch(() => ({{ error: 'parse' }}));
      el('raw').textContent = JSON.stringify(data, null, 2);
      const tbody = el('tbl').querySelector('tbody');
      tbody.innerHTML = '';
      if (!res.ok) {{
        el('info').textContent = 'Errore: ' + ((data && data.error) || res.status);
        return;
      }}
      (data.items || []).forEach(item => {{
        const tr = document.createElement('tr');
        const baseUrl = "/api/logs/" + esc(item.PartitionKey || "") + "/" + esc(item.ExecId || "");
        const urlWithCode = {code_js} && {code_js} !== ""
          ? baseUrl + "?code=" + encodeURIComponent({code_js})
          : baseUrl;

        tr.innerHTML =
          '<td class="nowrap">' + esc(item.RequestedAt || '') + '</td>' +
          '<td>' + rowBadge(item.Status || '') + '</td>' +
          '<td class="nowrap">' + esc(item.ExecId || '') + '</td>' +
          '<td>' + esc(item.Name || '') + '</td>' +
          '<td>' + esc(item.Id || '') + '</td>' +
          '<td>' + esc(item.Runbook || '') + '</td>' +
          '<td>' +
            '<div style="display:flex; gap:6px; flex-wrap:nowrap; align-items:center">' +
              '<button class="btn" data-url="' + urlWithCode + '" onclick="openTraceModal(this)">Trace</button>' +
              '<button class="btn" data-url="' + urlWithCode + '" onclick="openOnlyLogModal(this)">Log</button>' +
            '</div>' +
          '</td>';
        tbody.appendChild(tr);
      }});
      el('info').textContent = (data.items || []).length + ' risultato/i';
    }}
    el('run').addEventListener('click', runQuery);
    function setDefaultPartitionKey(){{
      const d = new Date();
      const pad = n => String(n).padStart(2,'0');
      const yyyy = d.getFullYear();
      const mm = pad(d.getMonth()+1);
      const dd = pad(d.getDate());
      const today = `${{yyyy}}${{mm}}${{dd}}`;
      const input = document.getElementById('partitionKey');
      if (input && !input.value) input.value = today;
    }};
    el('clear').addEventListener('click', ()=>{{
      ['partitionKey','execId','q','from','to'].forEach(id=>el(id).value='');
      el('status').value='';
      el('limit').value='200';
      el('order').value='desc';
      el('tbl').querySelector('tbody').innerHTML='';
      el('raw').textContent='';
      el('info').textContent='';
      setDefaultPartitionKey();
    }});
    setDefaultPartitionKey();
  </script>
 </body>
</html>
""".strip()
    return func.HttpResponse(html, status_code=200, mimetype="text/html")


# fmt: on


@app.table_input(
    arg_name="rows",
    table_name=TABLE_NAME,
    partition_key="{partitionKey}",
    connection=STORAGE_CONN,
)
@app.route(route="logs/query", auth_level=AUTH)
def logs_query(req: func.HttpRequest, rows: str) -> func.HttpResponse:
    """
    Query dei log via Table Input Binding:
    - partitionKey (required) -> used for the binding
    - execId, status -> filtered by memory
    - q (contains on some fileds), from/to (range on RequestedAt), order, limit -> in memory
    """
    try:
        partition_key = (req.params.get("partitionKey") or "").strip()
        if not partition_key:
            return func.HttpResponse(
                json.dumps({"error": "partitionKey required"}, ensure_ascii=False),
                status_code=400,
                mimetype="application/json",
            )
        exec_id = (req.params.get("execId") or "").strip()
        status = (req.params.get("status") or "").strip().lower()
        q = (req.params.get("q") or "").strip()
        from_dt = (req.params.get("from") or "").strip()
        to_dt = (req.params.get("to") or "").strip()
        try:
            limit = min(max(int(req.params.get("limit") or 200), 1), 5000)
        except Exception:
            limit = 200
        order = (req.params.get("order") or "desc").strip().lower()

        try:
            data = json.loads(rows) if isinstance(rows, str) else rows
        except Exception:
            data = None

        if not isinstance(data, list):
            return func.HttpResponse(
                json.dumps(
                    {"error": "Table format unexpected"},
                    ensure_ascii=False,
                ),
                status_code=500,
                mimetype="application/json",
            )

        # Helpers
        def parse_dt_local(v: str) -> Optional[datetime]:
            if not v:
                return None
            try:
                return datetime.fromisoformat(v)
            except Exception:
                try:
                    from datetime import datetime as dt

                    return dt.strptime(v.replace(" ", "T"), "%Y-%m-%dT%H:%M:%S")
                except Exception:
                    return None

        f_dt = parse_dt_local(from_dt)
        t_dt = parse_dt_local(to_dt)

        def contains_any(e: dict, s: str) -> bool:
            s = s.lower()
            for k in ("Name", "Id", "Url", "Runbook", "Log", "Run_Args"):
                v = e.get(k)
                if v is None:
                    continue
                if isinstance(v, (dict, list)):
                    v = json.dumps(v, ensure_ascii=False)
                if s in str(v).lower():
                    return True
            return False

        # Memory filters
        filtered: list[dict[str, Any]] = []
        for e in data:
            ok = True
            if exec_id and str(e.get("ExecId") or "").strip() != exec_id:
                ok = False
            if ok and status and str(e.get("Status") or "").strip().lower() != status:
                ok = False
            if ok and q and not contains_any(e, q):
                ok = False
            if ok and (f_dt or t_dt):
                rd = parse_dt_local(str(e.get("RequestedAt") or ""))
                if not rd:
                    ok = False
                else:
                    if f_dt and rd < f_dt:
                        ok = False
                    if t_dt and rd > t_dt:
                        ok = False
            if ok:
                filtered.append(e)

        # Order by RequestedAt
        def key_dt(e: dict):
            d = parse_dt_local(str(e.get("RequestedAt") or "")) or datetime.min
            return d

        reverse = order != "asc"
        filtered.sort(key=key_dt, reverse=reverse)

        # Apply limits
        if len(filtered) > limit:
            filtered = filtered[:limit]

        body = json.dumps({"items": filtered}, ensure_ascii=False)
        return func.HttpResponse(body, status_code=200, mimetype="application/json")
    except Exception as e:
        logging.exception("logs_query (binding) failed")
        return func.HttpResponse(
            json.dumps({"error": str(e)}, ensure_ascii=False),
            status_code=500,
            mimetype="application/json",
        )
