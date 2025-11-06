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
    import re

    def esc(s: str) -> str:
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    # RAW
    raw_tokens = {}

    def raw_sub(m):
        k = m.group(1)
        v = "" if ctx.get(k) is None else str(ctx[k])
        t = f"__RAW__{len(raw_tokens)}__"
        raw_tokens[t] = v
        return t

    tmp = re.sub(r"\{raw:([a-z0-9_]+)\}", raw_sub, template, flags=re.I)
    # ONLY known keys
    keys = "|".join(map(re.escape, ctx.keys()))

    def norm_sub(m):
        k = m.group(1)
        v = ctx.get(k)
        return "" if v is None else esc(str(v))

    if keys:
        tmp = re.sub(r"\{(" + keys + r")\}", norm_sub, tmp)
    for t, v in raw_tokens.items():
        tmp = tmp.replace(t, v)
    return tmp


@lru_cache(maxsize=32)
def load_template(name: str) -> str:
    path = FRONTEND_DIR / name
    return path.read_text(encoding="utf-8")


def render_template(name: str, ctx: dict[str, Any]) -> str:
    tpl = load_template(name)
    return render_template_str(tpl, ctx)
