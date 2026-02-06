# Get data of  default key orchestrator function due sensitive output.
data "azurerm_function_app_host_keys" "orchestrator_key" {
  name                = module.cloudo_orchestrator.name
  resource_group_name = module.cloudo_orchestrator.resource_group
}
