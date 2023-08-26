# SRF Weather Home Assistant Integration

[![GitHub Release](https://img.shields.io/github/release/siku2/hass-srf-weather.svg?style=for-the-badge)](https://github.com/siku2/hass-srf-weather/releases)
[![GitHub Activity](https://img.shields.io/github/commit-activity/y/siku2/hass-srf-weather.svg?style=for-the-badge)](https://github.com/siku2/hass-srf-weather/commits/main)
[![License](https://img.shields.io/github/license/siku2/hass-srf-weather.svg?style=for-the-badge)](LICENSE)

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://hacs.xyz/docs/faq/custom_repositories)

[![GitLocalize](https://gitlocalize.com/repo/$GIT_LOCALIZE_PROJECT/whole_project/badge.svg)](https://gitlocalize.com/repo/$GIT_LOCALIZE_PROJECT/whole_project?utm_source=badge)

_Brings [SRF Meteo](https://www.srf.ch/meteo) weather forecasts to your Home Assistant._

## Installation

1. Add this repository as a custom repository to HACS: [![Add Repository](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=siku2&repository=hass-srf-weather&category=integration)
2. Use HACS to install the integration.
3. Restart Home Assistant.
4. Set up the integration using the UI: [![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=srf_weather)

## Contributions are welcome

If you want to contribute to this please read the [Contribution guidelines](CONTRIBUTING.md)

### Providing translations for other languages

If you would like to use the integration in another language, you can help out by providing the necessary translations.

[Head over to **GitLocalize** to start translating.](https://gitlocalize.com/repo/$GIT_LOCALIZE_PROJECT)

If your desired language isn't available there, just open an issue to request it.

You can also just do the translations manually in [custom_components/srf_weather/translations/](./custom_components/srf_weather/translations/) and open a pull request with the changes.
