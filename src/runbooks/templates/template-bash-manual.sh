#!/bin/bash
set -euo pipefail

# ==============================================================================
# Script Name: [Action Name]
# Description: [Brief description]
# Usage:       ./script.sh <RESOURCE_GROUP> <RESOURCE_NAME> [EXTRA_ARG]
# ==============================================================================

# --- 1. Arguments & Help ---
usage() {
    echo "Usage: $0 <RESOURCE_GROUP> <RESOURCE_NAME> [EXTRA_ARG]"
    echo ""
    echo "Arguments:"
    echo "  RESOURCE_GROUP  The Azure Resource Group name"
    echo "  RESOURCE_NAME   The name of the target resource (e.g., Cluster name, VM name)"
    echo "  EXTRA_ARG       (Optional) Additional parameter"
    echo ""
    exit 1
}

if [ "$#" -lt 2 ]; then
    usage
fi

RESOURCE_GROUP=$1
RESOURCE_NAME=$2
EXTRA_ARG=${3:-"default-value"} # Default value if 3rd arg is missing

# --- 2. Helper Functions ---
log_info() { echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $1"; }
log_error() { echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') - $1" >&2; }

# --- 3. Azure Login ---
login_azure() {
    # Check if already logged in to avoid redundant login
    if az account show > /dev/null 2>&1; then
        log_info "Already logged into Azure."
    else
        log_info "Logging into Azure..."

        # Priority to Managed Identity if variable exists
        if [[ -n "${AZURE_CLIENT_ID:-}" ]]; then
             if ! az login --identity --client-id "$AZURE_CLIENT_ID" > /dev/null; then
                log_error "Failed to login with User Assigned Managed Identity"
                exit 1
             fi
        else
            # Fallback: Try standard identity or interactive if run locally
            # Using 'az login' without arguments might trigger browser login locally
            if ! az login --identity > /dev/null 2>&1; then
                 log_info "Managed Identity not found. Attempting interactive login..."
                 az login > /dev/null
            fi
        fi
    fi
}

# --- 4. Main Logic ---
main() {
    log_info "Starting manual operation..."
    log_info "Target: $RESOURCE_NAME in RG: $RESOURCE_GROUP"

    login_azure

    # --- YOUR COMMANDS HERE ---
    # Example:
    # az aks show --resource-group "$RESOURCE_GROUP" --name "$RESOURCE_NAME"

    log_info "Manual operation completed successfully."
}

main "$@"
