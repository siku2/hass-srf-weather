# Home Assistant SRG SSR Weather integration

Brings [SRF Meteo](https://www.srf.ch/meteo) weather forecasts to your Home Assistant.

Note that the SRG SSR APIs require a developer account.
Follow the installation instructions shown in HACS or read the [info](info.md) file directly. 

## Installation with HACS

1. Go to the HACS Settings and add the custom repository `siku2/hass-weather-srgssr` with category "Integration".
2. Open the "Integrations" tab and search for "SRG SSR Weather".
3. Follow the instructions there to install and setup the integration.

## Limitations

The SRG SSR Weather API doesn't report humidity and air pressure.