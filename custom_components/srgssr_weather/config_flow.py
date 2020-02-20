import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN, HOME_LOCATION_NAME


def has_config_entry(hass: HomeAssistantType, key: str) -> bool:
    for entry in hass.config_entries.async_entries(DOMAIN):
        data = entry.data
        entry_key = f"{data[CONF_LATITUDE]}-{data[CONF_LONGITUDE]}"
        if entry_key == key:
            return True

    return False


class SRGSSRConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None) -> dict:
        errors = {}

        if user_input is not None:
            key = f"{user_input[CONF_LATITUDE]}-{user_input[CONF_LONGITUDE]}"
            if has_config_entry(self.hass, key):
                errors[CONF_NAME] = "name_exists"
            else:
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        hass_config = self.hass.config

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME, default=HOME_LOCATION_NAME): str,
                vol.Required(CONF_LATITUDE, default=hass_config.latitude): cv.latitude,
                vol.Required(CONF_LONGITUDE, default=hass_config.longitude): cv.longitude,
            }),
            errors=errors,
        )
