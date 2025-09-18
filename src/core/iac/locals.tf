locals {
  entity_executor = flatten([
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
}
