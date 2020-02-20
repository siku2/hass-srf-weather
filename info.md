# SRG SSR Weather

Integration to get weather forecasts from SRF Meteo using the SRG SSR Weather API. 

## Configuration

You need to add the following to your `configuration.yaml`.
After adding these settings and restarting Home Assistant you can head over to `Configuration > Integrations` and setup the integration.
Press the plus button and search for "SRG SSR Weather".

```yaml
srgssr_weather:
  consumer_key: CONSUMER KEY
  consumer_secret: CONSUMER SECRET
```

### How to get these keys

Go to https://developer.srgssr.ch and create a new account (or login with your existing one).

Open [My Apps](https://developer.srgssr.ch/user/me/apps) and press "ADD A NEW APP".

Give the app a name like "Home Assistant" (the name is irrelevant).
Make sure that the Product is set to "SRG-SSR-PUBLIC-API-V2".
All other options may be left at their default value.

Open the "Info" tab of the app you just created and find both keys in the "Keys" column.
