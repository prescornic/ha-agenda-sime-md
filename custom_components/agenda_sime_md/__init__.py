"""The Agenda SIME MD Home Assistant Integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .agenda_sime_md.client import SimeClient
from .agenda_sime_md.models import SimeAccountRole
from .const import (
    CONF_ROLE,
    CONF_STUDENTS,
    DEFAULT_ROLE,
    DOMAIN,
    PLATFORMS,
    ROLE_PARENT,
)
from .coordinator import SimeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Agenda SIME MD from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    role_str = entry.data.get(CONF_ROLE, DEFAULT_ROLE)
    student_ids = entry.data.get(CONF_STUDENTS, [])

    role_enum = SimeAccountRole.PARENT if role_str == ROLE_PARENT else SimeAccountRole.STUDENT

    session = async_create_clientsession(hass)
    client = SimeClient(
        username=username,
        password=password,
        role=role_enum,
        session=session,
    )

    coordinator = SimeDataUpdateCoordinator(
        hass=hass,
        client=client,
        entry=entry,
        student_ids=student_ids,
    )

    # Perform initial data fetch
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward entry setups to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register reload listener when options change
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Agenda SIME MD config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and DOMAIN in hass.data:
        coordinator: SimeDataUpdateCoordinator | None = hass.data[DOMAIN].pop(entry.entry_id, None)
        if coordinator and coordinator.client:
            await coordinator.client.close()
            if coordinator.client._session and not coordinator.client._session.closed:
                await coordinator.client._session.close()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)
