"""Pydantic response schemas for Phase 1 (official-API) tools.

Every model uses `extra="ignore"` -- Moodle's JSON payloads carry many more
fields than we care about, and picking out only the ones we need keeps the
tool output focused instead of dumping the raw API response at the LLM.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _epoch_to_datetime(value: int | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(value, tz=UTC)


class CourseSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    fullname: str
    shortname: str
    visible: bool = True
    # Moodle has no separate "term/semester" field -- startdate/enddate (from
    # core_enrol_get_users_courses) are the only structured signal of which
    # semester a course belongs to. enddate=0 means "no end date set" (some
    # long-running programs are like this), which maps to None below.
    startdate: datetime | None = None
    enddate: datetime | None = None

    @field_validator("startdate", "enddate", mode="before")
    @classmethod
    def _convert_epoch(cls, v: int | None) -> datetime | None:
        return _epoch_to_datetime(v)


class FileEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    filename: str
    fileurl: str
    filesize: int | None = None
    type: str | None = None
    mimetype: str | None = None
    author: str | None = Field(
        default=None, description="Who uploaded this file (often the instructor)."
    )
    timemodified: datetime | None = None
    needs_token: bool = Field(
        default=True,
        description="Append ?token={wstoken} to fileurl before downloading (see issue #20).",
    )

    @field_validator("timemodified", mode="before")
    @classmethod
    def _convert_epoch(cls, v: int | None) -> datetime | None:
        return _epoch_to_datetime(v)


class CourseModule(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    modname: str
    url: str | None = None
    completed: bool | None = Field(
        default=None, description="Whether this account has marked/viewed this module complete."
    )
    contents: list[FileEntry] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _extract_completed(cls, data):
        # Moodle nests completion under completiondata.isoverallcomplete rather than
        # a flat field -- pull it up so callers don't need to know that shape.
        if isinstance(data, dict) and "completed" not in data:
            completiondata = data.get("completiondata")
            if isinstance(completiondata, dict):
                data = {**data, "completed": completiondata.get("isoverallcomplete")}
        return data


class CourseSection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    modules: list[CourseModule] = Field(default_factory=list)


class AssignmentSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    courseid: int | None = None
    duedate: datetime | None = None
    allowsubmissionsfromdate: datetime | None = None

    @field_validator("duedate", "allowsubmissionsfromdate", mode="before")
    @classmethod
    def _convert_epoch(cls, v: int | None) -> datetime | None:
        return _epoch_to_datetime(v)


class SubmissionStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")

    submitted: bool
    status: str | None = None
    late: bool = False


class AssignmentDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    assignment: AssignmentSummary
    submission: SubmissionStatus | None = None


class GradeItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    itemname: str | None = None
    itemtype: str
    graderaw: float | None = None
    gradeformatted: str | None = None
    grademin: float | None = None
    grademax: float | None = None
    feedback: str | None = None


class GradesResult(BaseModel):
    courseid: int
    available: bool
    gradeitems: list[GradeItem] = Field(default_factory=list)
    message: str | None = None


class CalendarEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    description: str | None = Field(default=None, description="HTML-formatted event description.")
    eventtype: str | None = None
    courseid: int | None = None
    timestart: datetime | None = None

    @field_validator("timestart", mode="before")
    @classmethod
    def _convert_epoch(cls, v: int | None) -> datetime | None:
        return _epoch_to_datetime(v)


class MessageItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    useridfrom: int
    userfromfullname: str | None = None
    subject: str | None = None
    fullmessage: str | None = None
    eventtype: str | None = None
    timecreated: datetime | None = None

    @field_validator("timecreated", mode="before")
    @classmethod
    def _convert_epoch(cls, v: int | None) -> datetime | None:
        return _epoch_to_datetime(v)
