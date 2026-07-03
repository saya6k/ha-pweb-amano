"""Sensor platform for PWEB Amano.

Only a login/last-sync status sensor exists so far — the authenticated
dashboard page hasn't been inspected yet, so no data fields have been mapped
to entities. See AGENTS.md before adding more.
"""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
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
    """Set up the sensor platform."""
    async_add_entities([PwebAmanoLastSyncSensor(entry.runtime_data, entry.entry_id)])


class PwebAmanoLastSyncSensor(CoordinatorEntity[PwebAmanoCoordinator], SensorEntity):
    """Timestamp of the last successful login + fetch."""

    _attr_has_entity_name = True
    _attr_translation_key = "last_sync"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: PwebAmanoCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_last_sync"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="PWEB Amano",
            manufacturer="Amano Korea",
        )

    @property
    def native_value(self):
        return self.coordinator.data.get("last_sync")
