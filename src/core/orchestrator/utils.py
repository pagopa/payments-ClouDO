import json
from datetime import datetime, timezone
from typing import Any, Optional, Union
from zoneinfo import ZoneInfo

import azure.functions as func

# =========================
# UTILS Functions
# =========================


def lower_keys(obj: Any) -> Any:
    """Recursively lower-case dict keys."""
    if isinstance(obj, dict):
        return {str(k).lower(): lower_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [lower_keys(x) for x in obj]
    return obj


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


def _truncate_for_table(
    s: Optional[str], max_chars: int
) -> Union[str, tuple[str, bool]]:
    if not s:
        return "", False
    return s if len(s) <= max_chars else (s[:max_chars])


def create_cors_response(body=None, status_code=200, mimetype="application/json"):
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS, PUT, DELETE",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, x-cloudo-key",
    }

    if body is None and status_code == 200:
        return func.HttpResponse(status_code=status_code, headers=headers)

    return func.HttpResponse(
        body=json.dumps(body, ensure_ascii=False)
        if isinstance(body, (dict, list))
        else body,
        status_code=status_code,
        mimetype=mimetype,
        headers=headers,
    )
