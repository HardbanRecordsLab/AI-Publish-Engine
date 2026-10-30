from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.models.content_block import ContentBlock


class AwaitingApproval(Exception):
    """Raised by an agent that needs the author's go-ahead (e.g. the course outline). The orchestrator parks the job
    instead of failing it; approving it resumes the pipeline after the steps that already ran."""


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
    course_format: str = ""   # interactive-course only: "program" (days with sessions, the default) or "lessons"
    keywords: str = ""
    language: str = ""
    author: str = ""
    kind: str = "guide"
    document: ContentBlock | None = None
    design: dict[str, Any] = Field(default_factory=dict)
    infographics: list[dict[str, Any]] = Field(default_factory=list)
    ebook_dict: dict[str, Any] = Field(default_factory=dict)
    html: str | None = None
    output_paths: dict[str, str] = Field(default_factory=dict)
    progress: int = 0
    error: str | None = None
    review_outline: bool = False   # interactive-course only: stop after the outline until the author approves it
    awaiting_approval: bool = False
    research: dict[str, Any] = Field(default_factory=dict)
    # interactive-course pipeline: numbered web sources (Source dicts) and the course being built
    web_sources: list[dict[str, Any]] = Field(default_factory=list)
    course: dict[str, Any] = Field(default_factory=dict)
    fact_check: list[dict[str, Any]] = Field(default_factory=list)
    qa_report: dict[str, Any] = Field(default_factory=dict)
    chapter_reviews: list[dict[str, Any]] = Field(default_factory=list)
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

    # What a resumed job needs from the steps that already ran. The brief (text) is stored once with the job inputs and the
    # rendered page (html) is rebuilt, so neither is repeated in every snapshot.
    _NOT_SNAPSHOT = {"text", "html", "error", "awaiting_approval"}

    def snapshot(self) -> dict[str, Any]:
        snap = self.model_dump(mode="json", exclude=self._NOT_SNAPSHOT)
        (snap.get("course", {}).get("outline") or {}).pop("_brief", None)
        return snap

    def restored(self, snap: dict[str, Any]) -> PipelineContext:
        outline = (snap.get("course") or {}).get("outline")
        if isinstance(outline, dict):
            outline["_brief"] = self.text
        return PipelineContext.model_validate({**snap, "text": self.text, "html": self.html})


class BaseAgent(ABC):
    """Abstract base for all pipeline agents."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def run(self, ctx: PipelineContext) -> PipelineContext:
        ...
