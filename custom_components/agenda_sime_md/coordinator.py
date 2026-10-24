"""DataUpdateCoordinator for Agenda SIME MD."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .agenda_sime_md.client import SimeClient
from .agenda_sime_md.exceptions import (
    SimeAuthError,
    SimeConnectionError,
    SimeError,
    SimeRateLimitError,
)
from .agenda_sime_md.models import SimeStudentData
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
        self._absence_baseline: dict[str, tuple[date, int]] = {}
        self._absences_today: dict[str, int] = {}

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

    def get_absences_today(self, student_id: str) -> int:
        """Return count of absences recorded today for the student."""
        return self._absences_today.get(student_id, 0)

    def get_absence_baseline(self, student_id: str) -> int | None:
        """Return baseline absence count for the student today."""
        if student_id in self._absence_baseline:
            return self._absence_baseline[student_id][1]
        return None

    def set_absence_baseline(
        self, student_id: str, baseline_date: date, baseline_count: int
    ) -> None:
        """Set baseline absence count (used when restoring state across restarts)."""
        self._absence_baseline[student_id] = (baseline_date, baseline_count)
        if self.data and student_id in self.data:
            current_total = self.data[student_id].absence_summary.total
            self._absences_today[student_id] = max(0, current_total - baseline_count)

    async def _async_update_data(self) -> dict[str, SimeStudentData]:
        """Fetch data from agenda.sime.md for all configured students."""
        # Dynamically adapt next update interval based on current time
        self.update_interval = self._calculate_update_interval()

        data: dict[str, SimeStudentData] = {}
        today = dt_util.now().date()
        try:
            for student_id in self.student_ids:
                student_data = await self.client.get_student_data(student_id)
                data[student_id] = student_data

                current_total = student_data.absence_summary.total
                if student_id not in self._absence_baseline:
                    self._absence_baseline[student_id] = (today, current_total)
                    self._absences_today[student_id] = 0
                else:
                    base_date, base_count = self._absence_baseline[student_id]
                    if base_date != today:
                        self._absence_baseline[student_id] = (today, current_total)
                        self._absences_today[student_id] = 0
                    else:
                        self._absences_today[student_id] = max(0, current_total - base_count)
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
