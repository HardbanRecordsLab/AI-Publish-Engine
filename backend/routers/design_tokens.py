from fastapi import APIRouter, Request

from backend.core.tokens import DAISYUI_MAP, TOPIC_MAP, get_tokens_for_ai
from backend.limiter import limiter
from backend.themes import get_theme, list_themes

router = APIRouter(prefix="/api/design-tokens", tags=["design-tokens"])


@router.get("/themes")
@limiter.limit("60/minute")
def get_themes(request: Request):
    return list_themes()


@router.get("/themes/{theme_id}")
@limiter.limit("60/minute")
def get_theme_detail(request: Request, theme_id: str):
    t = get_theme(theme_id)
    if not t.get("id"):
        return {"error": "Theme not found"}
    from pathlib import Path
    theme_dir = Path(__file__).resolve().parent.parent.parent / "templates" / "themes" / theme_id
    css_content = ""
    if theme_dir.exists() and (theme_dir / "theme.css").exists():
        css_content = (theme_dir / "theme.css").read_text(encoding="utf-8")
    return {
        **t,
        "page": {k: str(v) for k, v in t.get("page", {}).items()},
        "daisyui_theme": DAISYUI_MAP.get(theme_id, "winter"),
        "css": css_content,
    }


@router.get("/topic-map")
@limiter.limit("60/minute")
def get_topic_map(request: Request):
    return [
        {"topic": topic, "themes": styles}
        for topic, styles in sorted(TOPIC_MAP.items())
    ]


@router.get("/ai-context")
@limiter.limit("60/minute")
def get_ai_context(request: Request):
    return {"context": get_tokens_for_ai()}
