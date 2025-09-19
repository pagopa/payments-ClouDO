resource "azurerm_resource_group" "rg" {
  name     = "${var.prefix}-cloudo-rg"
  location = var.location

  tags = var.tags
}

module "function_app" {
  source = "../"

  prefix                    = var.prefix
  location                  = var.location
  resource_group_name       = azurerm_resource_group.rg.name
  application_insights_name = "dvopla-d-itn-appinsights"
  application_insights_rg   = "dvopla-d-itn-monitor-rg"

  schemas = file("${path.module}/schemas.json.tpl")
}
