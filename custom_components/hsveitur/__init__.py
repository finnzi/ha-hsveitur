"""HS Veitur electricity usage."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HsVeiturClient
from .const import CONF_CUSTOMER_ID, CONF_PRIVATE_KEY, CONF_PUBLIC_KEY, DOMAIN
from .coordinator import HsVeiturConfigEntry, HsVeiturCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: HsVeiturConfigEntry) -> bool:
    client = HsVeiturClient(
        async_get_clientsession(hass),
        entry.data[CONF_PUBLIC_KEY],
        entry.data[CONF_PRIVATE_KEY],
        entry.data[CONF_CUSTOMER_ID],
    )
    coordinator = HsVeiturCoordinator(hass, entry, client)
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # API calls take minutes; do not block startup or the config flow on them.
    entry.async_create_background_task(
        hass, coordinator.async_refresh(), f"{DOMAIN} first refresh"
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HsVeiturConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
