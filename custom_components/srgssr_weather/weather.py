from typing import List

from homeassistant.components.weather import WeatherEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import HomeAssistantType

from . import get_api_key


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities) -> None:
    async_add_entities((SRGSSTWeather(),))


URL_BASE = "https://api.srgssr.ch/forecasts/v1.0/weather"
URL_HOUR_FORECAST_BY_ID = URL_BASE + "/nexthour"


class SRGSSTWeather(WeatherEntity):
    def __init__(self) -> None:
        super().__init__()

    @property
    def name(self) -> str:
        pass

    def state(self) -> str:
        pass

    def temperature(self) -> float:
        pass

    def pressure(self) -> float:
        pass

    def humidity(self) -> float:
        pass

    def visibility(self) -> float:
        pass

    def wind_speed(self) -> float:
        pass

    def wind_bearing(self) -> str:
        pass

    def forecast(self) -> List[dict]:
        pass

    def attribution(self) -> str:
        return "SRF Schweizer Radio und Fernsehen"

    async def async_update(self) -> None:
        session = async_get_clientsession(self.hass)

        headers = {
            "Authorization": f"Bearer {get_api_key(self.hass)}",
        }
        params = {}
        async with session.get(URL_HOUR_FORECAST_BY_ID, params=params, headers=headers) as resp:
            data = await resp.json()

        print(data)
