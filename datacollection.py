import csv
import os
import json
import requests

import json
import requests
from dotenv import load_dotenv

load_dotenv()


GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

STREETVIEW_METADATA_URL = "https://maps.googleapis.com/maps/api/streetview/metadata"

def has_streetview_pano(address: str) -> bool:
    if not address or not address.strip():
        return False

    params = {
        "location": address.strip(),
        "key": GOOGLE_MAPS_API_KEY,
        "radius": 50,
        "source": "outdoor",
    }

    try:
        response = requests.get(
            STREETVIEW_METADATA_URL,
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        return data.get("status") == "OK" and bool(data.get("pano_id"))

    except requests.RequestException as e:
        print(f"Request failed for address: {address} | {e}")
        return False

def main():
    input_file = "NC_Master_Address_Dataset_-_2014.csv"
    output_file = "accumulated_data.csv"

    url = "https://services.nconemap.gov/secure/rest/services/NC1Map_Parcels/MapServer/1/query"

    output_fields = [
        "objectid",
        "zipcode",
        "state",
        "ddlat",
        "ddlon",
        "full_addre",
        "parno",
        "scity",
        "siteadd",
    ]

    with open(input_file, mode="r", encoding="utf-8", newline="") as infile, \
         open(output_file, mode="a", encoding="utf-8", newline="") as outfile:

        reader = csv.DictReader(infile)
        
        writer = csv.DictWriter(outfile, fieldnames=output_fields)

        for row in reader:
            lat_raw = row["ddlat"].strip()
            lon_raw = row["ddlon"].strip()

            if not lat_raw or not lon_raw:
                continue

            try:
                lat = float(lat_raw[:len(lat_raw) - 1])
                lon = -1 * float(lon_raw[:len(lon_raw) - 1])
            except ValueError:
                continue

            # Sanity check for North Carolina coordinates
            if not (33 <= lat <= 37 and -85 <= lon <= -75):
                print("Bad-looking coordinate:", row.get("full_addre", ""), lat, lon)
                continue

            point_geometry = {
                "x": lon,
                "y": lat,
                "spatialReference": {
                    "wkid": 4326
                }
            }

            params = {
                "where": "1=1",
                "geometry": json.dumps(point_geometry),
                "geometryType": "esriGeometryPoint",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "parno,scity,siteadd,cntyname",
                "returnGeometry": "false",
                "f": "json",

            }

            try:
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as e:
                print("Request failed:", row.get("full_addre", ""), e)
                continue

            if "error" in data:
                print("ArcGIS error:", data["error"])
                continue

            features = data.get("features", [])

            if not features:
                print("No parcel found:", row.get("full_addre", ""), lat, lon)
                continue

            attrs = features[0]["attributes"]
            att = attrs["siteadd"].split()
            if len(att) == 0:
                continue
            
            if attrs["siteadd"].split()[0] != row["full_addre"].split()[0]:
                continue
            
            if has_streetview_pano(attrs["siteadd"]):
                writer.writerow({
                    "objectid": row.get("objectid", ""),
                    "zipcode": row.get("zipcode", ""),
                    "state": row.get("state", ""),
                    "ddlat": lat,
                    "ddlon": lon,
                    "full_addre": row.get("full_addre", ""),
                    "parno": attrs.get("parno", ""),
                    "scity": attrs.get("scity", ""),
                    "siteadd": attrs.get("siteadd", ""),
                })
            else:
                continue

            print("Matched:", row.get("full_addre", ""), "->", attrs.get("siteadd", ""))

if __name__ == "__main__":
    main()
