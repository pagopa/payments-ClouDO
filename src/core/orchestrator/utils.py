import logging
from typing import Optional

import azure.functions as func


# Python
def parse_resource_fields(payload: func.HttpRequest):
    # Extracts resourceId, resourceGroup, and resourceName from a generic Azure Monitor alert payload
    data = payload.get_json() or {}
    e = data.get("data", {}) or {}
    ctx = e.get("alertContext", {}) or {}
    labels = ctx.get("labels") or {}
    annotations = ctx.get("annotations") or {}

    # Collect candidate ARM resource IDs from reliable locations
    candidates = []
    candidates += e.get("alertContext") or []
    rid = ctx.get("resourceId")
    if rid:
        candidates.append(rid)

    # Pick the first valid ARM ID (must start with '/subscriptions/')
    resource_id = next(
        (
            x
            for x in candidates
            if isinstance(x, str) and x.startswith("/subscriptions/")
        ),
        None,
    )

    alert_id = extract_schema_id_from_req(payload)

    resource_group = None
    resource_name = None
    namespace = None

    if resource_id:
        # Parse ARM segments to get resource group and resource name
        parts = resource_id.strip("/").split("/")
        try:
            rg_index = parts.index("resourceGroups") + 1
            resource_group = parts[rg_index]
        except Exception:
            # Gracefully handle unexpected shapes
            resource_group = None

        # Take the last segment as the resource name (works with nested types too)
        resource_name = parts[-1] if parts else None

        namespace = (
            labels.get("namespace")
            or labels.get("kubernetes_namespace")
            or annotations.get("namespace")
            or annotations.get("kubernetes_namespace")
        )
    else:
        # Fallbacks when a proper ARM ID is missing
        config_items = e.get("configurationItems") or []
        if config_items:
            resource_name = config_items[0]
        resource_name = resource_name or ctx.get("resourceName")
        resource_group = resource_group or ctx.get("resourceGroup")
        resource_id = resource_id or ctx.get("resourceId")

    return {
        "resourceName": resource_name,
        "resourceGroup": resource_group,
        "resourceId": resource_id,
        "schema_id": alert_id,
        "namespace": namespace,
    }


def extract_schema_id_from_req(req: func.HttpRequest) -> Optional[str]:
    """
    Resolve schema_id from the incoming request:
    1) Prefer query string (?id=...)
    2) Fallback to JSON body: data.essentials.alertId (or schemaId if available)
    Returns the alertId as-is. If you want only the trailing GUID, enable the split below.
    """
    q_id = req.params.get("id")
    if q_id:
        return q_id
    logging.info("Resolving schema_id: %s", req.params.get("id"))
    try:
        body = req.get_json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        alert_id = body.get("data", {}).get("essentials", {}).get(
            "alertId"
        ) or body.get("schemaId")
        if alert_id:
            aid = str(alert_id).strip()
            if "/" in aid:
                last = aid.strip("/").split("/")[-1]
                return last or aid
            return aid
    return None


# def is_aks_alert(payload: func.HttpRequest) -> bool:
#     # Heuristics to detect AKS-related alerts (Managed AKS or Arc-enabled Kubernetes)
#     data = payload.get_json() or {}
#     e = data.get("data", {}) or {}
#     ctx = e.get("alertContext", {}) or {}
#
#     # Check ARM resource IDs for AKS/Arc Kubernetes providers
#     candidates = []
#     candidates += e.get("alertTargetIDs") or []
#     rid = ctx.get("resourceId")
#     if rid:
#         candidates.append(rid)
#     def looks_like_aks_id(x: str) -> bool:
#         s = (x or "").lower()
#         return (
#             "/providers/microsoft.containerservice/managedclusters/" in s
#             or "/providers/microsoft.kubernetes/connectedclusters/" in s
#         )
#
#     if any(isinstance(x, str) and looks_like_aks_id(x) for x in candidates):
#         return True
#
#     # Look for Kubernetes/Prometheus signals in labels/annotations
#     labels = ctx.get("labels") or {}
#     annotations = ctx.get("annotations") or {}
#     keys = {k.lower() for k in list(labels.keys()) + list(annotations.keys())}
#     k8s_keys = {"namespace", "kubernetes_namespace", "pod", "container", "node", "cluster", "cluster_name"}
#     if keys & k8s_keys:
#         return True
#
#     # Prometheus generator URL hint
#     gen = (ctx.get("generatorURL") or "").lower()
#     if "prometheus" in gen:
#         return True
#
#     # Optional: resourceType hints in essentials
#     rt = (e.get("resourceType") or "").lower()
#     if "containerservice" in rt or "kubernetes" in rt:
#         return True
#
#     return False
