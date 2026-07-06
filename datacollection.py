import csv
import os
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from dotenv import load_dotenv

load_dotenv()


GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

STREETVIEW_METADATA_URL = "https://maps.googleapis.com/maps/api/streetview/metadata"
PARCEL_URL = "https://services.nconemap.gov/secure/rest/services/NC1Map_Parcels/MapServer/1/query"

# Number of concurrent worker threads. Tune based on API rate limits.
MAX_WORKERS = 16

# Thread-local storage so each worker thread reuses its own HTTP connection pool.
_thread_local = threading.local()


def get_session() -> requests.Session:
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        _thread_local.session = session
    return session


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
        response = get_session().get(
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


def process_row(row: dict) -> dict | None:
    """Process a single input row. Returns the output dict to write, or None to skip.

    Runs inside a worker thread and performs the two network calls (parcel
    lookup + street view check) that dominate the runtime.
    """
    lat_raw = row["ddlat"].strip()
    lon_raw = row["ddlon"].strip()

    if not lat_raw or not lon_raw:
        return None

    try:
        lat = float(lat_raw[:len(lat_raw) - 1])
        lon = -1 * float(lon_raw[:len(lon_raw) - 1])
    except ValueError:
        return None

    # Sanity check for North Carolina coordinates
    if not (33 <= lat <= 37 and -85 <= lon <= -75):
        print("Bad-looking coordinate:", row.get("full_addre", ""), lat, lon)
        return None

    point_geometry = {
        "x": lon,
        "y": lat,
        "spatialReference": {"wkid": 4326},
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
        response = get_session().get(PARCEL_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print("Request failed:", row.get("full_addre", ""), e)
        return None

    if "error" in data:
        print("ArcGIS error:", data["error"])
        return None

    features = data.get("features", [])
    if not features:
        print("No parcel found:", row.get("full_addre", ""), lat, lon)
        return None

    attrs = features[0]["attributes"]
    att = attrs["siteadd"].split()
    if len(att) == 0:
        return None

    if attrs["siteadd"].split()[0] != row["full_addre"].split()[0]:
        return None

    if not has_streetview_pano(attrs["siteadd"]):
        return None

    print("Matched:", row.get("full_addre", ""), "->", attrs.get("siteadd", ""))

    return {
        "objectid": row.get("objectid", ""),
        "zipcode": row.get("zipcode", ""),
        "state": row.get("state", ""),
        "ddlat": lat,
        "ddlon": lon,
        "full_addre": row.get("full_addre", ""),
        "parno": attrs.get("parno", ""),
        "scity": attrs.get("scity", ""),
        "siteadd": attrs.get("siteadd", ""),
    }

def main():
    input_file = "NC_Master_Address_Dataset_-_2014.csv"
    output_file = "accumulated_data.csv"

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

    written = 0

    with open(input_file, mode="r", encoding="utf-8", newline="") as infile, \
         open(output_file, mode="a", encoding="utf-8", newline="") as outfile:

        reader = csv.DictReader(infile)
        writer = csv.DictWriter(outfile, fieldnames=output_fields)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit rows in bounded batches so the whole input file is never
            # held in memory at once. Results are written by this (main) thread,
            # keeping the non-thread-safe csv.writer single-threaded.
            batch_size = MAX_WORKERS * 8
            batch = []

            def flush(rows):
                nonlocal written
                futures = [executor.submit(process_row, r) for r in rows]
                for future in as_completed(futures):
                    result = future.result()
                    if result is not None:
                        writer.writerow(result)
                        written += 1
                outfile.flush()

            for row in reader:
                batch.append(row)
                if len(batch) >= batch_size:
                    flush(batch)
                    batch = []

            if batch:
                flush(batch)

    print(f"Done. Wrote {written} matched rows to {output_file}.")


if __name__ == "__main__":
    main()
