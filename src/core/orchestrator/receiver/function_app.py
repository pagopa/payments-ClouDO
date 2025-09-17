import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import azure.functions as func

# Azure Functions application instance
app = func.FunctionApp()

# =========================
# Constants
# =========================

# Centralize configuration strings to avoid "magic strings"
TABLE_NAME = "RunbookLogs"
STORAGE_CONN = "AzureWebJobsStorage"


# =========================
# Helpers
# =========================


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
    return "succeeded" if normalized == "completed" else "failed"


def resolve_caller_url(req: func.HttpRequest) -> str:
    return (
        get_header(req, "X-Caller-Url")
        or get_header(req, "Referer")
        or get_header(req, "Origin")
        or req.url
    )


def utc_now_iso() -> str:
    # ISO-like UTC timestamp used in health endpoint
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_log_entity(
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
# HTTP Function: receiver
# =========================


@app.route(route="receiver", auth_level=func.AuthLevel.FUNCTION)
@app.table_output(
    arg_name="log_table",
    table_name=TABLE_NAME,
    connection=STORAGE_CONN,
)
def receiver(req: func.HttpRequest, log_table: func.Out[str]) -> func.HttpResponse:
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
    requested_at_utc = utc_now_iso_seconds()
    partition_key = utc_partition_key()
    row_key = str(uuid.uuid4())  # stable hex representation for RowKey
    request_origin_url = resolve_caller_url(req)
    status_label = resolve_status(get_header(req, "Status"))

    # Build and write the log entity
    log_entity = make_log_entity(
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
            "service": "Receiver",
        },
        ensure_ascii=False,
    )
    return func.HttpResponse(
        body,
        status_code=200,
        mimetype="application/json",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )
