"""Agenda SIME MD Python Library.

Standalone asynchronous client library for agenda.sime.md
(Sistemul Informațional de Management în Educație din Republica Moldova).
"""

from .auth import SimeAuthManager
from .client import SimeClient
from .exceptions import (
    SimeAuthError,
    SimeConnectionError,
    SimeError,
    SimeParseError,
    SimeRateLimitError,
)
from .models import (
    SimeAbsenceSummary,
    SimeAccountRole,
    SimeHomework,
    SimeLesson,
    SimeRecentGrade,
    SimeStudent,
    SimeStudentData,
    SimeSubjectGrades,
)

__version__ = "0.1.0"

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
    "SimeRateLimitError",
    "SimeRecentGrade",
    "SimeStudent",
    "SimeStudentData",
    "SimeSubjectGrades",
]
