locals {
  schemas_entities = flatten([
    for partition, k in jsondecode(var.schemas) :
    [
      for item in k.entity :
      {
        entity        = item
        partition_key = k.partition_key
      }
    ]
    ]
  )

  schedules_entities = flatten([
    for schedule_group, k in jsondecode(var.schedules) :
    [
      for idx, item in k.entity :
      {
        schedule_key  = "${schedule_group}:${idx}"
        entity        = item
        partition_key = k.partition_key
      }
    ]
    ]
  )
}

resource "random_uuid" "schema_ids" {
  for_each = {
    for i in local.schemas_entities : i.entity.id => i
  }
}

resource "azurerm_storage_table_entity" "schemas" {
  for_each = {
    for i in local.schemas_entities : i.entity.id => i
  }

  storage_table_id = var.schemas_table_id

  partition_key = each.value.partition_key
  row_key       = random_uuid.schema_ids[each.key].result

  entity = merge(
    each.value.entity,
    {
      enabled = try(tobool(lookup(each.value.entity, "enabled", true)), true)
      group   = lookup(each.value.entity, "group", null) == null ? "-" : each.value.entity.group
      tags    = lookup(each.value.entity, "tags", null) == null ? "terraform" : contains(split(",", each.value.entity.tags), "terraform") ? each.value.entity.tags : "${each.value.entity.tags},terraform"
    }
  )
}

resource "random_uuid" "schedule_ids" {
  for_each = {
    for i in local.schedules_entities :
    i.schedule_key => i
  }
}

resource "azurerm_storage_table_entity" "schedules" {
  for_each = {
    for i in local.schedules_entities :
    i.schedule_key => i
  }

  storage_table_id = var.schedules_table_id
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
