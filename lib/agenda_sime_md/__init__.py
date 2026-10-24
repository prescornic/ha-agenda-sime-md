"""Agenda SIME MD Python Library.

Standalone asynchronous client library for agenda.sime.md
(Sistemul Informațional de Management în Educație din Republica Moldova).
"""

from custom_components.agenda_sime_md.agenda_sime_md import (
    SimeAbsenceSummary,
    SimeAccountRole,
    SimeAuthError,
    SimeAuthManager,
    SimeClient,
    SimeConnectionError,
    SimeError,
    SimeHomework,
    SimeLesson,
    SimeParseError,
    SimePortalInfo,
    SimeRateLimitError,
    SimeRecentGrade,
    SimeStudent,
    SimeStudentDashboardData,
    SimeStudentData,
    SimeSubjectGrades,
    __version__,
)

__all__ = [
    "SimeAbsenceSummary",
    "SimeAccountRole",
    "SimeAuthError",
    "SimeAuthManager",
    "SimeClient",
    "SimeConnectionError",
    "SimeError",
    "SimeHomework",
    "SimeLesson",
    "SimeParseError",
    "SimePortalInfo",
    "SimeRateLimitError",
    "SimeRecentGrade",
    "SimeStudent",
    "SimeStudentDashboardData",
    "SimeStudentData",
    "SimeSubjectGrades",
    "__version__",
]
