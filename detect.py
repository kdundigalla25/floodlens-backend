import csv
import os
import random
import shutil
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

if not API_KEY:
    raise RuntimeError("Missing GOOGLE_MAPS_API_KEY in .env")

BASE_DIR = Path("datasets/houston-doors-attempt-2")

ALL_IMAGES_DIR = BASE_DIR / "all" / "images"

TRAIN_IMAGES_DIR = BASE_DIR / "train" / "images"
TRAIN_LABELS_DIR = BASE_DIR / "train" / "labels"

VAL_IMAGES_DIR = BASE_DIR / "val" / "images"
VAL_LABELS_DIR = BASE_DIR / "val" / "labels"

TEST_MODE = False

TEST_ADDRESSES = [
    "15774 CLARKE SPRINGS DR",
    "1018 DEWALT ST",
    "1858 LIBBEY DR",
]

CSV_PATH = "filtered_output.csv"
CSV_ADDRESS_COLUMN = "Full Address"

# Process this range of CSV rows.
# Since you already did the first 1000 rows, start at 1001.
CSV_START_ROW = 1002
CSV_END_ROW = 4000

REQUEST_DELAY_SECONDS = 0.15

IMAGE_SIZE = "640x640"
FOV = 60
PITCH = 0
RADIUS_METERS = 25

SKIP_DUPLICATE_PANOS = True

CREATE_SPLIT_AFTER_DOWNLOAD = True
VAL_RATIO = 0.2

RANDOM_SEED = 42

for folder in [
    ALL_IMAGES_DIR,
    TRAIN_IMAGES_DIR,
    TRAIN_LABELS_DIR,
    VAL_IMAGES_DIR,
    VAL_LABELS_DIR,
]:
    folder.mkdir(parents=True, exist_ok=True)

USED_PANO_IDS = set()
random.seed(RANDOM_SEED)


def normalize_houston_address(address: str) -> str:
    address = " ".join(address.strip().split())

    lower = address.lower()

    has_houston = "houston" in lower
    has_tx = (
        ", tx" in lower
        or " tx " in lower
        or lower.endswith(" tx")
        or ",tx" in lower
        or "texas" in lower
    )

    if has_houston and has_tx:
        return address

    if has_houston and not has_tx:
        return f"{address}, TX"

    return f"{address}, Houston, TX"


def safe_filename(index: int, address: str, suffix: str) -> str:
    cleaned = (
        address.lower()
        .replace(",", "")
        .replace(".", "")
        .replace("#", "")
        .replace("/", "-")
        .replace("\\", "-")
        .replace(" ", "_")
    )

    cleaned = "".join(
        ch for ch in cleaned
        if ch.isalnum() or ch in ["_", "-"]
    )

    return f"houston_{index:05d}_{cleaned[:70]}_{suffix}.jpg"


def get_streetview_metadata(location: str, radius_meters: int = RADIUS_METERS):
    url = "https://maps.googleapis.com/maps/api/streetview/metadata"

    params = {
        "location": location,
        "radius": radius_meters,
        "source": "outdoor",
        "key": API_KEY,
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    data = response.json()

    if data.get("status") != "OK":
        return None

    return data


def download_streetview_image(params: dict, output_path: Path):
    url = "https://maps.googleapis.com/maps/api/streetview"

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    output_path.write_bytes(response.content)


def build_candidate(address: str):
    return {
        "type": "auto_address",
        "params": {
            "size": IMAGE_SIZE,
            "location": address,
            "radius": RADIUS_METERS,
            "pitch": PITCH,
            "fov": FOV,
            "source": "outdoor",
            "key": API_KEY,
        },
    }


def process_address(index: int, raw_address: str):
    normalized_address = normalize_houston_address(raw_address)

    print(f"[{index}] Processing: {normalized_address}")

    metadata = get_streetview_metadata(
        location=normalized_address,
        radius_meters=RADIUS_METERS,
    )

    if not metadata:
        print("  Skipping: no Street View metadata found")
        return []

    pano_id = metadata.get("pano_id")
    pano_location = metadata.get("location", {})

    if not pano_id or "lat" not in pano_location or "lng" not in pano_location:
        print("  Skipping: metadata missing pano_id/location")
        return []

    if SKIP_DUPLICATE_PANOS and pano_id in USED_PANO_IDS:
        print(f"  Skipping: duplicate pano {pano_id}")
        return []

    USED_PANO_IDS.add(pano_id)

    candidate = build_candidate(normalized_address)

    saved_paths = []

    filename = safe_filename(index, normalized_address, candidate["type"])
    output_path = ALL_IMAGES_DIR / filename

    if output_path.exists():
        print(f"  Already exists, skipping image request: {output_path.name}")
        saved_paths.append(output_path)
        return saved_paths

    try:
        download_streetview_image(
            params=candidate["params"],
            output_path=output_path,
        )

        saved_paths.append(output_path)

        print(f"  Saved: {output_path.name}")

    except requests.HTTPError as error:
        print(f"  Failed candidate {candidate['type']}: {error}")
    except requests.RequestException as error:
        print(f"  Request error for {candidate['type']}: {error}")

    return saved_paths


def collect_from_addresses(addresses: list[str]):
    downloaded = []

    for index, address in enumerate(addresses, start=1):
        saved = process_address(index, address)
        downloaded.extend(saved)
        time.sleep(REQUEST_DELAY_SECONDS)

    return downloaded


def collect_from_csv(csv_path: str, start_row: int, end_row: int):
    downloaded = []

    with open(csv_path, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for csv_row_number, row in enumerate(reader, start=1):
            if csv_row_number < start_row:
                continue

            if csv_row_number > end_row:
                break

            raw_address = row.get(CSV_ADDRESS_COLUMN, "").strip()

            if not raw_address:
                print(f"[{csv_row_number}] Skipping empty address")
                continue

            saved = process_address(csv_row_number, raw_address)
            downloaded.extend(saved)

            time.sleep(REQUEST_DELAY_SECONDS)

    return downloaded


def clear_existing_split_folders():
    for folder in [
        TRAIN_IMAGES_DIR,
        TRAIN_LABELS_DIR,
        VAL_IMAGES_DIR,
        VAL_LABELS_DIR,
    ]:
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True, exist_ok=True)


def create_train_val_split(val_ratio: float = VAL_RATIO):
    images = list(ALL_IMAGES_DIR.glob("*.jpg"))

    if not images:
        print("No images found for train/val split.")
        return

    clear_existing_split_folders()

    random.shuffle(images)

    split_index = int(len(images) * (1 - val_ratio))

    train_images = images[:split_index]
    val_images = images[split_index:]

    def copy_image_and_empty_label(
        image_path: Path,
        images_dir: Path,
        labels_dir: Path,
    ):
        dest_image_path = images_dir / image_path.name
        shutil.copy2(image_path, dest_image_path)

        label_path = labels_dir / f"{image_path.stem}.txt"
        label_path.touch(exist_ok=True)

    for image in train_images:
        copy_image_and_empty_label(
            image,
            TRAIN_IMAGES_DIR,
            TRAIN_LABELS_DIR,
        )

    for image in val_images:
        copy_image_and_empty_label(
            image,
            VAL_IMAGES_DIR,
            VAL_LABELS_DIR,
        )

    print(f"Train images: {len(train_images)}")
    print(f"Val images: {len(val_images)}")


def write_data_yaml():
    yaml_path = BASE_DIR / "data.yaml"

    yaml_content = f"""path: {BASE_DIR.resolve().as_posix()}

train: train/images
val: val/images

names:
  0: front_door
"""

    yaml_path.write_text(yaml_content, encoding="utf-8")

    print(f"Wrote {yaml_path}")


def main():
    print("===================================")
    print("GSV Houston Door Image Collector")
    print("===================================")
    print(f"BASE_DIR: {BASE_DIR}")
    print(f"TEST_MODE: {TEST_MODE}")
    print(f"FOV: {FOV}")
    print(f"PITCH: {PITCH}")
    print(f"RADIUS_METERS: {RADIUS_METERS}")
    print("===================================")

    # if TEST_MODE:
    #     print("Running test address collection.")

    #     downloaded = collect_from_addresses(TEST_ADDRESSES)

    # else:
    #     print("Running CSV collection.")
    #     print(f"CSV_PATH: {CSV_PATH}")
    #     print(f"CSV_ADDRESS_COLUMN: {CSV_ADDRESS_COLUMN}")
    #     print(f"CSV_START_ROW: {CSV_START_ROW}")
    #     print(f"CSV_END_ROW: {CSV_END_ROW}")

    #     downloaded = collect_from_csv(
    #         csv_path=CSV_PATH,
    #         start_row=CSV_START_ROW,
    #         end_row=CSV_END_ROW,
    #     )

    #     print(f"Downloaded/saved {len(downloaded)} images.")

    if CREATE_SPLIT_AFTER_DOWNLOAD:
        create_train_val_split(val_ratio=VAL_RATIO)
        write_data_yaml()


if __name__ == "__main__":
    main()