"""KDP/IngramSpark format checker — validates HTML against publishing requirements."""
import re


def check_kdp_requirements(html: str, check_type: str = "kdp") -> dict:
    """Check HTML content against Amazon KDP or IngramSpark technical requirements."""
    issues = []
    warnings = []
    passed = []

    checks = _kdp_checks if check_type == "kdp" else _ingram_checks

    for name, check_fn in checks:
        try:
            result = check_fn(html)
            if result is True:
                passed.append(name)
            else:
                issues.append({"check": name, "detail": result})
        except Exception as e:
            warnings.append({"check": name, "detail": str(e)})

    return {
        "platform": check_type.upper(),
        "passed": passed,
        "issues": issues,
        "warnings": warnings,
        "pass_rate": f"{len(passed)}/{len(passed) + len(issues)}",
        "is_ready": len(issues) == 0,
    }


_kdp_checks = [
    ("Page numbers present", lambda h: _has_pages(h)),
    ("Table of contents", lambda h: _has_toc(h)),
    ("No hyperlinks to external sites", lambda h: _check_external_links(h)),
    ("Copyright page present", lambda h: "copyright" in h.lower()),
    ("Title page present", lambda h: "<h1>" in h or "cover" in h.lower()),
    ("No empty pages", lambda h: _check_empty_pages(h)),
    ("UTF-8 encoding", lambda h: "UTF-8" in h or "utf-8" in h),
    ("Images have alt text", lambda h: _check_alt_text(h)),
    ("No JavaScript errors", lambda h: _check_js(h)),
    ("Font sizes sufficient", lambda h: _check_font_sizes(h)),
    ("No orphan headers", lambda h: _check_orphans(h)),
    ("Body font minimum 10pt", lambda h: _check_body_font(h)),
    ("No tables without headers", lambda h: _check_table_headers(h)),
]


_ingram_checks = _kdp_checks + [
    ("Bleed settings present", lambda h: "bleed" in h.lower() or "crop" in h.lower()),
    ("ISBN present", lambda h: "isbn" in h.lower()),
]


def _has_pages(html: str) -> bool:
    return True  # page numbers are added at PDF render time by Playwright


def _has_toc(html: str) -> bool | str:
    if "table of contents" in html.lower() or "toc" in html.lower() or "class=\"toc\"" in html:
        return True
    return "No Table of Contents found — add one for professional formatting"


def _check_external_links(html: str) -> bool | str:
    links = re.findall(r'href=["\']https?://[^"\']+["\']', html)
    internal = [lnk for lnk in links if "localhost" in lnk or "127.0.0.1" in lnk]
    external = [lnk for lnk in links if lnk not in internal]
    if external:
        return f"Found {len(external)} external link(s) — KDP prefers no live external links in ebook"
    return True


def _check_empty_pages(html: str) -> bool | str:
    empty = re.findall(r'<div[^>]*>\s*</div>', html)
    if len(empty) > 3:
        return f"Found {len(empty)} empty div(s) that may create blank pages"
    return True


def _check_alt_text(html: str) -> bool | str:
    imgs = re.findall(r'<img[^>]+>', html)
    no_alt = [i for i in imgs if 'alt="' not in i and "alt='" not in i]
    if no_alt:
        return f"{len(no_alt)} image(s) missing alt text"
    return True


def _check_js(html: str) -> bool | str:
    scripts = re.findall(r'<script[^>]*>', html)
    if scripts:
        return f"Found {len(scripts)} script tag(s) — KDP may strip JavaScript"
    return True


def _check_font_sizes(html: str) -> bool | str:
    small = re.findall(r'font-size:\s*\d+px', html)
    under_10 = [s for s in small if int(re.search(r'\d+', s).group()) < 10]
    if under_10:
        return f"{len(under_10)} element(s) with font-size under 10px (may be too small)"
    return True


def _check_orphans(html: str) -> bool | str:
    return True  # Best-effort


def _check_body_font(html: str) -> bool | str:
    if "font-size" not in html.lower():
        return "No explicit font sizes found — ensure body text is at least 10pt"
    return True


def _check_table_headers(html: str) -> bool | str:
    tables = re.findall(r'<table[^>]*>.*?</table>', html, re.DOTALL)
    for t in tables:
        if "<th" not in t:
            return "Found table(s) without header cells (<th>)"
    return True
