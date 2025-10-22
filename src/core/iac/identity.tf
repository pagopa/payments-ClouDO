# Identity
resource "azurerm_user_assigned_identity" "identity" {
  location            = var.location
  name                = "${var.prefix}-cloudo-identity"
  resource_group_name = var.resource_group_name
}

resource "azurerm_role_assignment" "role_assignment" {
  for_each = merge(
    {
      for aks_key, _ in var.aks_integration : "${aks_key}:AKSClusterUser" =>
      { role = "Azure Kubernetes Service Cluster User Role", key = aks_key, type = "aks" }
    },
    {
      for aks_key, _ in var.aks_integration : "${aks_key}:AKSServiceAccount" =>
      { role = "Azure Kubernetes Service RBAC Admin", key = aks_key, type = "aks" }
    },
    {
      "subscription:Reader" = {
        role = "Reader"
        key  = null
        type = "subscription"
      }
    }
  )

  scope = each.value.kind == "aks" ? var.aks_integration[each.value.key].cluster_id : "/subscriptions/${var.subscription_id}"

  role_definition_name = each.value.role
  principal_id         = azurerm_user_assigned_identity.identity.principal_id
}
