import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_BASE
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.typing import HomeAssistantType

from . import api
from .coordinator import get_coordinator, Coordinator
from .const import CONF_CONSUMER_KEY, CONF_CONSUMER_SECRET, CONF_GEOLOCATION_ID, DOMAIN
from .helpers import get_geolocation_description

_LOGGER = logging.getLogger(__name__)

ERROR_INVALID_CREDENTIALS = "invalid_credentials"
ERROR_NO_GEOLOCATION_FOUND = "no_geolocation_found"
ERROR_GEOLOCATION_EXISTS = "geolocation_exists"
ERROR_HOME_NOT_FOUND = "home_not_found"

CONF_ZIP_CODE = "zip_code"


def has_config_entry_for_geolocation_id(
    hass: HomeAssistantType, geolocation_id: str
) -> bool:
    for entry in hass.config_entries.async_entries(DOMAIN):
        data = entry.data
        if data[CONF_GEOLOCATION_ID] == geolocation_id:
            return True

    return False


class SrfMeteoConfigFlow(ConfigFlow, domain=DOMAIN):
    """SRF-Meteo configuration flow."""

    VERSION = 2

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._coordinator: Coordinator | None = None
        self._geolocations: list[api.Geolocation] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 0"""
        return await self.async_step_credentials(user_input)

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: provide credentials"""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._coordinator = get_coordinator(self.hass, user_input)

            try:
                await self._coordinator.client.attemp_auth()
            except Exception as exc:
                _LOGGER.warn(
                    "authentication attemp failed in config flow", exc_info=exc
                )
                errors[CONF_BASE] = ERROR_INVALID_CREDENTIALS
            else:
                self._data = user_input
                return await self.async_step_search_menu()

        return self.async_show_form(
            step_id="credentials",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CONSUMER_KEY): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT)
                    ),
                    vol.Required(CONF_CONSUMER_SECRET): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_search_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1.5: let the user pick how to search for the geolocation"""
        return self.async_show_menu(
            step_id="search_menu", menu_options=["search_ha_home", "search_zip"]
        )

    async def async_step_search_ha_home(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2a: discover geolocations for Home Assistant home"""
        assert self._coordinator  # step 1 will set the client

        try:
            self._geolocations = await self._coordinator.client.get_geolocations(
                str(self.hass.config.latitude), str(self.hass.config.longitude)
            )
        except Exception as exc:
            _LOGGER.warn("failed to get geolocations in config flow", exc_info=exc)
            self._geolocations = []

        if self._geolocations:
            # move on
            return await self.async_step_choose_geolocation()
        else:
            # fall back on ZIP search
            return await self.async_step_search_zip(ha_home_not_found=True)

    async def async_step_search_zip(
        self,
        user_input: dict[str, Any] | None = None,
        *,
        ha_home_not_found: bool = False
    ) -> FlowResult:
        """Step 2b: discover geolocations for provided ZIP code"""
        assert self._coordinator  # step 1 will set the client

        errors: dict[str, str] = {}
        if ha_home_not_found:
            errors[CONF_BASE] = ERROR_HOME_NOT_FOUND

        if user_input is not None:
            zip_code = user_input[CONF_ZIP_CODE]
            try:
                results = await self._coordinator.client.search_geolocation(
                    zip=zip_code,
                    limit=30,
                )
            except Exception as exc:
                _LOGGER.warn(
                    "failed to search geolocations in config flow", exc_info=exc
                )
                results = []

            self._geolocations = [result["geolocation"] for result in results]

            if self._geolocations:
                return await self.async_step_choose_geolocation()
            else:
                errors[CONF_BASE] = ERROR_NO_GEOLOCATION_FOUND

        return self.async_show_form(
            step_id="search_zip",
            data_schema=vol.Schema({vol.Required(CONF_ZIP_CODE): int}),
            errors=errors,
        )

    async def async_step_choose_geolocation(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: select specific geolocation"""
        assert self._geolocations  # step 2 will set this to a non-empty list

        errors: dict[str, str] = {}

        if user_input is not None:
            if has_config_entry_for_geolocation_id(
                self.hass, user_input[CONF_GEOLOCATION_ID]
            ):
                errors[CONF_BASE] = ERROR_GEOLOCATION_EXISTS
            else:
                self._data.update(user_input)
                geolocation = next(
                    geolocation
                    for geolocation in self._geolocations
                    if geolocation["id"] == user_input[CONF_GEOLOCATION_ID]
                )
                geolocation_name = get_geolocation_description(geolocation)
                _LOGGER.info("creating config entry with data: %s", self._data)
                return self.async_create_entry(title=geolocation_name, data=self._data)

        return self.async_show_form(
            step_id="choose_geolocation",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_GEOLOCATION_ID): vol.In(
                        {
                            geolocation["id"]: get_geolocation_description(geolocation)
                            for geolocation in self._geolocations
                        }
                    )
                }
            ),
            errors=errors,
        )
