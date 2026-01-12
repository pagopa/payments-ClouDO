# Azure Subscription
data "azurerm_subscription" "current" {}

resource "random_password" "internal_auth_token" {
  length  = 32
  special = false
}

# Service Plan
resource "azurerm_service_plan" "orchestrator" {
  name                = "${var.prefix}-cloudo-orchestrator-service-plan"
  location            = var.location
  resource_group_name = var.resource_group_name
  os_type             = "Linux"

  sku_name = var.service_plan_sku
  tags     = var.tags
}

resource "azurerm_service_plan" "workers" {
  name                = "${var.prefix}-cloudo-workers-service-plan"
  location            = var.location
  resource_group_name = var.resource_group_name
  os_type             = "Linux"

  sku_name = var.service_plan_sku
  tags     = var.tags
}

# Function Orchestrator and Executor
resource "azurerm_linux_function_app" "orchestrator" {
  name                       = "${var.prefix}-cloudo"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  service_plan_id            = azurerm_service_plan.orchestrator.id
  storage_account_name       = module.storage_account.name
  storage_account_access_key = module.storage_account.primary_access_key
  https_only                 = true

  identity {
    type = "SystemAssigned"
  }

  site_config {
    app_service_logs {
      disk_quota_mb         = var.app_service_logs.disk_quota_mb
      retention_period_days = var.app_service_logs.retention_period_days
    }
    application_stack {
      docker {
        image_name        = var.orchestrator_image.image_name
        image_tag         = var.orchestrator_image.image_tag
        registry_url      = var.orchestrator_image.registry_url
        registry_username = var.orchestrator_image.registry_username
        registry_password = var.orchestrator_image.registry_password
      }
    }
    application_insights_connection_string = data.azurerm_application_insights.this.connection_string
    application_insights_key               = data.azurerm_application_insights.this.instrumentation_key
    always_on                              = true
    http2_enabled                          = true
  }
  app_settings = merge(
    {
      "TABLE_SCHEMA_NAME"                   = azurerm_storage_table.runbook_schemas.name
      "TABLE_LOGGER_NAME"                   = azurerm_storage_table.runbook_logger.name
      "SLACK_TOKEN_DEFAULT"                 = var.slack_integration.token
      "SLACK_CHANNEL_DEFAULT"               = var.slack_integration.channel
      "OPSGENIE_API_KEY_DEFAULT"            = var.opsgenie_api_key
      "GITHUB_REPO"                         = var.github_repo_info.repo_name
      "GITHUB_BRANCH"                       = var.github_repo_info.repo_branch
      "GITHUB_TOKEN"                        = var.orchestrator_image.registry_password
      "GITHUB_PATH_PREFIX"                  = var.github_repo_info.runbook_path
      "WEBSITES_ENABLE_APP_SERVICE_STORAGE" = false
      "APPROVAL_TTL_MIN"                    = var.approval_runbook.ttl_min
      "APPROVAL_SECRET"                     = var.approval_runbook.secret
      "CLOUDO_SECRET_KEY"                   = random_password.internal_auth_token.result
    },
    local.orchestrator_smart_routing_app_settings
  )

  virtual_network_subnet_id = try(module.cloudo_flexible_snet[0].id, null)

  lifecycle {
    ignore_changes = [tags]
  }
  tags = var.tags
}

# UI App Service
# resource "azurerm_linux_web_app" "ui" {
#   count               = var.enable_ui ? 1 : 0
#   name                = "${var.prefix}-cloudo-ui"
#   location            = var.location
#   resource_group_name = var.resource_group_name
#   service_plan_id     = azurerm_service_plan.orchestrator.id
#   https_only          = true
#
#   identity {
#     type = "SystemAssigned"
#   }
#
#   site_config {
#     # app_service_logs {
#     #   disk_quota_mb         = var.app_service_logs.disk_quota_mb
#     #   retention_period_days = var.app_service_logs.retention_period_days
#     # }
#     application_stack {
#       docker_image_name        = "${var.ui_image.image_name}:${var.ui_image.image_tag}"
#       docker_registry_url      = var.ui_image.registry_url
#       docker_registry_password = var.ui_image.registry_password
#       docker_registry_username = var.ui_image.registry_username
#     }
#     # application_insights_connection_string = data.azurerm_application_insights.this.connection_string
#     # application_insights_key               = data.azurerm_application_insights.this.instrumentation_key
#     always_on     = true
#     http2_enabled = true
#   }
#
#   app_settings = {
#     "ORCHESTRATOR_URL"                    = "https://${azurerm_linux_function_app.orchestrator.default_hostname}"
#     "API_URL"                             = "https://${azurerm_linux_function_app.orchestrator.default_hostname}/api"
#     "FUNCTION_KEY"                        = data.azurerm_function_app_host_keys.orchestrator.default_function_key
#     "CLOUDO_KEY"                          = random_password.internal_auth_token.result
#     "WEBSITES_ENABLE_APP_SERVICE_STORAGE" = false
#   }
#
#   virtual_network_subnet_id = try(module.cloudo_flexible_snet[0].id, null)
#
#   lifecycle {
#     ignore_changes = [tags]
#   }
#
#   tags = var.tags
# }

module "cloudo_ui" {
  count               = var.enable_ui ? 1 : 0
  source              = "git::https://github.com/pagopa/terraform-azurerm-v4//IDH/app_service_webapp?ref=add-app-service-module-github-credential"
  env                 = var.env
  idh_resource_tier   = var.cluodo_ui_tier
  location            = var.location
  name                = "${var.prefix}-cloudo-ui"
  product_name        = var.product_name
  resource_group_name = var.resource_group_name

  app_service_plan_name = azurerm_service_plan.orchestrator.name
  app_settings = {
    "ORCHESTRATOR_URL"                    = "https://${azurerm_linux_function_app.orchestrator.default_hostname}"
    "API_URL"                             = "https://${azurerm_linux_function_app.orchestrator.default_hostname}/api"
    "FUNCTION_KEY"                        = data.azurerm_function_app_host_keys.orchestrator.default_function_key
    "CLOUDO_KEY"                          = random_password.internal_auth_token.result
    "WEBSITES_ENABLE_APP_SERVICE_STORAGE" = false
  }

  docker_image             = var.ui_image.image_name
  docker_image_tag         = var.ui_image.image_tag
  docker_registry_url      = var.ui_image.registry_url
  docker_registry_password = var.ui_image.registry_password
  docker_registry_username = var.ui_image.registry_username
  subnet_id                = module.cloudo_flexible_snet[0].subnet_id
  tags                     = var.tags

  # which subnet is allowed to reach this app service
  allowed_subnet_ids = [var.vpn_subnet_id]

  private_endpoint_dns_zone_id = var.private_endpoint_dns_zone_id
  private_endpoint_subnet_id   = var.private_endpoint_subnet_id

  autoscale_settings = {
    max_capacity                  = 1
    scale_up_requests_threshold   = 250
    scale_down_requests_threshold = 150
  }

  always_on = true
}

resource "azurerm_storage_queue" "this" {
  for_each             = var.workers_config.workers
  name                 = "${var.prefix}-${each.key}-queue"
  storage_account_name = module.storage_account.name
}

#F Workers unction Module
resource "azurerm_linux_function_app" "worker" {
  for_each                   = var.workers_config.workers
  name                       = "${var.prefix}-cloudo-${each.key}"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  service_plan_id            = azurerm_service_plan.workers.id
  storage_account_name       = module.storage_account.name
  storage_account_access_key = module.storage_account.primary_access_key
  https_only                 = true

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.identity.id]
  }

  site_config {
    app_service_logs {
      disk_quota_mb         = var.app_service_logs.disk_quota_mb
      retention_period_days = var.app_service_logs.retention_period_days
    }
    application_stack {
      docker {
        image_name        = var.workers_config.image_name
        image_tag         = var.workers_config.image_tag
        registry_url      = var.workers_config.registry_url
        registry_username = var.workers_config.registry_username
        registry_password = var.workers_config.registry_password
      }
    }
    application_insights_connection_string = data.azurerm_application_insights.this.connection_string
    application_insights_key               = data.azurerm_application_insights.this.instrumentation_key
    always_on                              = true
    http2_enabled                          = true
  }
  app_settings = {
    "QUEUE_NAME"                          = azurerm_storage_queue.this[each.key].name
    "TABLE_SCHEMA_NAME"                   = azurerm_storage_table.runbook_schemas.name
    "TABLE_LOGGER_NAME"                   = azurerm_storage_table.runbook_logger.name
    "GITHUB_REPO"                         = var.github_repo_info.repo_name
    "GITHUB_BRANCH"                       = var.github_repo_info.repo_branch
    "GITHUB_TOKEN"                        = var.workers_config.registry_password
    "GITHUB_PATH_PREFIX"                  = var.github_repo_info.runbook_path
    "AZURE_TENANT_ID"                     = azurerm_user_assigned_identity.identity.tenant_id
    "AZURE_CLIENT_ID"                     = azurerm_user_assigned_identity.identity.client_id
    "AZURE_SUBSCRIPTION_ID"               = data.azurerm_subscription.current.subscription_id
    "AzureWebJobsFeatureFlags"            = "EnableWorkerIndexing"
    "FUNCTIONS_WORKER_PROCESS_COUNT"      = 1
    "FUNCTIONS_WORKER_RUNTIME"            = "python"
    "DOTNET_RUNNING_IN_CONTAINER"         = true
    "WEBSITES_ENABLE_APP_SERVICE_STORAGE" = false
    "ORCHESTRATOR_URL"                    = "https://${azurerm_linux_function_app.orchestrator.default_hostname}/api/workers/register"
    "CLOUDO_SECRET_KEY"                   = random_password.internal_auth_token.result
    "WORKER_CAPABILITY"                   = each.value
  }

  virtual_network_subnet_id = try(module.cloudo_flexible_snet[0].id, null)

  lifecycle {
    ignore_changes = [tags]
  }

  tags = var.tags
}

module "storage_account" {
  source = "git::https://github.com/pagopa/terraform-azurerm-v4.git//storage_account?ref=8265f125b07251a5efe7b9ff57707109de8b46ba"

  name                          = replace("${var.prefix}cloudosa", "-", "")
  location                      = var.location
  resource_group_name           = var.resource_group_name
  account_tier                  = "Standard"
  account_replication_type      = "LRS"
  is_hns_enabled                = false
  public_network_access_enabled = true

  tags = var.tags
}

resource "azurerm_storage_queue" "notification" {
  name                 = "cloudo-notification"
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

resource "azurerm_storage_table" "workers_registry" {
  name                 = "WorkersRegistry"
  storage_account_name = module.storage_account.name
}

resource "azurerm_storage_table" "audit_logs" {
  name                 = "CloudoAuditLogs"
  storage_account_name = module.storage_account.name
}

resource "azurerm_storage_table" "cloudo_schedules" {
  name                 = "CloudoSchedules"
  storage_account_name = module.storage_account.name
}

resource "azurerm_storage_table" "cloudo_settings" {
  name                 = "CloudoSettings"
  storage_account_name = module.storage_account.name
}

resource "azurerm_storage_table" "cloudo_users" {
  name                 = "CloudoUsers"
  storage_account_name = module.storage_account.name
}

resource "azurerm_storage_table_entity" "admin_user" {
  storage_table_id = azurerm_storage_table.cloudo_users.id
  partition_key    = "Operator"
  row_key          = "admin"
  entity           = { password = random_password.admin_password.result, role = "ADMIN", email = "admin@cloudo.local" }
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
      tags = lookup(each.value.entity, "tags", null) == null ? "terraform" : contains(split(",", each.value.entity.tags), "terraform") ? each.value.entity.tags : "${each.value.entity.tags},terraform"
    }
  )
}
