import asyncio
import base64
import logging
import random
import time
from datetime import datetime
from typing import Iterable, List, Mapping, MutableMapping, Optional

from homeassistant.components.weather import WeatherEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, TEMP_CELSIUS
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import HomeAssistantType

from .const import ATTR_API_KEY, ATTR_EXPIRES_AT, CONF_CONSUMER_KEY, CONF_CONSUMER_SECRET

logger = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities) -> None:
    async_add_entities((SRGSSTWeather(config_entry.data),))


API_URL = "https://api.srgssr.ch"

URL_OAUTH = API_URL + "/oauth/v1/accesstoken"

URL_FORECASTS = API_URL + "/forecasts/v1.0/weather"
URL_HOUR_FORECAST_BY_ID = URL_FORECASTS + "/nexthour"
URL_WEEKS_FORECAST_BY_ID = URL_FORECASTS + "/7day"


async def request_access_token(hass: HomeAssistantType, key: str, secret: str) -> dict:
    session = async_get_clientsession(hass)

    auth = base64.b64encode(f"{key}:{secret}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}"}
    params = {"grant_type": "client_credentials"}
    async with session.post(URL_OAUTH, params=params, headers=headers) as resp:
        return await resp.json()


async def _renew_api_key(hass: HomeAssistantType, data: MutableMapping) -> None:
    token_data = await request_access_token(hass, data[CONF_CONSUMER_KEY], data[CONF_CONSUMER_SECRET])

    data[ATTR_EXPIRES_AT] = int(token_data["expires_in"]) + int(token_data["issued_at"]) // 1000
    data[ATTR_API_KEY] = token_data["access_token"]


async def get_api_key(hass: HomeAssistantType, data: MutableMapping) -> str:
    try:
        expires_at = data[ATTR_EXPIRES_AT]
    except KeyError:
        renew = True
    else:
        renew = time.time() >= expires_at

    if renew:
        logger.info("renewing api key")
        await _renew_api_key(hass, data)

    return data[ATTR_API_KEY]


class SRGSSTWeather(WeatherEntity):
    def __init__(self, config: dict) -> None:
        self._config = config
        self._default_params = {
            "latitude": str(config[CONF_LATITUDE]),
            "longitude": str(config[CONF_LONGITUDE]),
        }
        self.__update_loop_task = None

        self._forecast = []
        self._state = None
        self._temperature = None
        self._wind_speed = None
        self._wind_bearing = None

        self._state_attrs = {}

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def unique_id(self):
        return f"{self._config[CONF_LATITUDE]}-{self._config[CONF_LONGITUDE]}"

    @property
    def name(self) -> Optional[str]:
        return self._config.get(CONF_NAME)

    @property
    def device_state_attributes(self) -> dict:
        return self._state_attrs

    @property
    def state(self) -> Optional[str]:
        return self._state

    @property
    def temperature(self) -> Optional[float]:
        return self._temperature

    @property
    def temperature_unit(self):
        return TEMP_CELSIUS

    @property
    def pressure(self) -> Optional[float]:
        return None

    @property
    def humidity(self) -> Optional[float]:
        return None

    @property
    def visibility(self) -> Optional[float]:
        return None

    @property
    def wind_speed(self) -> Optional[float]:
        return self._wind_speed

    @property
    def wind_bearing(self) -> Optional[str]:
        return self._wind_bearing

    @property
    def forecast(self) -> List[dict]:
        return self._forecast

    @property
    def attribution(self) -> str:
        return "SRF Schweizer Radio und Fernsehen"

    async def __get(self, url: str, **kwargs) -> dict:
        session = async_get_clientsession(self.hass)
        api_key = await get_api_key(self.hass, self._config)
        weak_update(kwargs, "headers", {
            "Authorization": f"Bearer {api_key}",
        })
        weak_update(kwargs, "params", self._default_params)
        async with session.get(url, **kwargs) as resp:
            return await resp.json()

    async def __update_current(self) -> None:
        data = await self.__get(URL_HOUR_FORECAST_BY_ID)

        forecast = merge_mappings(data["nexthour"][0]["values"])

        symbol_id = int(forecast["smb3"])
        self._state = SYMBOL_STATE_MAP.get(symbol_id)
        self._temperature = float(forecast["ttt"])
        self._wind_speed = float(forecast["fff"])
        self._wind_speed = float(forecast["ffx3"])
        wind_bearing_deg = float(forecast["ddd"])
        self._wind_bearing = deg_to_cardinal(wind_bearing_deg)

        self._state_attrs.update(
            wind_direction=wind_bearing_deg,
            symbol_id=symbol_id,
            precipitation=float(forecast["rr3"]),
            rain_probability=float(forecast["pr3"]),
        )

    async def __update_forecast(self) -> None:
        data = await self.__get(URL_WEEKS_FORECAST_BY_ID)

        forecast = []
        for day in data["7days"]:
            date = datetime.strptime(day["date"], "%Y-%m-%d")
            values = merge_mappings(day["values"])

            temp_high = float(values["ttn"])
            temp_low = float(values["ttx"])
            symbol_id = int(values["smbd"])
            state = SYMBOL_STATE_MAP.get(symbol_id)

            forecast.append({
                "datetime": date.isoformat(),
                "temperature": temp_high,
                "condition": state,
                "symbol_id": symbol_id,
                "templow": temp_low,
            })

        self._forecast = forecast

    async def __update_loop(self) -> None:
        while True:
            try:
                await self.__update_current()
                await self.__update_forecast()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("failed to update weather")
            else:
                await self.async_update_ha_state()

            delay = random.randrange(55, 65) * 60
            await asyncio.sleep(delay)

    async def async_added_to_hass(self) -> None:
        self.__update_loop_task = asyncio.create_task(self.__update_loop())

    async def async_will_remove_from_hass(self) -> None:
        if self.__update_loop_task:
            self.__update_loop_task.cancel()
            self.__update_loop_task = None


CARDINALS = (
    "N", "NNE", "NE", "ENE",
    "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW",
    "W", "WNW", "NW", "NNW",
)

DEG_HALF_CIRCLE = 180
DEG_FULL_CIRCLE = 2 * DEG_HALF_CIRCLE
_CARDINAL_DEGREE = DEG_FULL_CIRCLE / len(CARDINALS)


def deg_to_cardinal(deg: float) -> str:
    i = round((deg % DEG_FULL_CIRCLE) / _CARDINAL_DEGREE)
    return CARDINALS[i % len(CARDINALS)]


SYMBOL_STATE_MAP = {
    1: "sunny",  # sonnig
    2: "sunny",  # Sonne und Nebelbänke
    3: "windy-variant",  # Sonne und Wolken im Wechsel
    4: "sunny",  # teils sonnig, teils Schauer
    5: "lightning",  # sonnige Abschnitte und einige Gewitter
    6: "sunny",  # teils sonnig, einzelne Schneeschauer
    7: "snowy-rainy",  # sonnige Abschnitte und einige Gewitter mit Schnee
    8: "snowy-rainy",  # sonnige Abschnitte und Schneeregenschauer
    9: "snowy-rainy",  # wechselhaft mit Schneeregenschauern und Gewittern
    10: "partlycloudy",  # ziemlich sonnig
    11: "sunny",  # sonnig, aber auch einzelne Schauer
    12: "sunny",  # sonnig und nur einzelne Gewitter
    13: "sunny",  # sonnig und nur einzelne Schneeschauer
    14: "sunny",  # sonnig, einzelne Schneeschauer, dazwischen sogar Blitz und Donner
    15: "sunny",  # sonnig und nur einzelne Schauer, vereinzelt auch Flocken
    16: "sunny",  # oft sonnig, nur einzelne gewittrige Schauer, teils auch Flocken
    17: "fog",  # Nebel
    18: "cloudy",  # stark bewölkt
    19: "cloudy",  # bedeckt
    20: "rainy",  # regnerisch
    21: "snowy",  # stark bewölkt mit Schnee
    22: "snowy-rainy",  # Regen, zeitweise auch mit Flocken
    23: "pouring",  # Dauerregen
    24: "snowy",  # starker Schneefall
    25: "windy",  # trockene Phasen und Schauer im Wechsel
    26: "lightning",  # stark bewölkt und einige Gewitter
    27: "snowy",  # trüb mit einigen Schneeschauern
    28: "cloudy",  # stark bewölkt, Schneeschauer, dazwischen Blitz und Donner
    29: "snowy-rainy",  # ab und zu Schneeregen
    30: "snowy-rainy",  # Schneeregen, einzelne Gewitter
    -1: "clear-night",  # klar
    -2: "partlycloudy",  # klar mit ein paar Nebelbänken
    -3: "sunny",  # ab und zu Wolken
    -4: "rainy",  # einige Schauer
    -5: "lightning",  # wenige Gewitter
    -6: "snowy",  # einzelne Schneeschauer
    -7: "snowy",  # einige Gewitter mit Schnee
    -8: "snowy-rainy",  # Schneeregenschauer
    -9: "lightning-rainy",  # wechselhaft mit Schneeregenschauern und Gewittern
    -10: "partlycloudy",  # nur selten Wolken
    -11: "rainy",  # einzelne Schauer
    -12: "lightning",  # einzelne Gewitter
    -13: "snowy",  # einzelne Schneeschauer
    -14: "snowy",  # einzelne Schneeschauer, dazwischen sogar Blitz und Donner
    -15: "snowy-rainy",  # einzelne Schauer, vereinzelt auch Flocken
    -16: "partlycloudy",  # oft sonnig, nur einzelne gewittrige Schauer, teils auch Flocken
    -17: "fog",  # Nebel
    -18: "cloudy",  # stark bewölkt
    -19: "cloudy",  # bedeckt
    -20: "rainy",  # regnerisch
    -21: "snowy",  # stark bewölkt mit Schnee
    -22: "snowy-rainy",  # Regen, zeitweise auch mit Flocken
    -23: "pouring",  # Dauerregen
    -24: "snowy",  # starker Schneefall
    -25: "rainy",  # trockene Phasen und Schauer im Wechsel
    -26: "lightning",  # stark bewölkt und einige Gewitter
    -27: "rainy",  # trüb mit einigen Schneeschauern
    -28: "lightning-rainy",  # stark bewölkt, Schneeschauer, dazwischen Blitz und Donner
    -29: "snowy-rainy",  # ab und zu Schneeregen
    -30: "snowy-rainy",  # Schneeregen, einzelne Gewitter
}


def merge_mappings(maps: Iterable[Mapping]) -> dict:
    d = {}
    for m in maps:
        d.update(m)
    return d


def weak_update(d: MutableMapping, key: str, value: MutableMapping) -> None:
    try:
        existing = d[key]
    except KeyError:
        pass
    else:
        value.update(existing)

    d[key] = value
