from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict
from backend.models.content_block import ContentBlock


class PipelineContext(BaseModel):
    """Shared context flowing through the agent pipeline."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    job_id: str
    text: str
    style: str
    provider: Optional[str] = None
    content_type: str = "ebook"
    audience: str = ""
    tone: str = ""
    chapters: str = ""
    keywords: str = ""
    language: str = ""
    document: Optional[ContentBlock] = None
    design: Dict[str, Any] = Field(default_factory=dict)
    infographics: List[Dict[str, Any]] = Field(default_factory=list)
    ebook_dict: Dict[str, Any] = Field(default_factory=dict)
    html: Optional[str] = None
    output_paths: Dict[str, str] = Field(default_factory=dict)
    progress: int = 0
    error: Optional[str] = None
    research: Dict[str, Any] = Field(default_factory=dict)
    fact_check: List[Dict[str, Any]] = Field(default_factory=list)
    qa_report: Dict[str, Any] = Field(default_factory=dict)
    introduction: str = ""
    author_bio: str = ""
    references: List[str] = Field(default_factory=list)
    glossary_terms: List[Dict[str, str]] = Field(default_factory=list)
    back_cover_blurb: str = ""
    back_cover_tagline: str = ""
    cover_svg: str = ""
    cover_image: str = ""
    chapter_illustrations: List[Dict[str, Any]] = Field(default_factory=list)
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
