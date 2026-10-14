"""Exceptions for the agenda_sime_md library."""


class SimeError(Exception):
    """Base exception for all Agenda SIME MD errors."""


class SimeConnectionError(SimeError):
    """Raised when communication with agenda.sime.md fails."""


class SimeAuthError(SimeError):
    """Raised when authentication credentials are invalid or session expired."""


class SimeRateLimitError(SimeAuthError):
    """Raised when agenda.sime.md rate-limits or throttles login attempts."""

    def __init__(self, message: str, wait_seconds: int = 60) -> None:
        super().__init__(message)
        self.wait_seconds = wait_seconds


class SimeParseError(SimeError):
    """Raised when response data cannot be parsed."""
