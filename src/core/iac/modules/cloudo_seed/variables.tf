variable "schemas_table_id" {
  description = "Storage table id for RunbookSchemas."
  type        = string
}

variable "schedules_table_id" {
  description = "Storage table id for CloudoSchedules."
  type        = string
}

variable "schemas" {
  description = "Schemas json payload to seed into RunbookSchemas table."
  type        = string
}

variable "schedules" {
  description = "Schedules json payload to seed into CloudoSchedules table."
  type        = string
}
