"""DataUpdateCoordinator for PWEB Amano."""
from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PwebAmanoApiClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .exceptions import PwebAmanoError

_LOGGER = logging.getLogger(__name__)


class PwebAmanoCoordinator(DataUpdateCoordinator[dict]):
    """Logs in and fetches the dashboard page on each poll."""

    def __init__(self, hass: HomeAssistant, client: PwebAmanoApiClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict:
        try:
            await self.client.async_login()
            await self.client.async_fetch_dashboard()
        except PwebAmanoError as err:
            raise UpdateFailed(str(err)) from err

        return {"last_sync": datetime.now()}
