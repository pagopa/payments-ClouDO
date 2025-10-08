variable "prefix" {
  type        = string
  description = "(Required) The prefix of resources. Changing this forces a new resource to be created."
}

variable "env" {
  type        = string
  description = "Environment"
}

variable "location" {
  type        = string
  description = "(Required) Specifies the supported Azure location where the resource exists. Changing this forces a new resource to be created."
}

variable "resource_group_name" {
  type        = string
  description = "(Required) The name of the Resource Group in which the resources should be exist."
}

variable "application_insights_name" {
  description = "The ID of the Application Insights to be linked to the Function App."
  type        = string
}

variable "application_insights_rg" {
  description = "The RG of the Application Insights to be linked to the Function App."
  type        = string
}

variable "schemas" {
  description = "The name of the Storage Table for runbook schemas."
  type        = string
}

variable "key_vault" {
  description = "(Optional) Configuration for Azure Key Vault integration, including the vault name and resource group."
  type = object({
    name           = string
    resource_group = string
  })
  default = {
    name           = null
    resource_group = null
  }
}

variable "github_repo_info" {
  type = object({
    repo_name    = string
    repo_branch  = string
    repo_token   = string
    runbook_path = string
  })
  description = "A map containing GitHub repository information such as repo, branch, token."
  default = {
    repo_name    = "pagopa/payments-cloudo"
    repo_branch  = "main"
    repo_token   = ""
    runbook_path = "src/runbooks"
  }
}

variable "vnet_name" {
  description = "The name of the VNet in which the Subnet exists."
  type        = string
  default     = null
}

variable "vnet_rg" {
  description = "The name of the Resource Group in which the VNet exists."
  type        = string
  default     = null
}

variable "aks_integration" {
  type = map(object({
    name           = string
    resource_group = string
    location       = string
  }))
  description = "Map of AKS cluster configurations including name, resource group, and subnet name for each cluster."
  default     = {}
}

variable "orchestrator_image" {
  description = ""
  type = object({
    image_name        = string
    image_tag         = string
    registry_url      = string
    registry_username = optional(string)
    registry_password = optional(string)
  })
}

variable "worker_image" {
  description = ""
  type = object({
    image_name        = string
    image_tag         = string
    registry_url      = string
    registry_username = optional(string)
    registry_password = optional(string)
  })
}

variable "service_plan_sku" {
  type        = string
  default     = "B1"
  description = "(Required) The SKU for the plan. (Default: B1)"
}

variable "slack_integration" {
  description = "(Optional) Configuration for Slack integration including the authentication token and target channel. If not provided, Slack integration will be disabled."
  type = object({
    token   = string
    channel = optional(string)
  })
  default = {
    token   = ""
    channel = "#cloudo-test"
  }
}

variable "opsgenie_api_key" {
  description = "(Optional) The API key used for OpsGenie integration to create and manage alerts. If not provided, OpsGenie integration will be disabled."
  type        = string
  default     = ""
}

variable "app_service_logs" {
  description = "(Optional) Configuration for App Service file system logs including disk quota and retention period."
  type = object({
    disk_quota_mb         = number
    retention_period_days = number
  })
  default = {
    disk_quota_mb         = 35
    retention_period_days = 3
  }
}

variable "tags" {
  description = "A mapping of tags to assign to the Function App."
  type        = map(string)
  default     = {}
}
