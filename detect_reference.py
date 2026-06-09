from ultralytics import YOLO
import os
from dotenv import load_dotenv

load_dotenv()

MODEL_PATH = os.getenv("MODEL_PATH", "models/best.pt")
model = YOLO(MODEL_PATH)

def make_predictions(image_path: str) -> dict:
    results = model.predict(
        image_path,
        imgsz=640,
        conf=0.2,
        device=0,
        verbose=False,
    )

    if not results or results[0].boxes is None or len(results[0].boxes) == 0:
        return {
            "reference_type": None,
            "pixel_height": 0,
            "confidence": 0,
            "box": None,
        }

    best_front_door = None
    best_garage_door = None

    for box in results[0].boxes:
        class_id = int(box.cls[0])
        label = model.names[class_id]
        confidence = float(box.conf[0])

        if label not in ["front_door", "garage_door"]:
            continue

        x1, y1, x2, y2 = box.xyxy[0].tolist()

        detection = {
            "reference_type": label,
            "pixel_height": float(y2 - y1),
            "confidence": confidence,
            "box": {
                "x1": float(x1),
                "y1": float(y1),
                "x2": float(x2),
                "y2": float(y2),
            },
        }

        if label == "front_door":
            if best_front_door is None or confidence > best_front_door["confidence"]:
                best_front_door = detection

        elif label == "garage_door":
            if best_garage_door is None or confidence > best_garage_door["confidence"]:
                best_garage_door = detection

    best = best_garage_door or best_front_door

    if best is None:
        return {
            "reference_type": None,
            "pixel_height": 0,
            "confidence": 0,
            "box": None,
        }

    return best