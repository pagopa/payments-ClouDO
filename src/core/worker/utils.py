import base64
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo


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


def encode_logs(value: Optional[str]) -> bytes:
    """
    Encode a string value to base64 bytes.
    If the value is None or empty, returns empty bytes.
    """
    if not value:
        return b""
    return base64.b64encode(value.encode("utf-8"))


def get_sanitized_env(env_dict):
    """
    Returns a deep copy of the environment dictionary with sensitive values masked.
    Useful for safe logging.
    """
    # Keywords that strongly suggest a field is sensitive
    SENSITIVE_KEYWORDS = [
        "TOKEN",
        "SECRET",
        "KEY",
        "PASSWORD",
        "PASS",
        "PWD",
        "CONNECTION_STRING",
        "AUTH",
        "SIGNATURE",
        "AZUREWEBJOBSSTORAGE",
        "AZUREWEBJOBSDASHBOARD",
    ]

    # Explicit list of keys that must be blocked even if they don't match keywords
    EXPLICIT_BLOCKLIST = [
        "INTERNALAUTHAPISALLOWLIST",
        "SITETOKENISSUINGMODE",
    ]

    # Create a copy to avoid modifying the actual environment used for execution
    sanitized = env_dict.copy()

    for key, value in sanitized.items():
        upper_key = key.upper()

        if value == "******" or not value:
            continue

        # 1. Check Explicit Blocklist
        if upper_key in EXPLICIT_BLOCKLIST:
            sanitized[key] = "******"
            continue

        # 2. Heuristic Check (Substring matching)
        # We check if any sensitive keyword exists in the variable name.
        if any(keyword in upper_key for keyword in SENSITIVE_KEYWORDS):
            sanitized[key] = "******"

    return sanitized
