"""Base entity for Agenda SIME MD integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .agenda_sime_md.models import SimeStudent, SimeStudentData
from .const import DOMAIN
from .coordinator import SimeDataUpdateCoordinator


class SimeEntity(CoordinatorEntity[SimeDataUpdateCoordinator]):
    """Base class for Agenda SIME MD entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SimeDataUpdateCoordinator,
        student_id: str,
    ) -> None:
        """Initialize the base student entity."""
        super().__init__(coordinator)
        self._student_id = student_id

    @property
    def student_data(self) -> SimeStudentData | None:
        """Return the current data for this student."""
        return self.coordinator.data.get(self._student_id)

    @property
    def student(self) -> SimeStudent | None:
        """Return the student model."""
        if self.student_data:
            return self.student_data.student
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._student_id in self.coordinator.data

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information grouping entities per student."""
        student_name = (
            self.student.name if self.student else f"Elev {self._student_id}"
        )
        classroom = (
            f"Clasa {self.student.classroom}"
            if self.student and self.student.classroom
            else "Elev"
        )
        school_name = (
            self.student.school_name if self.student and self.student.school_name else None
        )

        return DeviceInfo(
            identifiers={(DOMAIN, self._student_id)},
            name=student_name,
            manufacturer="Ministerul Educației și Cercetării (SIME MD)",
            model=classroom,
            suggested_area=school_name,
        )
