import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_BASE, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .const import CONF_CONSUMER_KEY, CONF_CONSUMER_SECRET, CONF_GEOLOCATION_ID, DOMAIN, ERROR_INVALID_CREDENTIALS, ERROR_GEOLOCATION_EXISTS, \
    ERROR_NO_GEOLOCATION_FOUND, HOME_LOCATION_NAME
from .weather import request_access_token, get_geolocation_ids

logger = logging.getLogger(__name__)


def has_config_entry(hass: HomeAssistantType, key: str) -> bool:
    for entry in hass.config_entries.async_entries(DOMAIN):
        data = entry.data
        if data[CONF_GEOLOCATION_ID] == key:
            return True

    return False


class SRGSSRConfigFlow(ConfigFlow, domain=DOMAIN):
    def __init__(self) -> None:
        self._credentials = None
        self._location = None
        self._geolocations = None

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

    async def async_step_location(self, user_input: dict = None) -> dict:
        errors: dict[str, str] = {}

        if user_input is not None:
            latitude = user_input[CONF_LATITUDE]
            longitude = user_input[CONF_LONGITUDE]
            geolocations = await get_geolocation_ids(self.hass, self._credentials, latitude, longitude)

            if geolocations is None or len(geolocations) == 0:
                logger.debug("No geolocation found for coordinates %f, %f", latitude, longitude)
                errors[CONF_BASE] = ERROR_NO_GEOLOCATION_FOUND
            else:
                self._location = user_input
                self._geolocations = geolocations
                return await self.async_step_geolocationid()

        hass_config = self.hass.config
        logger.debug("Show again, with errors %s", errors)
        return self.async_show_form(
            step_id="location",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME, default=HOME_LOCATION_NAME): str,
                vol.Required(CONF_LATITUDE, default=hass_config.latitude): cv.latitude,
                vol.Required(CONF_LONGITUDE, default=hass_config.longitude): cv.longitude,
            }),
            errors=errors,
        )

    async def async_step_geolocationid(self, user_input: dict = None) -> dict:
        errors = {}

        if user_input is not None:
            if has_config_entry(self.hass, user_input[CONF_GEOLOCATION_ID]):
                errors[CONF_BASE] = ERROR_GEOLOCATION_EXISTS
            else:
                data = user_input
                data.update(self._credentials)
                data.update(self._location)
                logger.debug("Creating entity with data %s", data)
                return self.async_create_entry(title=data[CONF_NAME], data=data)

        geolocations = {
            geoloc["id"]: geoloc["default_name"]
            for geoloc in self._geolocations
        }
        logger.debug(geolocations)

        return self.async_show_form(
            step_id="geolocationid",
            data_schema=vol.Schema({
                vol.Required(CONF_GEOLOCATION_ID): vol.In(geolocations)
            }),
            errors=errors,
        )

    async def async_step_user(self, user_input: dict = None) -> dict:
        if self._credentials is None:
            return await self.async_step_credentials()
        elif self._location is None:
            return await self.async_step_location()
        else:
            return await self.async_step_location()