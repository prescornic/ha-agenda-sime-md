"""Test fixtures for Agenda SIME MD."""

from contextlib import suppress

import pytest

# Initialize pycares channel to warm up its safe shutdown loop thread before tests run
with suppress(ImportError, RuntimeError, OSError):
    import pycares
    _channel = pycares.Channel()


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for testing."""
    yield
