"""Latest meter reading sensor, one per meter."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HsVeiturConfigEntry, HsVeiturCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HsVeiturConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new_meters() -> None:
        new = [m for m in (coordinator.data or {}) if m not in known]
        known.update(new)
        async_add_entities(MeterIndexSensor(coordinator, m) for m in new)

    # The first refresh runs in the background (it can take minutes), so meters
    # are added as soon as data shows up. This listener also keeps polling alive.
    entry.async_on_unload(coordinator.async_add_listener(_add_new_meters))
    _add_new_meters()


class MeterIndexSensor(CoordinatorEntity[HsVeiturCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Energy"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: HsVeiturCoordinator, meter_id: str) -> None:
        super().__init__(coordinator)
        self._meter_id = meter_id
        reading = coordinator.data[meter_id]
        self._attr_unique_id = f"{DOMAIN}_{meter_id}_energy"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, meter_id)},
            manufacturer="HS Veitur",
            name=f"HS Veitur {reading.delivery_point_name or meter_id}",
            serial_number=meter_id,
        )

    @property
    def native_value(self) -> float | None:
        reading = (self.coordinator.data or {}).get(self._meter_id)
        return reading.index_value if reading else None
