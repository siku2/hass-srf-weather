import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .config_flow import ConfigFlow
from .const import CONF_CONSUMER_KEY, CONF_CONSUMER_SECRET, DATA_API_KEY, DOMAIN

__all__ = ["ConfigFlow"]

WEATHER_DOMAIN = "weather"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_CONSUMER_KEY): cv.string,
        vol.Required(CONF_CONSUMER_SECRET): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


# TODO configure in UI
async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    try:
        integ_config = config[DOMAIN]
    except KeyError:
        return False

    hass.data[DATA_API_KEY] = integ_config.copy()
    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry) -> bool:
    hass.async_create_task(hass.config_entries.async_forward_entry_setup(config_entry, WEATHER_DOMAIN))
    return True


async def async_unload_entry(hass: HomeAssistantType, config_entry: ConfigEntry) -> bool:
    await hass.config_entries.async_forward_entry_unload(config_entry, WEATHER_DOMAIN)
    return True
