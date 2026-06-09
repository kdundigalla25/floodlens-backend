import os
import uuid
from pathlib import Path
import base64

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, File, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from detect_reference import make_predictions
from pull_streetview_image import pull_image_from_address

load_dotenv()

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

if not GOOGLE_MAPS_API_KEY:
    raise ValueError("GOOGLE_MAPS_API_KEY is not set in the environment variables.")

app = FastAPI()

origins = [
    "http://localhost:5173",
    "http://0.0.0.0:8000",
    "http://127.0.0.1:8000",
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