import dataclasses
import logging
from collections.abc import Iterable, Iterator
from datetime import date, datetime, timedelta, timezone
from typing import Any, TypedDict

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from . import api
from .const import CONF_GEOLOCATION_ID
from .coordinator import Coordinator, get_coordinator
from .helpers import get_geolocation_description

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)

# you can download the icon set here: https://developer.srgssr.ch/api-catalog/srf-weather/srf-weather-description
ICON_CONDITION_MAP: dict[str, list[int]] = {
    ATTR_CONDITION_CLEAR_NIGHT: [-1],
    ATTR_CONDITION_CLOUDY: [18, 19],
    ATTR_CONDITION_EXCEPTIONAL: [],
    ATTR_CONDITION_FOG: [2, 17],
    ATTR_CONDITION_HAIL: [],
    ATTR_CONDITION_LIGHTNING_RAINY: [
        5,
        12,
        26,
        # these have snow (or hail?) in them as well
        9,
        16,
        30,
    ],
    ATTR_CONDITION_LIGHTNING: [],
    ATTR_CONDITION_PARTLYCLOUDY: [3, 10],
    ATTR_CONDITION_POURING: [23],
    ATTR_CONDITION_RAINY: [4, 11, 20, 25],
    ATTR_CONDITION_SNOWY_RAINY: [8, 15, 22, 29],
    ATTR_CONDITION_SNOWY: [
        6,
        13,
        21,
        24,
        27,
        # the following ones are more like "lightning snowy", but that doesn't exist
        5,
        12,
        26,
    ],
    ATTR_CONDITION_SUNNY: [1],
    ATTR_CONDITION_WINDY_VARIANT: [],
    ATTR_CONDITION_WINDY: [],
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    geolocation_id = config_entry.data[CONF_GEOLOCATION_ID]
    coordinator = get_coordinator(hass, config_entry.data)

    async_add_entities(
        [
            SrfWeather(coordinator, geolocation_id=geolocation_id),
        ],
    )


class SrfWeather(WeatherEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_should_poll = True

    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    _attr_native_pressure_unit = UnitOfPressure.PA
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_visibility_unit = None
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR

    def __init__(self, coordinator: Coordinator, *, geolocation_id: str) -> None:
        self.coordinator = coordinator
        self.geolocation_id = geolocation_id

        self._attr_unique_id = geolocation_id
        self._attr_name = None  # determined by data

        self._srf_data: SrfForecastData | None = None
        self._next_update_at: datetime | None = None

        self._set_forecast_now({})

    @property
    def extra_restore_state_data(self) -> ExtraStoredData | None:
        if not self._srf_data:
            return None
        return self._srf_data

    def _set_forecast_now(self, forecast_now: Forecast | dict[str, Any]) -> None:
        self._attr_condition = forecast_now.get("condition")
        self._attr_humidity = forecast_now.get("humidity")
        self._attr_native_apparent_temperature = forecast_now.get(
            "native_apparent_temperature"
        )
        self._attr_native_dew_point = forecast_now.get("native_dew_point")
        self._attr_native_pressure = forecast_now.get("native_pressure")
        self._attr_native_temperature = forecast_now.get("native_temperature")
        self._attr_native_wind_gust_speed = forecast_now.get("native_wind_gust_speed")
        self._attr_native_wind_speed = forecast_now.get("native_wind_speed")
        self._attr_uv_index = forecast_now.get("uv_index")
        self._attr_wind_bearing = forecast_now.get("wind_bearing")

        self._attr_extra_state_attributes = {}
        for key in (
            ForecastSrfExtra.__required_keys__ | ForecastSrfExtra.__optional_keys__
        ):
            value = forecast_now.get(key)
            if value is not None:
                self._attr_extra_state_attributes[key] = value

    def _set_srf_data(self, data: "SrfForecastData") -> None:
        self._srf_data = data
        self._next_update_at = self.coordinator.request_next_api_call()
        _LOGGER.debug("data updated, next update at %s", self._next_update_at)

        now = datetime.now(tz=timezone.utc)
        self._set_forecast_now(self._srf_data.get_forecast(now) or {})
        self._attr_name = data.name

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.coordinator.consumers += 1

        if last_extra_data := await self.async_get_last_extra_data():
            self._set_srf_data(SrfForecastData.from_dict(last_extra_data.as_dict()))
            _LOGGER.debug("restored srf data")
        self.async_schedule_update_ha_state(True)

    async def async_will_remove_from_hass(self) -> None:
        await super().async_will_remove_from_hass()
        self.coordinator.consumers -= 1

    async def async_update(self) -> None:
        now = datetime.now(tz=timezone.utc)
        should_update = self._srf_data is None
        should_update |= self._next_update_at is None or now >= self._next_update_at
        if should_update:
            _LOGGER.info("updating forecast from api")
            forecast_week = (
                await self.coordinator.client.get_forecast_week_by_geo_location(
                    self.geolocation_id
                )
            )
            self._set_srf_data(SrfForecastData.create_from_api(forecast_week))
            return

        assert self._srf_data  # is always set here
        self._set_forecast_now(self._srf_data.get_forecast(now) or {})

    @property
    def available(self) -> bool:
        return self._srf_data is not None

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        if not self._srf_data:
            return None
        now = datetime.now(tz=timezone.utc)
        return list(self._srf_data.iter_hourly(now))

    async def async_forecast_daily(self) -> list[Forecast] | None:
        if not self._srf_data:
            return None
        now = datetime.now(tz=timezone.utc)
        return list(self._srf_data.iter_daily(now))


class ForecastSrfExtra(TypedDict, total=False):
    symbol_code: int | None
    symbol24_code: int | None

    # for daily forecast
    sunrise: str | None
    sunset: str | None
    sunshine_hours: int | None

    # hourly forecast
    temphigh: float | None
    fresh_snow_cm: int | None
    sunshine_minutes: int | None
    irradiance: int | None
    color: api.Color | None


class ForecastSrf(ForecastSrfExtra, Forecast):
    ...


@dataclasses.dataclass(slots=True, kw_only=True)
class SrfForecastData(ExtraStoredData):
    name: str
    hourly: list[ForecastSrf]
    daily: list[ForecastSrf]

    def as_dict(self) -> dict[str, Any]:
        return {
            "hourly": self.hourly,
            "daily": self.daily,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SrfForecastData":
        return SrfForecastData(
            name=data.get("name", ""), hourly=data["hourly"], daily=data["daily"]
        )

    @classmethod
    def create_from_api(cls, forecast_week: api.ForecastPointWeek) -> "SrfForecastData":
        uvi_by_date = _build_uvi_by_date(forecast_week["days"])
        hourly = [
            forecast_from_hourly(
                forecast,
                uv_index=_get_uvi_for_hourly(uvi_by_date, forecast["date_time"]),
            )
            for forecast in forecast_week["hours"]
        ]
        hourly.extend(
            forecast_from_hourly(
                forecast,
                uv_index=_get_uvi_for_hourly(uvi_by_date, forecast["date_time"]),
            )
            for forecast in forecast_week["three_hours"]
        )
        daily = [forecast_from_daily(forecast) for forecast in forecast_week["days"]]
        name = get_geolocation_description(forecast_week["geolocation"])
        return SrfForecastData(name=name, hourly=hourly, daily=daily)

    def get_forecast(self, ts: datetime) -> ForecastSrf | None:
        return next(self.iter_hourly(ts), None)

    def iter_hourly(self, ts: datetime) -> Iterator[ForecastSrf]:
        return self._iter_forecasts(self.hourly, ts)

    def iter_daily(self, ts: datetime) -> Iterator[ForecastSrf]:
        return self._iter_forecasts(self.daily, ts)

    def _iter_forecasts(
        self, forecasts: Iterable[ForecastSrf], ts: datetime
    ) -> Iterator[ForecastSrf]:
        it = iter(forecasts)
        for forecast in it:
            ends_at = datetime.fromisoformat(forecast["datetime"])
            if ts < ends_at:
                yield forecast
                # once we've found the first valid forecast, the rest of them HAVE to be valid
                break
        yield from it


def _build_uvi_by_date(days: list[api.DayForecastInterval]) -> dict[date, float | None]:
    mapping: dict[date, float | None] = {}
    for day in days:
        dt = datetime.fromisoformat(day["date_time"])
        mapping[dt.date()] = day.get("UVI")
    return mapping


def _get_uvi_for_hourly(
    uvi_by_date: dict[date, float | None], date_time: str
) -> float | None:
    dt = datetime.fromisoformat(date_time)
    return uvi_by_date.get(dt.date())


def forecast_from_hourly(
    forecast: api.OneHourForecastInterval, *, uv_index: float | None
) -> ForecastSrf:
    return ForecastSrf(
        condition=condition_from_forecast(forecast),
        datetime=forecast["date_time"],
        humidity=forecast.get("RELHUM_PERCENT"),
        precipitation_probability=forecast["PROBPCP_PERCENT"],
        cloud_coverage=None,
        native_precipitation=forecast["RRR_MM"],
        native_pressure=forecast.get("PRESSURE_HPA"),
        native_temperature=forecast["TTT_C"],
        native_templow=forecast.get("TTL_C"),
        native_apparent_temperature=forecast.get("TTTFEEL_C"),
        wind_bearing=forecast["DD_DEG"],
        native_wind_gust_speed=forecast["FX_KMH"],
        native_wind_speed=forecast["FF_KMH"],
        native_dew_point=forecast.get("DEWPOINT_C"),
        uv_index=uv_index,
        is_daytime=None,
        # srf extra
        symbol_code=forecast.get("symbol_code"),
        symbol24_code=forecast.get("symbol24_code"),
        temphigh=forecast.get("TTH_C"),
        fresh_snow_cm=forecast.get("FRESHSNOW_CM"),
        sunshine_minutes=forecast.get("SUN_MIN"),
        irradiance=forecast.get("IRRADIANCE_WM2"),
        color=forecast.get("cur_color"),
    )


def forecast_from_daily(forecast: api.DayForecastInterval) -> ForecastSrf:
    return ForecastSrf(
        condition=condition_from_forecast(forecast),
        datetime=forecast["date_time"],
        humidity=None,
        precipitation_probability=forecast["PROBPCP_PERCENT"],
        cloud_coverage=None,
        native_precipitation=forecast["RRR_MM"],
        native_pressure=None,
        native_temperature=forecast["TX_C"],  # this is technically the max temperature
        native_templow=forecast["TN_C"],
        native_apparent_temperature=None,
        wind_bearing=forecast["DD_DEG"],
        native_wind_gust_speed=forecast["FX_KMH"],
        native_wind_speed=forecast["FF_KMH"],
        native_dew_point=None,
        uv_index=forecast.get("UVI"),
        is_daytime=None,
        # srf extra
        symbol_code=forecast.get("symbol_code"),
        symbol24_code=forecast.get("symbol24_code"),
        sunrise=forecast.get("SUNRISE"),
        sunset=forecast.get("SUNSET"),
        sunshine_hours=forecast.get("SUN_H"),
    )


_INV_ICON2COND = {
    icon: condition for condition, icons in ICON_CONDITION_MAP.items() for icon in icons
}


def condition_from_forecast(forecast: api.ForecastABC) -> str | None:
    icon = forecast["symbol_code"]
    try:
        return _INV_ICON2COND[icon]
    except KeyError:
        pass
    # invert day / night (night icons are negative) and try to look up that
    return _INV_ICON2COND.get(-icon)
