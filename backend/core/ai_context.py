"""AI Context — design system metadata for agent prompts (from CMLP research)."""
from backend.core.tokens import DAISYUI_MAP


def get_website_component_list() -> str:
    return """Available website component blocks (based on CMLP Design System):
  LAYOUT: container, grid, flex, stack, divider, section
  NAVIGATION: navbar (top|sticky|transparent), tabs, breadcrumbs, pagination, menu, steps
  HERO: hero-minimal, hero-split, hero-video, hero-animated, hero-gradient
  CONTENT: card (image|icon|horizontal|profile), accordion, timeline, table, article, prose
  FORMS: input, select, textarea, checkbox, radio, toggle, range, file-input, input-group
  FEEDBACK: alert (info|success|warning|error), toast, modal, drawer, tooltip, popover, badge
  MARKETING: stats, reviews, pricing, contact, newsletter, testimonial, team, faq, cta
  DATA: chart (bar|line|pie), table-sortable, stat-card, metric, progress, countdown
  MEDIA: image, video, audio-player, carousel, gallery, lightbox, icon-font
  SPECIAL: magical-button, gradient-text, animated-heading, floating-action, sticky-header"""


def get_website_page_templates() -> str:
    return """Website page templates (multi-section compositions):
  landing-page: hero + features + stats + testimonials + pricing/cta + faq + footer
  blog-post: header + article + sidebar + comments + related-posts + footer
  documentation: sidebar-nav + breadcrumbs + content + edit-link + footer
  dashboard: sidebar + topbar + stats-cards + data-table + charts + footer
  marketing: hero + logos + testimonials + features + comparison + cta + footer
  about: hero-story + mission-stats + team-grid + timeline + contact
  contact: form + info + map + social-links"""


def get_design_system_summary() -> str:
    return (
        "The design system uses Tailwind CSS + daisyUI with 30+ themes. "
        "daisyUI provides semantic CSS classes (btn, card, badge, etc.) that "
        "automatically adapt to the active theme. Components are framework-agnostic. "
        "The system supports dark mode via the 'dark' daisyUI theme or via "
        "media-query-based dark mode toggle. All layouts are responsive with "
        "Tailwind breakpoints (sm:640px, md:768px, lg:1024px, xl:1280px, 2xl:1536px)."
    )


def get_website_agent_context() -> str:
    lines = [get_design_system_summary(), ""]
    lines.append("DAISYUI THEMES (use data-theme attribute on <html>):")
    lines.append(", ".join(sorted(DAISYUI_MAP.values())))
    lines.append("")
    lines.append("COMPONENTS:")
    lines.append(get_website_component_list())
    lines.append("")
    lines.append("PAGE TEMPLATES:")
    lines.append(get_website_page_templates())
    lines.append("")
    lines.append("STYLE PREFERENCES:")
    lines.append("  Always use daisyUI component classes (btn, card, input, etc.)")
    lines.append("  Use Tailwind utility classes for custom styling")
    lines.append("  Include `data-theme` attribute for theme support")
    lines.append("  Use Alpine.js (x-data, x-model, @click) for interactivity")
    lines.append("  Make all components responsive and accessible")
    lines.append("  Load from CDN: Tailwind, daisyUI, Alpine.js")
    return "\n".join(lines)
