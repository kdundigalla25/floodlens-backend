from pathlib import Path

import cv2
from ultralytics import YOLO


# -----------------------------
# CONFIG
# -----------------------------

MODEL_PATH = "runs/detect/train/weights/best.pt"

# Can be one image OR a folder of images
SOURCE_PATH = "images"

TARGET_DIR = Path("runs/top_predictions")

IMG_SIZE = 640
DEVICE = 0

# Very low so we can find weak detections too
CONF_THRESHOLD = 0.2

# Only look for these classes
TARGET_LABELS = {"front_door", "garage_door"}


# -----------------------------
# SETUP
# -----------------------------

TARGET_DIR.mkdir(parents=True, exist_ok=True)

model = YOLO(MODEL_PATH)

print("Model classes:")
print(model.names)


def get_image_paths(source_path: str):
    source = Path(source_path)

    if source.is_file():
        return [source]

    image_paths = []
    for ext in ["*.jpg", "*.jpeg", "*.png", "*.webp"]:
        image_paths.extend(source.glob(ext))

    return sorted(image_paths)


def get_best_detections(image_path: Path):
    results = model(
        str(image_path),
        imgsz=IMG_SIZE,
        conf=CONF_THRESHOLD,
        device=DEVICE,
        verbose=False,
    )

    best_front_door = None
    best_garage_door = None

    for result in results:
        if result.boxes is None:
            continue

        for box in result.boxes:
            class_id = int(box.cls[0])
            label = model.names[class_id]
            confidence = float(box.conf[0])

            if label not in TARGET_LABELS:
                continue

            x1, y1, x2, y2 = box.xyxy[0].tolist()

            det = {
                "label": label,
                "confidence": confidence,
                "box": [x1, y1, x2, y2],
            }

            if label == "front_door":
                if best_front_door is None or confidence > best_front_door["confidence"]:
                    best_front_door = det

            elif label == "garage_door":
                if best_garage_door is None or confidence > best_garage_door["confidence"]:
                    best_garage_door = det

    return {
        "front_door": best_front_door,
        "garage_door": best_garage_door,
    }


def draw_detections(image_path: Path, detections: dict, output_path: Path):
    image = cv2.imread(str(image_path))

    if image is None:
        print(f"Could not read image: {image_path}")
        return

    # Draw front door and garage door on the same image
    for key in ["front_door", "garage_door"]:
        det = detections.get(key)

        if det is None:
            continue

        x1, y1, x2, y2 = det["box"]
        label = det["label"]
        confidence = det["confidence"]

        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])

        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)

        text = f"{label} {confidence:.3f}"

        text_size, _ = cv2.getTextSize(
            text,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            2,
        )

        text_w, text_h = text_size

        label_y1 = max(0, y1 - text_h - 10)

        cv2.rectangle(
            image,
            (x1, label_y1),
            (x1 + text_w + 8, y1),
            (0, 255, 0),
            -1,
        )

        cv2.putText(
            image,
            text,
            (x1 + 4, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 0),
            2,
        )

    cv2.imwrite(str(output_path), image)


def main():
    image_paths = get_image_paths(SOURCE_PATH)

    if not image_paths:
        print(f"No images found in {SOURCE_PATH}")
        return

    print(f"Found {len(image_paths)} image(s).")

    for image_path in image_paths:
        best = get_best_detections(image_path)

        if best["front_door"] is None and best["garage_door"] is None:
            print(f"{image_path.name}: no front_door or garage_door detections")
            continue

        output_path = TARGET_DIR / image_path.name

        draw_detections(
            image_path=image_path,
            detections=best,
            output_path=output_path,
        )

        print(f"\n{image_path.name}")

        if best["front_door"] is not None:
            print(
                f"  front_door conf={best['front_door']['confidence']:.4f}"
            )

        if best["garage_door"] is not None:
            print(
                f"  garage_door conf={best['garage_door']['confidence']:.4f}"
            )

        print(f"  saved={output_path}")


if __name__ == "__main__":
    main()