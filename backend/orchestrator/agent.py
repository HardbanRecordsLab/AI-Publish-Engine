from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.models.content_block import ContentBlock


class PipelineContext(BaseModel):
    """Shared context flowing through the agent pipeline."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    job_id: str
    text: str
    style: str
    provider: str | None = None
    content_type: str = "ebook"
    audience: str = ""
    tone: str = ""
    chapters: str = ""
    keywords: str = ""
    language: str = ""
    document: ContentBlock | None = None
    design: dict[str, Any] = Field(default_factory=dict)
    infographics: list[dict[str, Any]] = Field(default_factory=list)
    ebook_dict: dict[str, Any] = Field(default_factory=dict)
    html: str | None = None
    output_paths: dict[str, str] = Field(default_factory=dict)
    progress: int = 0
    error: str | None = None
    research: dict[str, Any] = Field(default_factory=dict)
    fact_check: list[dict[str, Any]] = Field(default_factory=list)
    qa_report: dict[str, Any] = Field(default_factory=dict)
    introduction: str = ""
    author_bio: str = ""
    references: list[str] = Field(default_factory=list)
    glossary_terms: list[dict[str, str]] = Field(default_factory=list)
    back_cover_blurb: str = ""
    back_cover_tagline: str = ""
    cover_svg: str = ""
    cover_image: str = ""
    chapter_illustrations: list[dict[str, Any]] = Field(default_factory=list)
    accent_color: str = ""
    bg_color: str = ""
    heading_font: str = ""
    body_font: str = ""

    def set_progress(self, pct: int) -> None:
        self.progress = pct


class BaseAgent(ABC):
    """Abstract base for all pipeline agents."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def run(self, ctx: PipelineContext) -> PipelineContext:
        ...
