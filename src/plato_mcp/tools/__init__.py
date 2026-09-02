from . import assignments, calendar, courses, downloads, grades, messages, notices_qna


def register_all(mcp) -> None:
    courses.register(mcp)
    assignments.register(mcp)
    grades.register(mcp)
    calendar.register(mcp)
    messages.register(mcp)
    notices_qna.register(mcp)
    downloads.register(mcp)
