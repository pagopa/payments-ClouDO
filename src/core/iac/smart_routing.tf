
locals {
  sanitized_rules = [
    for r in var.routing_config.rules : {
      when = merge(
        {},
        r.when.any != null ? { any = r.when.any } : {},
        r.when.finalOnly != null ? { finalOnly = r.when.finalOnly } : {},
        length(try(r.when.statusIn, [])) > 0 ? { statusIn = r.when.statusIn } : {},
        r.when.resourceId != null ? { resourceId = r.when.resourceId } : {},
        r.when.resourceGroup != null ? { resourceGroup = r.when.resourceGroup } : {},
        r.when.resourceName != null ? { resourceName = r.when.resourceName } : {},
        r.when.subscriptionId != null ? { subscriptionId = r.when.subscriptionId } : {},
        r.when.namespace != null ? { namespace = r.when.namespace } : {},
        r.when.alertRule != null ? { alertRule = r.when.alertRule } : {},
        r.when.oncall != null ? { oncall = r.when.oncall } : {},
        r.when.resourceGroupPrefix != null ? { resourceGroupPrefix = r.when.resourceGroupPrefix } : {},
        r.when.severityMin != null ? { severityMin = r.when.severityMin } : {},
        r.when.severityMax != null ? { severityMax = r.when.severityMax } : {}
      )
      then = [
        for a in r.then : merge(
          { type = a.type },
          a.team != null ? { team = a.team } : {},
          a.channel != null ? { channel = a.channel } : {},
          a.token != null ? { token = a.token } : {},
          a.apiKey != null ? { apiKey = a.apiKey } : {}
        )
      ]
    }
  ]

  sanitized_teams = {
    for tname, t in var.routing_config.teams :
    tname => merge(
      {},
      try(t.slack, null) != null ? { slack = t.slack } : {},
      try(t.opsgenie, null) != null ? { opsgenie = t.opsgenie } : {}
    )
  }

  routing_rules_clean = {
    teams = local.sanitized_teams
    rules = local.sanitized_rules
  }


  routing_rules_json_from_object = jsonencode(local.routing_rules_clean)
}
