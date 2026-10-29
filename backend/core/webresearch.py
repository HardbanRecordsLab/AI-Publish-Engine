"""Real web research for course generation: search providers, safe page fetching, and a numbered source list.

Until now the "research" step only asked the model for suggestions, so nothing in a book was grounded in a page anybody had
actually read. This module searches the web and reads the pages, then hands the course writer short extracts with a
stable id (S1, S2 ...) so lessons can cite them and the course can list its sources.

Search providers (the first ones configured win, the keyless baseline is always available):
  BRAVE_API_KEY      Brave Search API
  TAVILY_API_KEY     Tavily
  SEARXNG_URL        a SearXNG instance (JSON output enabled)
  Wikipedia + OpenAlex   no key; encyclopaedic background and scholarly abstracts

Everything fetched is untrusted: the caller must fence() it before it goes into a prompt (see course_gen.py).
Page fetching refuses non-public addresses (SSRF), honours robots.txt, caps size and time, and follows only a few redirects.
"""
from __future__ import annotations

import ipaddress
import os
import re
import socket
import time
import urllib.robotparser
from dataclasses import asdict, dataclass
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from loguru import logger

USER_AGENT = "HRL-AIPublish-Research/1.0 (+https://hardbanrecordslab.online; contact@hardbanrecordslab.online)"
MAX_PAGE_BYTES = 1_500_000
MAX_EXTRACT_CHARS = 3500
HTTP_TIMEOUT = 12.0
MAX_REDIRECTS = 4
_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")


@dataclass
class Hit:
    title: str
    url: str
    snippet: str = ""
    provider: str = ""
    license: str = ""


@dataclass
class Source:
    id: str
    title: str
    url: str
    text: str
    provider: str
    license: str = ""

    def public(self) -> dict:
        """What ends up in the published course: no raw page text, only what a reader needs to find the source."""
        return {"id": self.id, "title": self.title, "url": self.url, "license": self.license}


# ---------------------------------------------------------------- safe HTTP

class UnsafeURL(ValueError):
    pass


def check_public_url(url: str) -> str:
    """Return the URL when it is http(s) and every address its host resolves to is public; raise UnsafeURL otherwise."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise UnsafeURL(f"unsupported URL: {url[:80]}")
    if p.port not in (None, 80, 443):
        raise UnsafeURL(f"unusual port refused: {p.port}")
    host = p.hostname
    try:
        infos = socket.getaddrinfo(host, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise UnsafeURL(f"cannot resolve {host}: {e}") from e
    if not infos:
        raise UnsafeURL(f"no address for {host}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise UnsafeURL(f"{host} resolves to a non-public address")
    return url


def _get(url: str, *, headers: dict | None = None, params: dict | None = None, json_body: dict | None = None,
         timeout: float = HTTP_TIMEOUT) -> httpx.Response:
    """Single seam for API calls to the search providers (tests replace it)."""
    h = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    h.update(headers or {})
    if json_body is not None:
        return httpx.post(url, headers=h, params=params, json=json_body, timeout=timeout)
    return httpx.get(url, headers=h, params=params, timeout=timeout)


def fetch_page(url: str, *, max_bytes: int = MAX_PAGE_BYTES, timeout: float = HTTP_TIMEOUT) -> tuple[str, str] | None:
    """Read one public HTML/text page and return (title, readable text), or None when it must not or cannot be read."""
    try:
        current = check_public_url(url)
        for _ in range(MAX_REDIRECTS + 1):
            if not _robots_allows(current):
                logger.info(f"research: robots.txt disallows {current[:100]}")
                return None
            with httpx.stream("GET", current, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain;q=0.9"},
                              timeout=timeout, follow_redirects=False) as r:
                if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                    current = check_public_url(urljoin(current, r.headers["location"]))
                    continue
                if r.status_code != 200:
                    return None
                ctype = r.headers.get("content-type", "").lower()
                if not any(t in ctype for t in ("text/html", "text/plain", "application/xhtml")):
                    return None
                body = b""
                for chunk in r.iter_bytes():
                    body += chunk
                    if len(body) > max_bytes:
                        break
                enc = r.encoding or "utf-8"
            raw = body[:max_bytes].decode(enc, "replace")
            return _readable(raw, plain="text/plain" in ctype)
        return None
    except (UnsafeURL, httpx.HTTPError, OSError) as e:
        logger.info(f"research: cannot read {url[:100]}: {e}")
        return None


_robots_cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def _robots_allows(url: str) -> bool:
    p = urlparse(url)
    key = f"{p.scheme}://{p.netloc}"
    if key not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        try:
            check_public_url(key + "/robots.txt")
            r = httpx.get(key + "/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=6.0, follow_redirects=False)
            if r.status_code == 200 and len(r.content) < 500_000:
                rp.parse(r.text.splitlines())
                _robots_cache[key] = rp
            else:
                _robots_cache[key] = None   # no robots.txt (or unreadable): nothing forbids reading
        except (UnsafeURL, httpx.HTTPError, OSError):
            _robots_cache[key] = None
    rp = _robots_cache[key]
    return True if rp is None else rp.can_fetch(USER_AGENT, url)


def _readable(raw: str, plain: bool = False) -> tuple[str, str]:
    if plain:
        return "", re.sub(r"\s+", " ", raw).strip()[:6000]
    soup = BeautifulSoup(raw, "lxml")
    title = re.sub(r"\s+", " ", soup.title.get_text()).strip() if soup.title else ""
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form", "iframe", "svg"]):
        tag.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    text = re.sub(r"\s+", " ", root.get_text(" ")).strip()
    return title[:200], text[:6000]


# ---------------------------------------------------------------- providers

def _brave(query: str, language: str) -> list[Hit]:
    key = os.getenv("BRAVE_API_KEY")
    if not key:
        return []
    r = _get("https://api.search.brave.com/res/v1/web/search", headers={"X-Subscription-Token": key},
             params={"q": query, "count": 6, "search_lang": language or "en"})
    r.raise_for_status()
    return [Hit(x.get("title", ""), x["url"], _plain(x.get("description", "")), "brave")
            for x in ((r.json().get("web") or {}).get("results") or []) if x.get("url")]


def _tavily(query: str, language: str) -> list[Hit]:
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        return []
    r = _get("https://api.tavily.com/search", json_body={"api_key": key, "query": query, "max_results": 6, "search_depth": "basic"})
    r.raise_for_status()
    return [Hit(x.get("title", ""), x["url"], _plain(x.get("content", "")), "tavily")
            for x in (r.json().get("results") or []) if x.get("url")]


def _searx(query: str, language: str) -> list[Hit]:
    base = (os.getenv("SEARXNG_URL") or "").rstrip("/")
    if not base:
        return []
    r = _get(base + "/search", params={"q": query, "format": "json", "language": language or "en"})
    r.raise_for_status()
    return [Hit(x.get("title", ""), x["url"], _plain(x.get("content", "")), "searxng")
            for x in (r.json().get("results") or [])[:6] if x.get("url")]


def _wikipedia(query: str, language: str) -> list[Hit]:
    lang = (language or "en")[:2].lower()
    r = _get(f"https://{lang}.wikipedia.org/w/api.php", params={
        "action": "query", "format": "json", "generator": "search", "gsrsearch": query, "gsrlimit": 4,
        "prop": "extracts|info", "exintro": 1, "explaintext": 1, "exchars": MAX_EXTRACT_CHARS, "exlimit": "max", "inprop": "url"})
    r.raise_for_status()
    pages = sorted(((r.json().get("query") or {}).get("pages") or {}).values(), key=lambda p: p.get("index", 99))
    return [Hit(p["title"], p["fullurl"], _plain(p.get("extract", "")), "wikipedia", "CC BY-SA 4.0 (Wikipedia)")
            for p in pages if p.get("fullurl") and len(p.get("extract", "")) > 150]


def _openalex(query: str, language: str) -> list[Hit]:
    r = _get("https://api.openalex.org/works", params={
        "search": query, "per-page": 5, "mailto": "contact@hardbanrecordslab.online",
        "select": "id,title,doi,publication_year,abstract_inverted_index", "filter": "has_abstract:true"})
    r.raise_for_status()
    hits = []
    for w in r.json().get("results") or []:
        abstract = _abstract(w.get("abstract_inverted_index"))
        url = w.get("doi") or w.get("id")
        if url and w.get("title") and len(abstract) > 200:
            hits.append(Hit(f"{w['title']} ({w.get('publication_year', 's.d.')})", url, abstract[:MAX_EXTRACT_CHARS], "openalex"))
    return hits


def _abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    pos = [(i, word) for word, idxs in inv.items() for i in idxs]
    return " ".join(w for _, w in sorted(pos))


def _plain(html: str) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(html or "", "lxml").get_text(" ")).strip()


PROVIDERS = [("brave", _brave), ("tavily", _tavily), ("searxng", _searx), ("wikipedia", _wikipedia), ("openalex", _openalex)]


def active_providers() -> list[str]:
    names = []
    if os.getenv("BRAVE_API_KEY"):
        names.append("brave")
    if os.getenv("TAVILY_API_KEY"):
        names.append("tavily")
    if os.getenv("SEARXNG_URL"):
        names.append("searxng")
    return names + ["wikipedia", "openalex"]


# ---------------------------------------------------------------- orchestration

def urls_in(text: str, limit: int = 6) -> list[str]:
    """URLs the author put in the brief or the uploaded material: those are read first."""
    seen, out = set(), []
    for u in _URL_RE.findall(text or ""):
        u = u.rstrip(".,;:!?")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out[:limit]


def _norm(url: str) -> str:
    p = urlparse(url)
    return f"{p.netloc.lower().removeprefix('www.')}{p.path.rstrip('/')}"


def gather_sources(queries: list[str], language: str = "en", *, user_urls: list[str] | None = None,
                   max_sources: int = 10, fetch_pages: int = 4, deadline_s: float = 120.0) -> list[Source]:
    """Search every query on every active provider, read the best pages, return numbered sources (S1, S2 ...)."""
    started = time.monotonic()
    hits: list[Hit] = []
    for u in user_urls or []:
        hits.append(Hit("", u, "", "author"))
    active = {name for name in active_providers()}
    per_query: list[list[Hit]] = []
    for q in queries:
        found: list[Hit] = []
        for name, fn in PROVIDERS:
            if name not in active or time.monotonic() - started > deadline_s:
                continue
            try:
                found += fn(q, language)
            except Exception as e:  # noqa: BLE001 - one failing provider must not end the research
                logger.warning(f"research: {name} failed for '{q[:50]}': {e}")
        per_query.append(found)
    # interleave so that the first query does not crowd out the others
    for i in range(max((len(f) for f in per_query), default=0)):
        for found in per_query:
            if i < len(found):
                hits.append(found[i])

    out: list[Source] = []
    seen: set[str] = set()
    fetched = 0
    for h in hits:
        if len(out) >= max_sources or time.monotonic() - started > deadline_s:
            break
        key = _norm(h.url)
        if key in seen:
            continue
        seen.add(key)
        title, text = h.title, h.snippet
        thin = len(text) < 500 and h.provider not in ("wikipedia", "openalex")
        if (thin or h.provider == "author") and fetched < fetch_pages + len(user_urls or []):
            page = fetch_page(h.url)
            fetched += 1
            if page:
                title = title or page[0]
                text = page[1] if len(page[1]) > len(text) else text
        if len(text) < 150:
            continue
        out.append(Source(f"S{len(out) + 1}", (title or urlparse(h.url).netloc)[:200], h.url, text[:MAX_EXTRACT_CHARS], h.provider, h.license))
    logger.info(f"research: {len(out)} sources from {len(queries)} queries via {', '.join(sorted(active))} in {time.monotonic() - started:.0f}s")
    return out


def sources_as_dicts(sources: list[Source]) -> list[dict]:
    return [asdict(s) for s in sources]
