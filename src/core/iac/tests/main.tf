resource "azurerm_resource_group" "rg" {
  name     = "${local.project}-rg"
  location = var.location

  tags = var.tags
}

resource "azurerm_service_plan" "this" {
  name                = "${local.project}-service-plan"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  os_type             = "Linux"

  sku_name = "B1"
  tags     = var.tags
}

module "storage_account" {
  source = "git::https://github.com/pagopa/terraform-azurerm-v4.git//storage_account?ref=8265f125b07251a5efe7b9ff57707109de8b46ba"

  name                          = "${local.project}sa"
  location                      = var.location
  resource_group_name           = azurerm_resource_group.rg.name
  account_tier                  = "Standard"
  account_replication_type      = "LRS"
  is_hns_enabled                = false
  public_network_access_enabled = true
  tags                          = var.tags
}

module "function_app" {
  source = "../"

  name                       = "${local.project}-function-app"
  location                   = var.location
  resource_group_name        = azurerm_resource_group.rg.name
  service_plan_id            = azurerm_service_plan.this.id
  storage_account_name       = module.storage_account.name
  storage_account_access_key = module.storage_account.primary_access_key
}
