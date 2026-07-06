import csv
import os
import time
import shutil
from pathlib import Path
from dotenv import load_dotenv

import requests

load_dotenv()


INPUT_CSV = "accumulated_data.csv"
ADDRESS_FIELD = "full_addre"

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


def filter_csv_by_streetview(input_csv: str) -> None:
    if not GOOGLE_MAPS_API_KEY:
        raise RuntimeError("Missing GOOGLE_MAPS_API_KEY environment variable.")

    input_path = Path(input_csv)
    temp_path = input_path.with_suffix(".filtered.tmp.csv")
    backup_path = input_path.with_suffix(".backup.csv")

    kept_count = 0
    removed_count = 0
    checked_count = 0

    with input_path.open("r", encoding="utf-8", newline="") as infile, temp_path.open(
        "w", encoding="utf-8", newline=""
    ) as outfile:
        reader = csv.DictReader(infile)

        if not reader.fieldnames:
            raise RuntimeError("CSV file has no header row.")

        if ADDRESS_FIELD not in reader.fieldnames:
            raise RuntimeError(f"CSV is missing required field: {ADDRESS_FIELD}")

        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
        writer.writeheader()

        for row in reader:
            checked_count += 1
            address = row.get(ADDRESS_FIELD, "")

            if has_streetview_pano(address):
                writer.writerow(row)
                kept_count += 1
                print(f"{checked_count} KEEP: {address}")
            else:
                removed_count += 1
                print(f"{checked_count} REMOVE: {address}")

            # Small delay to avoid hammering the API too aggressively
            time.sleep(0.05)

    shutil.copy2(input_path, backup_path)
    shutil.move(temp_path, input_path)

    print()
    print("Done.")
    print(f"Checked: {checked_count}")
    print(f"Kept: {kept_count}")
    print(f"Removed: {removed_count}")
    print(f"Backup saved to: {backup_path}")


if __name__ == "__main__":
    filter_csv_by_streetview(INPUT_CSV)