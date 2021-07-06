# SRG SSR Weather

Integration to get weather forecasts from SRF Meteo using the SRG SSR Weather API.

## Configuration

Head over to `Configuration > Integrations` to set the integration up.
Press the plus button and search for "SRG SSR Weather".

The first step will ask you for API credentials, refer to the next section for
instructions on how to get them.

### How to get the API Credentials

Go to <https://developer.srgssr.ch> and create a new account (or login with your existing one).

Open [My Apps](https://developer.srgssr.ch/user/me/apps) and press "ADD A NEW APP".

Give the app a name like "Home Assistant" (the name is irrelevant).
Make sure that the Product is set to a SRF-MeteoProduct, e.g. "SRF-MeteoProductFreemium".
All other options may be left at their default value.

Open the "Info" tab of the app you just created and find both keys in the "Keys" column.
