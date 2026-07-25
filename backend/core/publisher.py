"""Direct Publishing API — generate platform-ready files + metadata for self-publishing."""
from datetime import datetime
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring

# Every book from this pipeline is AI-generated — surfaced in metadata output
# so publishers remember to declare it where the platform requires that.
# Confirmed requirement: Amazon KDP's "Content Rights" step (since 2023) asks
# authors to disclose AI-generated/AI-assisted content. Other platforms'
# policies vary and change — verify current requirements before publishing.
AI_CONTENT_DISCLOSURE = (
    "This book was generated with AI assistance by AI Publishing Engine. "
    "Amazon KDP requires disclosing AI-generated or AI-assisted content in "
    "the 'Content Rights' section of the KDP dashboard — check the current "
    "AI-content policy of any other platform before publishing there too."
)

PLATFORMS = {
    "amazon_kdp": {
        "name": "Amazon KDP",
        "icon": "📕",
        "formats": ["pdf", "epub", "docx"],
        "cost": "Free — no setup fees, 30-70% royalty",
        "reach": "Global — 200+ countries",
        "requirements": "PDF with bleed, EPUB with valid OPF",
        "guide_url": "https://kdp.amazon.com/help/topic/G200735480",
    },
    "google_play": {
        "name": "Google Play Books",
        "icon": "📗",
        "formats": ["pdf", "epub"],
        "cost": "Free — no setup fees, ~52-70% royalty",
        "reach": "Global — 70+ countries",
        "requirements": "EPUB with valid OPF + ONIX metadata",
        "guide_url": "https://play.google.com/books/publish/",
    },
    "apple_books": {
        "name": "Apple Books",
        "icon": "📘",
        "formats": ["epub"],
        "cost": "Free — no setup fees, 70% royalty",
        "reach": "Global — 50+ countries",
        "requirements": "EPUB with Apple-specific metadata",
        "guide_url": "https://authors.apple.com/",
    },
    "kobo": {
        "name": "Kobo Writing Life",
        "icon": "📚",
        "formats": ["epub", "pdf"],
        "cost": "Free — no setup fees, 45-70% royalty",
        "reach": "Global — 190+ countries",
        "requirements": "EPUB + cover image",
        "guide_url": "https://www.kobo.com/writinglife",
    },
    "bn_press": {
        "name": "Barnes & Noble Press",
        "icon": "📖",
        "formats": ["epub", "pdf", "docx"],
        "cost": "Free — no setup fees, 65% royalty",
        "reach": "US only",
        "requirements": "EPUB or DOCX",
        "guide_url": "https://press.barnesandnoble.com/",
    },
    "draft2digital": {
        "name": "Draft2Digital",
        "icon": "📔",
        "formats": ["epub", "docx"],
        "cost": "Free — no setup fees, 10% commission, distributes to 40+ stores",
        "reach": "Global — via affiliates",
        "requirements": "Clean EPUB or DOCX",
        "guide_url": "https://draft2digital.com/",
    },
    "streetlib": {
        "name": "StreetLib",
        "icon": "📓",
        "formats": ["epub", "pdf"],
        "cost": "Free — no setup fees, commission-based",
        "reach": "Global — 100+ stores",
        "requirements": "EPUB + metadata",
        "guide_url": "https://streetlib.com/",
    },
    "smashwords": {
        "name": "Smashwords",
        "icon": "📗",
        "formats": ["epub"],
        "cost": "Free — no setup fees, commission-based",
        "reach": "Global — via affiliates",
        "requirements": "EPUB",
        "guide_url": "https://www.smashwords.com/",
    },
    "lulu": {
        "name": "Lulu",
        "icon": "📕",
        "formats": ["pdf", "epub", "docx"],
        "cost": "Free to publish — optional paid services, commission on sales",
        "reach": "Global",
        "requirements": "PDF with proper margins",
        "guide_url": "https://www.lulu.com/",
    },
    "publio_pl": {
        "name": "Publio",
        "icon": "🇵🇱",
        "formats": ["epub", "pdf"],
        "cost": "Free — prowizja od sprzedaży, brak opłat stałych",
        "reach": "Polska",
        "requirements": "EPUB z metadanymi po polsku",
        "guide_url": "https://publio.pl/",
    },
    "virtualo_pl": {
        "name": "Virtualo",
        "icon": "🇵🇱",
        "formats": ["epub", "pdf"],
        "cost": "Free — prowizja od sprzedaży, brak opłat stałych",
        "reach": "Polska",
        "requirements": "EPUB + opis po polsku",
        "guide_url": "https://virtualo.pl/",
    },
    "legimi_pl": {
        "name": "Legimi",
        "icon": "🇵🇱",
        "formats": ["epub", "pdf"],
        "cost": "Free — model subskrypcyjny dla czytelników, autor dostaje %",
        "reach": "Polska + Czechy",
        "requirements": "EPUB + metadane",
        "guide_url": "https://legimi.pl/",
    },
    "woblink_pl": {
        "name": "Woblink",
        "icon": "🇵🇱",
        "formats": ["epub", "pdf"],
        "cost": "Free — prowizja od sprzedaży, brak opłat stałych",
        "reach": "Polska",
        "requirements": "EPUB",
        "guide_url": "https://woblink.com/",
    },
    "ebookpoint_pl": {
        "name": "Ebookpoint / Nexto",
        "icon": "🇵🇱",
        "formats": ["pdf", "epub"],
        "cost": "Free — prowizja od sprzedaży, brak opłat stałych",
        "reach": "Polska",
        "requirements": "PDF + EPUB",
        "guide_url": "https://ebookpoint.pl/",
    },
}


def get_platforms() -> list:
    return [
        {"id": pid, **info}
        for pid, info in PLATFORMS.items()
    ]


def generate_onix_metadata(ebook_dict: dict, language: str = "en", isbn: str = "") -> str:
    """Generate ONIX 3.0 XML metadata for book distribution."""
    title = ebook_dict.get("title", "Untitled")
    author = ebook_dict.get("author", "Unknown")
    summary = ebook_dict.get("summary", "")

    root = Element("ONIXMessage", release="3.0")
    header = SubElement(root, "Header")
    sender = SubElement(header, "Sender")
    sender_name = SubElement(sender, "SenderName")
    sender_name.text = "AI Design Engine"
    sent_date = SubElement(header, "SentDateTime")
    sent_date.text = datetime.now().isoformat()

    product = SubElement(root, "Product")
    record_ref = SubElement(product, "RecordReference")
    record_ref.text = isbn or f"ADE-{datetime.now().timestamp()}"

    notification = SubElement(product, "NotificationType")
    notification.text = "03"

    desc_detail = SubElement(product, "DescriptiveDetail")
    product_composition = SubElement(desc_detail, "ProductComposition")
    product_composition.text = "00"
    product_form = SubElement(desc_detail, "ProductForm")
    product_form.text = "DG"

    title_detail = SubElement(desc_detail, "TitleDetail")
    title_type = SubElement(title_detail, "TitleType")
    title_type.text = "01"
    title_element = SubElement(title_detail, "TitleElement")
    title_element_level = SubElement(title_element, "TitleElementLevel")
    title_element_level.text = "01"
    title_text = SubElement(title_element, "TitleText")
    title_text.text = title

    contributor = SubElement(desc_detail, "Contributor")
    contributor_role = SubElement(contributor, "ContributorRole")
    contributor_role.text = "A01"
    person_name = SubElement(contributor, "PersonName")
    person_name.text = author

    language_tag = SubElement(desc_detail, "Language")
    language_role = SubElement(language_tag, "LanguageRole")
    language_role.text = "01"
    language_code = SubElement(language_tag, "LanguageCode")
    language_code.text = language

    extent = SubElement(desc_detail, "Extent")
    extent_type = SubElement(extent, "ExtentType")
    extent_type.text = "00"
    extent_value = SubElement(extent, "ExtentValue")
    extent_value.text = str(len(summary.split()))

    collateral = SubElement(product, "CollateralDetail")
    text_content = SubElement(collateral, "TextContent")
    text_type = SubElement(text_content, "TextType")
    text_type.text = "03"
    content_text = SubElement(text_content, "Text")
    content_text.text = summary[:4000]

    publishing = SubElement(product, "PublishingDetail")
    publisher = SubElement(publishing, "Publisher")
    publisher_role = SubElement(publisher, "PublishingRole")
    publisher_role.text = "01"
    publisher_name = SubElement(publisher, "PublisherName")
    publisher_name.text = "AI Design Engine Publishing"

    return minidom.parseString(tostring(root, encoding="unicode")).toprettyxml(indent="  ")


def generate_kdp_metadata(ebook_dict: dict) -> dict:
    """Generate KDP-specific metadata and formatting guide."""
    title = ebook_dict.get("title", "Untitled")
    author = ebook_dict.get("author", "Unknown")
    summary = ebook_dict.get("summary", "")
    return {
        "title": title,
        "author": author,
        "description": summary[:4000],
        "format_recommendations": {
            "pdf": "Use PDF with 0.125in bleed, 6x9 trim size, embedded fonts",
            "epub": "Validate with EpubCheck before upload",
            "cover": "3000x4500px, 300 DPI, CMYK color",
        },
        "isbn": "Use Amazon's free ASIN or purchase ISBN from Bowker",
        "pricing": "Set royalty to 70% for 2.99-9.99 USD range",
        "categories": "Select 2 categories and 7 keywords in KDP dashboard",
        "ai_content_disclosure": AI_CONTENT_DISCLOSURE,
    }


def generate_google_play_metadata(ebook_dict: dict) -> dict:
    """Generate Google Play Books metadata."""
    return {
        "title": ebook_dict.get("title", ""),
        "author": ebook_dict.get("author", ""),
        "description": ebook_dict.get("summary", "")[:4000],
        "language": "en",
        "categories": ["BOOKS_AND_REFERENCE"],
        "distribution": {
            "channels": ["RETAIL", "SUBSCRIPTION"],
            "countries": ["ALL"],
        },
        "pricing": {"currency": "USD", "amount": 9.99},
        "ai_content_disclosure": AI_CONTENT_DISCLOSURE,
    }


def generate_polish_metadata(ebook_dict: dict) -> dict:
    """Generate Polish platform-specific metadata."""
    title = ebook_dict.get("title", "")
    author = ebook_dict.get("author", "")
    summary = ebook_dict.get("summary", "")
    return {
        "tytul": title,
        "autor": author,
        "opis": summary,
        "jezyk": "polski",
        "gatunek": "poradnik / literatura faktu",
        "platformy": ["Publio", "Virtualo", "Legimi", "Woblink", "Ebookpoint"],
        "wymagania_techniczne": {
            "epub": "EPUB 3.0 z osadzonymi czcionkami",
            "pdf": "PDF z zakładkami, format A5 lub 6x9",
            "cover": "1400x2100px, JPG lub PNG",
        },
        "vat": "5% VAT na ebooki w Polsce (23% na drukowane)",
        "dystrybucja": "Przez Publio Direct lub własne konto na każdej platformie",
        "ujawnienie_tresci_ai": AI_CONTENT_DISCLOSURE,
    }
