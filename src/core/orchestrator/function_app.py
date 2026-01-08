import base64
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union
from urllib.parse import urlsplit, urlunsplit

import azure.functions as func
from models import Schema
from utils import create_cors_response

app = func.FunctionApp()

# =========================
# Constants and Utilities
# =========================

# Centralize configuration strings to avoid "magic strings"
TABLE_NAME = "RunbookLogs"
TABLE_SCHEMAS = "RunbookSchemas"
TABLE_WORKERS_SCHEMAS = "WorkersRegistry"
TABLE_USERS = "CloudoUsers"
TABLE_SETTINGS = "CloudoSettings"
TABLE_AUDIT = "CloudoAuditLogs"
TABLE_SCHEDULES = "CloudoSchedules"
STORAGE_CONN = "AzureWebJobsStorage"
NOTIFICATION_QUEUE_NAME = os.environ.get(
    "NOTIFICATION_QUEUE_NAME", "cloudo-notification"
)
STORAGE_CONNECTION = "AzureWebJobsStorage"
MAX_TABLE_CHARS = int(os.getenv("MAX_TABLE_LOG_CHARS", "32000"))
APPROVAL_TTL_MIN = int(os.getenv("APPROVAL_TTL_MIN", "60"))
APPROVAL_SECRET = (os.getenv("APPROVAL_SECRET") or "").strip()
SESSION_SECRET = (os.getenv("SESSION_SECRET") or "").strip()
if not SESSION_SECRET and os.getenv("FEATURE_DEV", "false").lower() != "true":
    logging.error("CRITICAL: SESSION_SECRET not configured. Authentication will fail.")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "pagopa/payments-cloudo")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
GITHUB_PATH_PREFIX = os.environ.get("GITHUB_PATH_PREFIX", "")

if os.getenv("FEATURE_DEV", "false").lower() != "true":
    AUTH = func.AuthLevel.FUNCTION
else:
    AUTH = func.AuthLevel.ANONYMOUS


def _b64url_encode(data: bytes) -> str:
    # Base64 URL-safe without padding
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    # Decode Base64 URL-safe without padding
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign_payload_b64(payload_b64: str) -> str:
    # HMAC-SHA256 signature over base64url payload (no padding)
    import hashlib
    import hmac

    key = (APPROVAL_SECRET or "default").encode("utf-8")
    return hmac.new(key, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()


def _verify_signed_payload(exec_id_path: str, p: str, s: str) -> tuple[bool, dict]:
    """
    Verify signature, parse payload (JSON), and basic invariants:
    - signature matches
    - exp not expired
    - execId in payload matches route
    Returns (ok, payload_dict_or_empty)
    """
    try:
        if not p or not s:
            return False, {}
        expected = _sign_payload_b64(p)
        import hmac

        if not hmac.compare_digest(expected, s):
            return False, {}
        payload_raw = _b64url_decode(p)
        payload = json.loads(payload_raw.decode("utf-8"))
        # Validate execId match
        if (payload.get("execId") or "").strip() != (exec_id_path or "").strip():
            return False, {}
        # Validate expiration
        exp_str = str(payload.get("exp") or "").replace(" ", "").replace("Z", "+00:00")
        exp_dt = datetime.fromisoformat(exp_str)
        if datetime.now(timezone.utc) > exp_dt.astimezone(timezone.utc):
            return False, {}
        return True, payload
    except Exception as e:
        logging.warning(f"verify signed payload failed: {e}")
        return False, {}


def _create_session_token(username: str, role: str, expires_at: str) -> str:
    import hashlib
    import hmac

    payload = json.dumps(
        {"username": username, "role": role, "expires_at": expires_at}
    ).encode("utf-8")
    payload_b64 = _b64url_encode(payload)
    key = SESSION_SECRET.encode("utf-8")
    sig = hmac.new(key, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def _verify_session_token(token: str) -> tuple[bool, dict]:
    try:
        if not token or "." not in token:
            return False, {}
        p_b64, s = token.split(".", 1)
        import hashlib
        import hmac

        key = SESSION_SECRET.encode("utf-8")
        expected_s = hmac.new(key, p_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_s, s):
            return False, {}

        payload_raw = _b64url_decode(p_b64)
        payload = json.loads(payload_raw.decode("utf-8"))

        exp_str = payload.get("expires_at")
        if not exp_str:
            return False, {}

        exp_dt = datetime.fromisoformat(exp_str)
        if datetime.now(timezone.utc) > exp_dt.astimezone(timezone.utc):
            return False, {}

        return True, payload
    except Exception as e:
        logging.warning(f"Session verification failed: {e}")
        return False, {}


def _get_authenticated_user(
    req: func.HttpRequest,
) -> tuple[Optional[dict], Optional[func.HttpResponse]]:
    # 1. Check Bearer Token
    auth_header = req.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        ok, session = _verify_session_token(token)
        if ok:
            return session, None

    # 2. Fallback to x-cloudo-key
    cloudo_key = req.headers.get("x-cloudo-key")
    expected_cloudo_key = os.environ.get("CLOUDO_SECRET_KEY")
    if cloudo_key and expected_cloudo_key and cloudo_key == expected_cloudo_key:
        return {"user": "api", "username": "api", "role": "ADMIN"}, None

    # 3. Fallback to x-functions-key (Azure Actions or direct calls)
    func_key = req.headers.get("x-functions-key")
    expected_func_key = os.environ.get("FUNCTION_KEY")
    if func_key and expected_func_key and func_key == expected_func_key:
        return {
            "user": "azure-action",
            "username": "azure-action",
            "role": "ADMIN",
        }, None

    return None, func.HttpResponse(
        json.dumps({"error": "Unauthorized: Missing or invalid credentials"}),
        status_code=401,
        mimetype="application/json",
        headers={"Access-Control-Allow-Origin": "*"},
    )


def _rows_from_binding(rows: Union[str, list[dict]]) -> list[dict]:
    try:
        return json.loads(rows) if isinstance(rows, str) else (rows or [])
    except Exception:
        return []


def log_audit(user: str, action: str, target: str, details: str = ""):
    """Log an action to the Audit table."""
    try:
        from azure.data.tables import TableClient

        conn_str = os.environ.get(STORAGE_CONN)
        table_client = TableClient.from_connection_string(
            conn_str, table_name=TABLE_AUDIT
        )

        now = datetime.now(timezone.utc)
        entity = {
            "PartitionKey": now.strftime("%Y%m%d"),
            "RowKey": str(uuid.uuid4()),
            "timestamp": now.isoformat(),
            "operator": user,
            "action": action,
            "target": target,
            "details": details,
        }
        table_client.create_entity(entity=entity)
    except Exception as e:
        logging.error(f"Failed to log audit: {e}")


def _only_pending_for_exec(rows: list[dict], exec_id: str) -> bool:
    """
    True if ExecId had only 'pending' (o nothing).
    False if there are some other rows not 'pending'.
    """
    for e in rows:
        if str(e.get("ExecId") or "") != exec_id:
            continue
        st = str(e.get("Status") or "").strip().lower()
        if st != "pending":
            return False
    return True


def _notify_slack_decision(
    exec_id: str, schema_id: str, decision: str, approver: str, extra: str = ""
) -> None:
    from escalation import send_slack_execution

    token = (os.environ.get("SLACK_TOKEN") or "").strip()
    channel = (os.environ.get("SLACK_CHANNEL") or "").strip() or "#cloudo-test"
    if not token:
        return
    emoji = "✅" if decision == "approved" else "❌"
    try:
        send_slack_execution(
            token=token,
            channel=channel,
            message=f"[{exec_id}] {emoji} {decision.upper()} - {schema_id}",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*{decision}*\n"
                            f"*ExecId:* `{exec_id}`\n"
                            f"*SchemaId:* `{schema_id}`\n"
                            f"*By:* {approver}"
                        ),
                    },
                },
                *(
                    [
                        {
                            "type": "context",
                            "elements": [{"type": "mrkdwn", "text": extra}],
                        }
                    ]
                    if extra
                    else []
                ),
            ],
        )
    except Exception as e:
        logging.error(f"[{exec_id}] Slack notify failed: {e}")


def decode_base64(data: str) -> str:
    """Decode base64 encoded string to utf-8 string"""
    try:
        return base64.b64decode(data).decode("utf-8")
    except Exception as e:
        logging.warning(f"Failed to decode base64 encoded string: {e}")
        return data


def _encode_logs(text: str) -> bytes:
    """Encode log text in base64 UTF-8."""
    raw = (text or "").encode("utf-8", errors="replace")
    return base64.b64encode(raw)


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


def safe_json(response) -> Optional[Union[dict, str]]:
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
    resource_info: Optional[dict],
    routing_info: Optional[dict],
    monitor_condition: Optional[str],
    severity: Optional[str],
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
        "Worker": schema.worker,
        "x-cloudo-key": os.environ.get("CLOUDO_SECRET_KEY", ""),
    }
    if resource_info is not None:
        headers["resource_info"] = json.dumps(resource_info, ensure_ascii=False)
    if routing_info is not None:
        headers["routing_info"] = json.dumps(routing_info, ensure_ascii=False)
    return headers


def build_response_body(
    status_code: int,
    schema: "Schema",
    partition_key: str,
    exec_id: str,
    api_json: Optional[Union[dict, str]],
) -> str:
    # Build the HTTP response payload returned by this function
    return json.dumps(
        {
            "status": status_code,
            "schema": {
                "id": schema.id,
                "name": schema.name,
                "description": schema.description,
                "oncall": schema.oncall,
                "runbook": schema.runbook,
                "run_args": schema.run_args,
                "worker": schema.worker,
                "monitor_condition": schema.monitor_condition,
                "severity": schema.severity,
            },
            "response": api_json,
            "log": {"partitionKey": partition_key, "exec_id": exec_id},
        },
        ensure_ascii=False,
    )


def parse_header_json(req, name):
    raw = get_header(req, name)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def build_log_entry(
    *,
    status: str,
    partition_key: str,
    row_key: str,
    exec_id: Optional[str],
    requested_at: str,
    name: Optional[str],
    schema_id: Optional[str],
    runbook: Optional[str],
    run_args: Optional[str],
    worker: Optional[str],
    log_msg: Optional[str],
    oncall: Optional[str],
    monitor_condition: Optional[str],
    severity: Optional[str],
    approval_required: Optional[bool] = None,
    approval_expires_at: Optional[str] = None,
    approval_decision_by: Optional[str] = None,
) -> dict[str, Any]:
    # Normalized log entity for Azure Table Storage (with optional approval fields)
    return {
        "PartitionKey": partition_key,
        "RowKey": row_key,
        "ExecId": exec_id,
        "Status": status,
        "RequestedAt": requested_at,
        "Name": name,
        "Id": schema_id,
        "Runbook": runbook,
        "Run_Args": run_args,
        "Worker": worker,
        "Log": log_msg,
        "OnCall": oncall,
        "MonitorCondition": monitor_condition,
        "Severity": severity,
        "ApprovalRequired": approval_required,
        "ApprovalExpiresAt": approval_expires_at,
        "ApprovalDecisionBy": approval_decision_by,
    }


def _post_status(payload: dict, status: str, log_message: str) -> str:
    """
    Build the status message (with base64-encoded, truncated logs) to send
    on the notification queue. Used by the orchestrator to talk to the Receiver.
    """
    from utils import format_requested_at

    exec_id = payload.get("exec_id")
    log_text = log_message or ""
    log_bytes = _encode_logs(log_text)

    MAX_LOG_BODY_BYTES = 64 * 1024
    if len(log_bytes) > MAX_LOG_BODY_BYTES:
        log_bytes = log_bytes[:MAX_LOG_BODY_BYTES]

    message = {
        "requestedAt": payload.get("requestedAt"),
        "id": payload.get("id"),
        "name": payload.get("name"),
        "exec_id": exec_id,
        "runbook": payload.get("runbook"),
        "run_args": payload.get("run_args"),
        "worker": payload.get("worker"),
        "status": status,
        "oncall": payload.get("oncall"),
        "monitor_condition": payload.get("monitor_condition"),
        "severity": payload.get("severity"),
        "resource_info": payload.get("resource_info"),
        "routing_info": payload.get("routing_info"),
        "logs_b64": log_bytes.decode("utf-8"),
        "content_type": "text/plain; charset=utf-8",
        "sent_at": format_requested_at(),
    }
    return json.dumps(message, ensure_ascii=False)


# =========================
# HTTP Function: Trigger
# =========================


@app.route(
    route="Trigger/{team?}",
    methods=[func.HttpMethod.POST, func.HttpMethod.OPTIONS],
    auth_level=AUTH,
)
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
@app.table_input(
    arg_name="workers",
    table_name=TABLE_WORKERS_SCHEMAS,
    connection=STORAGE_CONN,
)
@app.queue_output(
    arg_name="cloudo_notification_q",
    queue_name=NOTIFICATION_QUEUE_NAME,
    connection=STORAGE_CONNECTION,
)
def Trigger(
    req: func.HttpRequest,
    log_table: func.Out[str],
    entities: str,
    workers: str,
    cloudo_notification_q: func.Out[str],
) -> func.HttpResponse:
    import detection
    import utils
    from escalation import (
        format_opsgenie_description,
        send_opsgenie_alert,
        send_slack_execution,
    )
    from worker_routing import worker_routing

    if req.method == "OPTIONS":
        return create_cors_response()

    try:
        from smart_routing import (
            execute_actions,
            resolve_opsgenie_apikey,
            resolve_slack_token,
            route_alert,
        )
    except ImportError:
        route_alert = None
        execute_actions = None

        def resolve_slack_token(_):
            return None

        def resolve_opsgenie_apikey(_):
            return None

    # Init payload variables to None
    resource_name = resource_group = resource_id = schema_id = monitor_condition = (
        severity
    ) = ""
    route_params = getattr(req, "route_params", {}) or {}
    logging.debug(route_params)
    # Pre-compute logging fields
    requested_at = utils.format_requested_at()
    partition_key = utils.today_partition_key()
    exec_id = str(uuid.uuid4())

    # Security: check session token
    session, error_res = _get_authenticated_user(req)
    if error_res:
        return error_res
    requester_username = session.get("username")
    logging.warning(requester_username)

    # Resolve schema_id from route first; fallback to query/body (alertId/schemaId)
    if (req.params.get("id")) is not None:
        schema_id = detection.extract_schema_id_from_req(req)
        resource_info = {}
        routing_info = {
            "team": route_params.get("team") or "",
            "slack_token": req.params.get("slack_token")
            or resolve_slack_token(route_params.get("team") or ""),
            "slack_channel": req.params.get("slack_channel")
            or (os.environ.get("SLACK_CHANNEL") or "#cloudo-test").strip(),
            "opsgenie_token": req.params.get("opsgenie_api_key")
            or resolve_opsgenie_apikey(route_params.get("team") or ""),
        }
    else:
        (
            _raw,
            resource_name,
            resource_group,
            resource_id,
            schema_id,
            namespace,
            pod,
            deployment,
            horizontalpodautoscaler,
            job,
            monitor_condition,
            severity,
        ) = detection.parse_resource_fields(req).values()
        resource_info = (
            {
                "_raw": _raw,
                "resource_name": resource_name,
                "resource_rg": resource_group,
                "resource_id": resource_id,
                "aks_namespace": namespace,
                "aks_pod": pod,
                "aks_deployment": deployment,
                "aks_job": job,
                "aks_horizontalpodautoscaler": horizontalpodautoscaler,
                "team": route_params.get("team"),
            }
            if resource_name
            else {}
        )
        routing_info = {
            "team": route_params.get("team") or "",
            "slack_token": req.params.get("slack_token")
            or resolve_slack_token(route_params.get("team") or ""),
            "slack_channel": req.params.get("slack_channel")
            or (os.environ.get("SLACK_CHANNEL") or "#cloudo-test").strip(),
            "opsgenie_token": req.params.get("opsgenie_api_key")
            or resolve_opsgenie_apikey(route_params.get("team") or ""),
        }
        logging.debug(f"[{exec_id}] Resource info: %s", resource_info)

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
            headers={
                "Access-Control-Allow-Origin": "*",
            },
        )

    # Apply optional filter in code (case-insensitive fallback on 'Id'/'id')
    def get_id(e: dict) -> str:
        return str(e.get("Id") or e.get("id") or "").strip()

    schema_entity = next((e for e in parsed if get_id(e) in schema_id), None)

    if not schema_entity:
        if monitor_condition and severity:
            log_msg = (
                "routed: Alarm detected\n\n"
                f"{json.dumps(json.loads(resource_info.get('_raw')), ensure_ascii=False, indent=2) or '{}'}\n\n"
                "ALARM -> ROUTED"
            )
            payload_for_status = {
                "requestedAt": requested_at,
                "id": "NaN",
                "name": resource_name or "",
                "exec_id": exec_id,
                "runbook": "NaN",
                "run_args": "NaN",
                "worker": "NaN",
                "oncall": "NaN",
                "monitor_condition": monitor_condition or "",
                "severity": severity or "",
                "resource_info": resource_info if "resource_info" in locals() else {},
                "routing_info": routing_info if "routing_info" in locals() else {},
            }
            cloudo_notification_q.set(
                _post_status(payload_for_status, status="routed", log_message=log_msg)
            )
            return func.HttpResponse(
                json.dumps(
                    {
                        "routed": (
                            "Alarm detected.\n "
                            "(This alert has not a runbook to be executed) -> ROUTED"
                        )
                    },
                    ensure_ascii=False,
                ),
                status_code=200,
                mimetype="application/json",
                headers={
                    "Access-Control-Allow-Origin": "*",
                },
            )
        else:
            return func.HttpResponse(
                json.dumps(
                    {
                        "ignored": f"No alert detected for {schema_id}",
                    },
                    ensure_ascii=False,
                ),
                status_code=204,
                mimetype="application/json",
                headers={
                    "Access-Control-Allow-Origin": "*",
                },
            )

    logging.info(f"[{exec_id}] Getting schema entity id '{schema_entity}'")
    # Build domain model
    schema = Schema(
        id=schema_entity.get("id"),
        entity=schema_entity,
        monitor_condition=monitor_condition,
        severity=severity,
    )
    try:
        # Approval-required path: create pending with signed URL embedding resource_info and function key
        if schema.require_approval:
            expires_at = (
                (datetime.now(timezone.utc) + timedelta(minutes=APPROVAL_TTL_MIN))
                .isoformat()
                .replace(" ", "")
            )
            # function key to pass along (from header or query)
            func_key = (
                req.headers.get("x-functions-key") or req.params.get("code") or ""
            )
            # Build payload
            payload = {
                "execId": exec_id,
                "schemaId": schema.id,
                "exp": expires_at,
                "resource_info": resource_info or {},
                "routing_info": routing_info or {},
                "code": func_key or "",
                "monitorCondition": monitor_condition,
                "severity": severity,
                "worker": schema.worker,
            }
            payload_b64 = _b64url_encode(
                json.dumps(payload, ensure_ascii=False).encode("utf-8")
            )
            sig = _sign_payload_b64(payload_b64)

            base_env = os.getenv("ORCHESTRATOR_BASE_URL")
            if not base_env:
                hostname = os.getenv("WEBSITE_HOSTNAME", "localhost:7071")
                scheme = "https" if "localhost" not in hostname else "http"
                base = f"{scheme}://{hostname}"
            else:
                base = base_env.rstrip("/")
            approve_url = f"{base}/api/approvals/{partition_key}/{exec_id}/approve?p={payload_b64}&s={sig}&code={func_key}"
            reject_url = f"{base}/api/approvals/{partition_key}/{exec_id}/reject?p={payload_b64}&s={sig}&code={func_key}"

            pending_log = build_log_entry(
                status="pending",
                partition_key=partition_key,
                exec_id=exec_id,
                row_key=exec_id,
                requested_at=requested_at,
                name=schema.name or "",
                schema_id=schema.id,
                runbook=schema.runbook,
                run_args=schema.run_args,
                worker=schema.worker,
                log_msg=json.dumps(
                    {
                        "message": "Awaiting approval",
                        "approve": approve_url,
                        "reject": reject_url,
                        "resource_info": resource_info,
                    },
                    ensure_ascii=False,
                ),
                oncall=schema.oncall,
                monitor_condition=monitor_condition,
                severity=severity,
                approval_required=True,
                approval_expires_at=expires_at,
            )
            log_table.set(json.dumps(pending_log, ensure_ascii=False))

            if requester_username:
                log_audit(
                    user=requester_username,
                    action="RUNBOOK_MANUAL_GATE_SCHEDULE",
                    target=exec_id,
                    details=f"ID: {schema.id}, Runbook: {schema.runbook}, Args: {schema.run_args}",
                )

            # Optional Slack notify
            slack_token = routing_info.get("slack_token")
            slack_channel = routing_info.get("slack_channel")
            if slack_token:
                try:
                    send_slack_execution(
                        token=slack_token,
                        channel=slack_channel,
                        message=f"[{exec_id}] APPROVAL REQUIRED: {schema.name}",
                        blocks=[
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": (
                                        f"*Approval required* <!here>\n"
                                        f"*Name:* {schema.name}\n"
                                        f"*Id:* `{schema.id}`\n"
                                        f"*ExecId:* `{exec_id}`\n"
                                        f"*Severity:* {severity or '-'}\n"
                                        f"*Worker:* `{schema.worker or 'unknow(?)'}`\n"
                                        f"*Runbook:* `{schema.runbook or '-'}`\n"
                                        f"*Args:* ```{(schema.run_args or '').strip() or '-'}```"
                                    ),
                                },
                            },
                            {
                                "type": "section",
                                "fields": [
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*Worker:* {schema.worker or 'unknow(?)'}",
                                    }
                                ],
                            },
                            {
                                "type": "actions",
                                "elements": [
                                    {
                                        "type": "button",
                                        "text": {
                                            "type": "plain_text",
                                            "text": "Approve ✅",
                                        },
                                        "url": approve_url,
                                    },
                                    {
                                        "type": "button",
                                        "text": {
                                            "type": "plain_text",
                                            "text": "Reject ❌",
                                        },
                                        "url": reject_url,
                                    },
                                ],
                            },
                        ],
                    )
                except Exception as e:
                    logging.error(f"[{exec_id}] Slack approval notify failed: {e}")

            body = json.dumps(
                {
                    "status": 202,
                    "message": "Job is pending approval",
                    "exec_id": exec_id,
                    "approve": approve_url,
                    "reject": reject_url,
                    "expires_at (UTC)": expires_at,
                },
                ensure_ascii=False,
            )
            return func.HttpResponse(
                body,
                status_code=202,
                mimetype="application/json",
                headers={
                    "Access-Control-Allow-Origin": "*",
                },
            )

        # ---------------------------------------------------------
        # DYNAMIC WORKER SELECTION (Binding Version)
        # ---------------------------------------------------------
        target_queue = worker_routing(workers, schema)

        api_body = {}
        status_code = 202

        if target_queue:
            logging.info(
                f"[{exec_id}] 🎯 Dynamic Routing: Selected Queue '{target_queue}'"
            )

            try:
                from azure.storage.queue import QueueClient, TextBase64EncodePolicy

                # Construct the payload (formerly HTTP headers)
                queue_payload = {
                    "runbook": schema.runbook,
                    "run_args": schema.run_args,
                    "id": schema.id,
                    "name": schema.name or "",
                    "requestedAt": requested_at,
                    "exec_id": exec_id,
                    "oncall": schema.oncall,
                    "monitor_condition": monitor_condition,
                    "severity": severity,
                    "worker": schema.worker,
                    "resource_info": resource_info or {},
                    "routing_info": routing_info or {},
                }

                # Send it to the specific dynamic queue
                # We use TextBase64EncodePolicy because Azure Function Triggers usually expect Base64 encoded strings
                q_client = QueueClient.from_connection_string(
                    conn_str=os.environ.get(STORAGE_CONN),
                    queue_name=target_queue,
                    message_encode_policy=TextBase64EncodePolicy(),
                )
                q_client.send_message(json.dumps(queue_payload, ensure_ascii=False))

                api_body = {"status": "accepted", "queue": target_queue}

                if resource_info == {}:
                    log_audit(
                        user=requester_username,
                        action="RUNBOOK_MANUAL_SCHEDULE",
                        target=exec_id,
                        details=f"ID: {schema.id}, Runbook: {schema.runbook}, Args: {schema.run_args}",
                    )

            except Exception as e:
                logging.error(f"[{exec_id}] ❌ Queue send failed: {e}")
                status_code = 500
                api_body = {"error": str(e)}
        else:
            err_msg = f"❌ No workers ({schema.worker}) available and no static queue configured for {schema.id}"
            logging.error(f"[{exec_id}] {err_msg}")
            status_code = 500
            api_body = {"error": err_msg}
        # ---------------------------------------------------------

        # Status label for logs
        status_label = "accepted" if status_code == 202 else "error"

        # Write log entry to the table
        start_log = build_log_entry(
            status=status_label,
            partition_key=partition_key,
            exec_id=exec_id,
            row_key=exec_id,
            requested_at=requested_at,
            name=schema.name or "",
            schema_id=schema.id,
            runbook=schema.runbook,
            run_args=schema.run_args,
            worker=schema.worker,
            log_msg=api_body,
            oncall=schema.oncall,
            monitor_condition=monitor_condition,
            severity=severity,
        )
        log_table.set(json.dumps(start_log, ensure_ascii=False))

        # smart routing notification (if routing module available)
        if status_label != "accepted":
            if route_alert and execute_actions:
                ctx = {
                    "resourceId": resource_id,
                    "resourceGroup": resource_group,
                    "resourceName": resource_name,
                    "alertRule": (schema.name or ""),
                    "severity": severity,
                    "namespace": ((resource_info or {}).get("namespace") or ""),
                    "oncall": schema.oncall,
                    "status": status_label,
                    "execId": exec_id,
                    "name": schema.name or "",
                    "id": schema.id,
                    "routing_info": routing_info,
                }
                decision = route_alert(ctx)
                logging.debug(f"[{exec_id}] {decision}")
                status_emoji = "✅" if status_label == "succeeded" else "❌"
                payload = {
                    "slack": {
                        "message": f"[{exec_id}] Status: {status_label}: {schema.name or ''}",
                        "blocks": [
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
                                        "text": f"*Name:*\n{schema.name or ''}",
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*Id:*\n{schema.id or ''}",
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*ExecId:*\n{exec_id or ''}",
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*Status:*\n{status_label}",
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*Severity:*\n{severity or ''}",
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*OnCall:*\n{schema.oncall or ''}",
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*Origin*:\n{schema.worker or 'unknown(?)'}",
                                    },
                                ],
                            },
                            {
                                "type": "section",
                                "fields": [
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*Runbook:*\n{schema.runbook or ''}",
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*MonitorCondition:*\n{schema.monitor_condition or ''}",
                                    },
                                ],
                            },
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"*Run Args:*\n```{schema.run_args or ''}```",
                                },
                            },
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"*Logs (truncated):*\n```{(json.dumps(api_body, ensure_ascii=False) if isinstance(api_body, (dict, list)) else str(api_body))[:1500]}```",
                                },
                            },
                            {
                                "type": "context",
                                "elements": [
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*Severity:* {severity}",
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*Teams:* {', '.join(dict.fromkeys(a.team for a in decision.actions if getattr(a, 'team', None)))}",
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": f"Timestamp: <!date^{int(__import__('time').time())}^{{date_short}} {{time}}|now>",
                                    },
                                ],
                            },
                            {"type": "divider"},
                        ],
                    },
                    "opsgenie": {
                        "message": f"[{schema.id}] [{severity}] {schema.name}",
                        "priority": f"P{int(str(severity).strip().lower().replace('sev', '') or '4') + 1}",
                        "alias": schema.id,
                        "monitor_condition": monitor_condition or "",
                        "details": {
                            "Name": schema.name,
                            "Id": schema.id,
                            "ExecId": exec_id,
                            "Status": status_label,
                            "Runbook": schema.runbook,
                            "Run_Args": schema.run_args,
                            "OnCall": schema.oncall,
                            "MonitorCondition": monitor_condition,
                            "Severity": severity,
                            "Teams:": ", ".join(
                                dict.fromkeys(
                                    a.team
                                    for a in decision.actions
                                    if getattr(a, "team", None)
                                )
                            ),
                        },
                        "description": f"{format_opsgenie_description(exec_id, resource_info, api_body)}",
                    },
                }
                try:
                    execute_actions(
                        decision,
                        payload,
                        send_slack_fn=lambda token, channel, **kw: send_slack_execution(
                            token=token, channel=channel, **kw
                        ),
                        send_opsgenie_fn=lambda api_key, **kw: send_opsgenie_alert(
                            api_key=api_key, **kw
                        ),
                    )
                except Exception as e:
                    logging.error(f"[{exec_id}] smart routing failed: {e}")

        # Return HTTP response mirroring downstream status
        response_body = build_response_body(
            status_code=status_code,
            schema=schema,
            partition_key=partition_key,
            exec_id=exec_id,
            api_json=api_body,
        )
        return func.HttpResponse(
            response_body,
            status_code=status_code,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
            },
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
            runbook=schema.runbook,
            run_args=schema.run_args,
            worker=schema.worker,
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
            headers={
                "Access-Control-Allow-Origin": "*",
            },
        )


# =========================
# HTTP Function: Approval
# =========================
@app.route(
    route="approvals/{partitionKey}/{execId}/approve",
    methods=[func.HttpMethod.GET, func.HttpMethod.OPTIONS],
    auth_level=AUTH,
)
@app.table_output(
    arg_name="log_table",
    table_name=TABLE_NAME,
    connection=STORAGE_CONN,
)
@app.table_input(
    arg_name="schemas",
    table_name=TABLE_SCHEMAS,
    connection=STORAGE_CONN,
)
@app.table_input(
    arg_name="workers",
    table_name=TABLE_WORKERS_SCHEMAS,
    connection=STORAGE_CONN,
)
@app.table_input(
    arg_name="today_logs",
    table_name=TABLE_NAME,
    partition_key="{partitionKey}",
    connection=STORAGE_CONN,
)
def approve(
    req: func.HttpRequest,
    log_table: func.Out[str],
    schemas: str,
    today_logs: str,
    workers: str,
) -> func.HttpResponse:
    import utils
    from escalation import send_slack_execution
    from frontend import render_template
    from worker_routing import worker_routing

    if req.method == "OPTIONS":
        return create_cors_response()

    try:
        from smart_routing import execute_actions, route_alert
    except ImportError:
        route_alert = None
        execute_actions = None

    route_params = getattr(req, "route_params", {}) or {}
    execId = (route_params.get("execId") or "").strip()

    p = (req.params.get("p") or "").strip()
    s = (req.params.get("s") or "").strip()

    # Security: check session token if not in FEATURE_DEV mode
    if os.getenv("FEATURE_DEV", "false").lower() != "true":
        session, error_res = _get_authenticated_user(req)
        if error_res:
            # Fallback for Slack/Email links: if no session, we might still allow it if p and s are valid
            # and the payload is signed. But it's better to log who did it if they are logged in.
            approver = req.headers.get("X-Approver") or "anonymous-link"
        else:
            approver = session.get("username")
    else:
        approver = req.headers.get("X-Approver") or "unknown"

    if not execId:
        return func.HttpResponse(
            json.dumps({"error": "Missing execId in route"}, ensure_ascii=False),
            status_code=400,
            mimetype="application/json",
        )

    ok, payload = _verify_signed_payload(execId, p, s)
    if not ok:
        return func.HttpResponse(
            json.dumps({"error": "Invalid or expired payload"}, ensure_ascii=False),
            status_code=401,
            mimetype="application/json",
        )

    rows = _rows_from_binding(today_logs)
    if not _only_pending_for_exec(rows, execId):
        return func.HttpResponse(
            json.dumps(
                {"message": "Already decided or executed for this ExecId"},
                ensure_ascii=False,
            ),
            status_code=409,
            mimetype="application/json",
        )

    schema_id = payload.get("schemaId") or ""
    resource_info = payload.get("resource_info") or None
    routing_info = payload.get("routing_info") or None
    func_key = payload.get("code") or ""
    monitor_condition = payload.get("monitorCondition") or ""
    severity = payload.get("severity") or ""

    # Load schema entity
    try:
        parsed = json.loads(schemas) if isinstance(schemas, str) else schemas
    except Exception:
        parsed = None
    if not isinstance(parsed, list):
        return func.HttpResponse(
            json.dumps({"error": "Schemas not available"}, ensure_ascii=False),
            status_code=500,
            mimetype="application/json",
        )

    def get_id(e: dict) -> str:
        return str(e.get("Id") or e.get("id") or "").strip()

    schema_entity = next((e for e in parsed if get_id(e) == schema_id), None)
    if not schema_entity:
        return func.HttpResponse(
            json.dumps({"error": "Schema not found"}, ensure_ascii=False),
            status_code=404,
            mimetype="application/json",
        )

    schema = Schema(id=schema_entity.get("id"), entity=schema_entity)

    partition_key = utils.today_partition_key()
    requested_at = utils.format_requested_at()

    # Execute once (pass embedded resource_info and propagate the function key if needed)
    try:
        # ---------------------------------------------------------
        # DYNAMIC WORKER SELECTION (Binding Version)
        # ---------------------------------------------------------
        target_queue = worker_routing(workers, schema)

        api_body = {}
        status_code = 202

        if target_queue:
            logging.info(
                f"[{execId}] 🎯 Dynamic Routing: Selected Queue '{target_queue}'"
            )

            try:
                from azure.storage.queue import QueueClient, TextBase64EncodePolicy

                # Construct the payload (formerly HTTP headers)
                queue_payload = {
                    "runbook": schema.runbook,
                    "run_args": schema.run_args,
                    "id": schema.id,
                    "name": schema.name or "",
                    "requestedAt": requested_at,
                    "exec_id": execId,
                    "oncall": schema.oncall,
                    "monitor_condition": monitor_condition,
                    "severity": severity,
                    "worker": schema.worker,
                    "resource_info": resource_info or {},
                    "routing_info": routing_info or {},
                }

                # Send it to the specific dynamic queue
                # We use TextBase64EncodePolicy because Azure Function Triggers usually expect Base64 encoded strings
                q_client = QueueClient.from_connection_string(
                    conn_str=os.environ.get(STORAGE_CONN),
                    queue_name=target_queue,
                    message_encode_policy=TextBase64EncodePolicy(),
                )
                q_client.send_message(json.dumps(queue_payload, ensure_ascii=False))

                api_body = {
                    "status": "accepted",
                    "queue": target_queue,
                    "payload": queue_payload,
                }

            except Exception as e:
                logging.error(f"[{execId}] ❌ Queue send failed: {e}")
                status_code = 500
                api_body = {"error": str(e)}
        else:
            err_msg = f"❌ No workers ({schema.worker}) available and no static queue configured for {schema.id}"
            logging.error(f"[{execId}] {err_msg}")
            status_code = 500
            api_body = {"error": err_msg}
        # ---------------------------------------------------------

        # Status label for logs
        status_label = "accepted" if status_code == 202 else "error"

        log_entity = build_log_entry(
            status=status_label,
            partition_key=partition_key,
            row_key=str(uuid.uuid4()),
            exec_id=execId,
            requested_at=requested_at,
            name=schema.name or "",
            schema_id=schema.id,
            runbook=schema.runbook,
            run_args=schema.run_args,
            worker=schema.worker,
            log_msg=json.dumps(
                {
                    "message": "Approved and executed",
                    "response": api_body,
                    "resource_info": resource_info,
                },
                ensure_ascii=False,
            ),
            oncall=schema.oncall,
            monitor_condition=monitor_condition,
            severity=severity,
            approval_required=True,
            approval_decision_by=approver,
        )
        log_table.set(json.dumps(log_entity, ensure_ascii=False))

        log_audit(
            user=approver,
            action="RUNBOOK_APPROVE",
            target=execId,
            details=f"Runbook: {schema.runbook}, Schema: {schema.id}",
        )

        # smart routing notification (if routing module available)
        if route_alert and execute_actions:
            ctx = {
                "resourceId": ((resource_info or {}).get("resource_id") or ""),
                "resourceGroup": ((resource_info or {}).get("resource_group") or ""),
                "resourceName": ((resource_info or {}).get("resource_name") or ""),
                "alertRule": (schema.name or ""),
                "severity": severity,
                "namespace": ((resource_info or {}).get("namespace") or ""),
                "oncall": schema.oncall,
                "status": status_label,
                "execId": execId,
                "name": schema.name or "",
                "id": schema.id,
                "routing_info": routing_info,
            }
            decision = route_alert(ctx)
            logging.debug(f"[{execId}] Approval: {decision}")
            payload = {
                "slack": {
                    "message": f"[{execId}] 🚀 Approved - {schema_id}",
                    "blocks": [
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": f"🚀 Approved - {schema_id}",
                                "emoji": True,
                            },
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": (
                                    f"*ExecId:* `{execId}`\n"
                                    f"*SchemaId:* `{schema_id}`\n"
                                    f"*By:* {approver}"
                                ),
                            },
                        },
                        *(
                            [
                                {
                                    "type": "context",
                                    "elements": [
                                        {
                                            "type": "mrkdwn",
                                            "text": f"*Status:* {status_label}",
                                        }
                                    ],
                                }
                            ]
                            if status_label
                            else []
                        ),
                    ],
                }
            }
            try:
                execute_actions(
                    decision,
                    payload,
                    send_slack_fn=lambda token, channel, **kw: send_slack_execution(
                        token=token, channel=channel, **kw
                    ),
                )
            except Exception as e:
                logging.error(f"[{execId}] smart routing approval failed: {e}")

        html = render_template(
            "approve.html",
            {
                "status_label": status_label,
                "execId": execId,
                "schema_id": schema.id,
                "schema_name": schema.name or "-",
                "schema_runbook": schema.runbook or "-",
                "schema_run_args": (schema.run_args or "-"),
                "severity": severity or "-",
                "requested_at": requested_at,
                "partition_key": partition_key,
                "func_key": func_key,
            },
        )

        return func.HttpResponse(
            html,
            status_code=200,
            mimetype="text/html",
            headers={
                "Content-Type": "text/html",
                "Access-Control-Allow-Origin": "*",
            },
        )

    except Exception as e:
        err_log = build_log_entry(
            status="error",
            partition_key=partition_key,
            row_key=str(uuid.uuid4()),
            exec_id=execId,
            requested_at=requested_at,
            name=schema.name or "",
            schema_id=schema.id,
            runbook=schema.runbook,
            run_args=schema.run_args,
            worker=schema.worker,
            log_msg=f"Approve failed: {str(e)}",
            oncall=schema.oncall,
            monitor_condition=None,
            severity=None,
            approval_required=True,
            approval_decision_by=approver,
        )
        log_table.set(json.dumps(err_log, ensure_ascii=False))
        _notify_slack_decision(
            execId,
            schema_id,
            f"approved {execId}",
            approver,
            extra=f"*Error:* {str(e)}",
        )
        return func.HttpResponse(
            json.dumps({"error": str(e)}, ensure_ascii=False),
            status_code=500,
            mimetype="application/json",
        )


# =========================
# HTTP Function: Rejecter
# =========================
@app.route(
    route="approvals/{partitionKey}/{execId}/reject",
    methods=[func.HttpMethod.GET, func.HttpMethod.OPTIONS],
    auth_level=AUTH,
)
@app.table_output(
    arg_name="log_table",
    table_name=TABLE_NAME,
    connection=STORAGE_CONN,
)
@app.table_input(
    arg_name="schemas",
    table_name=TABLE_SCHEMAS,
    connection=STORAGE_CONN,
)
@app.table_input(
    arg_name="today_logs",
    table_name=TABLE_NAME,
    partition_key="{partitionKey}",
    connection=STORAGE_CONN,
)
def reject(
    req: func.HttpRequest, log_table: func.Out[str], schemas: str, today_logs: str
) -> func.HttpResponse:
    import utils
    from escalation import send_slack_execution
    from frontend import render_template

    if req.method == "OPTIONS":
        return create_cors_response()

    try:
        from smart_routing import execute_actions, route_alert
    except ImportError:
        route_alert = None
        execute_actions = None

    route_params = getattr(req, "route_params", {}) or {}
    execId = (route_params.get("execId") or "").strip()

    rows = _rows_from_binding(today_logs)
    if not _only_pending_for_exec(rows, execId):
        return func.HttpResponse(
            json.dumps(
                {"message": "Already decided or executed for this ExecId"},
                ensure_ascii=False,
            ),
            status_code=409,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
            },
        )

    p = (req.params.get("p") or "").strip()
    s = (req.params.get("s") or "").strip()

    # Security: check session token if not in FEATURE_DEV mode
    if os.getenv("FEATURE_DEV", "false").lower() != "true":
        session, error_res = _get_authenticated_user(req)
        if error_res:
            # Fallback for Slack/Email links
            approver = req.headers.get("X-Approver") or "anonymous-link"
        else:
            approver = session.get("username")
    else:
        approver = req.headers.get("X-Approver") or "unknown"

    if not execId:
        return func.HttpResponse(
            json.dumps({"error": "Missing execId in route"}, ensure_ascii=False),
            status_code=400,
            mimetype="application/json",
        )

    ok, payload = _verify_signed_payload(execId, p, s)
    if not ok:
        return func.HttpResponse(
            json.dumps({"error": "Invalid or expired payload"}, ensure_ascii=False),
            status_code=401,
            mimetype="application/json",
        )

    schema_id = payload.get("schemaId") or ""
    resource_info = payload.get("resource_info") or None
    routing_info = payload.get("routing_info") or None
    monitor_condition = payload.get("monitorCondition") or ""
    severity = payload.get("severity") or ""

    # Load schema entity
    try:
        parsed = json.loads(schemas) if isinstance(schemas, str) else schemas
    except Exception:
        parsed = None
    if not isinstance(parsed, list):
        return func.HttpResponse(
            json.dumps({"error": "Schemas not available"}, ensure_ascii=False),
            status_code=500,
            mimetype="application/json",
        )

    def get_id(e: dict) -> str:
        return str(e.get("Id") or e.get("id") or "").strip()

    schema_entity = next((e for e in parsed if get_id(e) == schema_id), None)
    if not schema_entity:
        return func.HttpResponse(
            json.dumps({"error": "Schema not found"}, ensure_ascii=False),
            status_code=404,
            mimetype="application/json",
        )

    schema = Schema(id=schema_entity.get("id"), entity=schema_entity)

    partition_key = utils.today_partition_key()
    requested_at = utils.format_requested_at()

    log_entity = build_log_entry(
        status="rejected",
        partition_key=partition_key,
        row_key=str(uuid.uuid4()),
        exec_id=execId,
        requested_at=requested_at,
        name=schema.name or "",
        schema_id=schema.id,
        runbook=schema.runbook,
        run_args=schema.run_args,
        worker=schema.worker,
        log_msg=json.dumps({"message": "Rejected by approver"}, ensure_ascii=False),
        oncall=schema.oncall,
        monitor_condition=monitor_condition,
        severity=severity,
        approval_required=True,
        approval_decision_by=approver,
    )
    log_table.set(json.dumps(log_entity, ensure_ascii=False))

    log_audit(
        user=approver,
        action="RUNBOOK_REJECT",
        target=execId,
        details=f"Runbook: {schema.runbook}, Schema: {schema.id}",
    )

    # smart routing notification (if routing module available)
    if route_alert and execute_actions:
        ctx = {
            "resourceId": ((resource_info or {}).get("resource_id") or ""),
            "resourceGroup": ((resource_info or {}).get("resource_group") or ""),
            "resourceName": ((resource_info or {}).get("resource_name") or ""),
            "alertRule": (schema.name or ""),
            "severity": severity,
            "namespace": ((resource_info or {}).get("namespace") or ""),
            "oncall": schema.oncall,
            "status": "rejected",
            "execId": execId,
            "name": schema.name or "",
            "id": schema.id,
            "routing_info": routing_info,
        }
        decision = route_alert(ctx)
        logging.debug(f"[{execId}] Reject: {decision}")

        payload = {
            "slack": {
                "message": f"[{execId}] ⛔️ Rejected - {schema_id}",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"⛔️ Rejected - {schema_id}",
                            "emoji": True,
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"*ExecId:* `{execId}`\n"
                                f"*SchemaId:* `{schema_id}`\n"
                                f"*By:* {approver}"
                            ),
                        },
                    },
                    *(
                        [
                            {
                                "type": "context",
                                "elements": [
                                    {"type": "mrkdwn", "text": "*Status:* rejected"}
                                ],
                            }
                        ]
                        if "rejected"
                        else []
                    ),
                ],
            }
        }
        try:
            execute_actions(
                decision,
                payload,
                send_slack_fn=lambda token, channel, **kw: send_slack_execution(
                    token=token, channel=channel, **kw
                ),
            )
        except Exception as e:
            logging.error(f"[{execId}] smart routing approval failed: {e}")

    html = render_template(
        "reject.html",
        {
            "execId": execId,
            "schema_id": schema_id,
            "approver": approver or "-",
            "requested_at": requested_at,
        },
    )

    return func.HttpResponse(
        html,
        status_code=200,
        mimetype="text/html",
        headers={
            "Content-Type": "text/html",
            "Access-Control-Allow-Origin": "*",
        },
    )


# =========================
# HTTP Function: receiver
# =========================


@app.queue_trigger(
    arg_name="msg", queue_name=NOTIFICATION_QUEUE_NAME, connection=STORAGE_CONNECTION
)
@app.table_output(
    arg_name="log_table",
    table_name=TABLE_NAME,
    connection=STORAGE_CONN,
)
def Receiver(msg: func.QueueMessage, log_table: func.Out[str]) -> None:
    import utils
    from escalation import (
        format_opsgenie_description,
        send_opsgenie_alert,
        send_slack_execution,
    )

    try:
        from smart_routing import execute_actions, route_alert
    except ImportError:
        route_alert = None
        execute_actions = None

    try:
        body = json.loads(msg.get_body().decode("utf-8"))
    except Exception as e:
        logging.error(f"[Receiver] Invalid queue message: {e}")
        return

    required_fields = ["exec_id", "status", "name", "id", "runbook"]
    missing = [k for k in required_fields if not (body.get(k) or "").strip()]
    if missing:
        logging.warning(f"[{body.get('exec_id')}] Missing required fields: {missing}")
        return

    logging.info(
        f"[{body.get('exec_id')}] Receiver invoked",
        extra={
            "headers": {
                "ExecId": body.get("exec_id"),
                "Status": body.get("status"),
                "Name": body.get("name"),
                "Id": body.get("id"),
                "Runbook": body.get("runbook"),
                "Run_Args": body.get("run_args"),
                "OnCall": body.get("oncall"),
                "MonitorCondition": body.get("monitor_condition"),
                "Severity": body.get("severity"),
            }
        },
    )

    requested_at = utils.format_requested_at()
    partition_key = utils.today_partition_key()
    row_key = str(uuid.uuid4())
    status_label = resolve_status(body.get("status"))

    logs_raw = ""
    try:
        logs_raw = decode_base64(body.get("logs_b64") or "")
    except Exception:
        logs_raw = ""
    log_entity = build_log_entry(
        status=status_label,
        partition_key=partition_key,
        row_key=row_key,
        exec_id=body.get("exec_id"),
        requested_at=requested_at,
        name=body.get("name"),
        schema_id=body.get("id"),
        runbook=body.get("runbook"),
        run_args=body.get("run_args"),
        worker=body.get("worker"),
        log_msg=utils._truncate_for_table(logs_raw, MAX_TABLE_CHARS),
        oncall=body.get("oncall"),
        monitor_condition=body.get("monitor_condition"),
        severity=body.get("severity"),
    )
    log_table.set(json.dumps(log_entity, ensure_ascii=False))

    # TODO check if can be deprecated
    if status_label == "running":
        logging.debug(f"[{body.get('exec_id')}] Status 'running' logged to table")
        return

    resource_info = body.get("resource_info") or {}
    routing_info = body.get("routing_info") or {}
    if isinstance(resource_info, str):
        try:
            parsed = json.loads(resource_info)
            resource_info = parsed if isinstance(parsed, dict) else {}
        except Exception:
            resource_info = {}
    if isinstance(routing_info, str):
        try:
            parsed = json.loads(routing_info)
            routing_info = parsed if isinstance(parsed, dict) else {}
        except Exception:
            routing_info = {}

    resource_id = (body.get("resource_id") or "") or (
        resource_info.get("resource_id") or ""
    )
    resource_group = (body.get("resource_group") or "") or (
        resource_info.get("resource_rg") or ""
    )
    resource_name = (body.get("resource_name") or "") or (
        resource_info.get("resource_name") or ""
    )
    namespace = (body.get("namespace") or "") or (
        resource_info.get("aks_namespace") or ""
    )

    if route_alert and execute_actions:
        exec_id = body.get("exec_id")
        ctx = {
            "resourceId": resource_id or None,
            "resourceGroup": resource_group or None,
            "resourceName": resource_name or None,
            "alertRule": body.get("name"),
            "severity": body.get("severity"),
            "namespace": namespace or None,
            "oncall": (body.get("oncall") or "").strip().lower(),
            "status": status_label,
            "execId": exec_id,
            "name": body.get("name"),
            "id": body.get("id"),
            "routing_info": routing_info,  # sempre dict qui
        }
        decision = route_alert(ctx)
        logging.debug(f"[{exec_id}] {decision}")
        status_emojis = {
            "succeeded": "✅",
            "running": "🏃",
            "skipped": "⏭️",
            "routed": "🧭",
            "error": "❌",
            "failed": "❌",
        }
        status_emoji = status_emojis.get(status_label, "ℹ️")
        payload = {
            "slack": {
                "message": f"[{exec_id}] Status: {status_label}: {body.get('name')}",
                "blocks": [
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
                            {"type": "mrkdwn", "text": f"*Name:*\n{body.get('name')}"},
                            {"type": "mrkdwn", "text": f"*Id:*\n{body.get('id')}"},
                            {"type": "mrkdwn", "text": f"*ExecId:*\n{exec_id}"},
                            {"type": "mrkdwn", "text": f"*Status:*\n{status_label}"},
                            {
                                "type": "mrkdwn",
                                "text": f"*Severity:*\n{body.get('severity')}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*OnCall:*\n{body.get('oncall')}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Worker*:\n{body.get('worker') or 'unknown(?)'}",
                            },
                        ],
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Runbook:*\n{body.get('runbook')}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*MonitorCondition:*\n{body.get('monitor_condition')}",
                            },
                        ],
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Run Args:*\n```{body.get('run_args')}```",
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Logs (truncated):*\n```{(logs_raw or '')[:1500]}```",
                        },
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Severity:* {body.get('severity')}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Teams:* {', '.join(dict.fromkeys(a.team for a in decision.actions if getattr(a, 'team', None)))}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"Timestamp: <!date^{int(__import__('time').time())}^{{date_short}} {{time}}|now>",
                            },
                        ],
                    },
                    {"type": "divider"},
                ],
            },
            "opsgenie": {
                "message": f"[{body.get('id')}] [{body.get('severity')}] {body.get('name')}",
                "priority": f"P{int(str(body.get('severity') or '').strip().lower().replace('sev', '') or '4') + 1}",
                "alias": body.get("id"),
                "monitor_condition": body.get("monitor_condition") or "",
                "details": {
                    "Name": body.get("name"),
                    "Id": body.get("id"),
                    "ExecId": exec_id,
                    "Status": body.get("status"),
                    "Runbook": body.get("runbook"),
                    "Run_Args": body.get("run_args"),
                    "Worker": body.get("worker"),
                    "OnCall": body.get("oncall"),
                    "MonitorCondition": body.get("monitor_condition"),
                    "Severity": body.get("severity"),
                    "Teams:": ", ".join(
                        dict.fromkeys(
                            a.team for a in decision.actions if getattr(a, "team", None)
                        )
                    ),
                },
                "description": f"{format_opsgenie_description(exec_id, resource_info, utils._truncate_for_table(logs_raw, MAX_TABLE_CHARS or ''))}",
            },
        }
        try:
            execute_actions(
                decision,
                payload,
                send_slack_fn=lambda token, channel, **kw: send_slack_execution(
                    token=token, channel=channel, **kw
                ),
                send_opsgenie_fn=lambda api_key, **kw: send_opsgenie_alert(
                    api_key=api_key, **kw
                ),
            )
        except Exception as e:
            logging.error(f"[{exec_id}] smart routing failed: {e}")
    else:
        logging.warning("Routing module not available, keeping legacy notifications")


# =========================
# Heartbeat
# =========================


@app.route(route="healthz", auth_level=AUTH)
def heartbeat(req: func.HttpRequest) -> func.HttpResponse:
    import utils

    now_utc = utils.utc_now_iso()
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
    Returns the entity from the RunbookLogs table identified by PartitionKey and RowKey.
    Uso: GET /api/logs/{partitionKey}/{execId}
    """
    if req.method == "OPTIONS":
        return create_cors_response()

    # Security: check session token
    session, error_res = _get_authenticated_user(req)
    if error_res:
        return error_res

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


@app.route(route="logs", auth_level=func.AuthLevel.ANONYMOUS)
@app.table_input(
    arg_name="workers", table_name="WorkersRegistry", connection=STORAGE_CONNECTION
)
# ruff: noqa
def logs_frontend(req: func.HttpRequest, workers: str) -> func.HttpResponse:
    from frontend import render_template
    from requests import request

    # --- 1. Key Extraction ---
    candidate_key = req.headers.get("x-functions-key") or req.params.get("code")

    if not candidate_key:
        cookie_header = req.headers.get("Cookie")
        if cookie_header:
            parts = cookie_header.split(";")
            for part in parts:
                clean_part = part.strip()
                if clean_part.startswith("x-functions-key="):
                    candidate_key = clean_part.split("=", 1)[1]
                    break

    # --- 2. Key Validation ---
    is_valid = False

    if candidate_key:
        # Build the test URL
        # req.url is the full current URL. Remove everything after /api/
        base_url = str(req.url).split("/api/")[0]
        if "localhost:7071" in base_url:
            base_url = base_url.replace(":7071", ":80")

        check_url = f"{base_url}/api/healthz"

        try:
            res = request(
                method="GET",
                url=check_url,
                headers={"x-functions-key": candidate_key},
                timeout=5,
            )
            if res.status_code == 200:
                is_valid = True
            else:
                logging.warning(f"Key present but invalid. Status: {res.status_code}")
        except Exception as e:
            logging.error(f"Key validation error: {e}")

    # --- 3. Response ---

    if is_valid:
        try:
            workers = json.loads(workers) if isinstance(workers, str) else workers
            workers = list({w.get("RowKey") for w in workers if w.get("RowKey")})
        except Exception as e:
            logging.warning(f"Error parsing workers: {e}")
        code_js = json.dumps(candidate_key or "")
        html = render_template(
            "logs.html",
            {
                "code_js": code_js,
                "workers": workers,
            },
        )
        return func.HttpResponse(html, status_code=200, mimetype="text/html")

    else:
        error_msg = ""
        if candidate_key:
            error_msg = (
                "<p style='color: red; font-weight: bold;'>Invalid or expired key.</p>"
            )

        login_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Login Required</title>
            <style>
                body {{ font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background-color: #f4f4f4; margin: 0; }}
                .login-box {{ background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; width: 300px; }}
                input {{ width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }}
                button {{ width: 100%; padding: 10px; background-color: #0078d4; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; }}
                button:hover {{ background-color: #0063b1; }}
            </style>
        </head>
        <body>
            <div class="login-box">
                <h2>Access Logs</h2>
                {error_msg}
                <form onsubmit="doLogin(event)">
                    <input type="password" id="key" placeholder="Function Key" required>
                    <button type="submit">Login</button>
                </form>
            </div>
            <script>
                function doLogin(e) {{
                    e.preventDefault();
                    const val = document.getElementById('key').value;

                    const d = new Date();
                    d.setTime(d.getTime() + (1*24*60*60*100)); // 1 day

                    // Fix for localhost vs Azure
                    const isSecure = window.location.protocol === 'https:' ? '; Secure' : '';

                    document.cookie = "x-functions-key=" + val + "; expires=" + d.toUTCString() + "; path=/; SameSite=Lax" + isSecure;

                    window.location.reload();
                }}
            </script>
        </body>
        </html>
        """
        return func.HttpResponse(login_html, status_code=200, mimetype="text/html")


# TODO Manage empty partitions
# @app.table_input(
#     arg_name="rows",
#     table_name=TABLE_NAME,
#     partition_key="{partitionKey}",
#     connection=STORAGE_CONN,
# )
@app.route(
    route="logs/query",
    methods=[func.HttpMethod.GET, func.HttpMethod.OPTIONS],
    auth_level=AUTH,
)
def logs_query(req: func.HttpRequest) -> func.HttpResponse:
    """
    Query dei log via Table Input Binding:
    - partitionKey (required) -> used for the binding
    - execId, status -> filtered by memory
    - q (contains on some filed), from/to (range on RequestedAt), order, limit -> in memory
    """
    if req.method == "OPTIONS":
        return create_cors_response()

    # Security: check session token
    session, error_res = _get_authenticated_user(req)
    if error_res:
        return error_res

    from azure.data.tables import TableClient

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

        conn_str = os.environ.get(STORAGE_CONN)
        table_client = TableClient.from_connection_string(
            conn_str, table_name=TABLE_NAME
        )

        filter_query = f"PartitionKey eq '{partition_key}'"
        if exec_id:
            filter_query += f" and ExecId eq '{exec_id}'"

        try:
            entities = table_client.query_entities(query_filter=filter_query)
            data = list(entities)
        except Exception as e:
            logging.error(f"Table query failed: {e}")
            return func.HttpResponse(
                json.dumps(
                    {"error": "Failed to fetch data from storage"}, ensure_ascii=False
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
        return func.HttpResponse(
            body,
            status_code=200,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
            },
        )

    except Exception as e:
        logging.exception("logs_query (binding) failed")
        return func.HttpResponse(
            json.dumps({"error": str(e)}, ensure_ascii=False),
            status_code=500,
            mimetype="application/json",
        )


@app.route(
    route="workers/register",
    methods=[func.HttpMethod.POST],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def register_worker(req: func.HttpRequest) -> func.HttpResponse:
    import utils
    from azure.data.tables import TableClient, UpdateMode

    expected_key = os.environ.get("CLOUDO_SECRET_KEY")
    request_key = req.headers.get("x-cloudo-key")

    if not expected_key or request_key != expected_key:
        return func.HttpResponse(
            json.dumps({"error": "Unauthorized"}, ensure_ascii=False),
            status_code=401,
            mimetype="application/json",
        )

    try:
        body = req.get_json()

        capability = (body.get("capability") or body.get("id") or "").strip()
        worker_instance_id = (body.get("worker_id") or "").strip()
        worker_queue = body.get("queue")

        if not capability or not worker_queue or not worker_instance_id:
            return func.HttpResponse(
                "Missing capability, worker_id or url", status_code=400
            )

        conn_str = os.environ.get("AzureWebJobsStorage")
        table_client = TableClient.from_connection_string(
            conn_str, table_name="WorkersRegistry"
        )

        entity = {
            "PartitionKey": capability,
            "RowKey": worker_instance_id,
            "Queue": worker_queue,
            "LastSeen": utils.utc_now_iso(),
            "Region": body.get("region", "default"),
            "Load": body.get("load", 0),
        }

        table_client.upsert_entity(entity=entity, mode=UpdateMode.REPLACE)

        return func.HttpResponse(
            json.dumps({"status": "registered", "timestamp": entity["LastSeen"]}),
            status_code=200,
        )

    except Exception as e:
        logging.error(f"Register failed: {e}")
        return func.HttpResponse(str(e), status_code=500)


@app.route(
    route="workers",
    methods=[func.HttpMethod.GET, func.HttpMethod.OPTIONS],
    auth_level=func.AuthLevel.ANONYMOUS,
)
@app.table_input(
    arg_name="workers",
    table_name=TABLE_WORKERS_SCHEMAS,
    connection=STORAGE_CONN,
)
def list_workers(req: func.HttpRequest, workers: str) -> func.HttpResponse:
    """
    Returns the list of registered workers available in the registry.
    """
    if req.method == "OPTIONS":
        return create_cors_response()

    # Security: check session token
    session, error_res = _get_authenticated_user(req)
    if error_res:
        return error_res

    try:
        # Parse binding result (can be string or list depending on extension version)
        data = json.loads(workers) if isinstance(workers, str) else (workers or [])

        return func.HttpResponse(
            json.dumps(data, ensure_ascii=False),
            status_code=200,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
            },
        )
    except Exception as e:
        logging.error(f"Failed to list workers: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}, ensure_ascii=False),
            status_code=500,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
            },
        )


@app.route(
    route="workers/processes",
    methods=[func.HttpMethod.GET, func.HttpMethod.OPTIONS],
    auth_level=AUTH,
)
def get_worker_processes(req: func.HttpRequest) -> func.HttpResponse:
    """
    Proxy endpoint: calls the worker API from the backend.
    Expected param: worker (hostname/ip:port)
    """
    import requests

    if req.method == "OPTIONS":
        return create_cors_response()

    # Security: check session token
    session, error_res = _get_authenticated_user(req)
    if error_res:
        return error_res

    worker = req.params.get("worker")
    if not worker:
        return func.HttpResponse(
            json.dumps({"error": "Missing 'worker' param"}, ensure_ascii=False),
            status_code=400,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
            },
        )

    # Construct target URL (assuming http protocol for internal workers)
    # If your workers use https or a specific port logic, adjust here.
    if os.getenv("FEATURE_DEV", "false").lower() != "true":
        target_url = f"https://{worker}.azurewebsites.net/api/processes"
    else:
        target_url = f"http://{worker}/api/processes"

    try:
        # Timeout short to avoid blocking the orchestrator for too long
        resp = requests.get(
            target_url,
            headers={"x-cloudo-key": os.getenv("CLOUDO_SECRET_KEY")},
            timeout=5,
        )
        return func.HttpResponse(
            resp.text,
            status_code=resp.status_code,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
            },
        )
    except Exception as e:
        logging.error(f"Failed to proxy processes for {worker}: {e}")
        return func.HttpResponse(
            json.dumps(
                {"error": f"Failed to reach worker: {str(e)}"}, ensure_ascii=False
            ),
            status_code=502,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
            },
        )


@app.route(
    route="auth/login",
    methods=[func.HttpMethod.POST, func.HttpMethod.OPTIONS],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def auth_login(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return create_cors_response()

    body = req.get_json()
    try:
        from azure.data.tables import TableClient

        username = body.get("username")
        password = body.get("password")

        if not username or not password:
            return func.HttpResponse(
                json.dumps({"error": "Username and password required"}),
                status_code=400,
                mimetype="application/json",
                headers={"Access-Control-Allow-Origin": "*"},
            )

        conn_str = os.environ.get(STORAGE_CONN)
        table_client = TableClient.from_connection_string(
            conn_str, table_name=TABLE_USERS
        )

        user_entity = table_client.get_entity(
            partition_key="Operator", row_key=username
        )

        import bcrypt

        db_password = user_entity.get("password")
        is_valid = False

        if db_password:
            # Check if it's already hashed (bcrypt hashes start with $2b$ or $2a$)
            if db_password.startswith("$2b$") or db_password.startswith("$2a$"):
                try:
                    if bcrypt.checkpw(
                        password.encode("utf-8"), db_password.encode("utf-8")
                    ):
                        is_valid = True
                except Exception as e:
                    logging.warning(f"Bcrypt check failed: {e}")
            else:
                # Fallback for plain text (for migration period)
                if db_password == password:
                    is_valid = True
                    # Optional: auto-migrate to hash here if we have the plain password
                    try:
                        hashed = bcrypt.hashpw(
                            password.encode("utf-8"), bcrypt.gensalt()
                        ).decode("utf-8")
                        user_entity["password"] = hashed
                        table_client.update_entity(entity=user_entity)
                        logging.info(f"User {username} password migrated to hash")
                    except Exception as e:
                        logging.error(f"Failed to migrate password for {username}: {e}")

        if is_valid:
            log_audit(
                user=user_entity.get("RowKey"),
                action="USER_LOGIN_SUCCESS",
                target=user_entity.get("email"),
                details=f"user: {user_entity.get('RowKey')}, email: {user_entity.get('email')}, role: {user_entity.get('role')}",
            )
            # Token expiration (e.g. 8 hours)
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()

            # Create session token
            session_token = _create_session_token(
                username=user_entity.get("RowKey"),
                role=user_entity.get("role"),
                expires_at=expires_at,
            )

            return func.HttpResponse(
                json.dumps(
                    {
                        "success": True,
                        "user": {
                            "username": user_entity.get("RowKey"),
                            "email": user_entity.get("email"),
                            "role": user_entity.get("role"),
                        },
                        "expires_at": expires_at,
                        "token": session_token,
                    }
                ),
                status_code=200,
                mimetype="application/json",
                headers={"Access-Control-Allow-Origin": "*"},
            )
        else:
            return func.HttpResponse(
                json.dumps({"error": "Invalid credentials"}),
                status_code=401,
                mimetype="application/json",
                headers={"Access-Control-Allow-Origin": "*"},
            )
    except Exception as e:
        logging.error(f"Login error: {e}")
        log_audit(
            user=body.get("username"),
            action="USER_LOGIN_FAILED",
            target=body.get("username"),
            details=f"user: {body.get('username')}",
        )

        return func.HttpResponse(
            json.dumps({"error": "Authentication failed"}),
            status_code=401,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"},
        )


@app.route(
    route="users",
    methods=[
        func.HttpMethod.GET,
        func.HttpMethod.POST,
        func.HttpMethod.DELETE,
        func.HttpMethod.OPTIONS,
    ],
    auth_level=AUTH,
)
def users_management(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return create_cors_response()

    from azure.data.tables import TableClient, UpdateMode

    conn_str = os.environ.get(STORAGE_CONN)
    table_client = TableClient.from_connection_string(conn_str, table_name=TABLE_USERS)

    # Verification of admin role
    # Security: check session token
    session, error_res = _get_authenticated_user(req)
    if error_res:
        return error_res

    if session.get("role") != "ADMIN":
        return func.HttpResponse(
            json.dumps({"error": "Unauthorized: Admin role required"}),
            status_code=403,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    if req.method == "GET":
        try:
            entities = table_client.query_entities(
                query_filter="PartitionKey eq 'Operator'"
            )
            users = []
            for e in entities:
                users.append(
                    {
                        "username": e.get("RowKey"),
                        "email": e.get("email"),
                        "role": e.get("role"),
                        "created_at": e.get("created_at"),
                    }
                )
            return func.HttpResponse(
                json.dumps(users),
                status_code=200,
                mimetype="application/json",
                headers={"Access-Control-Allow-Origin": "*"},
            )
        except Exception:
            return func.HttpResponse(
                json.dumps([]),
                status_code=200,
                headers={"Access-Control-Allow-Origin": "*"},
            )

    if req.method == "POST":
        try:
            body = req.get_json()
            username = body.get("username")
            if not username:
                return func.HttpResponse("Missing username", status_code=400)

            # Check if user exists to preserve created_at
            try:
                existing_user = table_client.get_entity(
                    partition_key="Operator", row_key=username
                )
                created_at = existing_user.get("created_at")
                # If password is not provided in body, keep the old one
                password = body.get("password") or existing_user.get("password")
            except Exception:
                created_at = datetime.now(timezone.utc).isoformat()
                password = body.get("password")

            import bcrypt

            # If password is provided and doesn't look like a bcrypt hash, hash it
            if password and not (
                password.startswith("$2b$") or password.startswith("$2a$")
            ):
                password = bcrypt.hashpw(
                    password.encode("utf-8"), bcrypt.gensalt()
                ).decode("utf-8")

            entity = {
                "PartitionKey": "Operator",
                "RowKey": username,
                "password": password,
                "email": body.get("email"),
                "role": body.get("role", "OPERATOR"),
                "created_at": created_at,
            }
            table_client.upsert_entity(entity=entity, mode=UpdateMode.REPLACE)

            # Audit log
            log_audit(
                user=session.get("username") or "SYSTEM",
                action="USER_ENROLL" if not body.get("created_at") else "USER_UPDATE",
                target=username,
                details=f"Role: {body.get('role')}, Email: {body.get('email')}",
            )

            return func.HttpResponse(
                json.dumps({"success": True}),
                status_code=200,
                headers={"Access-Control-Allow-Origin": "*"},
            )
        except Exception as e:
            return func.HttpResponse(
                json.dumps({"error": str(e)}),
                status_code=500,
                headers={"Access-Control-Allow-Origin": "*"},
            )

    if req.method == "DELETE":
        try:
            username = req.params.get("username")
            if not username:
                return func.HttpResponse("Missing username", status_code=400)
            table_client.delete_entity(partition_key="Operator", row_key=username)

            # Audit log
            log_audit(
                user=session.get("username") or "SYSTEM",
                action="USER_REVOKE",
                target=username,
                details="Identity destroyed",
            )

            return func.HttpResponse(
                json.dumps({"success": True}),
                status_code=200,
                headers={"Access-Control-Allow-Origin": "*"},
            )
        except Exception as e:
            return func.HttpResponse(
                json.dumps({"error": str(e)}),
                status_code=500,
                headers={"Access-Control-Allow-Origin": "*"},
            )


@app.route(
    route="settings",
    methods=[func.HttpMethod.GET, func.HttpMethod.POST, func.HttpMethod.OPTIONS],
    auth_level=AUTH,
)
def settings_management(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return create_cors_response()

    from azure.data.tables import TableClient

    conn_str = os.environ.get(STORAGE_CONN)
    table_client = TableClient.from_connection_string(
        conn_str, table_name=TABLE_SETTINGS
    )

    # Verification of admin role
    session, error_res = _get_authenticated_user(req)
    if error_res:
        return error_res

    if session.get("role") != "ADMIN":
        return func.HttpResponse(
            json.dumps({"error": "Unauthorized: Admin role required"}),
            status_code=403,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    if req.method == "GET":
        try:
            entities = table_client.query_entities(
                query_filter="PartitionKey eq 'GlobalConfig'"
            )
            settings = {e["RowKey"]: e["value"] for e in entities}
            return func.HttpResponse(
                json.dumps(settings),
                status_code=200,
                mimetype="application/json",
                headers={"Access-Control-Allow-Origin": "*"},
            )
        except Exception:
            return func.HttpResponse(
                json.dumps({}),
                status_code=200,
                headers={"Access-Control-Allow-Origin": "*"},
            )

    if req.method == "POST":
        try:
            body = req.get_json()
            for key, value in body.items():
                entity = {
                    "PartitionKey": "GlobalConfig",
                    "RowKey": key,
                    "value": str(value),
                }
                table_client.upsert_entity(entity=entity)

            log_audit(
                user=session.get("username") or "SYSTEM",
                action="SETTINGS_UPDATE",
                target="GLOBAL_CONFIG",
                details=str(list(body.keys())),
            )
            return func.HttpResponse(
                json.dumps({"success": True}),
                status_code=200,
                headers={"Access-Control-Allow-Origin": "*"},
            )
        except Exception as e:
            return func.HttpResponse(
                json.dumps({"error": str(e)}),
                status_code=500,
                headers={"Access-Control-Allow-Origin": "*"},
            )


@app.route(
    route="audit",
    methods=[func.HttpMethod.GET, func.HttpMethod.OPTIONS],
    auth_level=AUTH,
)
def get_audit_logs(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return create_cors_response()

    from azure.data.tables import TableClient

    conn_str = os.environ.get(STORAGE_CONN)
    table_client = TableClient.from_connection_string(conn_str, table_name=TABLE_AUDIT)

    # Verification of admin role
    session, error_res = _get_authenticated_user(req)
    if error_res:
        return error_res

    if session.get("role") != "ADMIN":
        return func.HttpResponse(
            json.dumps({"error": "Unauthorized: Admin role required"}),
            status_code=403,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    try:
        entities = table_client.query_entities(query_filter="")
        logs = []
        for e in entities:
            logs.append(
                {
                    "timestamp": e.get("timestamp"),
                    "operator": e.get("operator"),
                    "action": e.get("action"),
                    "target": e.get("target"),
                    "details": e.get("details"),
                }
            )
        # Sort by timestamp descending
        logs.sort(key=lambda x: x["timestamp"] or "", reverse=True)
        return func.HttpResponse(
            json.dumps(logs[:100]),
            status_code=200,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"},
        )
    except Exception:
        return func.HttpResponse(
            json.dumps([]),
            status_code=200,
            headers={"Access-Control-Allow-Origin": "*"},
        )


@app.route(
    route="schedules",
    methods=[
        func.HttpMethod.GET,
        func.HttpMethod.POST,
        func.HttpMethod.DELETE,
        func.HttpMethod.OPTIONS,
    ],
    auth_level=AUTH,
)
def schedules_management(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return create_cors_response()

    from azure.data.tables import TableClient, UpdateMode

    conn_str = os.environ.get(STORAGE_CONN)
    table_client = TableClient.from_connection_string(
        conn_str, table_name=TABLE_SCHEDULES
    )

    # Verification of authentication
    session, error_res = _get_authenticated_user(req)
    if error_res:
        return error_res

    if req.method == "GET":
        try:
            entities = table_client.query_entities(
                query_filter="PartitionKey eq 'Schedule'"
            )
            schedules = []
            for e in entities:
                schedules.append(
                    {
                        "id": e.get("RowKey"),
                        "name": e.get("name"),
                        "cron": e.get("cron"),
                        "runbook": e.get("runbook"),
                        "run_args": e.get("run_args"),
                        "queue": e.get("queue"),
                        "worker_pool": e.get("worker_pool"),
                        "enabled": e.get("enabled"),
                        "last_run": e.get("last_run"),
                    }
                )
            return func.HttpResponse(
                json.dumps(schedules),
                status_code=200,
                mimetype="application/json",
                headers={"Access-Control-Allow-Origin": "*"},
            )
        except Exception:
            return func.HttpResponse(
                json.dumps([]),
                status_code=200,
                headers={"Access-Control-Allow-Origin": "*"},
            )

    if req.method == "POST":
        try:
            body = req.get_json()
            schedule_id = body.get("id") or str(uuid.uuid4())

            entity = {
                "PartitionKey": "Schedule",
                "RowKey": schedule_id,
                "name": body.get("name"),
                "cron": body.get("cron"),
                "runbook": body.get("runbook"),
                "run_args": body.get("run_args"),
                "queue": body.get("queue"),
                "worker_pool": body.get("worker_pool"),
                "enabled": body.get("enabled", True),
                "last_run": body.get("last_run", ""),
            }
            table_client.upsert_entity(entity=entity, mode=UpdateMode.REPLACE)

            log_audit(
                user=session.get("username") or "SYSTEM",
                action="SCHEDULE_UPSERT",
                target=schedule_id,
                details=f"Name: {body.get('name')}, Cron: {body.get('cron')}",
            )
            return func.HttpResponse(
                json.dumps({"success": True, "id": schedule_id}),
                status_code=200,
                headers={"Access-Control-Allow-Origin": "*"},
            )
        except Exception as e:
            return func.HttpResponse(
                json.dumps({"error": str(e)}),
                status_code=500,
                headers={"Access-Control-Allow-Origin": "*"},
            )

    if req.method == "DELETE":
        try:
            schedule_id = req.params.get("id")
            if not schedule_id:
                return func.HttpResponse(
                    json.dumps({"error": "Missing id"}),
                    status_code=400,
                    headers={"Access-Control-Allow-Origin": "*"},
                )

            table_client.delete_entity(partition_key="Schedule", row_key=schedule_id)
            log_audit(
                user=session.get("username") or "SYSTEM",
                action="SCHEDULE_DELETE",
                target=schedule_id,
            )
            return func.HttpResponse(
                json.dumps({"success": True}),
                status_code=200,
                headers={"Access-Control-Allow-Origin": "*"},
            )
        except Exception as e:
            return func.HttpResponse(
                json.dumps({"error": str(e)}),
                status_code=500,
                headers={"Access-Control-Allow-Origin": "*"},
            )


@app.route(
    route="workers/stop",
    methods=[func.HttpMethod.POST, func.HttpMethod.OPTIONS],
    auth_level=AUTH,
)
def stop_worker_process(req: func.HttpRequest) -> func.HttpResponse:
    """
    Proxy endpoint: calls the worker STOP API from the backend.
    Expected param: worker (hostname/ip:port), exec_id
    """
    import requests

    logging.info(f"Stop worker process requested. Params: {req.params}")

    if req.method == "OPTIONS":
        return create_cors_response()

    # Security: check session token
    session, error_res = _get_authenticated_user(req)
    if error_res:
        return error_res
    worker = req.params.get("worker")
    exec_id = req.params.get("exec_id")

    if not worker or not exec_id:
        return func.HttpResponse(
            json.dumps(
                {"error": "Missing 'worker' or 'exec_id' param"}, ensure_ascii=False
            ),
            status_code=400,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
            },
        )

    if os.getenv("FEATURE_DEV", "false").lower() != "true":
        target_url = (
            f"https://{worker}.azurewebsites.net/api/processes/stop?exec_id={exec_id}"
        )
    else:
        target_url = f"http://{worker}/api/processes/stop?exec_id={exec_id}"

    try:
        resp = requests.delete(
            target_url,
            headers={"x-cloudo-key": os.getenv("CLOUDO_SECRET_KEY")},
            timeout=5,
        )
        return func.HttpResponse(
            resp.text,
            status_code=resp.status_code,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
            },
        )
    except Exception as e:
        logging.error(f"Failed to proxy stop for {worker}/{exec_id}: {e}")
        return func.HttpResponse(
            json.dumps(
                {"error": f"Failed to reach worker: {str(e)}"}, ensure_ascii=False
            ),
            status_code=502,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
            },
        )


@app.route(
    route="schemas",
    methods=[
        func.HttpMethod.GET,
        func.HttpMethod.POST,
        func.HttpMethod.OPTIONS,
        func.HttpMethod.DELETE,
        func.HttpMethod.PUT,
    ],
    auth_level=AUTH,
)
@app.table_input(arg_name="entities", table_name=TABLE_SCHEMAS, connection=STORAGE_CONN)
@app.table_output(
    arg_name="outputTable", table_name=TABLE_SCHEMAS, connection=STORAGE_CONN
)
def runbook_schemas(
    req: func.HttpRequest, entities: str, outputTable: func.Out[str]
) -> func.HttpResponse:
    logging.info(f"Processing {req.method} request for schemas.")

    if req.method == "OPTIONS":
        return create_cors_response()

    session, error_res = _get_authenticated_user(req)
    if error_res:
        return error_res

    requester_username = session.get("username")
    # OPERATOR and ADMIN can manage schemas

    if req.method == "GET":
        try:
            schemas_data = json.loads(entities)
            logging.info(f"schemas: {str(schemas_data)}")

            return func.HttpResponse(
                body=json.dumps(schemas_data),
                status_code=200,
                mimetype="application/json",
                headers={
                    "Access-Control-Allow-Origin": "*",
                },
            )
        except Exception as e:
            logging.error(f"Error processing schemas: {str(e)}")
            return func.HttpResponse(
                body=json.dumps({"error": "Failed to fetch schemas"}),
                status_code=500,
                mimetype="application/json",
            )

    if req.method == "POST":
        try:
            body = req.get_json()

            schema_id = body.get("id", str(uuid.uuid4()))
            new_entity = {
                "PartitionKey": body.get("PartitionKey", "RunbookSchema"),
                "RowKey": schema_id,
                **body,
            }

            outputTable.set(json.dumps(new_entity))

            # Audit log
            log_audit(
                user=requester_username or "SYSTEM",
                action="SCHEMA_CREATE",
                target=schema_id,
                details=f"Name: {body.get('name')}, Runbook: {body.get('runbook')}",
            )

            return func.HttpResponse(
                body=json.dumps(new_entity),
                status_code=201,
                mimetype="application/json",
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Content-Type": "application/json",
                },
            )
        except Exception as e:
            logging.error(f"Error creating schema: {str(e)}")
            return func.HttpResponse(
                body=json.dumps({"error": "Failed to create schema"}),
                status_code=400,
                mimetype="application/json",
                headers={
                    "Access-Control-Allow-Origin": "*",
                },
            )

    if req.method == "PUT":
        try:
            from azure.data.tables import TableClient, UpdateMode

            body = req.get_json()
            schema_id = body.get("id")

            if not schema_id:
                return func.HttpResponse(
                    body=json.dumps({"error": "Missing 'id' field"}),
                    status_code=400,
                    mimetype="application/json",
                    headers={
                        "Access-Control-Allow-Origin": "*",
                    },
                )

            updated_entity = {
                "PartitionKey": body.get("PartitionKey", "RunbookSchema"),
                "RowKey": schema_id,
                **body,
            }

            conn_str = os.environ.get(STORAGE_CONN)
            table_client = TableClient.from_connection_string(
                conn_str, table_name=TABLE_SCHEMAS
            )
            table_client.upsert_entity(entity=updated_entity, mode=UpdateMode.REPLACE)

            # Audit log
            log_audit(
                user=requester_username or "SYSTEM",
                action="SCHEMA_UPDATE",
                target=schema_id,
                details=f"Name: {body.get('name')}",
            )

            return func.HttpResponse(
                body=json.dumps(updated_entity),
                status_code=200,
                mimetype="application/json",
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Content-Type": "application/json",
                },
            )
        except Exception as e:
            logging.error(f"Error updating schema: {str(e)}")
            return func.HttpResponse(
                body=json.dumps({"error": f"Failed to update schema: {str(e)}"}),
                status_code=400,
                mimetype="application/json",
                headers={
                    "Access-Control-Allow-Origin": "*",
                },
            )

    if req.method == "DELETE":
        try:
            from azure.data.tables import TableClient

            # Try to get schema_id from query params first, then body
            schema_id = req.params.get("id")
            partition_key = req.params.get("PartitionKey", "RunbookSchema")

            if not schema_id:
                try:
                    body = req.get_json()
                    schema_id = body.get("id")
                    partition_key = body.get("PartitionKey", "RunbookSchema")
                except Exception:
                    pass

            if not schema_id:
                return func.HttpResponse(
                    body=json.dumps({"error": "Missing 'id' field in params or body"}),
                    status_code=400,
                    mimetype="application/json",
                    headers={
                        "Access-Control-Allow-Origin": "*",
                    },
                )

            conn_str = os.environ.get(STORAGE_CONN)
            table_client = TableClient.from_connection_string(
                conn_str, table_name=TABLE_SCHEMAS
            )
            table_client.delete_entity(partition_key=partition_key, row_key=schema_id)

            # Audit log
            log_audit(
                user=requester_username or "SYSTEM",
                action="SCHEMA_DELETE",
                target=schema_id,
                details=f"PartitionKey: {partition_key}",
            )

            return func.HttpResponse(
                body=json.dumps(
                    {"message": "Schema deleted successfully", "id": schema_id}
                ),
                status_code=200,
                mimetype="application/json",
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Content-Type": "application/json",
                },
            )
        except Exception as e:
            logging.error(f"Error deleting schema: {str(e)}")
            return func.HttpResponse(
                body=json.dumps({"error": f"Failed to delete schema: {str(e)}"}),
                status_code=400,
                mimetype="application/json",
                headers={
                    "Access-Control-Allow-Origin": "*",
                },
            )

    return func.HttpResponse(
        body=json.dumps({"error": "Method not allowed"}),
        status_code=405,
        mimetype="application/json",
        headers={
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.route(
    route="runbooks/content",
    methods=[func.HttpMethod.GET, func.HttpMethod.OPTIONS],
    auth_level=AUTH,
)
def get_runbook_content(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return create_cors_response()

    script_name = req.params.get("name")
    if not script_name:
        return func.HttpResponse(
            json.dumps({"error": "Query parameter 'name' is required"}),
            status_code=400,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    owner_repo = (GITHUB_REPO or "").strip()
    if not owner_repo or "/" not in owner_repo:
        return func.HttpResponse(
            json.dumps({"error": "GITHUB_REPO not configured correctly"}),
            status_code=500,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    branch = (GITHUB_BRANCH or "main").strip()
    prefix = (GITHUB_PATH_PREFIX or "").strip().strip("/")
    path_parts = [p for p in [prefix, script_name] if p]
    repo_path = "/".join(path_parts)

    content_text = None
    error_msg = "File not found"

    # FEATURE_DEV: read from local file system
    if os.getenv("FEATURE_DEV", "false").lower() == "true":
        try:
            # Check if a dev script path is explicitly set (e.g. in Docker)
            dev_script_path = os.getenv("DEV_SCRIPT_PATH")
            if dev_script_path:
                local_path = os.path.join(dev_script_path, script_name)
            else:
                # Fallback to relative path discovery for local development
                # We assume runbooks are in src/runbooks relative to project root.
                # The function app runs in src/core/orchestrator.
                # __file__ is src/core/orchestrator/function_app.py
                base_dir = os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
                local_path = os.path.join(base_dir, "src", "runbooks", script_name)

            if os.path.exists(local_path):
                with open(local_path, encoding="utf-8") as f:
                    content_text = f.read()
                logging.info(f"Loaded runbook from local path: {local_path}")
            else:
                logging.warning(f"Local runbook not found at {local_path}")
        except Exception as e:
            logging.error(f"Error reading local runbook: {e}")

    if content_text is not None:
        return func.HttpResponse(
            json.dumps({"content": content_text}),
            status_code=200,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    # We try both Contents API and Raw download
    import requests

    headers_list = []
    base_headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers_list.append({**base_headers, "Authorization": f"Bearer {GITHUB_TOKEN}"})
        headers_list.append({**base_headers, "Authorization": f"token {GITHUB_TOKEN}"})
    else:
        headers_list.append(base_headers)

    content_text = None
    error_msg = "File not found"

    # Try Contents API first
    api_url = f"https://api.github.com/repos/{owner_repo}/contents/{repo_path}"
    for h in headers_list:
        try:
            resp = requests.get(api_url, headers=h, params={"ref": branch}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if (
                    isinstance(data, dict)
                    and data.get("encoding") == "base64"
                    and "content" in data
                ):
                    import base64

                    content_text = base64.b64decode(
                        data["content"].replace("\n", "")
                    ).decode("utf-8")
                    break
            elif resp.status_code in (401, 403):
                error_msg = f"GitHub Auth Error: {resp.status_code}"
                continue
        except Exception as e:
            logging.error(f"GitHub API error: {e}")

    # Fallback to Raw
    if content_text is None:
        raw_url = f"https://raw.githubusercontent.com/{owner_repo}/{branch}/{repo_path}"
        for h in headers_list:
            try:
                resp = requests.get(raw_url, headers=h, timeout=10)
                if resp.status_code == 200:
                    content_text = resp.text
                    break
            except Exception as e:
                logging.error(f"GitHub Raw error: {e}")

    if content_text is not None:
        return func.HttpResponse(
            json.dumps({"content": content_text}),
            status_code=200,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"},
        )
    else:
        return func.HttpResponse(
            json.dumps({"error": error_msg}),
            status_code=404,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"},
        )


@app.route(
    route="runbooks/list",
    methods=[func.HttpMethod.GET, func.HttpMethod.OPTIONS],
    auth_level=AUTH,
)
def list_runbooks(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return create_cors_response()

    runbooks = []

    # FEATURE_DEV: list from local file system
    if os.getenv("FEATURE_DEV", "false").lower() == "true":
        try:
            dev_script_path = os.getenv("DEV_SCRIPT_PATH")
            if dev_script_path:
                local_dir = dev_script_path
            else:
                base_dir = os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
                local_dir = os.path.join(base_dir, "src", "runbooks")

            if os.path.exists(local_dir):
                for root, dirs, files in os.walk(local_dir):
                    for file in files:
                        if file.endswith(".sh") or file.endswith(".py"):
                            rel_path = os.path.relpath(
                                os.path.join(root, file), local_dir
                            )
                            runbooks.append(rel_path)
                logging.info(f"Listed runbooks from local path: {local_dir}")
        except Exception as e:
            logging.error(f"Error listing local runbooks: {e}")

    # If no local runbooks found or not in DEV, try GitHub
    if not runbooks:
        owner_repo = (GITHUB_REPO or "").strip()
        branch = (GITHUB_BRANCH or "main").strip()
        prefix = (GITHUB_PATH_PREFIX or "").strip().strip("/")

        if owner_repo and "/" in owner_repo:
            import requests

            headers_list = []
            base_headers = {"Accept": "application/vnd.github.v3+json"}
            if GITHUB_TOKEN:
                headers_list.append(
                    {**base_headers, "Authorization": f"Bearer {GITHUB_TOKEN}"}
                )
                headers_list.append(
                    {**base_headers, "Authorization": f"token {GITHUB_TOKEN}"}
                )
            else:
                headers_list.append(base_headers)

            api_url = f"https://api.github.com/repos/{owner_repo}/git/trees/{branch}?recursive=1"
            for h in headers_list:
                try:
                    resp = requests.get(api_url, headers=h, timeout=15)
                    if resp.status_code == 200:
                        data = resp.json()
                        tree = data.get("tree", [])
                        for item in tree:
                            path = item.get("path", "")
                            # Filter by prefix and extension
                            if path.startswith(prefix) and (
                                path.endswith(".sh") or path.endswith(".py")
                            ):
                                # If prefix is present, remove it from the path to get relative path
                                if prefix:
                                    prefix_len = len(prefix)
                                    rel_path = path[prefix_len:].lstrip("/")
                                    if rel_path:
                                        runbooks.append(rel_path)
                                else:
                                    runbooks.append(path)
                        break
                except Exception as e:
                    logging.error(f"GitHub API list error: {e}")

    return func.HttpResponse(
        json.dumps({"runbooks": sorted(list(set(runbooks)))}),
        status_code=200,
        mimetype="application/json",
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.schedule(
    schedule="0 */1 * * * *",
    arg_name="schedulerTimer",
    run_on_startup=False,
    use_monitor=False,
)
def scheduler_engine(schedulerTimer: func.TimerRequest) -> None:
    """
    Scheduler Engine: Check for scheduled runbooks and execute them.
    """
    import logging
    import os
    from datetime import datetime, timezone

    from azure.data.tables import TableClient
    from azure.storage.queue import QueueClient, TextBase64EncodePolicy
    from utils import format_requested_at, is_cron_now, today_partition_key

    conn_str = os.environ.get("AzureWebJobsStorage")
    table_client = TableClient.from_connection_string(
        conn_str, table_name=TABLE_SCHEDULES
    )

    try:
        schedules = table_client.query_entities(
            query_filter="PartitionKey eq 'Schedule' and enabled eq true"
        )
        now = datetime.now(timezone.utc)

        for s in schedules:
            cron_expr = s.get("cron", "0 */1 * * * *")
            last_run_str = s.get("last_run", "")

            should_run_by_cron = is_cron_now(cron_expr, now)

            should_run = False
            if should_run_by_cron:
                if not last_run_str:
                    should_run = True
                else:
                    last_run_dt = datetime.fromisoformat(
                        last_run_str.replace("Z", "+00:00")
                    )
                    if (now - last_run_dt).total_seconds() >= 45:
                        should_run = True

            if should_run:
                exec_id = str(uuid.uuid4())
                logging.warning(
                    f"[Scheduler] Triggering {s['name']} (ID: {s['RowKey']}) -> ExecId: {exec_id}"
                )

                worker_pool = s.get("worker_pool")
                target_queue = "cloudo-default"

                if worker_pool:
                    try:
                        workers_table = TableClient.from_connection_string(
                            conn_str, table_name="WorkersRegistry"
                        )
                        # Cerchiamo un worker attivo in questo pool per estrarne la coda
                        entities = list(
                            workers_table.query_entities(
                                query_filter=f"PartitionKey eq '{worker_pool}'"
                            )
                        )
                        logging.warning(
                            f"[WorkersRegistry] Found {len(entities)} workers"
                        )
                        for w in entities:
                            if w.get("Queue"):
                                target_queue = w.get("Queue")
                                break
                    except Exception as e:
                        logging.error(
                            f"[Scheduler] Failed to resolve queue for pool {worker_pool}: {e}"
                        )

                requested_at = format_requested_at()
                partition_key = today_partition_key()

                queue_payload = {
                    "runbook": s.get("runbook"),
                    "run_args": s.get("run_args"),
                    "worker": worker_pool,
                    "exec_id": exec_id,
                    "id": s.get("RowKey"),
                    "name": s.get("name"),
                    "status": "scheduled",
                    "oncall": False,
                    "require_approval": False,
                    "requested_at": requested_at,
                }

                try:
                    log_table_client = TableClient.from_connection_string(
                        conn_str, table_name=TABLE_NAME
                    )
                    log_entry = build_log_entry(
                        status="scheduled",
                        partition_key=partition_key,
                        row_key=str(uuid.uuid4()),
                        exec_id=exec_id,
                        requested_at=requested_at,
                        name=s.get("name"),
                        schema_id=s.get("RowKey"),
                        runbook=s.get("runbook"),
                        run_args=s.get("run_args"),
                        worker=worker_pool,
                        oncall="false",
                        log_msg=json.dumps(
                            {
                                "status": "scheduled",
                                "queue": target_queue,
                            },
                            ensure_ascii=False,
                        ),
                        monitor_condition="",
                        severity="",
                    )
                    log_table_client.create_entity(entity=log_entry)
                except Exception as le:
                    logging.error(f"[Scheduler] Failed to log scheduled status: {le}")

                q_name = target_queue
                queue_service = QueueClient.from_connection_string(
                    conn_str, q_name, message_encode_policy=TextBase64EncodePolicy()
                )
                try:
                    queue_service.send_message(json.dumps(queue_payload))
                except Exception as qe:
                    if "QueueNotFound" in str(qe):
                        logging.warning(f"[Scheduler] Queue {q_name} not found")
                    else:
                        raise qe

                s["last_run"] = now.isoformat()
                table_client.update_entity(entity=s)

    except Exception as e:
        logging.error(f"[Scheduler] Error: {e}")


@app.schedule(
    schedule="0 */1 * * * *",
    arg_name="cleanupTimer",
    run_on_startup=False,
    use_monitor=False,
)
def worker_cleanup(cleanupTimer: func.TimerRequest) -> None:
    """
    Garbage Collector: Cleanup old workers where LastSeen is > 5 minutes.
    """
    import utils
    from azure.data.tables import TableClient

    conn_str = os.environ.get("AzureWebJobsStorage")
    table_client = TableClient.from_connection_string(
        conn_str, table_name="WorkersRegistry"
    )

    now_str = utils.utc_now_iso()
    now_dt = datetime.fromisoformat(now_str.replace("Z", "+00:00"))
    limit_time = now_dt - timedelta(minutes=5)
    limit_iso = limit_time.isoformat()
    logging.info(f"[Cleanup] Cleaning up {limit_iso}")

    filter_query = f"LastSeen lt '{limit_iso}'"

    logging.debug(f"[Cleanup] Searching for zombies older than {limit_iso}...")

    try:
        dead_workers = table_client.query_entities(query_filter=filter_query)

        count = 0
        for w in dead_workers:
            table_client.delete_entity(
                partition_key=w["PartitionKey"], row_key=w["RowKey"]
            )
            logging.debug(
                f"[Cleanup] Deleted zombie: {w['RowKey']} (Partition: {w['PartitionKey']})"
            )
            count += 1

        logging.info(f"[Cleanup] Completed. Removed {count} workers.")

    except Exception as e:
        logging.error(f"[Cleanup] Failed: {e}")
