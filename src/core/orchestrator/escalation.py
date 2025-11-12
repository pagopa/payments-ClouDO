import json
import logging

from opsgenie_sdk import (
    AlertApi,
    ApiClient,
    CloseAlertPayload,
    Configuration,
    CreateAlertPayload,
)
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# =========================
# ESCALATIONS Functions
# =========================


# =========================
# OPSGENIE
# =========================
def send_opsgenie_alert(
    api_key: str,
    message: str,
    description: str = None,
    priority: str = "P3",
    alias: str = None,
    tags: list = None,
    details: dict = None,
    monitor_condition: str = None,
) -> bool:
    """
    Create or close an Opsgenie alert using the Opsgenie SDK.
    - On 'Resolved', close the existing alert by alias (requires alias).
    - Otherwise, create (or de-duplicate) the alert.
    """
    if not api_key or not str(api_key).strip():
        logging.warning("Opsgenie: missing or empty apiKey, skipping alert send.")
        return False

    try:
        conf = Configuration()
        conf.api_key["Authorization"] = api_key
        client = ApiClient(configuration=conf)
        alert_api = AlertApi(api_client=client)

        # Close path for resolved signals
        if (monitor_condition or "").strip().lower() == "resolved":
            if not alias:
                logging.warning(
                    "Opsgenie: cannot close alert without alias when resolved."
                )
                return False
            try:
                cap = CloseAlertPayload(user="cloudo", note="Auto-closed on resolve")
                alert_api.close_alert_with_http_info(
                    identifier=alias, identifier_type="alias", close_alert_payload=cap
                )
                logging.info(f"Opsgenie: closed alert with alias={alias}")
                return True
            except Exception as e:
                logging.error(f"Opsgenie: close_alert failed for alias={alias}: {e}")
                return False

        # Create alert (de-dup su alias se presente)
        body = CreateAlertPayload(
            message=message,
            description=description,
            priority=priority,
            alias=alias,
            tags=tags or [],
            details=details or {},
        )
        response = alert_api.create_alert(body)
        return True if response else False

    except Exception as e:
        logging.error(
            f"Opsgenie: unexpected error while sending/closing alert: {str(e)}"
        )
        return False


def format_opsgenie_description(exec_id: str, resource_info: dict, api_body) -> str:
    sep = "—" * 64

    raw_val = resource_info.get("_raw") or ""
    try:
        raw_pretty = json.dumps(json.loads(raw_val), indent=2, ensure_ascii=False)
    except Exception:
        raw_pretty = str(raw_val)

    if isinstance(api_body, (dict, list)):
        result_text = json.dumps(api_body, indent=2, ensure_ascii=False)
    else:
        result_text = str(api_body)

    return (
        f"{sep}\n"
        f"Alarm content (JSON)\n"
        f"{sep}\n"
        f"{raw_pretty}\n"
        f"\n"
        f"{sep}\n"
        f"Execution result for {exec_id}\n"
        f"{sep}\n"
        f"{result_text}"
    )


# =========================
# SLACK
# =========================


def send_slack_execution(
    token: str, channel: str, message: str, blocks: list = None
) -> bool:
    """
    Send an alert to a Slack channel using the Slack SDK.

    Args:
        token (str): Slack Bot User OAuth Token
        channel (str): Channel ID or name to send the message to
        message (str): Message text to send
        blocks (list, optional): Slack blocks for advanced message formatting

    Returns:
        bool: True if a message was sent successfully, False otherwise
    """
    # Skip call if a token or channel are missing/empty
    if not token or not str(token).strip():
        logging.warning("Slack: missing or empty token, skipping message send.")
        return False
    if not channel or not str(channel).strip():
        logging.warning("Slack: missing or empty channel, skipping message send.")
        return False

    try:
        client = WebClient(token=token)
        response = client.chat_postMessage(channel=channel, text=message, blocks=blocks)
        return True if response["ok"] else False

    except SlackApiError as e:
        logging.error(f"Error sending Slack alert: {str(e.response['error'])}")
        return False
    except Exception as e:
        logging.error(f"Error sending Slack alert: {str(e)}")
        return False
