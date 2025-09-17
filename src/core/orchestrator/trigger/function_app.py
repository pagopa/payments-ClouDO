import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import azure.functions as func
import yaml
from requests import request

app = func.FunctionApp()

# =========================
# Constants and Utilities
# =========================

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
# Azure Functions
# =========================


@app.route(route="Trigger", auth_level=func.AuthLevel.FUNCTION)
@app.table_output(
    arg_name="log_table",
    table_name="RunbookLogs",
    connection="AzureWebJobsStorage",
)
def trigger(req: func.HttpRequest, log_table: func.Out[str]) -> func.HttpResponse:
    # Read schema identifier from a query string
    schema = Schema(id=req.params.get("id", None))

    # Pre-compute logging fields
    requested_at = format_requested_at()
    partition_key = today_partition_key()
    exec_id = str(uuid.uuid4())

    try:
        try:
            processes_url = f"{_strip_after_api(schema.url)}/api/processes"
            proc_resp = request(
                "GET", processes_url, headers={"Accept": "application/json"}
            )
            proc_json = safe_json(proc_resp) or {}
            runs = proc_json.get("runs", []) if isinstance(proc_json, dict) else []

            def _parse_dt(s: str) -> datetime:
                s2 = (s or "").strip()
                if not s2:
                    raise ValueError("empty datetime")
                if s2.endswith("Z"):
                    s2 = s2[:-1] + "+00:00"
                try:
                    dt = datetime.fromisoformat(s2)
                    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                except Exception:
                    return datetime.strptime(s2, "%Y-%m-%d %H:%M:%S").replace(
                        tzinfo=timezone.utc
                    )

            relevant = []
            for r in runs:
                try:
                    if (r.get("id") == schema.id) and (r.get("status") == "running"):
                        started = _parse_dt(
                            r.get("startedAt", "") or r.get("requestedAt", "")
                        )
                        relevant.append((started, r))
                except Exception:
                    continue
            relevant.sort(key=lambda x: x[0], reverse=True)
            last_two_active = [r for _, r in relevant[:2]]

            from datetime import timedelta

            threshold = datetime.now(timezone.utc) - timedelta(minutes=10)
            should_skip = any(
                _parse_dt(p.get("startedAt", "") or p.get("requestedAt", ""))
                >= threshold
                for p in last_two_active
            )

            if should_skip:
                skip_log = build_log_entry(
                    status="skipped",
                    partition_key=partition_key,
                    exec_id=exec_id,
                    requested_at=requested_at,
                    name=schema.name or "",
                    schema_id=schema.id,
                    url=schema.url,
                    runbook=schema.runbook,
                    log={
                        "reason": "process active in the last 10 minutes",
                        "source": "worker.processes",
                    },
                    oncall=schema.oncall,
                )
                log_table.set(json.dumps(skip_log, ensure_ascii=False))
                response_body = build_response_body(
                    status_code=200,
                    schema=schema,
                    partition_key=partition_key,
                    exec_id=exec_id,
                    api_json={"message": "Skip: process active in the last 10 minutes"},
                )
                return func.HttpResponse(
                    response_body,
                    status_code=200,
                    mimetype="application/json",
                )
        except Exception as proc_err:
            logging.warning(f"Active process check failed: {proc_err}")

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
    Restituisce l'entità della tabella RunbookLogs identificata da PartitionKey e RowKey.
    Uso: GET /api/logs/{partitionKey}/{execId}
    """
    # Se l'entità non esiste, il binding fornisce None/empty
    if not log_entity:
        return func.HttpResponse(
            json.dumps({"error": "Entity not found"}, ensure_ascii=False),
            status_code=404,
            mimetype="application/json",
        )

    # log_entity è una stringa JSON dell'entità completa
    return func.HttpResponse(
        log_entity,
        status_code=200,
        mimetype="application/json",
    )
