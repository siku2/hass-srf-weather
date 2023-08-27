import dataclasses
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

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

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)


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
        update_before_add=True,
    )


class SrfWeather(WeatherEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_should_poll = True
    _attr_attribution = "SRF Schweizer Radio und Fernsehen"

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
        self._attr_name = "HALP"

        self._srf_data: SrfForecastData | None = None
        self._next_update_at: datetime | None = None

    @property
    def extra_restore_state_data(self) -> ExtraStoredData | None:
        if not self._srf_data:
            return None
        return self._srf_data

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.coordinator.consumers += 1

        if last_extra_data := await self.async_get_last_extra_data():
            self._srf_data = SrfForecastData.from_dict(last_extra_data.as_dict())

    async def async_will_remove_from_hass(self) -> None:
        await super().async_will_remove_from_hass()
        self.coordinator.consumers -= 1

    async def async_update(self) -> None:
        now = datetime.now(tz=timezone.utc)
        should_update = self._srf_data is None
        should_update |= self._next_update_at is None or now >= self._next_update_at
        if should_update:
            forecast_week = (
                await self.coordinator.client.get_forecast_week_by_geo_location(
                    self.geolocation_id
                )
            )
            self._srf_data = SrfForecastData.create_from_api(forecast_week)
            self._next_update_at = self.coordinator.request_next_api_call()
            _LOGGER.debug("data updated, next update at %s", self._next_update_at)

        assert self._srf_data  # is always set here

        forecast_now = self._srf_data.get_forecast(now) or {}
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

    @property
    def available(self) -> bool:
        return self._srf_data is not None

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        if not self._srf_data:
            return None
        return self._srf_data.hourly

    async def async_forecast_daily(self) -> list[Forecast] | None:
        if not self._srf_data:
            return None
        return self._srf_data.daily


@dataclasses.dataclass(slots=True, kw_only=True)
class SrfForecastData(ExtraStoredData):
    hourly: list[Forecast]
    daily: list[Forecast]

    def as_dict(self) -> dict[str, Any]:
        return {
            "hourly": self.hourly,
            "daily": self.daily,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SrfForecastData":
        return SrfForecastData(hourly=data["hourly"], daily=data["daily"])

    @classmethod
    def create_from_api(cls, forecast_week: api.ForecastPointWeek) -> "SrfForecastData":
        # TODO: determine uv index for hourly
        hourly = [
            forecast_from_hourly(forecast, uv_index=None)
            for forecast in forecast_week["hours"]
        ]
        hourly.extend(
            forecast_from_hourly(forecast, uv_index=None)
            for forecast in forecast_week["three_hours"]
        )
        daily = [forecast_from_daily(forecast) for forecast in forecast_week["days"]]
        return SrfForecastData(hourly=hourly, daily=daily)

    def get_forecast(self, ts: datetime) -> Forecast | None:
        for forecast in self.hourly:
            ends_at = datetime.fromisoformat(forecast["datetime"])
            if ts < ends_at:
                return forecast
        return None


def forecast_from_hourly(
    forecast: api.OneHourForecastInterval, *, uv_index: float | None
) -> Forecast:
    return Forecast(
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
    )


def forecast_from_daily(forecast: api.DayForecastInterval) -> Forecast:
    return Forecast(
        condition=condition_from_forecast(forecast),
        datetime=forecast["date_time"],
        humidity=None,
        precipitation_probability=forecast["PROBPCP_PERCENT"],
        cloud_coverage=None,
        native_precipitation=forecast["RRR_MM"],
        native_pressure=None,
        native_temperature=None,
        native_templow=forecast["TN_C"],
        native_apparent_temperature=None,
        wind_bearing=forecast["DD_DEG"],
        native_wind_gust_speed=forecast["FX_KMH"],
        native_wind_speed=forecast["FF_KMH"],
        native_dew_point=None,
        uv_index=forecast.get("UVI"),
        is_daytime=None,
    )


def condition_from_forecast(forecast: api.ForecastABC) -> str:
    return "cloudy"  # TODO
