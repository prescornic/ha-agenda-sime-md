"""Tests for Agenda SIME MD calendar platform."""

from datetime import timedelta
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


async def test_calendar_timetable(hass: HomeAssistant):
    """Test timetable calendar entity and event querying."""
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

    cal_state = hass.states.get("calendar.elev_exemplar_timetable")
    assert cal_state is not None
    # Upcoming event should be present
    assert cal_state.attributes["message"] in ("Fizică", "Chimie", "Matematică")

    coordinator = hass.data[DOMAIN][entry.entry_id]
    from custom_components.agenda_sime_md.calendar import SimeTimetableCalendar

    calendar_entity = SimeTimetableCalendar(coordinator, "UK00000001")
    start = dt_util.now() - timedelta(days=1)
    end = dt_util.now() + timedelta(days=5)

    events = await calendar_entity.async_get_events(hass, start, end)
    assert len(events) == 4
    summaries = [e.summary for e in events]
    assert "Matematică" in summaries
    assert "Fizică" in summaries
    assert "Chimie" in summaries
    assert "Istorie" in summaries

    # Check topic / theme inclusion
    math_event = next(e for e in events if e.summary == "Matematică")
    assert "Tema: Ecuații de gradul II" in math_event.description
    assert math_event.location == "101"
