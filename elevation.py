import requests
from fastapi import HTTPException

# USGS Elevation Point Query Service (EPQS)
# Docs: https://apps.nationalmap.gov/epqs/
EPQS_URL = "https://epqs.nationalmap.gov/v1/json"


def get_elevation(latitude: float, longitude: float) -> float:
    """Look up ground elevation (meters) at a lat/lng via USGS EPQS."""
    params = {
        "x": longitude,
        "y": latitude,
        "units": "Meters",
        "wkid": 4326,
        "includeDate": "false",
    }

    try:
        response = requests.get(EPQS_URL, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as error:
        raise HTTPException(
            status_code=502,
            detail=f"Elevation lookup failed: {error}",
        )
    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="Elevation service returned an invalid response.",
        )

    value = data.get("value")

    if value is None:
        raise HTTPException(
            status_code=404,
            detail="No elevation data available for these coordinates.",
        )

    try:
        return float(value)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=502,
            detail="Elevation service returned a non-numeric value.",
        )
