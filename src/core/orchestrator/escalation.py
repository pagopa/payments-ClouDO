import logging

from opsgenie_sdk import AlertApi, ApiClient, Configuration, CreateAlertPayload


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
