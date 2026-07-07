"""Sample rows from joined.csv, pull a Street View image for each `siteadd`,
save images to datasets/nc-houses, and move the used rows into a separate file.

Flow per run:
  1. Randomly sample SAMPLE_SIZE rows from INPUT_FILE.
  2. For each row, confirm Street View imagery exists (free metadata check),
     then download the static image into IMAGE_DIR.
  3. Rows whose image downloaded successfully are:
       - appended to USED_FILE (with an `image_file` column), and
       - removed from INPUT_FILE.
     Rows that fail (no imagery / network error) are left in INPUT_FILE so a
     later run can retry them.

Downloads run concurrently (I/O-bound), mirroring datacollection.py.
"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# --- Config ---
INPUT_FILE = "joined.csv"
USED_FILE = "used_rows.csv"
IMAGE_DIR = os.path.join("datasets", "nc-houses")
ADDRESS_COLUMN = "siteadd"
SAMPLE_SIZE = 30_000
IMAGE_SIZE = "640x640"      # max free size is 640x640
IMAGE_FOV = 80              # field of view; lower = more zoomed in
MAX_WORKERS = 16

STREETVIEW_METADATA_URL = "https://maps.googleapis.com/maps/api/streetview/metadata"
STREETVIEW_IMAGE_URL = "https://maps.googleapis.com/maps/api/streetview"

# Thread-local HTTP session for per-thread connection pooling.
_thread_local = threading.local()


def get_session() -> requests.Session:
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        _thread_local.session = session
    return session


def fetch_image(address: str, dest_path: str) -> bool:
    """Confirm imagery exists, then download it to dest_path. Returns success."""
    if not address or not address.strip():
        return False

    address = address.strip()
    session = get_session()

    # 1) Free metadata check first: avoids downloading (and being billed for)
    #    the generic "no imagery available" gray placeholder image.
    try:
        meta = session.get(
            STREETVIEW_METADATA_URL,
            params={
                "location": address,
                "key": GOOGLE_MAPS_API_KEY,
                "radius": 50,
                "source": "outdoor",
            },
            timeout=15,
        )
        meta.raise_for_status()
        data = meta.json()
        if data.get("status") != "OK" or not data.get("pano_id"):
            return False
    except requests.RequestException as e:
        print(f"Metadata failed for '{address}': {e}")
        return False

    # 2) Download the actual static image.
    try:
        img = session.get(
            STREETVIEW_IMAGE_URL,
            params={
                "location": address,
                "size": IMAGE_SIZE,
                "fov": IMAGE_FOV,
                "key": GOOGLE_MAPS_API_KEY,
                "source": "outdoor",
            },
            timeout=30,
        )
        img.raise_for_status()
        if "image" not in img.headers.get("Content-Type", ""):
            print(f"Non-image response for '{address}'")
            return False
        with open(dest_path, "wb") as f:
            f.write(img.content)
        return True
    except requests.RequestException as e:
        print(f"Image download failed for '{address}': {e}")
        return False


def image_filename(idx, row) -> str:
    """Stable, collision-free filename. Prefixing with the row index guarantees
    uniqueness even if objectid is missing or duplicated."""
    oid = str(row.get("objectid", "")).strip()
    oid = "".join(c for c in oid if c.isalnum())
    return f"{idx}_{oid}.jpg" if oid else f"{idx}.jpg"


def main():
    if not GOOGLE_MAPS_API_KEY:
        raise SystemExit("GOOGLE_MAPS_API_KEY is not set (check your .env).")
    if not os.path.exists(INPUT_FILE):
        raise SystemExit(f"Input file '{INPUT_FILE}' not found.")

    os.makedirs(IMAGE_DIR, exist_ok=True)

    df = pd.read_csv(INPUT_FILE, dtype=str)
    if ADDRESS_COLUMN not in df.columns:
        raise SystemExit(
            f"Column '{ADDRESS_COLUMN}' not found in {INPUT_FILE}. "
            f"Available columns: {list(df.columns)}"
        )

    n = min(SAMPLE_SIZE, len(df))
    if n == 0:
        raise SystemExit(f"{INPUT_FILE} has no rows to process.")
    sample = df.sample(n=n)
    print(f"Sampled {n:,} of {len(df):,} rows from {INPUT_FILE}.")

    used_indices = []
    image_files = {}

    def worker(idx, row):
        fname = image_filename(idx, row)
        ok = fetch_image(row[ADDRESS_COLUMN], os.path.join(IMAGE_DIR, fname))
        return idx, (fname if ok else None)

    done = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(worker, idx, row) for idx, row in sample.iterrows()]
        for future in as_completed(futures):
            idx, fname = future.result()
            done += 1
            if fname is not None:
                used_indices.append(idx)
                image_files[idx] = fname
            if done % 500 == 0:
                print(f"  {done:,}/{n:,} processed, {len(used_indices):,} images saved")

    print(f"\nDownloaded {len(used_indices):,} images to {IMAGE_DIR}/.")

    if not used_indices:
        print("No images downloaded; leaving input file unchanged.")
        return

    # Move successfully-used rows into USED_FILE (append across runs).
    used_df = df.loc[used_indices].copy()
    used_df["image_file"] = [image_files[i] for i in used_indices]
    used_df.to_csv(
        USED_FILE,
        mode="a",
        index=False,
        header=not os.path.exists(USED_FILE),
    )
    print(f"Recorded {len(used_df):,} used rows in {USED_FILE}.")

    # Rewrite the input file without the used rows (atomic via temp + replace).
    remaining = df.drop(index=used_indices)
    tmp_path = INPUT_FILE + ".tmp"
    remaining.to_csv(tmp_path, index=False)
    os.replace(tmp_path, INPUT_FILE)
    print(f"Removed used rows from {INPUT_FILE}; {len(remaining):,} rows remain.")


if __name__ == "__main__":
    main()
