"""Free AI image generation — Pollinations.ai (no API key) + SVG fallback."""
import base64
import time
import urllib.error
import urllib.parse
import urllib.request

from loguru import logger

from backend.core.cover_art import generate_cover_svg, generate_illustration

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}?width={w}&height={h}&seed={seed}&nofeed=true&model=flux"
_last_fetch = 0.0


def _img_to_b64(data: bytes, fmt: str = "jpeg") -> str:
    return f"data:image/{fmt};base64," + base64.b64encode(data).decode()


def _fetch_image(url: str, timeout: int = 30, retry: int = 0) -> bytes | None:
    global _last_fetch
    # Rate limit: max 1 request per 2 seconds (Pollinations free tier)
    now = time.time()
    since_last = now - _last_fetch
    if since_last < 2.0:
        time.sleep(2.0 - since_last)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AI-Publish-Engine/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            _last_fetch = time.time()
            return resp.read()
    except Exception as e:
        logger.warning(f"Image fetch failed: {e}")
        _last_fetch = time.time()  # prevent rapid retries
        return None


def generate_cover_image(title: str, subtitle: str, author: str, topic: str, colors: dict, fonts: dict,
                         style: str = "minimal") -> tuple[str, str]:
    """Generate a cover image using AI (Pollinations) or SVG fallback.
    Returns (image_data_uri: str, svg_fallback: str)."""
    prompt = f"Professional book cover, {topic}, {style} style, clean typography, abstract geometric, {colors.get('accent', 'blue')} color scheme, high quality, book cover design"
    seed = hash(title + author) % 100000
    url = POLLINATIONS_URL.format(prompt=urllib.parse.quote(prompt), w=1200, h=1600, seed=seed)

    data = _fetch_image(url)
    if data:
        logger.info(f"Cover image generated via Pollinations ({len(data)} bytes)")
        return _img_to_b64(data), ""

    logger.warning("Pollinations failed, using SVG fallback")
    svg = generate_cover_svg(title, subtitle, author, topic, colors, fonts)
    return "", svg


def generate_chapter_image(chapter_title: str, chapter_index: int, topic: str, colors: dict,
                           style: str = "minimal") -> tuple[str, str]:
    """Generate a chapter illustration using AI or SVG fallback."""
    prompt = f"Abstract illustration for chapter about {chapter_title}, {topic}, clean vector style, {colors.get('accent', 'blue')} accents, modern design"
    seed = hash(chapter_title + str(chapter_index)) % 100000
    url = POLLINATIONS_URL.format(prompt=urllib.parse.quote(prompt), w=800, h=200, seed=seed)

    data = _fetch_image(url, timeout=20)
    if data:
        logger.info(f"Chapter {chapter_index+1} image generated ({len(data)} bytes)")
        return _img_to_b64(data), ""

    svg = generate_illustration(topic, chapter_title, chapter_index, colors)
    return "", svg


def generate_infographic_image(title: str, description: str, chapter_title: str, colors: dict,
                               style: str = "minimal") -> tuple[str, str]:
    """Generate an infographic/image for data visualization."""
    prompt = f"Data visualization infographic, {title}, {description}, {style} style, clean modern chart, {colors.get('accent', 'blue')} colors"
    seed = hash(title + description) % 100000
    url = POLLINATIONS_URL.format(prompt=urllib.parse.quote(prompt[:200]), w=600, h=400, seed=seed)

    data = _fetch_image(url, timeout=20)
    if data:
        return _img_to_b64(data), ""
    return "", ""
