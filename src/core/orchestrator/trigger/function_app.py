import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit

import azure.functions as func
import yaml
from requests import request

app = func.FunctionApp()

# =========================
# Constants and Utilities
# =========================

# Centralize configuration strings to avoid "magic strings"
TABLE_NAME = "RunbookLogs"
STORAGE_CONN = "AzureWebJobsStorage"

# Single source of truth for configuration file name
CONFIG_FILE = "config.yaml"


def format_requested_at() -> str:
    # Human-readable UTC timestamp for logs (e.g., 2025-09-15 12:34:56)
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def today_partition_key() -> str:
    # Compact UTC date used as PartitionKey (e.g., 20250915)
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def utc_now_iso() -> str:
    # ISO-like UTC timestamp used in health endpoint
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_now_iso_seconds() -> str:
    # Generate a UTC timestamp in ISO 8601 format with seconds precision
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
    status: str,
    partition_key: str,
    exec_id: str,
    requested_at: str,
    name: str,
    schema_id: str,
    url: str | None,
    runbook: str | None,
    log: dict | str | None,
    oncall: str | None = "false",
) -> dict:
    # Standardize the log entity written to the Azure Table storage
    return {
        "PartitionKey": partition_key,
        "RowKey": exec_id,
        "ExecId": exec_id,
        "Status": status,
        "RequestedAt": requested_at,
        "Name": name,
        "Id": schema_id,
        "Url": url,
        "Runbook": runbook,
        "Log": log,
        "OnCall": oncall,
    }


def receiver_log_entity(
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


# =========================
# Domain Model
# =========================


@dataclass
class Schema:
    id: str
    name: str | None = None
    description: str | None = None
    url: str | None = None
    runbook: str | None = None
    oncall: str | None = "false"

    def __post_init__(self):
        # Validate and load schema configuration from CONFIG_FILE
        if not self.id or not isinstance(self.id, str):
            raise ValueError("Schema id must be a non-empty string")

        config_path = Path(__file__).parent / CONFIG_FILE
        logging.info(f"Loading config from {config_path}")

        if not config_path.exists():
            raise FileNotFoundError(f"{CONFIG_FILE} does not exist")

        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

        schema_cfg = config.get(self.id)
        if not schema_cfg:
            raise ValueError(f"Schema id '{self.id}' not found in {CONFIG_FILE}")

        self.name = schema_cfg.get("name", "")
        self.description = schema_cfg.get("description")
        self.url = schema_cfg.get("url")
        self.runbook = schema_cfg.get("runbook")
        self.oncall = str(schema_cfg.get("oncall", "false")).strip().lower() or "false"


# =========================
# HTTP Function: trigger
# =========================


@app.route(route="Trigger", auth_level=func.AuthLevel.FUNCTION)
@app.table_output(
    arg_name="log_table",
    table_name=TABLE_NAME,
    connection=STORAGE_CONN,
)
def Trigger(req: func.HttpRequest, log_table: func.Out[str]) -> func.HttpResponse:
    # Read schema identifier from a query string
    schema = Schema(id=req.params.get("id", None))

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
            requested_at=requested_at,
            name=schema.name or "",
            schema_id=schema.id,
            url=schema.url,
            runbook=schema.runbook,
            log=api_body,
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
            requested_at=requested_at,
            name=schema.name or "",
            schema_id=schema.id,
            url=schema.url,
            runbook=schema.runbook,
            log=str(e),
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
    log_entity = receiver_log_entity(
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
