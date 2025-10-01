# Azure Subscription
data "azurerm_subscription" "current" {}

# Service Plan
resource "azurerm_service_plan" "this" {
  name                = "${var.prefix}-cloudo-service-plan"
  location            = var.location
  resource_group_name = var.resource_group_name
  os_type             = "Linux"

  sku_name = "B2"
  tags     = var.tags
}

# Function Orchestrator and Executor
resource "azurerm_linux_function_app" "orchestrator" {
  name = "${var.prefix}-cloudo"
  #name                       = var.name
  location                   = var.location
  resource_group_name        = var.resource_group_name
  service_plan_id            = azurerm_service_plan.this.id
  storage_account_name       = module.storage_account.name
  storage_account_access_key = module.storage_account.primary_access_key
  https_only                 = true

  identity {
    type = "SystemAssigned"
  }

  site_config {
    app_service_logs {
      disk_quota_mb         = 35
      retention_period_days = 0
    }
    application_insights_connection_string = data.azurerm_application_insights.this.connection_string
    application_insights_key               = data.azurerm_application_insights.this.instrumentation_key
    always_on                              = true
    http2_enabled                          = true

    # health_check_eviction_time_in_min = 2
    # health_check_path = "/healthz"
  }
  app_settings = {
    "QUEUE_NAME"        = azurerm_storage_queue.this.name
    "TABLE_SCHEMA_NAME" = azurerm_storage_table.runbook_schemas.name
    "TABLE_LOGGER_NAME" = azurerm_storage_table.runbook_logger.name
  }

  virtual_network_subnet_id = var.subnet_id

  lifecycle {
    ignore_changes = [app_settings, tags]
  }
  tags = var.tags
}

#Function Module
resource "azurerm_linux_function_app" "worker" {
  name                       = "${var.prefix}-cloudo-worker"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  service_plan_id            = azurerm_service_plan.this.id
  storage_account_name       = module.storage_account.name
  storage_account_access_key = module.storage_account.primary_access_key
  https_only                 = true

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.identity.id]
  }

  site_config {
    app_service_logs {
      disk_quota_mb         = 35
      retention_period_days = 0
    }
    application_insights_connection_string = data.azurerm_application_insights.this.connection_string
    application_insights_key               = data.azurerm_application_insights.this.instrumentation_key
    always_on                              = true
    http2_enabled                          = true
    # health_check_eviction_time_in_min = 2
    # health_check_path = "/healthz"
  }
  app_settings = {
    "QUEUE_NAME"            = azurerm_storage_queue.this.name
    "TABLE_SCHEMA_NAME"     = azurerm_storage_table.runbook_schemas.name
    "TABLE_LOGGER_NAME"     = azurerm_storage_table.runbook_logger.name
    "RECEIVER_URL"          = "https://${azurerm_linux_function_app.orchestrator.default_hostname}/api/Receiver?code=${data.azurerm_function_app_host_keys.orchestrator.default_function_key}"
    "GITHUB_REPO"           = var.github_repo_info.repo_name
    "GITHUB_BRANCH"         = var.github_repo_info.repo_branch
    "GITHUB_TOKEN"          = var.github_repo_info.repo_token
    "GITHUB_PATH_PREFIX"    = var.github_repo_info.runbook_path
    "AZURE_TENANT_ID"       = azurerm_user_assigned_identity.identity.tenant_id
    "AZURE_CLIENT_ID"       = azurerm_user_assigned_identity.identity.client_id
    "AZURE_SUBSCRIPTION_ID" = data.azurerm_subscription.current.subscription_id
  }

  virtual_network_subnet_id = var.subnet_id

  lifecycle {
    ignore_changes = [tags]
  }

  tags = var.tags
}

module "storage_account" {
  source = "git::https://github.com/pagopa/terraform-azurerm-v4.git//storage_account?ref=8265f125b07251a5efe7b9ff57707109de8b46ba"

  #name                          = replace("${var.name}cloudosa", "-", "")
  name                          = replace("${var.prefix}cloudosa", "-", "")
  location                      = var.location
  resource_group_name           = var.resource_group_name
  account_tier                  = "Standard"
  account_replication_type      = "LRS"
  is_hns_enabled                = false
  public_network_access_enabled = true

  tags = var.tags
}

resource "azurerm_storage_queue" "this" {
  name                 = "queue"
  storage_account_name = module.storage_account.name
}

resource "azurerm_storage_table" "runbook_logger" {
  name                 = "RunbookLogs"
  storage_account_name = module.storage_account.name
}

resource "azurerm_storage_table" "runbook_schemas" {
  name                 = "RunbookSchemas"
  storage_account_name = module.storage_account.name
}

resource "azurerm_storage_table_entity" "schemas" {
  for_each = {
    for i in local.entity_executor : i.entity.id => i
  }

  storage_table_id = azurerm_storage_table.runbook_schemas.id

  partition_key = each.value.partition_key
  row_key       = random_uuid.uuid[each.key].result

  entity = merge(
    each.value.entity,
    {
      "url" : "https://${azurerm_linux_function_app.worker.default_hostname}/api/${each.value.entity.worker}?code=${data.azurerm_function_app_host_keys.worker.default_function_key}"
    }
  )
}


# Identity
resource "azurerm_user_assigned_identity" "identity" {
  location            = var.location
  name                = "${var.prefix}-cloudo-identity"
  resource_group_name = var.resource_group_name
}

resource "azurerm_role_assignment" "role_assignment" {
  for_each = toset([
    "Contributor",
    "Azure Kubernetes Service Cluster User Role",
    "Azure Kubernetes Service RBAC Writer"
  ])
  scope                = data.azurerm_subscription.current.id
  role_definition_name = each.key
  principal_id         = azurerm_user_assigned_identity.identity.principal_id
}
