"""DataUpdateCoordinator for Agenda SIME MD."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from lib.agenda_sime_md.client import SimeClient
from lib.agenda_sime_md.exceptions import (
    SimeAuthError,
    SimeConnectionError,
    SimeError,
    SimeRateLimitError,
)
from lib.agenda_sime_md.models import SimeStudentData

from .const import (
    CONF_DAY_END_HOUR,
    CONF_DAY_START_HOUR,
    CONF_SCAN_INTERVAL_DAY,
    CONF_SCAN_INTERVAL_NIGHT,
    DEFAULT_DAY_END_HOUR,
    DEFAULT_DAY_START_HOUR,
    DEFAULT_SCAN_INTERVAL_DAY,
    DEFAULT_SCAN_INTERVAL_NIGHT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class SimeDataUpdateCoordinator(DataUpdateCoordinator[dict[str, SimeStudentData]]):
    """Coordinator to fetch school data from agenda.sime.md with adaptive polling."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: SimeClient,
        entry: ConfigEntry,
        student_ids: list[str],
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.entry = entry
        self.student_ids = student_ids

        initial_interval = self._calculate_update_interval()
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=initial_interval,
        )

    def _calculate_update_interval(self) -> timedelta:
        """Compute adaptive update interval based on daytime school hours."""
        options = self.entry.options
        day_interval = options.get(CONF_SCAN_INTERVAL_DAY, DEFAULT_SCAN_INTERVAL_DAY)
        night_interval = options.get(CONF_SCAN_INTERVAL_NIGHT, DEFAULT_SCAN_INTERVAL_NIGHT)
        start_hour = options.get(CONF_DAY_START_HOUR, DEFAULT_DAY_START_HOUR)
        end_hour = options.get(CONF_DAY_END_HOUR, DEFAULT_DAY_END_HOUR)

        now = dt_util.now()
        is_daytime = start_hour <= now.hour < end_hour

        interval_minutes = day_interval if is_daytime else night_interval
        _LOGGER.debug(
            "Current hour %d: is_daytime=%s, setting interval to %d minutes",
            now.hour,
            is_daytime,
            interval_minutes,
        )
        return timedelta(minutes=interval_minutes)

    async def _async_update_data(self) -> dict[str, SimeStudentData]:
        """Fetch data from agenda.sime.md for all configured students."""
        # Dynamically adapt next update interval based on current time
        self.update_interval = self._calculate_update_interval()

        data: dict[str, SimeStudentData] = {}
        try:
            for student_id in self.student_ids:
                student_data = await self.client.get_student_data(student_id)
                data[student_id] = student_data
        except SimeRateLimitError as err:
            _LOGGER.warning("Rate limit encountered on agenda.sime.md: %s", err)
            raise UpdateFailed(f"Rate limited by SIME MD: {err}") from err
        except SimeAuthError as err:
            _LOGGER.error("Authentication error accessing agenda.sime.md: %s", err)
            raise ConfigEntryAuthFailed(err) from err
        except (SimeConnectionError, SimeError) as err:
            _LOGGER.error("Connection error communicating with agenda.sime.md: %s", err)
            raise UpdateFailed(f"Error fetching SIME MD data: {err}") from err
        except Exception as err:
            _LOGGER.exception("Unexpected error while updating SIME MD data")
            raise UpdateFailed(f"Unexpected error: {err}") from err

        return data
