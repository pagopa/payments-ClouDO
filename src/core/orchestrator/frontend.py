from functools import lru_cache
from pathlib import Path
from typing import Any

FRONTEND_DIR = Path(__file__).parent / "fe"


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def render_template_str(template: str, ctx: dict[str, Any]) -> str:
    """
    Supporta:
    - {chiave} -> con escape HTML
    - {raw:chiave} -> inserimento raw (nessun escape). Usa solo per JS/CSS già serializzati.
    """
    safe_ctx = {
        k: (_html_escape(str(v)) if v is not None else "") for k, v in ctx.items()
    }
    # 1) rimpiazzo RAW
    import re

    def raw_sub(m):
        key = m.group(1)
        return "" if key not in ctx or ctx[key] is None else str(ctx[key])

    out = re.sub(r"\{raw:([a-zA-Z0-9_]+)\}", raw_sub, template)
    # 2) rimpiazzo con escape
    try:
        return out.format(**safe_ctx)
    except KeyError:
        return out


@lru_cache(maxsize=32)
def load_template(name: str) -> str:
    path = FRONTEND_DIR / name
    return path.read_text(encoding="utf-8")


def render_template(name: str, ctx: dict[str, Any]) -> str:
    tpl = load_template(name)
    return render_template_str(tpl, ctx)
