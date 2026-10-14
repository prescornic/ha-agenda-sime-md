"""Tests for Agenda SIME MD DataUpdateCoordinator."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from custom_components.agenda_sime_md.const import (
    CONF_DAY_END_HOUR,
    CONF_DAY_START_HOUR,
    CONF_SCAN_INTERVAL_DAY,
    CONF_SCAN_INTERVAL_NIGHT,
    DOMAIN,
)
from custom_components.agenda_sime_md.coordinator import SimeDataUpdateCoordinator
from lib.agenda_sime_md.exceptions import (
    SimeAuthError,
    SimeConnectionError,
    SimeRateLimitError,
)
from lib.agenda_sime_md.models import SimeStudent, SimeStudentData


def create_mock_entry(options=None):
    """Create a mock ConfigEntry."""
    entry = MagicMock(spec=config_entries.ConfigEntry)
    entry.entry_id = "mock_entry_id"
    entry.domain = DOMAIN
    entry.options = options or {}
    return entry


async def test_coordinator_adaptive_interval_daytime(hass: HomeAssistant):
    """Test that coordinator sets fast interval during daytime school hours."""
    client = MagicMock()
    entry = create_mock_entry()
    coordinator = SimeDataUpdateCoordinator(
        hass=hass,
        client=client,
        entry=entry,
        student_ids=["UK00000001"],
    )

    # Mock time at 10:00 (daytime window is 7:00 - 19:00)
    fake_now = datetime(2026, 10, 15, 10, 0, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    with patch("homeassistant.util.dt.now", return_value=fake_now):
        interval = coordinator._calculate_update_interval()
        assert interval == timedelta(minutes=15)


async def test_coordinator_adaptive_interval_nighttime(hass: HomeAssistant):
    """Test that coordinator sets relaxed 1h interval during nighttime."""
    client = MagicMock()
    entry = create_mock_entry()
    coordinator = SimeDataUpdateCoordinator(
        hass=hass,
        client=client,
        entry=entry,
        student_ids=["UK00000001"],
    )

    # Mock time at 22:30 (nighttime window)
    fake_now = datetime(2026, 10, 15, 22, 30, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    with patch("homeassistant.util.dt.now", return_value=fake_now):
        interval = coordinator._calculate_update_interval()
        assert interval == timedelta(minutes=60)


async def test_coordinator_custom_options(hass: HomeAssistant):
    """Test that custom options for intervals and window hours are respected."""
    client = MagicMock()
    options = {
        CONF_SCAN_INTERVAL_DAY: 25,
        CONF_SCAN_INTERVAL_NIGHT: 90,
        CONF_DAY_START_HOUR: 8,
        CONF_DAY_END_HOUR: 16,
    }
    entry = create_mock_entry(options=options)
    coordinator = SimeDataUpdateCoordinator(
        hass=hass,
        client=client,
        entry=entry,
        student_ids=["UK00000001"],
    )

    # 07:30 is before 08:00 start -> should use night interval (90m)
    with patch(
        "homeassistant.util.dt.now",
        return_value=datetime(2026, 10, 15, 7, 30, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE),
    ):
        assert coordinator._calculate_update_interval() == timedelta(minutes=90)

    # 12:00 is between 08:00 and 16:00 -> should use day interval (25m)
    with patch(
        "homeassistant.util.dt.now",
        return_value=datetime(2026, 10, 15, 12, 0, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE),
    ):
        assert coordinator._calculate_update_interval() == timedelta(minutes=25)


async def test_coordinator_successful_data_fetch(hass: HomeAssistant):
    """Test successful data update for configured students."""
    mock_student = SimeStudent(id="UK00000001", name="Elev Exemplar")
    mock_data = SimeStudentData(student=mock_student)

    client = MagicMock()
    client.get_student_data = AsyncMock(return_value=mock_data)

    entry = create_mock_entry()
    coordinator = SimeDataUpdateCoordinator(
        hass=hass,
        client=client,
        entry=entry,
        student_ids=["UK00000001"],
    )

    data = await coordinator._async_update_data()
    assert "UK00000001" in data
    assert data["UK00000001"].student.name == "Elev Exemplar"
    assert client.get_student_data.called


async def test_coordinator_auth_error_triggers_reauth(hass: HomeAssistant):
    """Test that SimeAuthError raises ConfigEntryAuthFailed."""
    client = MagicMock()
    client.get_student_data = AsyncMock(side_effect=SimeAuthError("Session invalid"))

    entry = create_mock_entry()
    coordinator = SimeDataUpdateCoordinator(
        hass=hass,
        client=client,
        entry=entry,
        student_ids=["UK00000001"],
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_coordinator_rate_limit_error(hass: HomeAssistant):
    """Test that SimeRateLimitError raises UpdateFailed."""
    client = MagicMock()
    client.get_student_data = AsyncMock(side_effect=SimeRateLimitError("Rate limit", wait_seconds=30))

    entry = create_mock_entry()
    coordinator = SimeDataUpdateCoordinator(
        hass=hass,
        client=client,
        entry=entry,
        student_ids=["UK00000001"],
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_connection_error(hass: HomeAssistant):
    """Test that SimeConnectionError raises UpdateFailed."""
    client = MagicMock()
    client.get_student_data = AsyncMock(side_effect=SimeConnectionError("Network timeout"))

    entry = create_mock_entry()
    coordinator = SimeDataUpdateCoordinator(
        hass=hass,
        client=client,
        entry=entry,
        student_ids=["UK00000001"],
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
