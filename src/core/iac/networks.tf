
# Subnet
module "cloudo_flexible_snet" {
  count                = var.vnet_name != null ? 1 : 0
  source               = "git::https://github.com/pagopa/terraform-azurerm-v4//IDH/subnet?ref=e37760466d614653cd385450ec9458aae1055428"
  name                 = "${var.prefix}-snet"
  resource_group_name  = var.vnet_rg
  virtual_network_name = var.vnet_name
  service_endpoints    = [""]

  idh_resource_tier = "app_service"
  product_name      = var.product_name
  env               = var.env

  tags = var.tags
}
