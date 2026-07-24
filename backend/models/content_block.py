from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ContentBlock(BaseModel):
    """Universal content block — atomic unit for all output formats."""

    type: str
    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    data: dict[str, Any] = Field(default_factory=dict)
    children: list[ContentBlock] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)

    def add(self, block: ContentBlock) -> ContentBlock:
        self.children.append(block)
        return self

    def first(self, block_type: str) -> ContentBlock | None:
        for c in self.children:
            if c.type == block_type:
                return c
        return None

    def all(self, block_type: str) -> list[ContentBlock]:
        return [c for c in self.children if c.type == block_type]

    def to_ebook_dict(self) -> dict[str, Any]:
        """Rebuild legacy ebook dict for backward compat with builder/export."""
        if self.type == "document":
            return {
                "title": self.data.get("title", ""),
                "subtitle": self.data.get("subtitle", ""),
                "author": self.data.get("author", "AI Design Engine"),
                "topic": self.data.get("topic", "general"),
                "tone": self.data.get("tone", "professional"),
                "audience": self.data.get("audience", ""),
                "summary": self.data.get("summary", ""),
                "chapters": [c.to_ebook_dict() for c in self.all("chapter")],
                "conclusion": (
                    self.first("conclusion")
                    or ContentBlock(type="conclusion", data={"title": "Conclusion", "content": ""})
                ).to_ebook_dict(),
            }
        if self.type == "chapter":
            return {
                "title": self.data.get("title", f"Chapter {self.meta.get('index', 0) + 1}"),
                "introduction": self.data.get("introduction", ""),
                "key_takeaway": self.data.get("key_takeaway", ""),
                "sections": [s.to_ebook_dict() for s in self.all("section")],
            }
        if self.type == "section":
            texts = [c.data.get("text", "") for c in self.children if c.type == "paragraph"]
            return {
                "heading": self.data.get("heading", ""),
                "content": "\n\n".join(texts),
            }
        if self.type == "conclusion":
            return {
                "title": self.data.get("title", "Conclusion"),
                "content": self.data.get("content", ""),
            }
        return {}
