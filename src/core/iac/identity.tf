module "workload_identity_init" {
  for_each = var.aks_integration
  source   = "git::https://github.com/pagopa/terraform-azurerm-v4.git//kubernetes_workload_identity_init?ref=8265f125b07251a5efe7b9ff57707109de8b46ba"

  workload_identity_name                = azurerm_user_assigned_identity.identity.name
  workload_identity_resource_group_name = azurerm_user_assigned_identity.identity.resource_group_name
  workload_identity_location            = var.location
  workload_identity_name_prefix         = var.prefix
}

module "workload_identity_config" {
  for_each = var.aks_integration

  source = "git::https://github.com/pagopa/terraform-azurerm-v4.git//kubernetes_workload_identity_configuration?ref=8265f125b07251a5efe7b9ff57707109de8b46ba"

  workload_identity_name                = azurerm_user_assigned_identity.identity.name
  workload_identity_resource_group_name = azurerm_user_assigned_identity.identity.resource_group_name
  aks_name                              = each.value.name
  aks_resource_group_name               = each.value.resource_group
  namespace                             = "*"

  key_vault_id                      = data.azurerm_key_vault.kv.id
  key_vault_certificate_permissions = ["Get"]
  key_vault_key_permissions         = ["Get"]
  key_vault_secret_permissions      = ["Get"]
}
