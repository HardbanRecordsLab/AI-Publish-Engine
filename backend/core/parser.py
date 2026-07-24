import docx
from io import BytesIO
from pypdf import PdfReader


def extract_text(filename: str, content: bytes) -> str:
    name_lower = filename.lower()
    if name_lower.endswith(".docx"):
        doc = docx.Document(BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if name_lower.endswith(".pdf"):
        reader = PdfReader(BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return content.decode("utf-8", errors="ignore")
