variable "prefix" {
  description = "Resorce prefix"
  type        = string
  default     = "devops"
}

variable "location" {
  description = "Resorce location"
  type        = string
  default     = "italynorth"
}

variable "tags" {
  type        = map(string)
  description = "Azurerm test tags"
  default = {
    CreatedBy = "Terraform"
    Source    = "https://github.com/pagopa/terraform-azurerm-v3"
  }
}
