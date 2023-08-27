from . import api


def get_geolocation_name_description(geolocation_name: api.GeolocationName) -> str:
    if geolocation_name.get("type") == "poi":
        return f"{geolocation_name['name']} ({geolocation_name['description_short']})"

    parts = (
        str(part)
        for part in (
            geolocation_name.get("plz"),
            geolocation_name.get("description_long"),
        )
        if part
    )
    return " ".join(parts)


def get_geolocation_description(geolocation: api.Geolocation) -> str:
    if geolocation_names := geolocation.get("geolocation_names"):
        for name in geolocation_names:
            if name.get("translation_type") == "orig":
                return get_geolocation_name_description(name)
    return f"{geolocation['default_name']} ({geolocation['station_id']})"
