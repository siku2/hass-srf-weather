import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_BASE, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .const import CONF_CONSUMER_KEY, CONF_CONSUMER_SECRET, DOMAIN, ERROR_INVALID_CREDENTIALS, ERROR_LOCATION_EXISTS, \
    HOME_LOCATION_NAME
from .weather import request_access_token

logger = logging.getLogger(__name__)


def has_config_entry(hass: HomeAssistantType, key: str) -> bool:
    for entry in hass.config_entries.async_entries(DOMAIN):
        data = entry.data
        entry_key = f"{data[CONF_LATITUDE]}-{data[CONF_LONGITUDE]}"
        if entry_key == key:
            return True

    return False


class SRGSSRConfigFlow(ConfigFlow, domain=DOMAIN):
    def __init__(self) -> None:
        self._credentials = None

    async def async_step_credentials(self, user_input: dict = None) -> dict:
        errors = {}

        if user_input is not None:
            key = user_input[CONF_CONSUMER_KEY]
            secret = user_input[CONF_CONSUMER_SECRET]

            try:
                await request_access_token(self.hass, key, secret)
            except Exception:
                errors[CONF_BASE] = ERROR_INVALID_CREDENTIALS
            else:
                self._credentials = user_input
                return await self.async_step_location()

        return self.async_show_form(
            step_id="credentials",
            data_schema=vol.Schema({
                vol.Required(CONF_CONSUMER_KEY): str,
                vol.Required(CONF_CONSUMER_SECRET): str,
            }),
            errors=errors,
        )

    async def async_step_user(self, user_input: dict = None) -> dict:
        if self._credentials is None:
            return await self.async_step_credentials()
        else:
            return await self.async_step_location()

    async def async_step_location(self, user_input: dict = None) -> dict:
        errors = {}

        if user_input is not None:
            key = f"{user_input[CONF_LATITUDE]}-{user_input[CONF_LONGITUDE]}"
            if has_config_entry(self.hass, key):
                errors[CONF_BASE] = ERROR_LOCATION_EXISTS
            else:
                data = user_input
                data.update(self._credentials)
                return self.async_create_entry(title=data[CONF_NAME], data=data)

        hass_config = self.hass.config

        return self.async_show_form(
            step_id="location",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME, default=HOME_LOCATION_NAME): str,
                vol.Required(CONF_LATITUDE, default=hass_config.latitude): cv.latitude,
                vol.Required(CONF_LONGITUDE, default=hass_config.longitude): cv.longitude,
            }),
            errors=errors,
        )
