"""To-Do platform for Agenda SIME MD homework tasks."""

from __future__ import annotations

import hashlib
from datetime import date, datetime

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SimeDataUpdateCoordinator
from .entity import SimeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Agenda SIME MD homework todo list from a config entry."""
    coordinator: SimeDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        SimeHomeworkTodoList(coordinator, student_id)
        for student_id in coordinator.student_ids
    ]

    async_add_entities(entities)


def _parse_due_date(date_str: str) -> date | None:
    """Attempt to parse due date from various Moldovan date formats."""
    if not date_str:
        return None

    clean = date_str.strip().rstrip(":")
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(clean, fmt).date()
        except ValueError:
            pass
    return None


class SimeHomeworkTodoList(SimeEntity, TodoListEntity):
    """To-do list entity exposing active homework assignments for a student."""

    _attr_translation_key = "homework"
    _attr_icon = "mdi:notebook-edit-outline"
    _attr_supported_features = TodoListEntityFeature(0)

    def __init__(
        self, coordinator: SimeDataUpdateCoordinator, student_id: str
    ) -> None:
        """Initialize homework todo list."""
        super().__init__(coordinator, student_id)
        self._attr_unique_id = f"{student_id}_homework"

    @property
    def todo_items(self) -> list[TodoItem] | None:
        """Return the current active homework tasks."""
        if not self.student_data:
            return []

        items: list[TodoItem] = []
        for hw in self.student_data.homework:
            raw_id = f"{hw.subject}_{hw.due_date_str}_{hw.description}"
            uid = hashlib.sha1(raw_id.encode("utf-8")).hexdigest()[:16]
            due = _parse_due_date(hw.due_date_str)

            items.append(
                TodoItem(
                    uid=uid,
                    summary=f"{hw.subject}: {hw.description}",
                    status=TodoItemStatus.NEEDS_ACTION,
                    due=due,
                    description=f"Termen: {hw.due_date_str}\nDisciplină: {hw.subject}",
                )
            )

        return items
