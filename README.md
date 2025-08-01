# Drone Trace & Mapping Platform

This project mimics a drone performing visual inspection over a wildfire in a residential area. It generates, stores, and visualizes GPS traces for an autonomous drone using an two backend services, a timeseries database with geospatial capability, and interactive map. 

To generate the digital elevation model (DEM), the opentopography api is used. The overpass api is used to generate the geospatial tile context and buildings. 

In addition to a Vite frontend platform hosted on Flask, I used FastAPI for data streaming, and multiple python libraries for real-time geospatial processing. I also added my implementations of topography analytics, traveling salesman problem algorithm, and pathfinding algorithm for the drone flight planning task.

![Screenshot](drone_mapping_screenshot.png)

## Tech Stack

- **Frontend**: Vite, MapLibre GL JS
- **Backend**:
  - `FastAPI`: Ingest GPS data via API
  - `Flask`: Serves the interactive map UI
- **Database**: TimescaleDB + PostGIS
- **Containerization**: Docker, Docker Compose

---

## Local Development

### Project Structure
<pre> ```text 
├── flask_app/ 
├── fastapi_app/ 
├── db/ 
│ └── init.sql 
├── docker-compose.yml 
├── .env.example 
└── README.md ``` </pre>

### Requirements
- Docker & Docker Compose
- Python (optional if not using virtualenvs outside containers)

### Start the App

1. Copy the `.env.example`:
   ```bash
   cp .env.example .env

2. Run:
docker-compose up --build

3. Access:
* Flask app: http://localhost:8000
* FastAPI docs: http://localhost:8001/docs
* Postgres DB: localhost:5432 (via any SQL client)

4. Future Work:
Cloud Deployment: For production, this architecture is compatible with:
* Kubernetes: Helm charts or K8s manifests (not included here)
* Terraform: For provisioning cloud databases, services, and secrets

5. Testing:
You can use the FastAPI Swagger UI at:
http://localhost:8001/docs

License: MIT