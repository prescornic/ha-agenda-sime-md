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
CONF_ROLE = "role"
CONF_STUDENTS = "students"
CONF_STUDENT_NAMES = "student_names"
CONF_SCAN_INTERVAL_DAY = "scan_interval_day"
CONF_SCAN_INTERVAL_NIGHT = "scan_interval_night"
CONF_DAY_START_HOUR = "day_start_hour"
CONF_DAY_END_HOUR = "day_end_hour"

# Roles
ROLE_PARENT = "parent"
ROLE_STUDENT = "student"
DEFAULT_ROLE = ROLE_PARENT

# Polling interval defaults (in minutes)
DEFAULT_SCAN_INTERVAL_DAY = 15
DEFAULT_SCAN_INTERVAL_NIGHT = 60

# Daytime active school hours (07:00 - 19:00)
DEFAULT_DAY_START_HOUR = 7
DEFAULT_DAY_END_HOUR = 19
