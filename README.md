# Home Assistant SRF Weather integration

Brings [SRF Meteo](https://www.srf.ch/meteo) weather forecasts to your Home Assistant.

This integration uses the SRF Weather API provided by SRG SSR. The SRG SSR APIs
require an API key. You can create your personal API key by registering a
developer account. Follow the installation instructions shown in HACS or read
the [info](info.md) file directly.

Note: With version 2.0 this integration makes use of the new "SRF Weather" API.
For this reason the integration has been renamed. If you have been using
previous version of this integration, you need to remove the integration and
readd the "SRF Weather" integration.

## Installation with HACS

1. Go to the HACS Settings and add the custom repository `siku2/hass-srf-weather` with category "Integration".
2. Open the "Integrations" tab and search for "SRG SSR Weather".
3. Follow the instructions there to set the integration up.

## Limitations

- The SRG SSR Weather API now reports humidity and air pressur for 1h and 3h forecasts
- The freemium tier is limited to 50 requests per day (including geo location requests) 
