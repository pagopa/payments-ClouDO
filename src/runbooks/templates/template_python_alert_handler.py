#!/usr/bin/env python3
"""
Runbook Name: [Name]
Description: Python handler for ClouDO alerts
"""

import json
import logging
import os
import sys

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


class AlertContext:
    """Helper class to access environment variables provided by the alert system."""

    def __init__(self):
        # Azure Resource Context
        self.resource_id = os.environ.get("RESOURCE_ID")
        self.resource_rg = os.environ.get("RESOURCE_RG")
        self.resource_name = os.environ.get("RESOURCE_NAME")

        # AKS Context
        self.aks_job = os.environ.get("AKS_JOB")
        self.aks_deployment = os.environ.get("AKS_DEPLOYMENT")
        self.aks_namespace = os.environ.get("AKS_NAMESPACE", "default")
        self.aks_pod = os.environ.get("AKS_POD")
        self.aks_hpa = os.environ.get("AKS_HPA")

        # Alert State
        self.condition = os.environ.get("MONITOR_CONDITION", "Fired")

    def validate(self):
        """Check if critical variables are present."""
        if not self.resource_rg or not self.resource_name:
            raise ValueError(
                "Missing critical context: RESOURCE_RG or RESOURCE_NAME not set."
            )


def perform_remediation(ctx: AlertContext) -> dict:
    """
    Main logic based on the alert context.
    """
    logger.info(f"Handling alert for {ctx.resource_name} (State: {ctx.condition})")

    if ctx.condition == "Resolved":
        logger.info("Condition is Resolved. Executing rollback/cleanup...")
        # Add cleanup logic here
        action_taken = "rollback"
    else:
        logger.info("Condition is Fired. Executing remediation...")

        # Example: Check if it's an AKS alert
        if ctx.aks_deployment:
            logger.info(f"Targeting deployment: {ctx.aks_deployment}")
            # Add logic like calling kubectl or Azure SDK

        action_taken = "remediation"

    return {
        "status": "success",
        "resource": ctx.resource_name,
        "action": action_taken,
        "condition": ctx.condition,
    }


def main():
    try:
        # 1. Initialize Context
        ctx = AlertContext()
        ctx.validate()

        # 2. Perform Logic
        result = perform_remediation(ctx)

        # 3. Output Result
        print("RESULT:", json.dumps(result, ensure_ascii=False))
        return 0

    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        error_result = {"status": "error", "message": str(e)}
        print("RESULT:", json.dumps(error_result))
        return 1


if __name__ == "__main__":
    sys.exit(main())
