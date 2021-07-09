# Home Assistant SRF Weather integration

Brings [SRF Meteo](https://www.srf.ch/meteo) weather forecasts to your Home Assistant.

This integration uses the SRF Weather API provided by SRG SSR. The SRG SSR APIs
require an API key. You can create your personal API key by registering a
developer account. Follow the installation instructions shown in HACS or read
the [info](info.md) file directly.

## Installation with HACS

1. Go to the HACS Settings and add the custom repository `siku2/hass-weather-srgssr` with category "Integration".
2. Open the "Integrations" tab and search for "SRG SSR Weather".
3. Follow the instructions there to set the integration up.

## Limitations

- The SRG SSR Weather API doesn't report humidity and air pressure.
- The freemium tier is limited to 50 requests per day (including geo location requests) 
