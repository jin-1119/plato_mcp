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
    """Schema verified against Moodle 4.5's mod_assign/externallib.php source
    (PLATO runs 4.5.13) -- NOT yet verified against a live response, since no
    course in the test account has a real assignment. Re-check field names
    against a real payload once one exists (see tests/integration/README.md).
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    cmid: int | None = None
    name: str
    courseid: int | None = None
    duedate: datetime | None = None
    allowsubmissionsfromdate: datetime | None = None
    cutoffdate: datetime | None = Field(
        default=None, description="Hard deadline; submissions after this need an extension."
    )
    gradingduedate: datetime | None = None
    intro: str | None = Field(default=None, description="Assignment instructions (HTML).")
    introformat: int | None = None
    introfiles: list[FileEntry] = Field(default_factory=list)
    introattachments: list[FileEntry] = Field(default_factory=list)
    activity: str | None = Field(
        default=None, description="Some assignment types carry a separate 'activity' description."
    )
    activityformat: int | None = None
    activityattachments: list[FileEntry] = Field(default_factory=list)
    maxattempts: int | None = None
    attemptreopenmethod: str | None = None
    teamsubmission: bool | None = None
    requireallteammemberssubmit: bool | None = None
    teamsubmissiongroupingid: int | None = None

    @field_validator(
        "duedate", "allowsubmissionsfromdate", "cutoffdate", "gradingduedate", mode="before"
    )
    @classmethod
    def _convert_epoch(cls, v: int | None) -> datetime | None:
        return _epoch_to_datetime(v)

    @field_validator("teamsubmission", "requireallteammemberssubmit", mode="before")
    @classmethod
    def _convert_int_bool(cls, v: int | None) -> bool | None:
        return None if v is None else bool(v)


class PluginEditorField(BaseModel):
    """One text field of a submission/feedback plugin -- e.g. the actual
    written comment text for the 'comments' feedback plugin."""

    model_config = ConfigDict(extra="ignore")

    name: str
    description: str | None = None
    text: str | None = None
    format: int | None = None


class PluginFileArea(BaseModel):
    model_config = ConfigDict(extra="ignore")

    area: str
    files: list[FileEntry] = Field(default_factory=list)


class AssignmentPlugin(BaseModel):
    """A submission or feedback plugin (e.g. 'file', 'onlinetext', 'comments')
    and the actual content it holds for one submission/grade."""

    model_config = ConfigDict(extra="ignore")

    type: str
    name: str
    fileareas: list[PluginFileArea] = Field(default_factory=list)
    editorfields: list[PluginEditorField] = Field(default_factory=list)


class SubmissionStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")

    submitted: bool
    status: str | None = None
    late: bool = False
    timemodified: datetime | None = None
    cansubmit: bool | None = None
    locked: bool | None = None
    extensionduedate: datetime | None = Field(
        default=None, description="Individual extension granted to this student, if any."
    )
    gradingstatus: str | None = None

    @field_validator("timemodified", "extensionduedate", mode="before")
    @classmethod
    def _convert_epoch(cls, v: int | None) -> datetime | None:
        return _epoch_to_datetime(v)


class GradeInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    grade: str | None = Field(default=None, description="Raw grade value (Moodle returns as text).")
    gradefordisplay: str | None = None
    timemodified: datetime | None = None
    grader: int | None = None

    @field_validator("timemodified", mode="before")
    @classmethod
    def _convert_epoch(cls, v: int | None) -> datetime | None:
        return _epoch_to_datetime(v)


class SubmissionFeedback(BaseModel):
    model_config = ConfigDict(extra="ignore")

    grade: GradeInfo | None = None
    gradefordisplay: str | None = None
    gradeddate: datetime | None = None
    plugins: list[AssignmentPlugin] = Field(
        default_factory=list, description="Includes the instructor's written feedback comments."
    )

    @field_validator("gradeddate", mode="before")
    @classmethod
    def _convert_epoch(cls, v: int | None) -> datetime | None:
        return _epoch_to_datetime(v)


class SubmissionInfo(BaseModel):
    """Lightweight submission snapshot used inside previousattempts (as
    opposed to SubmissionStatus, which is this account's *current* status)."""

    model_config = ConfigDict(extra="ignore")

    status: str | None = None
    timemodified: datetime | None = None

    @field_validator("timemodified", mode="before")
    @classmethod
    def _convert_epoch(cls, v: int | None) -> datetime | None:
        return _epoch_to_datetime(v)


class PreviousAttempt(BaseModel):
    model_config = ConfigDict(extra="ignore")

    attemptnumber: int
    submission: SubmissionInfo | None = None
    grade: GradeInfo | None = None
    feedbackplugins: list[AssignmentPlugin] = Field(default_factory=list)


class AssignmentExtraData(BaseModel):
    """Maps from Moodle's `assignmentdata` (attachments nested under
    `attachments.intro`/`attachments.activity`) to a flat shape."""

    model_config = ConfigDict(extra="ignore")

    activity: str | None = None
    attachments_intro: list[FileEntry] = Field(default_factory=list)
    attachments_activity: list[FileEntry] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _flatten_attachments(cls, data):
        if isinstance(data, dict):
            attachments = data.get("attachments") or {}
            data = {
                **data,
                "attachments_intro": attachments.get("intro", []),
                "attachments_activity": attachments.get("activity", []),
            }
        return data


class AssignmentDetail(BaseModel):
    model_config = ConfigDict(extra="ignore")

    assignment: AssignmentSummary
    submission: SubmissionStatus | None = None
    feedback: SubmissionFeedback | None = None
    previousattempts: list[PreviousAttempt] = Field(default_factory=list)
    extra: AssignmentExtraData | None = None


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
