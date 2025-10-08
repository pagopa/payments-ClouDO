# Identity
resource "azurerm_user_assigned_identity" "identity" {
  for_each            = var.aks_integration
  location            = each.value.location
  name                = "${var.prefix}-${each.value.location}-cloudo-identity"
  resource_group_name = var.resource_group_name
}

resource "azurerm_role_assignment" "role_assignment" {
  for_each = merge(
    {
      for aks_key, _ in var.aks_integration : "${aks_key}:AKSClusterUser" =>
      { role = "Azure Kubernetes Service Cluster User Role", key = aks_key }
    },
    {
      for aks_key, _ in var.aks_integration : "${aks_key}:AKSServiceAccount" =>
      { role = "Azure Kubernetes Service RBAC Reader", key = aks_key }
    }
  )

  scope                = var.aks_integration[each.value.key].aks_cluster_id
  role_definition_name = each.value.role
  principal_id         = azurerm_user_assigned_identity.identity[each.value.key].principal_id
}
