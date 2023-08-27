import dataclasses
import logging
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Required, TypedDict

import aiohttp
from yarl import URL

_LOGGER = logging.getLogger(__name__)


class Color(TypedDict, total=False):
    temperature: Required[int]
    background_color: Required[str]
    text_color: Required[str]


class ForecastABC(TypedDict, total=False):
    date_time: Required[str]
    symbol_code: Required[int]
    symbol24_code: Required[int]
    PROBPCP_PERCENT: Required[int]
    """probability of rain in %"""
    RRR_MM: Required[float]
    """total rainfall in mm"""
    FF_KMH: Required[int]
    """avg. wind speed in km/h"""
    FX_KMH: Required[int]
    """gust speed in km/h"""
    DD_DEG: Required[int]
    """direction of wind, -1 means: turning winds"""


class DayForecastInterval(ForecastABC, total=False):
    SUNSET: Required[str | None]
    """datetime of sunset, null if no sunset on that point/day"""
    SUNRISE: Required[str | None]
    """datetime of sunrise, null if no sunrise on that point/day"""
    SUN_H: Required[int]
    """hours of sunshine"""
    TX_C: Required[int]
    """expected max temperature in celsius"""
    TN_C: Required[int]
    """expected min temperature in celsius"""
    min_color: Required[Color]
    max_color: Required[Color]

    UVI: int
    """UV index"""


class OneHourForecastInterval(ForecastABC, total=False):
    TTT_C: Required[int]
    """expected temperature in celsius"""
    TTL_C: float
    """lower bound of expected temperature range in celsius"""
    TTH_C: float
    """upper bound of expected temperature range in celsius"""
    DEWPOINT_C: float
    """Dewpoint"""
    RELHUM_PERCENT: int
    """Relative air humidity"""
    FRESHSNOW_CM: int
    """Fresh snow in the hour before event"""
    PRESSURE_HPA: int
    """Barometric pressure"""
    SUN_MIN: Required[int]
    """Sunshine duration in the hour before event"""
    IRRADIANCE_WM2: int
    """Global irradiance"""
    TTTFEEL_C: int
    """felt temperature"""
    cur_color: Required[Color]


class ThreeHourForecastInterval(OneHourForecastInterval):
    ...


class PoiType(TypedDict, total=False):
    id: Required[int]
    name: Required[str]


class GeolocationName(TypedDict, total=False):
    description_short: Required[str]
    description_long: Required[str]
    id: Required[str]
    geolocation: "Geolocation"
    location_id: Required[str]
    type: Literal["city"] | Literal["poi"] | Required[str]
    poi_type: PoiType
    language: Required[int]
    translation_type: Literal["orig"] | Literal["trans"] | str
    name: Required[str]
    country: str
    province: str
    inhabitants: int
    height: int
    plz: int
    ch: Required[int]


class Geolocation(TypedDict, total=False):
    id: Required[str]
    lat: Required[float]
    lon: Required[float]
    station_id: Required[str]
    timezone: Required[str]
    default_name: Required[str]

    alarm_region_id: str
    alarm_region_name: str
    district: str
    geolocation_names: list[GeolocationName]


class ForecastPointWeek(TypedDict, total=False):
    days: Required[list[DayForecastInterval]]
    three_hours: Required[list[ThreeHourForecastInterval]]
    hours: Required[list[OneHourForecastInterval]]
    geolocation: Required[Geolocation]


class GeolocationNamesSearch(TypedDict, total=False):
    district: Required[str]
    id: Required[int]
    geolocation: Required[Geolocation]
    location_id: Required[int]
    type: Required[str]
    default_name: str
    language: Required[str]
    translation_type: Required[str]
    name: Required[str]
    country: Required[str]
    province: Required[str]
    inhabitants: Required[str]
    height: Required[int]
    ch: Required[str]


class AccessToken(TypedDict, total=True):
    access_token: str
    expires_in: int
    token_type: Literal["Bearer"] | str


@dataclasses.dataclass(slots=True, kw_only=True)
class Ratelimit:
    allowed: int
    available: int
    reset_time: datetime

    @classmethod
    def from_response_headers(cls, headers: Mapping[str, Any]) -> "Ratelimit":
        try:
            allowed = int(headers["x-ratelimit-allowed"])
        except Exception:
            allowed = 0
        try:
            available = int(headers["x-ratelimit-available"])
        except Exception:
            available = 0
        try:
            reset_time_ms = int(headers["x-ratelimit-reset-time"])
        except Exception:
            reset_time_ms = 0

        reset_time = datetime.fromtimestamp(reset_time_ms / 1000.0, tz=timezone.utc)
        return cls(allowed=allowed, available=available, reset_time=reset_time)


_DEFAULT_OAUTH_URL = URL("https://api.srgssr.ch/oauth/v1/accesstoken")


class OauthClient:
    def __init__(
        self, session: aiohttp.ClientSession, *, consumer_auth: aiohttp.BasicAuth
    ) -> None:
        self._session = session
        self._consumer_auth = consumer_auth
        self._url = _DEFAULT_OAUTH_URL

        self._auth_expire_at: datetime | None = None
        self._auth_header: str = ""

    async def _get_access_token(self) -> AccessToken:
        _LOGGER.debug("getting access token")
        async with self._session.post(
            self._url,
            params={"grant_type": "client_credentials"},
            auth=self._consumer_auth,
            headers={"Accept": "application/json"},
            raise_for_status=True,
        ) as resp:
            data = await resp.json(content_type=None)
            _LOGGER.debug("json response: %s", data)
            return data

    async def _ensure_authorization(self) -> Any:
        now = datetime.now(tz=timezone.utc)
        if self._auth_expire_at and now < self._auth_expire_at:
            # auth is still valid
            return

        access_token = await self._get_access_token()
        self._auth_expire_at = (
            now + timedelta(seconds=access_token["expires_in"]) - timedelta(seconds=10)
        )
        self._auth_header = (
            f"{access_token['token_type']} {access_token['access_token']}"
        )

    async def get_authorization_header(self) -> str:
        await self._ensure_authorization()
        return self._auth_header


_DEFAULT_API_BASE_URL = URL("https://api.srgssr.ch/srf-meteo/v2")


class Client:
    def __init__(
        self, session: aiohttp.ClientSession, *, consumer_key: str, consumer_secret: str
    ) -> None:
        self._session = session
        self._base_url = _DEFAULT_API_BASE_URL

        self._oauth = OauthClient(
            session, consumer_auth=aiohttp.BasicAuth(consumer_key, consumer_secret)
        )
        self._ratelimit: Ratelimit | None = None

    async def _request(
        self, method: Literal["GET"], path: str, *, params: dict[str, Any] | None = None
    ) -> Any:
        url = self._base_url / path
        kwargs = {}
        kwargs["headers"] = headers = {"Accept": "application/json"}
        if params:
            kwargs["params"] = params

        async def once() -> Any:
            headers["Authorization"] = await self._oauth.get_authorization_header()
            _LOGGER.debug(
                "performing %s request on %s with params %s", method, path, params
            )
            async with self._session.request(method, url, **kwargs) as resp:
                self._ratelimit = Ratelimit.from_response_headers(resp.headers)
                data = await resp.json(content_type=None)
                _LOGGER.debug("json response: %s", data)
                resp.raise_for_status()
                return data

        _LOGGER.debug("ratelimit: %s", self._ratelimit)
        return await once()

    @property
    def ratelimit(self) -> Ratelimit | None:
        return self._ratelimit

    async def attemp_auth(self) -> None:
        await self._oauth.get_authorization_header()

    async def get_forecast_week_by_geo_location(
        self, geolocation_id: str
    ) -> ForecastPointWeek:
        return await self._request("GET", f"forecastpoint/{geolocation_id}")

    async def get_geolocations(self, lat: str, lon: str) -> list[Geolocation]:
        return await self._request(
            "GET", "geolocations", params={"latitude": lat, "longitude": lon}
        )

    async def search_geolocation(
        self,
        *,
        name: str | None = None,
        zip: int | None = None,
        limit: int = 0,
    ) -> list[GeolocationNamesSearch]:
        assert (name is not None) != (
            zip is not None
        ), "either name or zip must be given"
        params = {}
        if name is not None:
            params["name"] = name
        if zip is not None:
            params["zip"] = zip
        if limit:
            params["limit"] = limit
        return await self._request("GET", "geolocationNames", params=params)
