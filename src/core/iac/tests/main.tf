resource "azurerm_subnet" "subnet_functions" {
  name                 = "${var.prefix}-functions-snet"
  resource_group_name  = "dvopla-d-itn-vnet-rg"
  virtual_network_name = "dvopla-d-itn-vnet"
  address_prefixes     = ["10.3.124.0/27"]

  delegation {
    name = "serverFarms"
    service_delegation {
      name    = "Microsoft.Web/serverFarms"
      actions = ["Microsoft.Network/virtualNetworks/subnets/action"]
    }
  }
}

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

  schemas   = file("${path.module}/schemas.json.tpl")
  subnet_id = azurerm_subnet.subnet_functions.id
}
