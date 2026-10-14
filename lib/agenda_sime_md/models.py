"""Data models for agenda_sime_md."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional


class SimeAccountRole(str, Enum):
    """Account role on agenda.sime.md."""

    PARENT = "1"
    STUDENT = "2"


@dataclass
class SimeStudent:
    """Represents an enrolled student."""

    id: str
    name: str
    birthdate: Optional[str] = None
    permanent_code: Optional[str] = None
    school_name: Optional[str] = None
    classroom: Optional[str] = None
    class_master: Optional[str] = None
    address: Optional[str] = None
    study_year: Optional[str] = None
    current_semester: int = 1


@dataclass
class SimeRecentGrade:
    """A recent grade/evaluation entry from the last evaluations list."""

    date_str: str
    subject: str
    grade: float


@dataclass
class SimeSubjectGrades:
    """Grades and average for a single school discipline."""

    subject: str
    grades: list[float] = field(default_factory=list)
    average: Optional[float] = None
    semester_grade: Optional[float] = None

    def calculate_average(self) -> Optional[float]:
        """Calculate arithmetic average of registered marks."""
        if not self.grades:
            return None
        return round(sum(self.grades) / len(self.grades), 2)


@dataclass
class SimeAbsenceSummary:
    """Cumulative and semester absences."""

    presence_percent: int = 100
    sem1_motivated: int = 0
    sem1_unmotivated: int = 0
    sem2_motivated: int = 0
    sem2_unmotivated: int = 0

    @property
    def total_motivated(self) -> int:
        return self.sem1_motivated + self.sem2_motivated

    @property
    def total_unmotivated(self) -> int:
        return self.sem1_unmotivated + self.sem2_unmotivated

    @property
    def total(self) -> int:
        return self.total_motivated + self.total_unmotivated


@dataclass
class SimeHomework:
    """A homework task (sarcină de învățare)."""

    due_date_str: str
    subject: str
    description: str


@dataclass
class SimeLesson:
    """A scheduled class lesson in the school timetable."""

    id: str
    subject: str
    start_time: datetime
    end_time: datetime
    classroom: Optional[str] = None
    teacher: Optional[str] = None
    topic: Optional[str] = None


@dataclass
class SimeStudentData:
    """Aggregated data snapshot for an enrolled student."""

    student: SimeStudent
    recent_grades: list[SimeRecentGrade] = field(default_factory=list)
    subjects: dict[str, SimeSubjectGrades] = field(default_factory=dict)
    general_average: Optional[float] = None
    absence_summary: SimeAbsenceSummary = field(default_factory=SimeAbsenceSummary)
    homework: list[SimeHomework] = field(default_factory=list)
    timetable: list[SimeLesson] = field(default_factory=list)
