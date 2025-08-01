# main.py
from fastapi import FastAPI, HTTPException, Request, Query, Header
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import APIRouter
import psycopg2
from psycopg2.extras import RealDictCursor
import asyncio
import time
import httpx
import os
import json
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from dotenv import load_dotenv

from controller.models import DroneBatch, GPSPoint
from controller import db, ingest, query
from controller.sim_controller import PlaybackController
from controller.simulation_controller import SimulationController
from config.load_config import load_simulation_config

config = load_simulation_config()
load_dotenv()
key = os.getenv("CLEAR_API_KEY")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

controller = PlaybackController()
_psycopg_conn = db.get_psycopg_conn()
_psycopg_cur = _psycopg_conn.cursor()
app.state.db_conn = _psycopg_conn
app.state.db_cursor = _psycopg_cur
sim_controller = None

@app.on_event("startup")
async def startup_event():
    global sim_controller
    print("[STARTUP] Initializing SLAM system...")

    try:
        # Clear GPS trace table
        with psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM gps_trace;")
                conn.commit()
        print("[STARTUP] Cleared GPS trace table.")

        # Init SimulationController
        sim_controller = SimulationController(control_mode="slam_autostart")
        batch_dict = sim_controller.generated_trace
        print("[DEBUG] batch_dict keys:", batch_dict.keys())

        batch = DroneBatch(**batch_dict)  # Convert dict to DroneBatch Pydantic model
        num_points = ingest.ingest_drone_batch(_psycopg_cur, _psycopg_conn, batch)
        print(f"[STARTUP] Ingested {num_points} points into DB.")

    except Exception as e:
        print(f"[STARTUP ERROR] {e}")

@app.get("/api/start_location")
async def get_start_location(drone_id: str = Query(...)):
    try:
        conn = await db.get_asyncpg_conn()
        result = await query.get_first_point(conn, drone_id)
        await conn.close()

        if not result:
            raise HTTPException(status_code=404, detail="No location found for this drone.")

        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/readyz")
async def readiness_check():
    if sim_controller is None:
        raise HTTPException(status_code=503, detail="SimulationController not initialized.")
    return {"status": "ready"}

@app.get("/api/bbox")
async def serve_bbox():
    if sim_controller is None:
        raise HTTPException(status_code=503, detail="SimulationController not initialized.")

    bbox = sim_controller.get_bbox()
    if not bbox or bbox.get("min_lat") is None:
        raise HTTPException(status_code=503, detail="BBOX not available or not ready.")

    return JSONResponse(bbox)

@app.get("/api/waypoints")
async def get_waypoints():
    return JSONResponse(sim_controller.get_waypoints())


@app.get("/api/simulation_done")
async def simulation_done(request: Request):
    sim_complete_event = getattr(request.app.state, "sim_complete_event", None)
    if sim_complete_event is None:
        raise HTTPException(status_code=503, detail="Simulation event not available.")
    return {"done": sim_complete_event.is_set()}

@app.get("/api/resample")
async def resample_api(
    drone_id: str = Query(...),
    interval: str = Query("1 second")
):
    try:
        interval_td = query.parse_interval(interval)
        conn = await db.get_asyncpg_conn()
        result = await query.get_resampled_trace(conn, drone_id, interval_td)
        await conn.close()

        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def clear_timeseries_data(x_api_key: str = Header(None)):
    if x_api_key != os.getenv("CLEAR_API_KEY"):
        raise HTTPException(status_code=403, detail="Unauthorized")

    try:
        _psycopg_cur.execute("TRUNCATE TABLE gps_trace RESTART IDENTITY;")
        _psycopg_conn.commit()
        return {"status": "cleared"}
    except Exception as e:
        _psycopg_conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# Playback control (used by frontend buttons)
playback_state = {
    "trace": [],
    "index": 0,
    "last_ts": time.time()
}

@app.get("/api/gps/next")
async def get_next_point():
    if controller.paused:
        return {"paused": True, "point": None}

    # First load (or reload on reset)
    if not playback_state["trace"]:
        playback_state["trace"] = query.get_all_trace(_psycopg_cur)
        playback_state["index"] = 0

    trace = playback_state["trace"]
    i = playback_state["index"]

    if i >= len(trace):
        return {"done": True, "point": None}

    point = trace[i]
    playback_state["index"] += 1
    return {"paused": False, "point": point}

@app.post("/api/play")
async def play_simulation():
    controller.play()
    return {"status": "playing"}

@app.post("/api/pause")
async def pause_simulation():
    controller.pause()
    return {"status": "paused"}

@app.post("/api/reset")
async def reset_simulation():
    controller.reset()
    playback_state["trace"] = []
    playback_state["index"] = 0
    return {"status": "reset"}

@app.get("/status")
async def simulation_status():
    return controller.get_status()

@app.get("/db/status")
def check_db_status():
    _psycopg_cur.execute("SELECT COUNT(*) FROM your_timeseries_table;")
    count = _psycopg_cur.fetchone()[0]
    return {"rows_in_timeseries_db": count}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)