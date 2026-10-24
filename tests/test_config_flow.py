"""Tests for Agenda SIME MD config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.agenda_sime_md.const import (
    CONF_DAY_END_HOUR,
    CONF_DAY_START_HOUR,
    CONF_ROLE,
    CONF_SCAN_INTERVAL_DAY,
    CONF_SCAN_INTERVAL_NIGHT,
    CONF_STUDENTS,
    DOMAIN,
    ROLE_PARENT,
)
from lib.agenda_sime_md.exceptions import (
    SimeAuthError,
    SimeConnectionError,
    SimeRateLimitError,
)
from lib.agenda_sime_md.models import SimeStudent


@pytest.fixture
def mock_students():
    """Mock list of students."""
    return [
        SimeStudent(
            id="UK00000001",
            name="Elev Exemplar",
            school_name="Liceul Teoretic Model",
        ),
        SimeStudent(
            id="UK00000002",
            name="Al Doilea Elev",
            school_name="Liceul Teoretic Model",
        ),
    ]


async def test_flow_user_single_student(hass: HomeAssistant, mock_students):
    """Test full flow when account has a single student."""
    single_student = [mock_students[0]]

    with (
        patch("custom_components.agenda_sime_md.async_setup_entry", return_value=True),
        patch(
            "custom_components.agenda_sime_md.config_flow.SimeClient.login", new_callable=AsyncMock
        ) as mock_login,
        patch(
            "custom_components.agenda_sime_md.config_flow.SimeClient.get_students",
            new_callable=AsyncMock,
            return_value=single_student,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "parent_user",
                CONF_PASSWORD: "secure_password",
                CONF_ROLE: ROLE_PARENT,
            },
        )
        assert mock_login.called
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Elev Exemplar (parent_user)"
        assert result["data"][CONF_STUDENTS] == ["UK00000001"]
        assert result["data"][CONF_ROLE] == ROLE_PARENT


async def test_flow_user_multiple_students(hass: HomeAssistant, mock_students):
    """Test flow when account has multiple enrolled students."""
    with (
        patch("custom_components.agenda_sime_md.async_setup_entry", return_value=True),
        patch(
            "custom_components.agenda_sime_md.config_flow.SimeClient.login", new_callable=AsyncMock
        ),
        patch(
            "custom_components.agenda_sime_md.config_flow.SimeClient.get_students",
            new_callable=AsyncMock,
            return_value=mock_students,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "parent_multi",
                CONF_PASSWORD: "secure_password",
                CONF_ROLE: ROLE_PARENT,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "students"

        # Select only the first student
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_STUDENTS: ["UK00000001"],
            },
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_STUDENTS] == ["UK00000001"]


async def test_flow_user_invalid_auth(hass: HomeAssistant):
    """Test handling of invalid authentication."""
    with patch(
        "custom_components.agenda_sime_md.config_flow.SimeClient.login",
        side_effect=SimeAuthError("Login failed"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "wrong_user",
                CONF_PASSWORD: "wrong_password",
                CONF_ROLE: ROLE_PARENT,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}


async def test_flow_user_rate_limit(hass: HomeAssistant):
    """Test handling of rate limit / throttle."""
    with patch(
        "custom_components.agenda_sime_md.config_flow.SimeClient.login",
        side_effect=SimeRateLimitError("Blocked", wait_seconds=60),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "throttled_user",
                CONF_PASSWORD: "password",
                CONF_ROLE: ROLE_PARENT,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "rate_limit"}


async def test_flow_user_cannot_connect(hass: HomeAssistant):
    """Test handling of network/connection error."""
    with patch(
        "custom_components.agenda_sime_md.config_flow.SimeClient.login",
        side_effect=SimeConnectionError("Network unreachable"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "parent_user",
                CONF_PASSWORD: "password",
                CONF_ROLE: ROLE_PARENT,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_reauth(hass: HomeAssistant):
    """Test re-authentication flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Elev Exemplar (parent_user)",
        data={
            CONF_USERNAME: "parent_user",
            CONF_PASSWORD: "old_password",
            CONF_ROLE: ROLE_PARENT,
            CONF_STUDENTS: ["UK00000001"],
        },
        unique_id="parent_user_parent",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "custom_components.agenda_sime_md.config_flow.SimeClient.login",
        new_callable=AsyncMock,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "new_secure_password"},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert entry.data[CONF_PASSWORD] == "new_secure_password"


async def test_flow_options(hass: HomeAssistant, mock_students):
    """Test options flow for customizing scan intervals."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Elev Exemplar (parent_user)",
        data={
            CONF_USERNAME: "parent_user",
            CONF_PASSWORD: "password",
            CONF_ROLE: ROLE_PARENT,
            CONF_STUDENTS: ["UK00000001"],
        },
        options={},
        unique_id="parent_user_parent",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SCAN_INTERVAL_DAY: 20,
            CONF_SCAN_INTERVAL_NIGHT: 45,
            CONF_DAY_START_HOUR: 8,
            CONF_DAY_END_HOUR: 18,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_SCAN_INTERVAL_DAY: 20,
        CONF_SCAN_INTERVAL_NIGHT: 45,
        CONF_DAY_START_HOUR: 8,
        CONF_DAY_END_HOUR: 18,
    }
