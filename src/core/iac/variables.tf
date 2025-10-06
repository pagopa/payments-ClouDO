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

variable "tags" {
  description = "A mapping of tags to assign to the Function App."
  type        = map(string)
  default     = {}
}
