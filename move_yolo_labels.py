from pathlib import Path
import shutil

DATASET_DIR = Path("datasets/houston-doors-attempt-2")

ANNOTATIONS_DIR = DATASET_DIR / "labels"

TRAIN_IMAGES_DIR = DATASET_DIR / "train" / "images"
TRAIN_LABELS_DIR = DATASET_DIR / "train" / "labels"

VAL_IMAGES_DIR = DATASET_DIR / "val" / "images"
VAL_LABELS_DIR = DATASET_DIR / "val" / "labels"

TRAIN_LABELS_DIR.mkdir(parents=True, exist_ok=True)
VAL_LABELS_DIR.mkdir(parents=True, exist_ok=True)


def move_labels_for_split(images_dir: Path, labels_dir: Path):
    moved = 0
    missing = 0

    for image_path in images_dir.iterdir():
        if image_path.suffix.lower() not in [".jpg", ".jpeg", ".png"]:
            continue

        label_name = image_path.stem + ".txt"
        source_label = ANNOTATIONS_DIR / label_name
        dest_label = labels_dir / label_name

        if source_label.exists():
            shutil.copy2(source_label, dest_label)
            moved += 1
        else:
            # Create empty label file for negative examples / unlabeled images
            dest_label.touch(exist_ok=True)
            missing += 1

    return moved, missing


train_moved, train_missing = move_labels_for_split(TRAIN_IMAGES_DIR, TRAIN_LABELS_DIR)
val_moved, val_missing = move_labels_for_split(VAL_IMAGES_DIR, VAL_LABELS_DIR)

print("Done.")
print(f"Train labels copied: {train_moved}")
print(f"Train empty labels created: {train_missing}")
print(f"Val labels copied: {val_moved}")
print(f"Val empty labels created: {val_missing}")