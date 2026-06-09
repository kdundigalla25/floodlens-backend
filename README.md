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
