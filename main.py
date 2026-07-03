import os
import uuid
from pathlib import Path
import base64
import io

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, File, Form, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps
from detect_reference import make_predictions
from pull_streetview_image import pull_image_from_address
from elevation import get_elevation

DETECTION_SIZE = 640
d
load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

if not GOOGLE_MAPS_API_KEY:
    raise ValueError("GOOGLE_MAPS_API_KEY is not set in the environment variables.")

app = FastAPI()

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:8000",
    "https://floodlevel.netlify.app",

]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

IMAGE_DIR = Path("images")
IMAGE_DIR.mkdir(exist_ok=True)

@app.get("/")
def health_check():
    return {"status": "ok"}

@app.get("/gsv_prediction")
def predict_door_from_gsv(address: str):
    image_dir = Path("imageStorage")
    image_dir.mkdir(exist_ok=True)

    output_path = image_dir / f"{uuid.uuid4()}.jpg"

    try:
        altitude = pull_image_from_address(address, output_path)

        if not output_path.exists():
            raise HTTPException(
                status_code=404,
                detail="No Street View image found for this address.",
            )

        prediction = make_predictions(str(output_path))

        with open(output_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")

        return {
            **prediction,
            "image_base64": image_base64,
            "media_type": "image/jpeg",
            "altitude": altitude
        }

    finally:
        if output_path.exists():
            os.remove(output_path)


def _scale_box(prediction: dict, orig_width: int, orig_height: int) -> dict:
    """Scale a box detected in DETECTION_SIZE x DETECTION_SIZE space back to the
    original uploaded image's pixel space."""
    box = prediction.get("box")

    if box is None:
        return prediction

    scale_x = orig_width / DETECTION_SIZE
    scale_y = orig_height / DETECTION_SIZE

    x1 = box["x1"] * scale_x
    y1 = box["y1"] * scale_y
    x2 = box["x2"] * scale_x
    y2 = box["y2"] * scale_y

    return {
        **prediction,
        "box": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
        "pixel_height": y2 - y1,
    }


@app.post("/coords_prediction")
async def predict_door_from_coords(
    file: UploadFile = File(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
):
    contents = await file.read()

    try:
        image = Image.open(io.BytesIO(contents))
        # Phone photos carry an EXIF orientation flag that browsers auto-apply but
        # PIL does not. Bake it into the pixels so our dimensions and box coords match
        # the orientation the frontend reads client-side.
        image = ImageOps.exif_transpose(image).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.")

    orig_width, orig_height = image.size

    # Standardize to DETECTION_SIZE x DETECTION_SIZE for detection (consistent with GSV),
    # then scale the resulting box back to the original upload's resolution.
    resized = image.resize((DETECTION_SIZE, DETECTION_SIZE))

    image_dir = Path("imageStorage")
    image_dir.mkdir(exist_ok=True)
    output_path = image_dir / f"{uuid.uuid4()}.jpg"

    try:
        resized.save(output_path, format="JPEG")

        prediction = make_predictions(str(output_path))
        prediction = _scale_box(prediction, orig_width, orig_height)

        altitude = get_elevation(latitude, longitude)

        return {
            **prediction,
            "altitude": altitude,
        }

    finally:
        if output_path.exists():
            os.remove(output_path)


@app.post("/detect_reference")
async def detect_reference(file: UploadFile = File(...)):
    contents = await file.read()
    filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = Path("imageStorage") / filename
    with open(file_path, "wb") as f:
        f.write(contents)
        
    try:
        prediction = make_predictions(str(file_path))
        return prediction
    finally:
        os.remove(file_path)