# Key vault
# data "azurerm_key_vault" "kv" {
#   name                = var.key_vault.name
#   resource_group_name = var.key_vault.resource_group
# }

# App Insights
data "azurerm_application_insights" "this" {
  name                = var.application_insights_name
  resource_group_name = var.application_insights_rg
}

# Function APP Keys
data "azurerm_function_app_host_keys" "orchestrator" {
  name                = azurerm_linux_function_app.orchestrator.name
  resource_group_name = azurerm_linux_function_app.orchestrator.resource_group_name

  depends_on = [azurerm_linux_function_app.orchestrator]
}

data "azurerm_function_app_host_keys" "worker" {
  name                = azurerm_linux_function_app.worker.name
  resource_group_name = azurerm_linux_function_app.worker.resource_group_name

  depends_on = [azurerm_linux_function_app.worker]
}

# Random UUID for RowKey
resource "random_uuid" "uuid" {
  for_each = {
    for i in local.entity_executor : i.entity.id => i
  }
}
