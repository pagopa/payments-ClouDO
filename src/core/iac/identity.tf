# Identity
resource "azurerm_user_assigned_identity" "identity" {
  for_each            = var.aks_integration
  location            = each.value.location
  name                = "${var.prefix}-${each.value.location}-cloudo-identity"
  resource_group_name = var.resource_group_name
}

resource "azurerm_role_assignment" "role_assignment" {
  for_each = merge(
    { for aks_key, _ in var.aks_integration : "${aks_key}:Contributor" => { role = "Contributor", key = aks_key } },
    { for aks_key, _ in var.aks_integration : "${aks_key}:AKSClusterUser" => { role = "Azure Kubernetes Service Cluster User Role", key = aks_key } },
    { for aks_key, _ in var.aks_integration : "${aks_key}:AKSRBACWriter" => { role = "Azure Kubernetes Service RBAC Writer", key = aks_key } }
  )

  scope                = data.azurerm_subscription.current.id
  role_definition_name = each.value.role
  principal_id         = azurerm_user_assigned_identity.identity[each.value.key].principal_id
}


module "workload_identity_init" {
  for_each = var.aks_integration
  source   = "git::https://github.com/pagopa/terraform-azurerm-v4.git//kubernetes_workload_identity_init?ref=8265f125b07251a5efe7b9ff57707109de8b46ba"

  workload_identity_name                = azurerm_user_assigned_identity.identity[each.key].name
  workload_identity_resource_group_name = azurerm_user_assigned_identity.identity[each.key].resource_group_name
  workload_identity_location            = var.location
  workload_identity_name_prefix         = var.prefix
}
