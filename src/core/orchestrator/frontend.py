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

    safe_ctx = {k: ("" if v is None else _html_escape(str(v))) for k, v in ctx.items()}

    # capture {raw:key}
    raw_tokens: dict[str, str] = {}

    def raw_sub(m):
        key = m.group(1)
        val = "" if key not in ctx or ctx[key] is None else str(ctx[key])
        token = f"__RAW_TOKEN__{len(raw_tokens)}__"
        raw_tokens[token] = val
        return token

    tmp = re.sub(r"\{raw:([a-zA-Z0-9_]+)\}", raw_sub, template)

    # capture {key}
    norm_tokens: dict[str, str] = {}

    def norm_sub(m):
        key = m.group(1)
        token = f"__NORM_TOKEN__{len(norm_tokens)}__"
        norm_tokens[token] = key
        return token

    tmp = re.sub(r"\{([a-zA-Z0-9_]+)\}", norm_sub, tmp)

    # escape literal braces for str.format
    tmp = tmp.replace("{", "{{").replace("}", "}}")

    # restore {key}
    for token, key in norm_tokens.items():
        tmp = tmp.replace(token, "{" + key + "}")

    try:
        formatted = tmp.format(**safe_ctx)
    except KeyError:
        formatted = tmp

    # restore raw tokens
    for token, val in raw_tokens.items():
        formatted = formatted.replace(token, val)

    return formatted


@lru_cache(maxsize=32)
def load_template(name: str) -> str:
    path = FRONTEND_DIR / name
    return path.read_text(encoding="utf-8")


def render_template(name: str, ctx: dict[str, Any]) -> str:
    tpl = load_template(name)
    return render_template_str(tpl, ctx)
