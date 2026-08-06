resource "random_uuid" "schedule_ids" {
  for_each = {
    for i in local.schedules_executor :
    i.schedule_key => i
  }
}

resource "azurerm_storage_table_entity" "schedules" {
  for_each = {
    for i in local.schedules_executor :
    i.schedule_key => i
  }

  storage_table_id = azurerm_storage_table.cloudo_schedules.id
  partition_key    = each.value.partition_key
  row_key          = random_uuid.schedule_ids[each.key].result

  entity = merge(
    each.value.entity,
    {
      id         = random_uuid.schedule_ids[each.key].result
      enabled    = try(tobool(lookup(each.value.entity, "enabled", true)), true)
      oncall     = try(tobool(lookup(each.value.entity, "oncall", true)), true)
      run_args   = lookup(each.value.entity, "run_args", "")
      last_run   = ""
      managed_by = "terraform"
      locked     = true
    }
  )

  lifecycle {
    ignore_changes = [entity["last_run"]]
  }
}
