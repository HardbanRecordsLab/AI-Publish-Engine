from fastapi import APIRouter
from backend.themes import list_themes, get_theme
from backend.core.tokens import generate_design_system, list_themes as list_token_themes, get_tokens_for_ai, TOPIC_MAP
from backend.core.tokens import DAISYUI_MAP

router = APIRouter(prefix="/api/design-tokens", tags=["design-tokens"])


@router.get("/themes")
def get_themes():
    return list_themes()


@router.get("/themes/{theme_id}")
def get_theme_detail(theme_id: str):
    t = get_theme(theme_id)
    if not t.get("id"):
        return {"error": "Theme not found"}
    import json
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
def get_topic_map():
    return [
        {"topic": topic, "themes": styles}
        for topic, styles in sorted(TOPIC_MAP.items())
    ]


@router.get("/ai-context")
def get_ai_context():
    return {"context": get_tokens_for_ai()}
