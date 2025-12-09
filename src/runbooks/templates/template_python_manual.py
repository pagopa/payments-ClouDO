#!/usr/bin/env python3
"""
Runbook Name: [Name]
Description: Manual execution script for [Task]
Usage: python3 script.py --rg <resource-group> --name <resource-name>
"""

import argparse
import json
import logging
import os
import subprocess
import sys

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def check_azure_login():
    """Ensures the user is logged into Azure CLI."""
    try:
        # Fast check if we are logged in
        subprocess.run(
            ["az", "account", "show"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("Azure login verified.")
    except subprocess.CalledProcessError:
        logger.info("Not logged in. Attempting login...")
        # Check for Managed Identity env var
        client_id = os.environ.get("AZURE_CLIENT_ID")

        if client_id:
            cmd = ["az", "login", "--identity", "--client-id", client_id]
        else:
            # Fallback to simple identity or interactive
            cmd = [
                "az",
                "login",
            ]  # Will open browser if local, or fail if headless without identity

        subprocess.run(cmd, check=True)


def perform_manual_task(rg: str, resource_name: str, extra_param: str) -> dict:
    """
    Core logic for the manual task.
    """
    logger.info(f"Executing task on {resource_name} ({rg}) with param: {extra_param}")

    # --- YOUR LOGIC HERE ---
    # Example:
    # subprocess.run(["az", "group", "exists", "-n", rg], check=True)

    return {
        "status": "success",
        "resource": resource_name,
        "group": rg,
        "details": "Manual execution finished",
    }


def main():
    parser = argparse.ArgumentParser(description="Manual Runbook Execution")

    # Example: Define required arguments for manual run
    parser.add_argument("--rg", required=True, help="Azure Resource Group Name")
    parser.add_argument("--name", required=True, help="Resource Name")
    parser.add_argument(
        "--extra", default="default-val", help="Optional extra parameter"
    )
    parser.add_argument(
        "--skip-login", action="store_true", help="Skip Azure login check"
    )

    args = parser.parse_args()

    try:
        # 1. Login (unless skipped)
        if not args.skip_login:
            check_azure_login()

        # 2. Perform Logic
        result = perform_manual_task(args.rg, args.name, args.extra)

        # 3. Output Result
        print("RESULT:", json.dumps(result, ensure_ascii=False))
        return 0

    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        print("RESULT:", json.dumps({"status": "error", "message": str(e)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
