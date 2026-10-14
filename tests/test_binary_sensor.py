"""Tests for Agenda SIME MD binary sensor platform."""

from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.agenda_sime_md.const import (
    CONF_ROLE,
    CONF_STUDENTS,
    DOMAIN,
    ROLE_PARENT,
)
from tests.test_sensor import create_sample_student_data


async def test_binary_sensors_states(hass: HomeAssistant):
    """Test binary sensor states for school day, new grade today, and absence."""
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
    # First grade is from today, second grade is from 5 days ago
    sample_data.recent_grades[0].date_str = dt_util.now().strftime("%d.%m.%Y")
    sample_data.recent_grades[1].date_str = "01.01.2025"

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

    # 1. School Day binary sensor
    school_day = hass.states.get("sensor.elev_exemplar_school_day") or hass.states.get(
        "binary_sensor.elev_exemplar_school_day"
    )
    assert school_day is not None
    assert school_day.state == "on"

    # 2. New Grade Today binary sensor
    new_grade = hass.states.get("binary_sensor.elev_exemplar_new_grade_today")
    assert new_grade is not None
    assert new_grade.state == "on"
    assert len(new_grade.attributes["grades_today"]) == 1

    # 3. Absence Today binary sensor
    absence_today = hass.states.get("binary_sensor.elev_exemplar_absence_today")
    assert absence_today is not None
    assert absence_today.state == "off"
