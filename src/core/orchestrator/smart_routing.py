# Python
# routing.py
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

# =========================
# Routing: models
# =========================


@dataclass
class Action:
    type: str  # "slack" | "opsgenie"
    channel: Optional[str] = None
    token: Optional[str] = None
    team: Optional[str] = None
    apiKey: Optional[str] = None


@dataclass
class RoutingDecision:
    actions: list[Action]
    matched_rule_index: Optional[int]
    matched_team: Optional[str]
    reason: str  # "matched" | "fallback_opsgenie"


# =========================
# Config loader
# =========================


def load_routing_config() -> dict[str, Any]:
    """
    Load routing configuration from env ROUTING_RULES (JSON).
    If absent/invalid, return safe fallback with Opsgenie default.
    Do NOT store secrets (tokens/keys) in config JSON: resolve via environment.
    """
    raw = (os.environ.get("ROUTING_RULES") or "").strip()
    defaults = {
        "opsgenie": {"team": "oncall-default"},  # apiKey resolved via env
        "slack": {"channel": os.environ.get("SLACK_CHANNEL", "#cloudo-default")},
    }
    fallback = {
        "version": 1,
        "defaults": defaults,
        "teams": {},
        "rules": [
            {
                "when": {"any": "*"},
                "then": [
                    {
                        "type": "opsgenie",
                        "severityMin": "Sev2",
                        "statusIn": ["failed", "error"],
                    },
                    {"type": "slack"},
                ],
            }
        ],
    }
    if not raw:
        logging.info("ROUTING_RULES not set: using fallback configuration")
        return fallback
    try:
        cfg = json.loads(raw)
        # Soft-merge defaults to ensure required keys exist
        cfg.setdefault("defaults", {}).setdefault("opsgenie", {}).setdefault(
            "team", defaults["opsgenie"]["team"]
        )
        cfg.setdefault("defaults", {}).setdefault("slack", {}).setdefault(
            "channel", defaults["slack"]["channel"]
        )
        cfg.setdefault("teams", {})
        cfg.setdefault("rules", fallback["rules"])
        return cfg
    except Exception as e:
        logging.error(f"Invalid ROUTING_RULES JSON: {e}")
        return fallback


# =========================
# Severity and matching utils
# =========================


def _sev_to_num(sev: Optional[str]) -> Optional[int]:
    """
    Normalize Azure severity "Sev0-Sev4" to integer 0..4.
    Lower is more critical (0=Critical, 4=Informational).
    """
    if not sev:
        return None
    s = str(sev).strip().lower()
    if s.startswith("sev"):
        s = s.replace("sev", "")
    try:
        return int(s)
    except Exception:
        return None


def _eq(a: Optional[str], b: Optional[str]) -> bool:
    if a is None or b is None:
        return False
    return str(a).strip().lower() == str(b).strip().lower()


def _starts(a: Optional[str], prefix: Optional[str]) -> bool:
    if a is None or prefix is None:
        return False
    return str(a).lower().startswith(str(prefix).lower())


def _subscription_from_resource_id(resource_id: Optional[str]) -> Optional[str]:
    try:
        parts = (resource_id or "").split("/")
        return (
            parts[2] if len(parts) > 2 and parts[1].lower() == "subscriptions" else None
        )
    except Exception:
        return None


def _match_when(when: dict[str, Any], ctx: dict[str, Any]) -> bool:
    """
    Return True if context satisfies the rule's 'when' conditions.
    All conditions are AND-ed. Supports:
      - equality: resourceId, resourceGroup, subscriptionId, namespace, alertRule, oncall
      - prefix: resourceGroupPrefix
      - severity ranges: severityMin, severityMax (SevN semantics)
      - wildcard: any="*"
      - status filters: finalOnly (default True), statusIn (list of allowed statuses)
    """
    if "any" in when:
        return True

    # Status filtering (centralized)
    status = (ctx.get("status") or "").strip().lower()
    # By default, only route final outcomes
    final_only = when.get("finalOnly", True)
    final_statuses = {"succeeded", "error", "failed", "timeout"}
    if final_only and status not in final_statuses:
        return False
    if "statusIn" in when:
        allowed = {str(x).strip().lower() for x in (when.get("statusIn") or [])}
        if allowed and status not in allowed:
            return False

    # Equality
    if "resourceId" in when and not _eq(ctx.get("resourceId"), when["resourceId"]):
        return False
    if "resourceGroup" in when and not _eq(
        ctx.get("resourceGroup"), when["resourceGroup"]
    ):
        return False
    if "resourceName" in when and not _eq(
        ctx.get("resourceName"), when["resourceName"]
    ):
        return False
    if "subscriptionId" in when:
        sub = _subscription_from_resource_id(ctx.get("resourceId"))
        if not _eq(sub, when["subscriptionId"]):
            return False
    if "namespace" in when and not _eq(ctx.get("namespace"), when["namespace"]):
        return False
    if "alertRule" in when and not _eq(ctx.get("alertRule"), when["alertRule"]):
        return False
    if "oncall" in when and not _eq(str(ctx.get("oncall") or ""), str(when["oncall"])):
        return False

    # Prefix
    if "resourceGroupPrefix" in when and not _starts(
        ctx.get("resourceGroup"), when["resourceGroupPrefix"]
    ):
        return False
    # TODO dinamic match

    # Severity range
    sev = _sev_to_num(ctx.get("severity"))
    if "severityMin" in when:
        minv = _sev_to_num(when["severityMin"])
        if minv is not None and (sev is None or sev < minv):
            return False
    if "severityMax" in when:
        maxv = _sev_to_num(when["severityMax"])
        if maxv is not None and (sev is None or sev > maxv):
            return False

    return True


# =========================
# Team credential resolution
# =========================


def resolve_opsgenie_apikey(team: Optional[str]) -> Optional[str]:
    """
    Resolve Opsgenie apiKey from env using naming convention:
      - OPSGENIE_API_KEY_<TEAM> (preferred)
      - OPSGENIE_API_KEY (default)
    """
    if team:
        env_name = f"OPSGENIE_API_KEY_{team}".upper().replace("-", "_")
        key = os.getenv(env_name)
        if key:
            return key
    return os.getenv("OPSGENIE_API_KEY")


def resolve_slack_token(team: Optional[str]) -> Optional[str]:
    """
    Resolve Slack token from env using naming convention:
      - SLACK_TOKEN_<TEAM> (preferred)
      - SLACK_TOKEN (default)
    """
    if team:
        env_name = f"SLACK_TOKEN_{team}".upper().replace("-", "_")
        tok = os.getenv(env_name)
        if tok:
            return tok
    return os.getenv("SLACK_TOKEN")


# =========================
# Context normalization
# =========================


def normalize_context(raw_ctx: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize the incoming alert context to a stable key set for rule matching.
    """
    return {
        "resourceId": raw_ctx.get("resourceId"),
        "resourceGroup": raw_ctx.get("resourceGroup"),
        "resourceName": raw_ctx.get("resourceName"),
        "alertRule": raw_ctx.get("alertRule"),
        "severity": raw_ctx.get("severity"),
        "namespace": raw_ctx.get("namespace"),
        "oncall": str(raw_ctx.get("oncall") or "").strip().lower(),
        "status": raw_ctx.get("status"),
        "execId": raw_ctx.get("execId"),
        "name": raw_ctx.get("name"),
        "id": raw_ctx.get("id"),
        "routing_info": raw_ctx.get("routing_info") or {},
    }


# =========================
# Routing engine
# =========================


def route_alert(raw_ctx: dict[str, Any]) -> RoutingDecision:
    """
    Decide the actions to execute (Slack/Opsgenie) based on routing rules.
    Returns a RoutingDecision with the ordered list of actions.
    If nothing matches, returns Opsgenie fallback (only for final outcomes).
    """
    cfg = load_routing_config()
    ctx = normalize_context(raw_ctx)
    rules = cfg.get("rules", [])
    defaults = cfg.get("defaults", {})
    teams_cfg = cfg.get("teams", {})

    routing_info = ctx.get("routing_info") or {}

    logging.info(routing_info)
    ri_team = (routing_info.get("team") or "").strip() or None
    ri_slack_token = routing_info.get("slack_token") or None
    ri_slack_channel = routing_info.get("slack_channel") or None
    ri_opsgenie_token = routing_info.get("opsgenie_token") or None

    status = (ctx.get("status") or "").strip().lower()
    logging.info(
        f"Routing: evaluating {len(rules)} rules for execId={ctx.get('execId')} with status={status}"
    )

    for idx, rule in enumerate(rules):
        when = rule.get("when", {})
        if not _match_when(when, ctx):
            continue

        resolved_actions: list[Action] = []
        matched_team: Optional[str] = None

        for t in rule.get("then", []):
            atype = t.get("type")
            if atype not in ("slack", "opsgenie"):
                logging.warning(f"Ignoring unsupported action type: {atype}")
                continue
            logging.info(f"Executing action: {atype} for {t.get('team')}")

            team_name = t.get("team") or ri_team
            team_conf = teams_cfg.get(team_name, {}) if team_name else {}
            matched_team = matched_team or team_name

            if atype == "slack":
                channel = (
                    t.get("channel")
                    or (team_conf.get("slack", {}) or {}).get("channel")
                    or (defaults.get("slack", {}) or {}).get("channel")
                    or ri_slack_channel
                )
                token = (
                    t.get("token") or resolve_slack_token(team_name) or ri_slack_token
                )
                resolved_actions.append(
                    Action(type="slack", channel=channel, token=token, team=team_name)
                )

            elif atype == "opsgenie":
                og_team = (
                    team_name
                    or (team_conf.get("opsgenie", {}) or {}).get("team")
                    or (defaults.get("opsgenie", {}) or {}).get("team")
                    or ri_team
                )
                api_key = (
                    t.get("apiKey")
                    or resolve_opsgenie_apikey(og_team)
                    or ri_opsgenie_token
                )
                resolved_actions.append(
                    Action(type="opsgenie", team=og_team, apiKey=api_key)
                )

        action_types_in_rule = {a.type for a in resolved_actions}

        if "slack" in action_types_in_rule and ri_team:
            already_slack_for_team = any(
                a.type == "slack" and a.team == ri_team for a in resolved_actions
            )
            if not already_slack_for_team:
                ri_team_conf = teams_cfg.get(ri_team, {})
                extra_channel = (
                    ri_slack_channel
                    or (ri_team_conf.get("slack", {}) or {}).get("channel")
                    or (defaults.get("slack", {}) or {}).get("channel")
                )
                extra_token = ri_slack_token or resolve_slack_token(ri_team)
                if extra_channel or extra_token:
                    resolved_actions.append(
                        Action(
                            type="slack",
                            channel=extra_channel,
                            token=extra_token,
                            team=ri_team,
                        )
                    )

        if "opsgenie" in action_types_in_rule and (ri_team or ri_opsgenie_token):
            og_extra_team = ri_team or (defaults.get("opsgenie", {}) or {}).get("team")
            already_og_for_team = any(
                a.type == "opsgenie" and a.team == og_extra_team
                for a in resolved_actions
            )
            if not already_og_for_team:
                extra_api_key = ri_opsgenie_token or resolve_opsgenie_apikey(
                    og_extra_team
                )
                if extra_api_key:
                    resolved_actions.append(
                        Action(
                            type="opsgenie", team=og_extra_team, apiKey=extra_api_key
                        )
                    )

        if resolved_actions:
            logging.info(
                f"Routing: matched rule #{idx} (team={matched_team}) with {len(resolved_actions)} action(s)"
            )
            return RoutingDecision(
                actions=resolved_actions,
                matched_rule_index=idx,
                matched_team=matched_team,
                reason="matched",
            )

    # Fallback only for final outcomes
    final_statuses = {"error", "failed", "timeout"}
    if status in final_statuses:
        # Preferisci token/team da routing_info se disponibili
        og_team = ri_team or (defaults.get("opsgenie", {}) or {}).get("team")
        api_key = ri_opsgenie_token or resolve_opsgenie_apikey(og_team)
        logging.info(
            "Routing: no rule matched, using Opsgenie fallback (final outcome)"
        )
        return RoutingDecision(
            actions=[Action(type="opsgenie", team=og_team, apiKey=api_key)],
            matched_rule_index=None,
            matched_team=None,
            reason="fallback_opsgenie",
        )

    logging.debug("Routing: non-final status and no rule matched, no actions executed")
    return RoutingDecision(
        actions=[],
        matched_rule_index=None,
        matched_team=None,
        reason="no_action_non_final",
    )


# =========================
# Action execution with fallback
# =========================


def execute_actions(
    decision: RoutingDecision,
    payload: dict[str, Any],
    send_slack_fn=None,
    send_opsgenie_fn=None,
) -> None:
    """
    Execute the decided actions in order.
    - If any action succeeds, continue executing others (fan-out).
    - If all actions fail, attempt a final Opsgenie fallback using a default env key.
    """
    any_success = False

    for a in decision.actions:
        try:
            if a.type == "slack":
                if not a.token:
                    raise ValueError("Missing Slack token")
                if not a.channel:
                    raise ValueError("Missing Slack channel")
                logging.debug(
                    f"Routing: sending Slack (team={a.team}, channel={a.channel})"
                )
                send_slack_fn(token=a.token, channel=a.channel, **payload["slack"])
                any_success = True

            elif a.type == "opsgenie":
                if not a.apiKey:
                    raise ValueError("Missing Opsgenie apiKey")
                logging.debug(f"Routing: sending Opsgenie (team={a.team})")
                send_opsgenie_fn(api_key=a.apiKey, **payload["opsgenie"])
                any_success = True

        except Exception as e:
            logging.error(f"Routing action failed (type={a.type}, team={a.team}): {e}")
            continue

    if not any_success:
        # Final safety net
        try:
            api_key = resolve_opsgenie_apikey(None)
            if api_key:
                logging.warning(
                    "All actions failed, attempting final Opsgenie fallback"
                )
                try:
                    ok = send_opsgenie_fn(api_key=api_key, **payload["opsgenie"])
                    if not ok:
                        logging.error("Final Opsgenie fallback did not confirm success")
                except Exception as send_err:
                    logging.error(
                        f"Final Opsgenie fallback failed during send: {send_err}"
                    )
            else:
                logging.error("Final fallback skipped: OPSGENIE_API_KEY not set")
            # Do not raise: report and continue gracefully
            status_msg = (
                "Escalation finished with errors; Opsgenie fallback attempted"
                if api_key
                else "Escalation finished with errors; Opsgenie fallback skipped"
            )
            logging.warning(status_msg)
        except Exception as e:
            # Swallow any unexpected errors here and log them instead of raising
            logging.error(f"Final Opsgenie fallback handling encountered an error: {e}")
            logging.warning(
                "Escalation finished with errors; fallback handling error was logged"
            )
