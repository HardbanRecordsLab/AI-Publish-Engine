STYLE_PACKS = {
    "minimal": {
        "name": "Minimal Pro",
        "colors": {
            "background": "#FFFFFF",
            "text": "#1A1A1A",
            "heading": "#000000",
            "accent": "#4A4A4A",
            "secondary": "#F5F5F5",
            "muted": "#CCCCCC",
            "border": "#E5E5E5",
        },
        "fonts": {"heading": "Georgia, 'Times New Roman', serif", "body": "Inter, 'Helvetica Neue', Arial, sans-serif"},
        "spacing": "large",
        "cover_style": "clean_center",
    },
    "corporate": {
        "name": "Corporate Pro",
        "colors": {
            "background": "#FFFFFF",
            "text": "#1E2A3A",
            "heading": "#0F172A",
            "accent": "#2563EB",
            "secondary": "#F0F4FF",
            "muted": "#94A3B8",
            "border": "#CBD5E1",
        },
        "fonts": {"heading": "Georgia, 'Times New Roman', serif", "body": "Inter, 'Helvetica Neue', Arial, sans-serif"},
        "spacing": "medium",
        "cover_style": "structured_center",
    },
    "dark": {
        "name": "Dark Premium",
        "colors": {
            "background": "#0B0F1A",
            "text": "#E2E8F0",
            "heading": "#F1F5F9",
            "accent": "#00E5FF",
            "secondary": "#1A1F2E",
            "muted": "#475569",
            "border": "#1E293B",
        },
        "fonts": {"heading": "Georgia, 'Times New Roman', serif", "body": "Inter, 'Helvetica Neue', Arial, sans-serif"},
        "spacing": "medium",
        "cover_style": "bold_center",
    },
}


def get_style_pack(style: str) -> dict:
    return STYLE_PACKS.get(style, STYLE_PACKS["minimal"])


def list_styles() -> list:
    return [
        {"id": k, "name": v["name"], "colors": v["colors"]}
        for k, v in STYLE_PACKS.items()
    ]
