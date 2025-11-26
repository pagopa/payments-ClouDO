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

app = func.FunctionApp()

# =========================
# Constants and Utilities
# =========================

# Centralize configuration strings to avoid "magic strings"
TABLE_NAME = "RunbookLogs"
TABLE_SCHEMAS = "RunbookSchemas"
TABLE_WORKERS_SCHEMAS = "WorkersRegistry"
STORAGE_CONN = "AzureWebJobsStorage"
NOTIFICATION_QUEUE_NAME = os.environ.get(
    "NOTIFICATION_QUEUE_NAME", "cloudo-notification"
)
STORAGE_CONNECTION = "AzureWebJobsStorage"
MAX_TABLE_CHARS = int(os.getenv("MAX_TABLE_LOG_CHARS", "32000"))
APPROVAL_TTL_MIN = int(os.getenv("APPROVAL_TTL_MIN", "60"))
APPROVAL_SECRET = (os.getenv("APPROVAL_SECRET") or "").strip()


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


def _rows_from_binding(rows: Union[str, list[dict]]) -> list[dict]:
    try:
        return json.loads(rows) if isinstance(rows, str) else (rows or [])
    except Exception:
        return []


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


@app.route(route="Trigger/{team?}", methods=[func.HttpMethod.POST], auth_level=AUTH)
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
            )

    logging.info(f"[{exec_id}] Getting schema entity id '{schema_entity}'")
    # Build domain model
    schema = Schema(
        id=schema_entity.get("id"),
        entity=schema_entity,
        monitor_condition=monitor_condition,
        severity=severity,
    )
    logging.debug(f"[{exec_id}] Set schema: '{schema}'")
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

            base = _strip_after_api(resolve_caller_url(req))
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

            logging.debug(routing_info)

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
            return func.HttpResponse(body, status_code=202, mimetype="application/json")

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
        )


# =========================
# HTTP Function: Approval
# =========================
@app.route(
    route="approvals/{partitionKey}/{execId}/approve",
    methods=[func.HttpMethod.GET],
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

    try:
        from smart_routing import execute_actions, route_alert
    except ImportError:
        route_alert = None
        execute_actions = None

    route_params = getattr(req, "route_params", {}) or {}
    execId = (route_params.get("execId") or "").strip()

    p = (req.params.get("p") or "").strip()
    s = (req.params.get("s") or "").strip()
    approver = (req.headers.get("X-Approver") or "unknown").strip()

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

        return func.HttpResponse(html, status_code=200, mimetype="text/html")

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
    methods=[func.HttpMethod.GET],
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
        )

    p = (req.params.get("p") or "").strip()
    s = (req.params.get("s") or "").strip()
    approver = (req.headers.get("X-Approver") or "unknown").strip()

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

    return func.HttpResponse(html, status_code=200, mimetype="text/html")


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
# ruff: noqa
def logs_frontend(req: func.HttpRequest) -> func.HttpResponse:
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
        code_js = json.dumps(candidate_key or "")
        html = render_template(
            "logs.html",
            {
                "code_js": code_js,
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
    - q (contains on some filed), from/to (range on RequestedAt), order, limit -> in memory
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


# @app.route(route="ui/{*path}", auth_level=AUTH)
# @app.table_input(
#     arg_name="entities",
#     table_name=TABLE_SCHEMAS,
#     connection=STORAGE_CONN,
# )
# def ui(req: func.HttpRequest, entities: str) -> func.HttpResponse:
#     # Parse bound table entities (binding returns a JSON array)
#     urls = []
#     runbooks = []
#     try:
#         parsed = json.loads(entities) if isinstance(entities, str) else entities
#
#         for e in parsed:
#             urls.append(e.get("url"))
#             runbooks.append(e.get("runbook"))
#
#         urls = set(urls)
#         runbooks = set(runbooks)
#
#         logging.info(f"urls: {urls}, runbooks: {runbooks}")
#     except Exception:
#         parsed = None
#
#     logging.info(f"ui parsed: {parsed}")
#
#     rel = (req.route_params.get("path") or "index.html").strip("/")
#     root = os.path.join(os.getcwd(), "fe")
#     file_path = os.path.normpath(os.path.join(root, rel))
#     if not file_path.startswith(root) or not os.path.exists(file_path):
#         file_path = os.path.join(root, "index.html")  # fallback SPA/HTML
#     try:
#         with open(file_path, "rb"):
#             data = render_template(
#                 "index.html",
#                 {
#                     "orchestrator_uri": req.url,
#                     "urls": urls,
#                     "runbooks": runbooks,
#                 },
#             )
#         if file_path.endswith(".html"):
#             mime = "text/html; charset=utf-8"
#         elif file_path.endswith(".css"):
#             mime = "text/css; charset=utf-8"
#         elif file_path.endswith(".js"):
#             mime = "application/javascript; charset=utf-8"
#         elif file_path.endswith(".json"):
#             mime = "application/json; charset=utf-8"
#         elif file_path.endswith(".png"):
#             mime = "image/png"
#         elif file_path.endswith(".jpg") or file_path.endswith(".jpeg"):
#             mime = "image/jpeg"
#         elif file_path.endswith(".svg"):
#             mime = "image/svg+xml"
#         else:
#             mime = "application/octet-stream"
#         return func.HttpResponse(
#             data, status_code=200, mimetype=mime, headers={"Cache-Control": "no-store"}
#         )
#     except Exception as e:
#         logging.error("UI serving error: %s", e)
#         return func.HttpResponse("Not found", status_code=404)


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
