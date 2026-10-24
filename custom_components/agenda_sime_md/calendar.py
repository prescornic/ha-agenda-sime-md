"""Calendar platform for Agenda SIME MD school timetable."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .agenda_sime_md.models import SimeLesson
from .const import DOMAIN
from .coordinator import SimeDataUpdateCoordinator
from .entity import SimeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Agenda SIME MD calendar entities from a config entry."""
    coordinator: SimeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        SimeTimetableCalendar(coordinator, student_id) for student_id in coordinator.student_ids
    ]

    async_add_entities(entities)


def _lesson_to_calendar_event(lesson: SimeLesson) -> CalendarEvent:
    """Convert a SimeLesson into a Home Assistant CalendarEvent."""
    desc_lines = []
    if lesson.topic:
        desc_lines.append(f"Tema: {lesson.topic}")
    if lesson.teacher:
        desc_lines.append(f"Profesor: {lesson.teacher}")
    if lesson.classroom:
        desc_lines.append(f"Cabinet: {lesson.classroom}")

    return CalendarEvent(
        start=lesson.start_time,
        end=lesson.end_time,
        summary=lesson.subject,
        description="\n".join(desc_lines) if desc_lines else None,
        location=lesson.classroom,
        uid=lesson.id,
    )


class SimeTimetableCalendar(SimeEntity, CalendarEntity):
    """Calendar entity representing a student's school timetable."""

    _attr_translation_key = "timetable"
    _attr_icon = "mdi:calendar-month"

    def __init__(self, coordinator: SimeDataUpdateCoordinator, student_id: str) -> None:
        """Initialize timetable calendar."""
        super().__init__(coordinator, student_id)
        self._attr_unique_id = f"{student_id}_timetable"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current active or next upcoming calendar event."""
        if not self.student_data or not self.student_data.timetable:
            return None

        now = dt_util.now()
        upcoming_lessons = [l for l in self.student_data.timetable if l.end_time >= now]
        if not upcoming_lessons:
            return None

        upcoming_lessons.sort(key=lambda x: x.start_time)
        return _lesson_to_calendar_event(upcoming_lessons[0])

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a specified date range."""
        if not self.student_data or not self.student_data.timetable:
            return []

        events: list[CalendarEvent] = []
        for lesson in self.student_data.timetable:
            if lesson.end_time >= start_date and lesson.start_time <= end_date:
                events.append(_lesson_to_calendar_event(lesson))

        events.sort(key=lambda ev: ev.start)
        return events
