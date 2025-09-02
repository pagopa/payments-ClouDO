variable "name" {
  type        = string
  description = "(Required) The name of the Virtual Machine Scale Set. Changing this forces a new resource to be created."
}

variable "location" {
  type        = string
  description = "(Required) Specifies the supported Azure location where the resource exists. Changing this forces a new resource to be created."
}

variable "resource_group_name" {
  type        = string
  description = "(Required) The name of the Resource Group in which the resources should be exist."
}

variable "app_service_plan_id" {
  description = "The ID of the App Service Plan to host the Function App."
  type        = string
}

variable "storage_account_name" {
  description = "The name of the Storage Account used by the Function App."
  type        = string
}

variable "storage_account_access_key" {
  description = "The access key of the Storage Account used by the Function App."
  type        = string
  sensitive   = true
}

variable "kind" {
  description = "Specifies the kind of the Function App (e.g., 'functionapp')."
  type        = string
}

variable "source_control" {
  description = "Configuration for the source control integration."
  type = object({
    repo_url = string
    branch   = string
  })
}

variable "tags" {
  description = "A mapping of tags to assign to the Function App."
  type        = map(string)
  default     = {}
}
