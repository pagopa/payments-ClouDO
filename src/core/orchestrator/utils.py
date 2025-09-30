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


def extract_schema_id_from_req(req: func.HttpRequest) -> Optional[list]:
    """
    Resolve schema_id from the incoming request:
    1) Prefer query string (?id=...)
    2) Fallback to JSON body: data.essentials.alertId (or schemaId if available)
    Returns the alertId as-is. If you want only the trailing GUID, enable the split below.
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
        candidates.append(normalize(q_id))
    logging.info("Resolving schema_id: %s", req.params.get("id"))
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
    unique_candidates = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique_candidates.append(c)

    return unique_candidates
