import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import azure.functions as func
from requests import request

app = func.FunctionApp()

# =========================
# Constants and Utilities
# =========================

# Centralize configuration strings to avoid "magic strings"
TABLE_NAME = "RunbookLogs"
TABLE_SCHEMAS = "RunbookSchemas"
STORAGE_CONN = "AzureWebJobsStorage"

# Single source of truth for configuration file name
CONFIG_FILE = "config.yaml"


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
    return (
        get_header(req, "X-Caller-Url")
        or get_header(req, "Referer")
        or get_header(req, "Origin")
        or req.url
    )


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


def build_headers(schema: "Schema", exec_id: str) -> dict:
    # Standardize request headers sent to the downstream runbook endpoint
    return {
        "runbook": f"{schema.runbook}",
        "Id": schema.id,
        "Name": schema.name or "",
        "ExecId": exec_id,
        "OnCall": schema.oncall,
        "Content-Type": "application/json",
    }


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
    log_msg: Optional[str],
    oncall: Optional[str],
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
        "Log": log_msg,
        "OnCall": oncall,
    }


def extract_schema_id_from_req(req: func.HttpRequest) -> Optional[str]:
    """
    Resolve schema_id from the incoming request:
    1) Prefer query string (?id=...)
    2) Fallback to JSON body: data.essentials.alertId (or schemaId if available)
    Returns the alertId as-is. If you want only the trailing GUID, enable the split below.
    """
    q_id = req.params.get("id")
    if q_id:
        return q_id
    logging.info("Resolving schema_id: %s", req.params.get("id"))
    try:
        body = req.get_json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        alert_id = body.get("data", {}).get("essentials", {}).get(
            "alertId"
        ) or body.get("schemaId")
        if alert_id:
            aid = str(alert_id).strip()
            if "/" in aid:
                last = aid.strip("/").split("/")[-1]
                return last or aid
            return aid
    return None


# =========================
# Domain Model
# =========================


@dataclass
class Schema:
    id: str
    entity: Optional[dict] = None
    name: str | None = None
    description: str | None = None
    url: str | None = None
    runbook: str | None = None
    oncall: str | None = "false"

    def __post_init__(self):
        # Validate and load schema configuration from CONFIG_FILE
        if not self.id or not isinstance(self.id, str):
            raise ValueError("Schema id must be a non-empty string")

        if not self.entity:
            raise ValueError(
                "Entity not provided: use table input binding to inject the table entity"
            )

        e = self.entity
        self.name = e.get("name") or e.get("name") or ""
        self.description = e.get("description") or e.get("description")
        self.url = e.get("url") or e.get("url")
        self.runbook = e.get("runbook") or e.get("runbook")
        self.oncall = (
            str(e.get("oncall", e.get("oncall", "false"))).strip().lower() or "false"
        )


# =========================
# HTTP Function: trigger
# =========================


@app.route(route="Trigger/{id?}", auth_level=func.AuthLevel.FUNCTION)
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
    # Route params (optional): available via req.route_params
    route_params = getattr(req, "route_params", {}) or {}

    # Resolve schema_id from route first; fallback to query/body (alertId/schemaId)
    schema_id = (route_params.get("id") or "").strip() or extract_schema_id_from_req(
        req
    )
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

    schema_entity = next((e for e in parsed if get_id(e) == schema_id), None)

    if not schema_entity:
        return func.HttpResponse(
            json.dumps(
                {"error": f"Schema with Id '{schema_id}' not found in {TABLE_SCHEMAS}"},
                ensure_ascii=False,
            ),
            status_code=404,
            mimetype="application/json",
        )

    # Build domain model
    schema = Schema(id=schema_id, entity=schema_entity)

    # Pre-compute logging fields
    requested_at = format_requested_at()
    partition_key = today_partition_key()
    exec_id = str(uuid.uuid4())

    try:
        # Call downstream runbook endpoint
        response = request("POST", schema.url, headers=build_headers(schema, exec_id))
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
            log_msg=api_body,
            oncall=schema.oncall,
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
            log_msg=str(e),
            oncall=schema.oncall,
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


@app.route(route="Receiver", auth_level=func.AuthLevel.FUNCTION)
@app.table_output(
    arg_name="log_table",
    table_name=TABLE_NAME,
    connection=STORAGE_CONN,
)
def Receiver(req: func.HttpRequest, log_table: func.Out[str]) -> func.HttpResponse:
    # Log only relevant and serializable headers for observability
    logging.info(
        "Receiver invoked",
        extra={
            "headers": {
                "ExecId": get_header(req, "ExecId"),
                "Status": get_header(req, "Status"),
                "Name": get_header(req, "Name"),
                "Id": get_header(req, "Id"),
                "Runbook": get_header(req, "runbook"),
                "OnCall": get_header(req, "OnCall"),
            }
        },
    )

    # Precompute keys and timestamps for logging
    requested_at_utc = format_requested_at()
    partition_key = utc_partition_key()
    row_key = str(uuid.uuid4())  # stable hex representation for RowKey
    request_origin_url = resolve_caller_url(req)
    status_label = resolve_status(get_header(req, "Status"))

    # Build and write the log entity
    log_entity = build_log_entry(
        status=status_label,
        partition_key=partition_key,
        row_key=row_key,
        exec_id=get_header(req, "ExecId"),
        requested_at=requested_at_utc,
        name=get_header(req, "Name"),
        schema_id=get_header(req, "Id"),
        url=request_origin_url,
        runbook=get_header(req, "runbook"),
        log_msg=get_header(req, "Log"),
        oncall=get_header(req, "OnCall"),
    )
    log_table.set(json.dumps(log_entity, ensure_ascii=False))

    if req.headers.get("OnCall") == "true" and status_label == "failed":
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


@app.route(route="healthz", auth_level=func.AuthLevel.ANONYMOUS)
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


@app.route(route="logs/{partitionKey}/{execId}", auth_level=func.AuthLevel.FUNCTION)
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
