"""Tests for Agenda SIME MD setup and teardown (__init__.py)."""

from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.agenda_sime_md.const import (
    CONF_ROLE,
    CONF_STUDENTS,
    DOMAIN,
    ROLE_PARENT,
)
from lib.agenda_sime_md.models import SimeStudent, SimeStudentData


async def test_setup_and_unload_entry(hass: HomeAssistant):
    """Test setting up and unloading an Agenda SIME MD entry."""
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

    mock_student = SimeStudent(id="UK00000001", name="Elev Exemplar")
    mock_data = SimeStudentData(student=mock_student)

    with (
        patch("custom_components.agenda_sime_md.SimeClient.login", new_callable=AsyncMock),
        patch(
            "custom_components.agenda_sime_md.SimeClient.get_student_data",
            new_callable=AsyncMock,
            return_value=mock_data,
        ),
        patch("custom_components.agenda_sime_md.SimeClient.close", new_callable=AsyncMock),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id) is True
        await hass.async_block_till_done()
        assert DOMAIN in hass.data
        assert entry.entry_id in hass.data[DOMAIN]

        coordinator = hass.data[DOMAIN][entry.entry_id]
        assert "UK00000001" in coordinator.data

        assert await hass.config_entries.async_unload(entry.entry_id) is True
        await hass.async_block_till_done()
        assert entry.entry_id not in hass.data[DOMAIN]
