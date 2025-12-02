resource "azurerm_monitor_metric_alert" "function_failures" {
  for_each            = toset(concat([azurerm_linux_function_app.orchestrator.id], [for w in azurerm_linux_function_app.worker : w.id]))
  name                = "${var.prefix}-${var.env}-cloudo-function-failures-alert-${each.key}"
  resource_group_name = var.resource_group_name
  scopes              = [each.key]
  description         = "Alert when function execution failures occur"
  severity            = 2

  criteria {
    metric_namespace = "Microsoft.Web/sites"
    metric_name      = "FunctionExecutionErrors"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 0
  }
}

resource "azurerm_monitor_metric_alert" "function_duration" {
  for_each = toset(concat([azurerm_linux_function_app.orchestrator.id], [for w in azurerm_linux_function_app.worker : w.id]))

  name                = "${var.prefix}-${var.env}-cloudo-function-duration-alert-${each.key}"
  resource_group_name = var.resource_group_name
  scopes              = [each.key]
  description         = "Alert when function execution duration exceeds threshold"
  severity            = 2

  criteria {
    metric_namespace = "Microsoft.Web/sites"
    metric_name      = "FunctionExecutionUnits"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 1000
  }
}

resource "azurerm_monitor_metric_alert" "queue_message_count" {
  name                = "${var.prefix}-${var.env}-cloudo-queue-msg-count"
  resource_group_name = var.resource_group_name
  scopes              = [module.storage_account.id]
  description         = "Alert when queue message count exceeds threshold"
  severity            = 2

  criteria {
    metric_namespace = "Microsoft.Storage/storageAccounts"
    metric_name      = "QueueMessageCount"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 500
  }
}

resource "azurerm_monitor_metric_alert" "dead_letter_queue" {
  name                = "${var.prefix}-${var.env}-cloudo-dlq-alert"
  resource_group_name = var.resource_group_name
  scopes              = [module.storage_account.id]
  description         = "Alert when dead letter queue message count exceeds threshold"
  severity            = 1


  criteria {
    metric_namespace = "Microsoft.Storage/storageAccounts"
    metric_name      = "QueueMessageCount"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 0

    dimension {
      name     = "QueueName"
      operator = "Include"
      values = concat(
        ["${azurerm_storage_queue.notification.name}-poison"],
        [for q in values(azurerm_storage_queue.this) : "${q.name}-poison"]
      )
    }
  }
}
