# ClouDO - Centralized runbook automation for manual or event-driven execution

<p align="center">
  <img src="docs/images/cloudo_logo.png" width="500" alt="Architecture Diagram"/>
</p>

## Overview
ClouDO centralizes the definition, execution, and governance of operational runbooks. It supports both manual invocation and event-driven triggers, enabling consistent, repeatable responses to incidents, maintenance tasks, and routine operations.

## Architecture Overview
At a high level, the system comprises:
- API/Controller: Validates requests, authorizes actors, and dispatches runs.
- Orchestrator: Resolves dependencies and manages run lifecycle.
- Executors: Perform steps (scripts, HTTP calls, cloud operations, etc.).
- Event Ingestion: Webhooks/queue listeners for event-driven runs.
- State & Storage: Metadata, run history, artifacts, and secret references.
- UI: Discovery, execution, approvals, and observability.

Centralized runbook automation for manual or event-driven execution.

## Getting Started

### Installation
- Clone the repository.
- Install Python dependencies as documented in the project (e.g., using pip).
- Configure environment variables and credentials as needed.

### Test environment

To set up test environment with pre-compiled schemas (test, test-2, test-3) you need `docker-compose` installed
on your machine. Then run on root folder `make test-env-start` to set up environment and test
on http://localhost:7071/api/Trigger.

```bash
curl http://localhost:7071/api/Trigger?id=test
```

To exec the test the runbook and try the workflow, use → http://localhost:7071/api/logs to see result and process status.

### Configuration

ClouDO supports the Terraform module with the complete installation on your Azure subscription.


```hcl
module "cloudo" {
  source = "git::https://github.com/pagopa/payments-ClouDO.git//src/core/iac?ref=55a105d25eff99be8b5352db72074c4a2e56cb4a"

  prefix                    = local.product
  env                       = var.env
  location                  = var.location
  resource_group_name       = azurerm_resource_group.rg.name
  service_plan_sku          = "B1"
  application_insights_name = data.azurerm_application_insights.app_insight.name
  application_insights_rg   = data.azurerm_application_insights.app_insight.resource_group_name

  # Runbooks refer repository
  github_repo_info = {
    repo_name    = "organizzation/your_repo"
    repo_branch  = "main"
    repo_token   = "<TOKEN_IF_PRIVATE>"
    runbook_path = "your repo path where is the runbook collection. (e.g. src/runbook)"
  }

  # Multi-AKS cluster integration for RBAC service account profile.
  aks_integration = {
    weu = {
      cluster_id     = data.azurerm_kubernetes_cluster.aks_weu.id
    },
    itn = {
      cluster_id     = data.azurerm_kubernetes_cluster.aks_itn.id
    }
  }

  custom_roles_per_aks = {
    "weu" = [
      "Monitoring Reader",
      "Azure Kubernetes Service Cluster User Role"
    ]
    "itn" = [
      "Reader"
    ]
  }

  custom_roles_subscription = [
    "Reader",
    "Storage Blob Data Reader"
  ]

  custom_role_assignments = [
    {
      // Example: Assign by role name to a resource group
      role  = "Contributor"
      scope = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-app"
    },
    {
      // Example: Assign by role name to a specific resource
      role  = "Storage Blob Data Reader"
      scope = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-app/providers/Microsoft.Storage/storageAccounts/mystg"
    },
    {
      // Example: Assign by role_definition_id (built-in or custom role)
      role  = "/subscriptions/00000000-0000-0000-0000-000000000000/providers/Microsoft.Authorization/roleDefinitions/ba92f5b4-2d11-453d-a403-e96b0029c9fe"
      scope = "/subscriptions/00000000-0000-0000-0000-000000000000"
    },
    {
      // Example: Override principal_id
      role         = "Reader"
      scope        = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-ops"
      principal_id = "11111111-2222-3333-4444-555555555555"
    }
  ]

  app_service_logs = {
    retention_period_days = 3
    disk_quota_mb         = 35
  }

  slack_integration = {
    channel = "#your_slack_channel"
    token   = "APP_TOKEN"
  }

  opsgenie_api_key = "API_KEY_OPSGENIE"


  schemas = file("YOUR_PATH/schemas.json.tpl")

  orchestrator_image = {
    image_name        = "pagopa/cloudo-orchestrator"
    image_tag         = "VERSION"
    registry_url      = "https://ghcr.io"
    registry_username = "payments-cloud-bot"
    registry_password = data.azurerm_key_vault_secret.github_pat.value
  }

  worker_image = {
    image_name        = "pagopa/cloudo-worker"
    image_tag         = "VERSION"
    registry_url      = "https://ghcr.io"
    registry_username = "payments-cloud-bot"
    registry_password = data.azurerm_key_vault_secret.github_pat.value
  }

  tags = module.tag_config.tags
}
```

### How to write a runbook

Actually the Runbooks can be written with `bash` & `python` programming language.

When the alert originates from Azure Kubernetes Service (AKS),
the runbook has the following environment variables available:

- **RESOURCE_ID**: The full Azure resource ID.
- **RESOURCE_RG**: The Azure Resource Group name.
- **RESOURCE_NAME**: The resource name.
- **AKS_JOB**: The originating job/name from the alert context (if available).
- **AKS_DEPLOYMENT**: The Kubernetes Deployment name related to the alert (if available).
- **AKS_NAMESPACE**: The Kubernetes namespace associated with the alert (if available).
- **AKS_POD**: The specific Kubernetes Pod name related to the alert (if available).
- **MONITOR_CONDITION**: The monitor state for the alert, e.g., "Fired" or "Resolved."

The runbooks have already integrated the azcli support and the python library for az management.

### Example schemas

This is the example of schemas to map the runbooks to execute.

```
[
  {
    "partition_key": "generic",
    "entity": [
    {
      "id": "000-0000-0e0e00ww-wqesd",
      "name": "pippo",
      "description": "Hello Pippo V1!",
      "runbook": "check_sys.sh",
      "worker": "Runbook",
      "oncall": "false"
    },
    {
      "id": "000-0000-0e0e00wa-wqesd",
      "name": "pippo",
      "description": "Hello Pippo V2!",
      "runbook": "check_sys.sh",
      "worker": "Runbook",
      "oncall": "false",
      "run_args": ""
    }]
  },
  {
    "partition_key": "infra",
    "entity": [
    {
      "id": "000-0000-0e0e00ww-wasdsa",
      "name": "infra-pippo",
      "description": "Hello Pippo INFRA!",
      "runbook": "test.py",
      "run_args": "-n 1000 --repeats 1000",
      "worker": "Runbook",
      "oncall": "false"
    }]
  },
  {
    "partition_key": "alert",
    "entity": [
    {
      "id": "12345678-1234-1234-1234-1234567890ab",
      "name": "smart-alert",
      "description": "SMART!",
      "runbook": "check_sys.sh",
      "worker": "Runbook",
      "oncall": "false"
    }]
  }
]
```

A generic partition entry defining a runbook entity named “pippo,”
with ID 000-0000-0e0e00ww-wqesd. It describes versioned metadata (“Hello Pippo V1!”),
points to the runbook script check_sys.sh, is executed by the Runbook worker,
and is not marked for on-call.

If oncall was set to `true` in case runbook fail an alert will be opened on Opsgenie.
