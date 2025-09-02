# Function Module
resource "azurerm_function_app" "this" {
  name                       = var.name
  location                   = var.location
  resource_group_name        = var.resource_group_name
  app_service_plan_id        = var.app_service_plan_id
  storage_account_name       = var.storage_account_name
  storage_account_access_key = var.storage_account_access_key

  kind    = var.kind
  os_type = "Linux"

  site_config {
    scm_type = "GitHub"
  }

  source_control {
    repo_url = var.source_control.repo_url
    branch   = var.source_control.branch
  }

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}
