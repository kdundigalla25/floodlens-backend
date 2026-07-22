# FloodLens Backend

FastAPI backend for FloodLens, a flood visualization app that estimates and displays potential flood water levels on home images.

## Overview

This backend supports the FloodLens frontend by handling image-based and address-based flood preview workflows. It can retrieve Google Street View imagery from an address, run reference-object detection on home images, calculate image scale, and return the data needed to render a flood waterline preview.

## Features

- FastAPI backend API
- Google Street View image lookup from address
- Street View metadata retrieval
- Uploaded image processing
- Door / garage reference detection
- Camera / FFE calculation support
- Flood waterline calculation support
- Address-based and image-upload fallback flows
- JSON responses for frontend visualization

## Tech Stack

- Python
- FastAPI
- Uvicorn
- Requests
- Google Street View Static API
- Computer vision model integration
- Pillow / image processing utilities
- Environment variables for API keys

## Main Flow

```txt
Address flow:
User enters address
→ Backend checks Google Street View
→ Retrieves usable image if available
→ Runs reference detection
→ Calculates flood preview data
→ Returns result to frontend

Upload fallback flow:
User uploads image
→ Backend runs reference detection
→ Frontend/user provides ground line
→ Backend/frontend calculates flood waterline
→ Result is displayed on image

---

## Research pipeline

Beyond the API, this repo contains the statewide FFE validation study —
estimating First-Floor Elevation from Street View imagery and validating it
against NC OneMap across all 100 North Carolina counties.

- **[docs/FINDINGS.md](docs/FINDINGS.md)** — results, conclusions, limitations
- **[docs/PIPELINE.md](docs/PIPELINE.md)** — how to run each stage, design rules

**Headline:** 3,833 buildings statewide, **MAE 2.31 ft**, bias −0.17 ft.
Error grows ~4× from coast to mountains, driven independently by terrain slope
and inland location.

### Layout

| path | contents |
|---|---|
| `main.py` + `detect_reference.py`, `elevation.py`, `pull_streetview_image.py` | FastAPI backend (co-located by import) |
| `pipeline/` | data pipeline, stages 1–8 |
| `analysis/` | figures and detection QA |
| `training/` | YOLO training (local + SLURM) |
| `reference/` | HAZUS occupancy domain, coastline geometry |
| `docs/`, `figures/` | write-up and generated charts |
| `archive/` | superseded scripts and datasets |

All pipeline/analysis scripts are run **from the repository root**:
`python pipeline/compute_ffe.py --device mps`
