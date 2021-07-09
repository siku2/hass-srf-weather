from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .config_flow import ConfigFlow

__all__ = ["ConfigFlow"]

WEATHER_DOMAIN = "weather"


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry) -> bool:
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, WEATHER_DOMAIN)
    )
    return True


async def async_unload_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry
) -> bool:
    await hass.config_entries.async_forward_entry_unload(config_entry, WEATHER_DOMAIN)
    return True
