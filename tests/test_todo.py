"""Tests for Agenda SIME MD homework todo platform."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.todo import TodoItemStatus
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.agenda_sime_md.const import (
    CONF_ROLE,
    CONF_STUDENTS,
    DOMAIN,
    ROLE_PARENT,
)
from lib.agenda_sime_md.models import SimeHomework
from tests.test_sensor import create_sample_student_data


async def test_todo_homework_items(hass: HomeAssistant):
    """Test homework todo list items and parsing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Elev Exemplar (parent_user)",
        data={
            CONF_USERNAME: "parent_user",
            CONF_PASSWORD: "secret_password",
            CONF_ROLE: ROLE_PARENT,
            CONF_STUDENTS: ["UK00000001"],
        },
        unique_id="parent_user_parent",
    )
    entry.add_to_hass(hass)

    sample_data = create_sample_student_data()
    sample_data.homework = [
        SimeHomework(
            due_date_str="16.10.2026",
            subject="Matematică",
            description="Exercițiile 1-5 de la pagina 45",
        ),
        SimeHomework(
            due_date_str="17.10.2026",
            subject="Geografie",
            description="Harta reliefului Europei",
        ),
    ]

    with (
        patch("custom_components.agenda_sime_md.SimeClient.login", new_callable=AsyncMock),
        patch(
            "custom_components.agenda_sime_md.SimeClient.get_student_data",
            new_callable=AsyncMock,
            return_value=sample_data,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id) is True
        await hass.async_block_till_done()

    todo_state = hass.states.get("todo.elev_exemplar_homework")
    assert todo_state is not None
    assert int(todo_state.state) == 2
    assert len(todo_state.attributes["items"]) == 2
    assert todo_state.attributes["items"][0]["subject"] == "Matematică"
    assert todo_state.attributes["homework"] == todo_state.attributes["items"]
    assert todo_state.attributes["count"] == 2

    coordinator = hass.data[DOMAIN][entry.entry_id]
    from custom_components.agenda_sime_md.todo import SimeHomeworkTodoList

    todo_entity = SimeHomeworkTodoList(coordinator, "UK00000001")
    items = todo_entity.todo_items
    assert len(items) == 2

    math_item = next(i for i in items if "Matematică" in (i.description or ""))
    assert "Exercițiile 1-5" in math_item.summary
    assert math_item.summary == "Exercițiile 1-5 de la pagina 45"
    assert math_item.status == TodoItemStatus.NEEDS_ACTION
    assert math_item.due is not None
    assert math_item.due.day == 16
