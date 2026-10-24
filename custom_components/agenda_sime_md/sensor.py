"""Sensor platform for Agenda SIME MD integration."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .agenda_sime_md.models import SimeLesson, SimeSubjectGrades
from .const import DOMAIN
from .coordinator import SimeDataUpdateCoordinator
from .entity import SimeEntity


def _parse_date(date_str: str | None) -> date | None:
    """Attempt to parse date from common Moldovan date formats."""
    if not date_str:
        return None
    clean = date_str.strip().rstrip(":")
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(clean, fmt).date()
        except ValueError:
            pass
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Agenda SIME MD sensor entities based on a config entry."""
    coordinator: SimeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []
    known_subjects: set[tuple[str, str]] = set()

    for student_id in coordinator.student_ids:
        entities.extend(
            [
                SimeLatestGradeSensor(coordinator, student_id),
                SimeLatestGradeDateSensor(coordinator, student_id),
                SimeGpaSensor(coordinator, student_id),
                SimeAbsencesSensor(coordinator, student_id),
                SimeTodayLessonsSensor(coordinator, student_id),
                SimeNextDayLessonsSensor(coordinator, student_id),
            ]
        )

        if student_id in coordinator.data:
            student_data = coordinator.data[student_id]
            for subject_name in student_data.subjects:
                key = (student_id, subject_name)
                known_subjects.add(key)
                entities.append(SimeSubjectAverageSensor(coordinator, student_id, subject_name))

    async_add_entities(entities)

    @callback
    def _async_check_new_subjects() -> None:
        """Dynamically add sensors for new disciplines detected in coordinator updates."""
        new_sensors: list[SensorEntity] = []
        for student_id in coordinator.student_ids:
            if student_id in coordinator.data:
                for subject_name in coordinator.data[student_id].subjects:
                    key = (student_id, subject_name)
                    if key not in known_subjects:
                        known_subjects.add(key)
                        new_sensors.append(
                            SimeSubjectAverageSensor(coordinator, student_id, subject_name)
                        )
        if new_sensors:
            async_add_entities(new_sensors)

    entry.async_on_unload(coordinator.async_add_listener(_async_check_new_subjects))


class SimeLatestGradeSensor(SimeEntity, SensorEntity):
    """Sensor exposing the latest recorded grade/mark for a student."""

    _attr_translation_key = "latest_grade"
    _attr_icon = "mdi:school"

    def __init__(self, coordinator: SimeDataUpdateCoordinator, student_id: str) -> None:
        """Initialize latest grade sensor."""
        super().__init__(coordinator, student_id)
        self._attr_unique_id = f"{student_id}_latest_grade"

    @property
    def native_value(self) -> float | None:
        """Return the latest grade value."""
        if self.student_data and self.student_data.recent_grades:
            return self.student_data.recent_grades[0].grade
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return rich metadata about latest qualification and recent evaluations."""
        attrs: dict[str, Any] = {}
        if self.student_data and self.student_data.recent_grades:
            top = self.student_data.recent_grades[0]
            attrs["subject"] = top.subject
            attrs["date"] = top.date_str
            attrs["evaluation_date"] = top.date_str
            attrs["recent_grades"] = [
                {
                    "date": g.date_str,
                    "subject": g.subject,
                    "grade": g.grade,
                }
                for g in self.student_data.recent_grades
            ]
        return attrs


class SimeLatestGradeDateSensor(SimeEntity, SensorEntity):
    """Sensor exposing the date when the latest qualification was awarded."""

    _attr_translation_key = "latest_grade_date"
    _attr_icon = "mdi:calendar-star"
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator: SimeDataUpdateCoordinator, student_id: str) -> None:
        """Initialize latest grade date sensor."""
        super().__init__(coordinator, student_id)
        self._attr_unique_id = f"{student_id}_latest_grade_date"

    @property
    def native_value(self) -> date | None:
        """Return the date of the latest recorded grade."""
        if self.student_data and self.student_data.recent_grades:
            return _parse_date(self.student_data.recent_grades[0].date_str)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional details about the latest evaluation."""
        attrs: dict[str, Any] = {}
        if self.student_data and self.student_data.recent_grades:
            top = self.student_data.recent_grades[0]
            attrs["date_str"] = top.date_str
            attrs["subject"] = top.subject
            attrs["grade"] = top.grade
        return attrs


class SimeGpaSensor(SimeEntity, SensorEntity):
    """Sensor exposing the overall general average (GPA) for a student."""

    _attr_translation_key = "general_average"
    _attr_icon = "mdi:certificate"

    def __init__(self, coordinator: SimeDataUpdateCoordinator, student_id: str) -> None:
        """Initialize GPA sensor."""
        super().__init__(coordinator, student_id)
        self._attr_unique_id = f"{student_id}_general_average"

    @property
    def native_value(self) -> float | None:
        """Return the overall student GPA."""
        if self.student_data:
            return self.student_data.general_average
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return subject count and per-subject average breakdown."""
        attrs: dict[str, Any] = {}
        if self.student_data:
            attrs["subjects_count"] = len(self.student_data.subjects)
            attrs["subject_averages"] = {
                s.subject: s.average
                for s in self.student_data.subjects.values()
                if s.average is not None
            }
        return attrs


class SimeAbsencesSensor(SimeEntity, SensorEntity):
    """Sensor exposing total absences and attendance statistics."""

    _attr_translation_key = "absences"
    _attr_icon = "mdi:account-alert"

    def __init__(self, coordinator: SimeDataUpdateCoordinator, student_id: str) -> None:
        """Initialize absences sensor."""
        super().__init__(coordinator, student_id)
        self._attr_unique_id = f"{student_id}_absences"

    @property
    def native_value(self) -> int | None:
        """Return total absences count."""
        if self.student_data:
            return self.student_data.absence_summary.total
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed absence breakdown."""
        attrs: dict[str, Any] = {}
        if self.student_data:
            summary = self.student_data.absence_summary
            attrs["presence_percent"] = summary.presence_percent
            attrs["total_motivated"] = summary.total_motivated
            attrs["total_unmotivated"] = summary.total_unmotivated
            attrs["sem1_motivated"] = summary.sem1_motivated
            attrs["sem1_unmotivated"] = summary.sem1_unmotivated
            attrs["sem2_motivated"] = summary.sem2_motivated
            attrs["sem2_unmotivated"] = summary.sem2_unmotivated
        return attrs


class SimeSubjectAverageSensor(SimeEntity, SensorEntity):
    """Sensor exposing the academic average for a specific school subject."""

    _attr_icon = "mdi:book-open-page-variant"

    def __init__(
        self,
        coordinator: SimeDataUpdateCoordinator,
        student_id: str,
        subject: str,
    ) -> None:
        """Initialize subject average sensor."""
        super().__init__(coordinator, student_id)
        self._subject = subject
        safe_subject = re.sub(r"[^a-zA-Z0-9_]", "_", subject.lower()).strip("_")
        self._attr_unique_id = f"{student_id}_{safe_subject}_average"
        self._attr_name = f"{subject} Average"

    @property
    def _subject_data(self) -> SimeSubjectGrades | None:
        """Return subject grades data."""
        if self.student_data and self._subject in self.student_data.subjects:
            return self.student_data.subjects[self._subject]
        return None

    @property
    def native_value(self) -> float | None:
        """Return subject average grade."""
        if self._subject_data:
            return self._subject_data.average
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return subject marks list and semester grade."""
        attrs: dict[str, Any] = {"subject": self._subject}
        if self._subject_data:
            attrs["grades"] = self._subject_data.grades
            attrs["semester_grade"] = self._subject_data.semester_grade
        return attrs


def _format_lesson_dict(lesson: SimeLesson, now: datetime) -> dict[str, Any]:
    """Format lesson object into dictionary with dynamic status color coding."""
    start_time = lesson.start_time
    end_time = lesson.end_time
    if now.tzinfo is not None and end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=now.tzinfo)
        start_time = start_time.replace(tzinfo=now.tzinfo)
    elif now.tzinfo is None and end_time.tzinfo is not None:
        now = now.replace(tzinfo=end_time.tzinfo)

    status = "upcoming"
    if now > end_time:
        status = "past"
    elif start_time <= now <= end_time:
        status = "current"

    return {
        "id": lesson.id,
        "subject": lesson.subject,
        "classroom": lesson.classroom,
        "teacher": lesson.teacher,
        "topic": lesson.topic,
        "start_time": lesson.start_time.isoformat(),
        "end_time": lesson.end_time.isoformat(),
        "status": status,
    }


class SimeTodayLessonsSensor(SimeEntity, SensorEntity):
    """Sensor exposing today's scheduled lessons and themes with status tags."""

    _attr_translation_key = "today_lessons"
    _attr_icon = "mdi:calendar-today"

    def __init__(self, coordinator: SimeDataUpdateCoordinator, student_id: str) -> None:
        """Initialize today lessons sensor."""
        super().__init__(coordinator, student_id)
        self._attr_unique_id = f"{student_id}_today_lessons"

    @property
    def _today_lessons(self) -> list[SimeLesson]:
        """Return lessons scheduled for today."""
        if not self.student_data or not self.student_data.timetable:
            return []
        today = dt_util.now().date()
        return [
            lesson for lesson in self.student_data.timetable if lesson.start_time.date() == today
        ]

    @property
    def native_value(self) -> int:
        """Return count of lessons today."""
        return len(self._today_lessons)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return lesson list with status flags, plus active homework assignments."""
        now = dt_util.now()
        lessons_list = [_format_lesson_dict(lesson, now) for lesson in self._today_lessons]
        hw_list = []
        if self.student_data and self.student_data.homework:
            hw_list = [
                {
                    "subject": hw.subject,
                    "due_date": hw.due_date_str,
                    "description": hw.description,
                }
                for hw in self.student_data.homework
            ]
        return {
            "date": dt_util.now().date().isoformat(),
            "lessons": lessons_list,
            "homework": hw_list,
        }


class SimeNextDayLessonsSensor(SimeEntity, SensorEntity):
    """Sensor exposing the next active school day's timetable and lesson themes."""

    _attr_translation_key = "next_day_lessons"
    _attr_icon = "mdi:calendar-arrow-right"

    def __init__(self, coordinator: SimeDataUpdateCoordinator, student_id: str) -> None:
        """Initialize next school day lessons sensor."""
        super().__init__(coordinator, student_id)
        self._attr_unique_id = f"{student_id}_next_day_lessons"

    @property
    def _next_day_lessons(self) -> tuple[str | None, list[SimeLesson]]:
        """Find the next future school date that contains scheduled lessons."""
        if not self.student_data or not self.student_data.timetable:
            return None, []

        today = dt_util.now().date()
        future_lessons = [l for l in self.student_data.timetable if l.start_time.date() > today]
        if not future_lessons:
            return None, []

        future_lessons.sort(key=lambda x: x.start_time)
        next_date = future_lessons[0].start_time.date()
        lessons_on_date = [l for l in future_lessons if l.start_time.date() == next_date]
        return next_date.isoformat(), lessons_on_date

    @property
    def native_value(self) -> int:
        """Return count of lessons for the next active school day."""
        _, lessons = self._next_day_lessons
        return len(lessons)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return next school day date and lessons with themes."""
        next_date_str, lessons = self._next_day_lessons
        now = dt_util.now()
        return {
            "date": next_date_str,
            "lessons": [_format_lesson_dict(l, now) for l in lessons],
        }
