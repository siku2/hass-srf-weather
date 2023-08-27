import dataclasses
import logging
import math
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import api, const

_LOGGER = logging.getLogger(__name__)

_MIN_DELAY = timedelta(minutes=15)


@dataclasses.dataclass(slots=True)
class Coordinator:
    """Client API Coordinator.

    A single coordinator exists per customer key / secret. Use `get_coordinator` to get it.

    The coordinator exists to handle rate limits and fairly spread available slots across multiple weather entites.
    """

    client: api.Client
    consumers: int

    def request_next_api_call(self) -> datetime:
        if self.consumers == 0:
            _LOGGER.warn(
                "untracked consumer is requesting an api call", stack_info=True
            )
            self.consumers = 1

        now = datetime.now(tz=timezone.utc)
        ratelimit = self.client.ratelimit
        if not ratelimit:
            return now + self.consumers * timedelta(hours=1)

        calls_per_consumer = ratelimit.available / self.consumers
        if calls_per_consumer <= 0:
            return ratelimit.reset_time

        duration_to_reset = ratelimit.reset_time - now
        delay = duration_to_reset / math.floor(calls_per_consumer)
        return now + max(delay, _MIN_DELAY)


def get_coordinator(hass: HomeAssistant, config_data: Mapping[str, Any]) -> Coordinator:
    consumer_key = config_data[const.CONF_CONSUMER_KEY]
    consumer_secret = config_data[const.CONF_CONSUMER_SECRET]

    key = hash((consumer_key, consumer_secret))

    try:
        return hass.data[const.DOMAIN][key]
    except LookupError:
        pass

    client = api.Client(
        async_get_clientsession(hass),
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
    )
    coordinator = hass.data.setdefault(const.DOMAIN, {})[key] = Coordinator(
        client, consumers=0
    )
    return coordinator
