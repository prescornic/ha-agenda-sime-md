"""Constants for the Agenda SIME MD integration."""

from homeassistant.const import Platform

DOMAIN = "agenda_sime_md"
NAME = "Agenda SIME MD"

# Supported Platforms
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
    Platform.TODO,
]

# Configuration and Options keys
CONF_STUDENTS = "students"
CONF_SCAN_INTERVAL_DAY = "scan_interval_day"
CONF_SCAN_INTERVAL_NIGHT = "scan_interval_night"

# Default intervals in minutes
DEFAULT_SCAN_INTERVAL_DAY = 15
DEFAULT_SCAN_INTERVAL_NIGHT = 60

# Daytime window definition (07:00 - 19:00)
DAY_START_HOUR = 7
DAY_END_HOUR = 19
