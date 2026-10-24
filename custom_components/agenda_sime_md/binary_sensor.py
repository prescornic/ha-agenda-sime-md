"""Binary sensor platform for Agenda SIME MD integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import SimeDataUpdateCoordinator
from .entity import SimeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Agenda SIME MD binary sensor entities from a config entry."""
    coordinator: SimeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[BinarySensorEntity] = []
    for student_id in coordinator.student_ids:
        entities.extend(
            [
                SimeAbsenceTodayBinarySensor(coordinator, student_id),
                SimeNewGradeTodayBinarySensor(coordinator, student_id),
                SimeSchoolDayBinarySensor(coordinator, student_id),
            ]
        )

    async_add_entities(entities)


class SimeAbsenceTodayBinarySensor(SimeEntity, BinarySensorEntity, RestoreEntity):
    """Binary sensor indicating if an absence is recorded for the student today."""

    _attr_translation_key = "absence_today"
    _attr_icon = "mdi:account-cancel"

    def __init__(self, coordinator: SimeDataUpdateCoordinator, student_id: str) -> None:
        """Initialize absence today binary sensor."""
        super().__init__(coordinator, student_id)
        self._attr_unique_id = f"{student_id}_absence_today"

    async def async_added_to_hass(self) -> None:
        """Handle entity restored state on startup."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            today = dt_util.now().date()
            last_date_str = last_state.attributes.get("date")
            if last_date_str == today.isoformat():
                baseline = last_state.attributes.get("baseline_absences")
                if baseline is not None:
                    self.coordinator.set_absence_baseline(self._student_id, today, int(baseline))

    @property
    def is_on(self) -> bool:
        """Return True if an absence has occurred today."""
        if not self.student_data:
            return False
        return self.coordinator.get_absences_today(self._student_id) > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return absence attributes for today."""
        today = dt_util.now().date()
        return {
            "absences_today": self.coordinator.get_absences_today(self._student_id),
            "baseline_absences": self.coordinator.get_absence_baseline(self._student_id),
            "date": today.isoformat(),
        }


class SimeNewGradeTodayBinarySensor(SimeEntity, BinarySensorEntity):
    """Binary sensor turning on when a qualification/grade is registered today."""

    _attr_translation_key = "new_grade_today"
    _attr_icon = "mdi:bell-badge"

    def __init__(self, coordinator: SimeDataUpdateCoordinator, student_id: str) -> None:
        """Initialize new grade today binary sensor."""
        super().__init__(coordinator, student_id)
        self._attr_unique_id = f"{student_id}_new_grade_today"

    def _get_grades_today(self) -> list[dict[str, Any]]:
        """Return recent grades that match today's date."""
        if not self.student_data or not self.student_data.recent_grades:
            return []

        now = dt_util.now()
        date_patterns = {
            now.strftime("%d.%m.%Y"),
            now.strftime("%Y-%m-%d"),
            now.date().isoformat(),
        }

        return [
            {
                "date": g.date_str,
                "subject": g.subject,
                "grade": g.grade,
            }
            for g in self.student_data.recent_grades
            if any(p in g.date_str for p in date_patterns)
        ]

    @property
    def is_on(self) -> bool:
        """Return True if at least one grade was recorded today."""
        return len(self._get_grades_today()) > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return list of qualifications received today."""
        return {"grades_today": self._get_grades_today()}


class SimeSchoolDayBinarySensor(SimeEntity, BinarySensorEntity):
    """Binary sensor indicating whether classes are scheduled for the current date."""

    _attr_translation_key = "school_day"
    _attr_icon = "mdi:calendar-check"

    def __init__(self, coordinator: SimeDataUpdateCoordinator, student_id: str) -> None:
        """Initialize school day binary sensor."""
        super().__init__(coordinator, student_id)
        self._attr_unique_id = f"{student_id}_school_day"

    @property
    def is_on(self) -> bool:
        """Return True if classes are scheduled today."""
        today = dt_util.now().date()
        if self.student_data and self.student_data.timetable:
            today_lessons = [l for l in self.student_data.timetable if l.start_time.date() == today]
            return len(today_lessons) > 0
        # Fallback to standard school days (Monday to Friday)
        return today.weekday() < 5

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return count of classes today."""
        today = dt_util.now().date()
        count = 0
        if self.student_data and self.student_data.timetable:
            count = len([l for l in self.student_data.timetable if l.start_time.date() == today])
        return {"lessons_count": count}
