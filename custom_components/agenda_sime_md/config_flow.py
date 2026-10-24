"""Config flow for Agenda SIME MD integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .agenda_sime_md.client import SimeClient
from .agenda_sime_md.exceptions import (
    SimeAuthError,
    SimeConnectionError,
    SimeError,
    SimeRateLimitError,
)
from .agenda_sime_md.models import SimeAccountRole, SimeStudent
from .const import (
    CONF_DAY_END_HOUR,
    CONF_DAY_START_HOUR,
    CONF_ROLE,
    CONF_SCAN_INTERVAL_DAY,
    CONF_SCAN_INTERVAL_NIGHT,
    CONF_STUDENT_NAMES,
    CONF_STUDENTS,
    DEFAULT_DAY_END_HOUR,
    DEFAULT_DAY_START_HOUR,
    DEFAULT_ROLE,
    DEFAULT_SCAN_INTERVAL_DAY,
    DEFAULT_SCAN_INTERVAL_NIGHT,
    DOMAIN,
    ROLE_PARENT,
    ROLE_STUDENT,
)

_LOGGER = logging.getLogger(__name__)


class SimeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Agenda SIME MD."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._username: str | None = None
        self._password: str | None = None
        self._role: str = DEFAULT_ROLE
        self._discovered_students: list[SimeStudent] = []
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step where user provides credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]
            role_str = user_input.get(CONF_ROLE, DEFAULT_ROLE)

            unique_id = f"{username.lower()}_{role_str}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            role_enum = (
                SimeAccountRole.PARENT if role_str == ROLE_PARENT else SimeAccountRole.STUDENT
            )

            session = async_create_clientsession(self.hass)
            client = SimeClient(
                username=username,
                password=password,
                role=role_enum,
                session=session,
            )

            try:
                await client.login()
                students = await client.get_students()
            except SimeRateLimitError:
                errors["base"] = "rate_limit"
            except SimeAuthError:
                errors["base"] = "invalid_auth"
            except (SimeConnectionError, SimeError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during login verification")
                errors["base"] = "unknown"
            else:
                self._username = username
                self._password = password
                self._role = role_str
                self._discovered_students = students

                if len(students) > 1:
                    return await self.async_step_students()

                # Single student found
                student = students[0] if students else SimeStudent(id=username, name=username)
                return self.async_create_entry(
                    title=f"{student.name} ({username})",
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_ROLE: role_str,
                        CONF_STUDENTS: [student.id],
                        CONF_STUDENT_NAMES: {student.id: student.name},
                    },
                )
            finally:
                await session.close()

        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_ROLE, default=DEFAULT_ROLE): vol.In(
                    {
                        ROLE_PARENT: "Parent (Părinte)",
                        ROLE_STUDENT: "Student (Elev)",
                    }
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_students(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle multi-student selection step for parent accounts."""
        errors: dict[str, str] = {}

        student_options = {
            s.id: f"{s.name} ({s.school_name})" if s.school_name else s.name
            for s in self._discovered_students
        }

        if user_input is not None:
            selected_ids = user_input.get(CONF_STUDENTS, [])
            if not selected_ids:
                errors["base"] = "no_students_selected"
            else:
                student_names = {
                    s.id: s.name for s in self._discovered_students if s.id in selected_ids
                }
                title = (
                    f"{student_names[selected_ids[0]]} ({self._username})"
                    if len(selected_ids) == 1
                    else f"Agenda SIME MD ({self._username})"
                )
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_USERNAME: self._username,
                        CONF_PASSWORD: self._password,
                        CONF_ROLE: self._role,
                        CONF_STUDENTS: selected_ids,
                        CONF_STUDENT_NAMES: student_names,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_STUDENTS,
                    default=list(student_options.keys()),
                ): cv.multi_select(student_options),
            }
        )

        return self.async_show_form(
            step_id="students",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Handle re-authentication initiation."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-entering password for re-authentication."""
        errors: dict[str, str] = {}
        if self._reauth_entry is None:
            return self.async_abort(reason="unknown")

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            username = self._reauth_entry.data[CONF_USERNAME]
            role_str = self._reauth_entry.data.get(CONF_ROLE, DEFAULT_ROLE)
            role_enum = (
                SimeAccountRole.PARENT if role_str == ROLE_PARENT else SimeAccountRole.STUDENT
            )

            session = async_create_clientsession(self.hass)
            client = SimeClient(
                username=username,
                password=password,
                role=role_enum,
                session=session,
            )

            try:
                await client.login()
            except SimeRateLimitError:
                errors["base"] = "rate_limit"
            except SimeAuthError:
                errors["base"] = "invalid_auth"
            except (SimeConnectionError, SimeError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during reauth verification")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._reauth_entry,
                    data={
                        **self._reauth_entry.data,
                        CONF_PASSWORD: password,
                    },
                )
            finally:
                await session.close()

        schema = vol.Schema({vol.Required(CONF_PASSWORD): str})
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SimeOptionsFlowHandler:
        """Get options flow handler."""
        return SimeOptionsFlowHandler()


class SimeOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Agenda SIME MD."""

    def __init__(self, config_entry: ConfigEntry | None = None) -> None:
        """Initialize options flow."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage polling interval and school hours options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL_DAY,
                    default=options.get(CONF_SCAN_INTERVAL_DAY, DEFAULT_SCAN_INTERVAL_DAY),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=120)),
                vol.Required(
                    CONF_SCAN_INTERVAL_NIGHT,
                    default=options.get(CONF_SCAN_INTERVAL_NIGHT, DEFAULT_SCAN_INTERVAL_NIGHT),
                ): vol.All(vol.Coerce(int), vol.Range(min=15, max=240)),
                vol.Required(
                    CONF_DAY_START_HOUR,
                    default=options.get(CONF_DAY_START_HOUR, DEFAULT_DAY_START_HOUR),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
                vol.Required(
                    CONF_DAY_END_HOUR,
                    default=options.get(CONF_DAY_END_HOUR, DEFAULT_DAY_END_HOUR),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
