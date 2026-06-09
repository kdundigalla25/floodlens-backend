import os
from pathlib import Path
import requests
from fastapi import HTTPException
from dotenv import load_dotenv
import streetlevel.streetview as sv

load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")


def get_streetview_metadata(address: str):
    if not GOOGLE_MAPS_API_KEY:
        raise HTTPException(status_code=500, detail="Google Maps API key is not configured")
    
    url = "https://maps.googleapis.com/maps/api/streetview/metadata"

    params = {
        "location": address,
        "key": GOOGLE_MAPS_API_KEY,
        "radius": 50,
        "source": "outdoor",
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    data = response.json()

    status = data.get("status")

    if status != "OK":
        raise HTTPException(status_code=404, detail={"message": "No Street View image found for this address", "status": status, "data" : data})
    
    return data

def get_streetview_image(params: dict, output_path: Path):
    url = "https://maps.googleapis.com/maps/api/streetview"

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    output_path.write_bytes(response.content)

def pull_image_from_address(address: str, output_path: Path):
    metadata = get_streetview_metadata(address)

    pano = sv.find_panorama_by_id(metadata["pano_id"], download_depth=True)
    altitude = pano.elevation

    if not metadata:
        raise HTTPException(status_code=404, detail="No Street View image found for this address")
    
    params = {
        "location": address,
        "size": "640x640",
        "pitch": 0,
        "fov": 60,
        "key": GOOGLE_MAPS_API_KEY,
        "source": "outdoor",
    }

    get_streetview_image(params, output_path)
    return altitude