from loguru import logger

from backend.core.image_gen import generate_chapter_image, generate_cover_image, generate_infographic_image
from backend.core.jobs import update_job
from backend.orchestrator.agent import BaseAgent, PipelineContext


class CoverArtAgent(BaseAgent):
    """Generates cover art and illustrations using free AI image APIs + SVG fallback."""

    def __init__(self):
        super().__init__("CoverArtAgent")

    def run(self, ctx: PipelineContext) -> PipelineContext:
        logger.info("CoverArtAgent: generating cover art and illustrations")
        ebook = ctx.ebook_dict
        topic = ebook.get("topic", "general")
        title = ebook.get("title", "Ebook")
        subtitle = ebook.get("subtitle", "")
        author = ebook.get("author", "AI Design Engine")

        # Get theme colors
        from backend.themes import get_theme
        try:
            from backend.core.builder import STYLE_THEME_MAP
            theme_id = STYLE_THEME_MAP.get(ctx.style, ctx.style)
        except Exception:
            theme_id = ctx.style
        try:
            theme = get_theme(theme_id)
        except Exception:
            theme = get_theme("minimal")
        colors = theme["colors"]
        fonts = theme["fonts"]

        # 1. Generate cover image (AI or SVG fallback)
        cover_data_uri, cover_svg = generate_cover_image(
            title, subtitle, author, topic, colors, fonts, ctx.style,
        )
        ctx.cover_svg = cover_svg  # SVG fallback (empty if AI worked)
        ctx.cover_image = cover_data_uri  # AI image data URI (empty if AI failed)
        logger.info(f"Cover: {'AI image' if cover_data_uri else 'SVG'} ({max(len(cover_data_uri), len(cover_svg))} chars)")

        # 2. Generate chapter illustrations
        chapters = ebook.get("chapters", [])
        ctx.chapter_illustrations = []
        for ci, ch in enumerate(chapters):
            ch_title = ch.get("title", f"Chapter {ci+1}")
            img_uri, svg = generate_chapter_image(ch_title, ci, topic, colors, ctx.style)
            ctx.chapter_illustrations.append({
                "chapter_index": ci,
                "title": ch_title,
                "image_uri": img_uri,
                "svg": svg,
            })
        logger.success(f"CoverArtAgent: {len(ctx.chapter_illustrations)} chapter images generated")

        # 3. Generate infographic-style images
        for ig in ctx.infographics:
            if not ig.get("image_uri"):
                ch_title = ""
                ch_idx = ig.get("chapter_index", 0)
                if ch_idx < len(chapters):
                    ch_title = chapters[ch_idx].get("title", "")
                img_uri, _ = generate_infographic_image(
                    ig.get("title", "Diagram"),
                    ig.get("description", ""),
                    ch_title, colors, ctx.style,
                )
                if img_uri:
                    ig["image_uri"] = img_uri

        ctx.set_progress(64)
        update_job(ctx.job_id, "processing", 64)
        return ctx
