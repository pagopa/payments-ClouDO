import logging
from typing import Any, Optional

import azure.functions as func

# =========================
# UTILS Functions
# =========================


def lower_keys(obj: Any) -> Any:
    """Recursively lower-case dict keys."""
    if isinstance(obj, dict):
        return {str(k).lower(): lower_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [lower_keys(x) for x in obj]
    return obj


def parse_resource_fields(req: func.HttpRequest) -> dict[str, Any]:
    """
    Extract resource info from an Azure Monitor alert (Common Alert Schema).

    ARM resourceId resolution priority:
      1) data.essentials.alertTargetIDs (list of ARM IDs)
      2) data.alertContext.labels["microsoft.resourceid"]
      3) data.alertContext.resourceId
      4) data.essentials.monitorCondition (State of alert "Fired" or "Resolved)

    Fallbacks (when no ARM ID is available):
      - resourceName from essentials.configurationItems[0] or alertContext.resourceName
      - resourceGroup from alertContext.resourceGroup
      - resourceId from alertContext.resourceId

    Additionally extracts Kubernetes fields when present:
      - namespace (labels/annotations)
      - pod (labels/annotations: "pod" or "kubernetes_pod_name")
      - deployment (labels/annotations: "deployment" or "kubernetes_deployment")
      - job (labels/annotations: "job" but avoids Prometheus data-source "job" by preferring k8s-specific keys)

    Returns:
      {
        resourceName, resourceGroup, resourceId, schema_id, namespace,
        pod, deployment, job
      }
    """
    # Parse body defensively
    try:
        data = req.get_json() or {}
        lower = lower_keys(data)
    except ValueError:
        lower = {}

    e = lower.get("data", {}) or {}
    essentials = e.get("essentials", {}) or {}
    ctx = e.get("alertcontext", {}) or {}
    labels = ctx.get("labels") or {}
    annotations = ctx.get("annotations") or {}

    # Build candidate ARM IDs from the most reliable locations
    candidates: list[str] = []

    # 1) essentials.alertTargetIDs (list of ARM IDs)
    alert_target_ids = essentials.get("alerttargetids") or []
    candidates.extend(x for x in alert_target_ids if isinstance(x, str))

    # 2) alertContext.labels["microsoft.resourceid"]
    mrid = labels.get("microsoft.resourceid")
    if isinstance(mrid, str):
        candidates.append(mrid)

    # 3) alertContext.resourceId
    rid = ctx.get("resourceid")
    if isinstance(rid, str):
        candidates.append(rid)

    # Pick the first valid ARM ID (must start with '/subscriptions/')
    resource_id: Optional[str] = next(
        (
            x
            for x in candidates
            if isinstance(x, str) and x.startswith("/subscriptions/")
        ),
        None,
    )

    # Resolve schema identifiers (query ?id=..., essentials.alertId, essentials.alertRule)
    schema_ids = extract_schema_id_from_req(req)

    resource_group: Optional[str] = None
    resource_name: Optional[str] = None

    if resource_id:
        parts = resource_id.strip("/").split("/")
        parts_l = [p.lower() for p in parts]
        try:
            rg_index = parts_l.index("resourcegroups") + 1
            resource_group = parts_l[rg_index]
        except Exception:
            resource_group = None
        resource_name = parts_l[-1] if parts_l else None
    else:
        config_items = essentials.get("configurationitems") or []
        if config_items and isinstance(config_items, list):
            resource_name = config_items[0]
        resource_name = (
            resource_name or ctx.get("resourcename") or labels.get("resourcename")
        )
        resource_group = ctx.get("resourcegroup") or labels.get("resourcegroup")
        resource_id = ctx.get("resourceid") or labels.get("resourceid")

    # Kubernetes fields
    namespace = (
        labels.get("namespace")
        or labels.get("kubernetes_namespace")
        or annotations.get("namespace")
        or annotations.get("kubernetes_namespace")
    )

    # Prefer k8s-specific keys, then generic ones; avoid Prometheus data-source "job" collision
    pod = (
        labels.get("pod")
        or labels.get("kubernetes_pod_name")
        or annotations.get("pod")
        or annotations.get("kubernetes_pod_name")
    )

    deployment = (
        labels.get("deployment")
        or labels.get("kubernetes_deployment")
        or annotations.get("deployment")
        or annotations.get("kubernetes_deployment")
    )

    # For a job, first try k8s-specific; only then consider generic "job" if it doesn't look like "kube-state-metrics"
    job = (
        labels.get("kubernetes_job_name")
        or annotations.get("kubernetes_job_name")
        or labels.get("job_name")
        or annotations.get("job_name")
    )

    horizontalpodautoscaler = (
        labels.get("horizontalpodautoscaler")
        or labels.get("kubernetes_horizontalpodautoscaler")
        or annotations.get("horizontalpodautoscaler")
        or annotations.get("kubernetes_horizontalpodautoscaler")
    )

    monitor_condition = essentials.get("monitorcondition") or ""
    severity = essentials.get("severity") or ""
    if not job:
        cand = labels.get("job") or annotations.get("job")
        if cand and cand != "kube-state-metrics":
            job = cand

    return {
        "resourceName": resource_name,
        "resourceGroup": resource_group,
        "resourceId": resource_id,
        "schema_id": schema_ids,
        "namespace": namespace,
        "pod": pod,
        "deployment": deployment,
        "horizontalpodautoscaler": horizontalpodautoscaler,
        "job": job,
        "monitorCondition": monitor_condition,
        "severity": severity,
    }


def extract_schema_id_from_req(req: func.HttpRequest) -> Optional[list[str]]:
    """
    Resolve schema_id from the incoming request:
      1) Query string (?id=...)
      2) JSON body: data.essentials.alertId and data.essentials.alertRule

    Normalization:
      - If the value contains '/', return the trailing segment.
      - De-duplicate while preserving order.
    """

    def normalize(val) -> str:
        s = str(val).strip()
        if "/" in s:
            last = s.strip("/").split("/")[-1]
            return last or s
        return s

    candidates: list[str] = []

    q_id = req.params.get("id")
    if q_id:
        logging.info("Resolving schema_id: %s", q_id)
        candidates.append(normalize(q_id))
        return candidates

    try:
        body = req.get_json()
        logging.info("body: %s", body)
    except ValueError:
        body = None

    if isinstance(body, dict):
        essentials = body.get("data", {}).get("essentials", {}) or {}
        raw_candidates = [
            essentials.get("alertId"),
            essentials.get("alertRule"),
        ]
        for c in raw_candidates:
            if c:
                candidates.append(normalize(c))

    seen = set()
    unique_candidates: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique_candidates.append(c)

    return unique_candidates or None
