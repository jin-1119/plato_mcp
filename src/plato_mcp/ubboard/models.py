"""Pydantic schemas for ubboard (Notices/Q&A) content.

Unlike models.py (Phase 1, official webservice API), these are built from
scraped HTML, not a documented JSON schema -- see docs/ubboard_structure.md
for exactly which selectors back each field.
"""

from datetime import datetime

from pydantic import BaseModel


class UbboardPostSummary(BaseModel):
    """One row of a board's list view."""

    board_id: int
    post_id: int
    title: str
    writer: str | None = None
    posted_at: datetime | None = None
    view_count: int | None = None


class UbboardPostDetail(BaseModel):
    """A single post's detail page."""

    board_id: int
    post_id: int
    title: str
    writer: str | None = None
    posted_at: datetime | None = None
    view_count: int | None = None
    content_html: str
