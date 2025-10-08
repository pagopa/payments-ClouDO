data "azurerm_key_vault" "kv_pagopa" {
  provider = azurerm.dev_pagopa

  name                = "pagopa-d-kv"
  resource_group_name = "pagopa-d-sec-rg"
}

data "azurerm_key_vault_secret" "github_pat" {
  provider = azurerm.dev_pagopa

  name         = "payments-cloud-github-bot-pat"
  key_vault_id = data.azurerm_key_vault.kv_pagopa.id
}

resource "azurerm_resource_group" "rg" {
  name     = "${var.prefix}-cloudo-rg"
  location = var.location

  tags = var.tags
}

module "function_app" {
  source = "../"

  prefix                    = var.prefix
  env                       = var.env
  location                  = var.location
  resource_group_name       = azurerm_resource_group.rg.name
  application_insights_name = "dvopla-d-itn-appinsights"
  application_insights_rg   = "dvopla-d-itn-monitor-rg"
  # vnet_name = "dvopla-d-itn-vnet"
  # vnet_rg = "dvopla-d-itn-vnet-rg"


  schemas = file("${path.module}/schemas.json.tpl")

  orchestrator_image = {
    image_name        = "pagopa/cloudo-orchestrator"
    image_tag         = "0.2.1"
    registry_url      = "https://ghcr.io"
    registry_username = "payments-cloud-bot"
    registry_password = data.azurerm_key_vault_secret.github_pat.value
  }

  worker_image = {
    image_name        = "pagopa/cloudo-worker"
    image_tag         = "0.1.1"
    registry_url      = "https://ghcr.io"
    registry_username = "payments-cloud-bot"
    registry_password = data.azurerm_key_vault_secret.github_pat.value
  }
}
