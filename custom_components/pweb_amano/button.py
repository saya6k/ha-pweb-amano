"""Button platform for PWEB Amano — manual data refresh."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PwebAmanoConfigEntry
from .const import DOMAIN
from .coordinator import PwebAmanoCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PwebAmanoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button platform."""
    async_add_entities(
        [PwebAmanoRefreshButton(entry.runtime_data, entry)]
    )


class PwebAmanoRefreshButton(CoordinatorEntity[PwebAmanoCoordinator], ButtonEntity):
    """Forces an immediate re-login + data refresh, outside the normal poll interval."""

    _attr_has_entity_name = True
    _attr_translation_key = "refresh"

    def __init__(self, coordinator: PwebAmanoCoordinator, entry: PwebAmanoConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_refresh"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Amano Korea",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()
