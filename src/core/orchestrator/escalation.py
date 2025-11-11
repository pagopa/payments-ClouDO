import logging

from opsgenie_sdk import AlertApi, ApiClient, Configuration, CreateAlertPayload
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# =========================
# ESCALATIONS Functions
# =========================


def send_opsgenie_alert(
    api_key: str,
    message: str,
    description: str = None,
    priority: str = "P3",
    alias: str = None,
    tags: list = None,
    details: dict = None,
) -> bool:
    """
    Send an alert to OpsGenie using the OpsGenie SDK.

    Args:
        api_key (str): OpsGenie API key
        message (str): Alert message/title
        description (str, optional): Detailed description of the alert
        priority (str, optional): Alert priority (P1-P5). Defaults to "P3"
        alias (str, optional): Alias for alert deduplication
        tags (list, optional): List of tags for the alert
        details (dict, optional): Additional details for the alert

    Returns:
        bool: True if alert was sent successfully, False otherwise
    """
    # Skip call if the API key is missing/empty
    if not api_key or not str(api_key).strip():
        logging.warning("OpsGenie: missing or empty apiKey, skipping alert send.")
        return False
    try:
        conf = Configuration()
        conf.api_key["Authorization"] = api_key

        client = ApiClient(configuration=conf)
        alert_api = AlertApi(api_client=client)

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
        logging.error(f"Error sending OpsGenie alert: {str(e)}")
        return False


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
        bool: True if message was sent successfully, False otherwise
    """
    # Skip call if token or channel are missing/empty
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
