"""Pydantic schemas for ubboard (Notices/Q&A) content.

Unlike models.py (Phase 1, official webservice API), these are built from
scraped HTML, not a documented JSON schema -- see docs/ubboard_structure.md
for exactly which selectors back each field.

`writer` on a Q&A post can identify a classmate, not just course staff --
see docs/pii_review.md (issue #36) for the pass-through-as-is decision and
its caveats before changing this.
"""

from datetime import datetime

from pydantic import BaseModel, Field

_WRITER_DESC = (
    "Display name of who posted this. For Notices this is course staff "
    "(instructor/TA); for Q&A it can be any classmate. Passed through "
    "as-is -- see docs/pii_review.md for why, and its caveats."
)


class UbboardPostSummary(BaseModel):
    """One row of a board's list view."""

    board_id: int
    post_id: int
    title: str
    writer: str | None = Field(default=None, description=_WRITER_DESC)
    posted_at: datetime | None = None
    view_count: int | None = None


class UbboardPostDetail(BaseModel):
    """A single post's detail page."""

    board_id: int
    post_id: int
    title: str
    writer: str | None = Field(default=None, description=_WRITER_DESC)
    posted_at: datetime | None = None
    view_count: int | None = None
    content_html: str
