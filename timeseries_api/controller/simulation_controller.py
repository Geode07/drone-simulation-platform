# controller/simulation_controller.py
from config.load_config import load_simulation_config
CONFIG = load_simulation_config()
ELEVATION_PENALTY = CONFIG.get("simulation", {}).get("elevation_penalty", 0.01)
sim_cfg = CONFIG.get("drone_simulator", {})

import requests
import numpy as np
import pandas as pd
import json
import os
import math
from rasterio.transform import xy, rowcol
from geopy.distance import geodesic
from pyproj import Geod
from geopy.distance import geodesic
from fastapi import HTTPException, Query
from datetime import datetime

from .path_planner_wrapper import PathPlannerWrapper
from data_processing.external_data_manager import ExternalDataManager
from data_processing.utils import get_bbox_from_center
from .models import GPSPoint

class SimulationController:
    def __init__(self, control_mode="manual", ingest_url=None, drone_id=None, lat=None, lon=None):
        self.control_mode = control_mode
        self.lat = lat or CONFIG["location"]["lat"]
        self.lon = lon or CONFIG["location"]["lon"]

        self.edm = ExternalDataManager()
        data = self.edm.prepare_data(self.lat, self.lon)
        self.bbox = data["bbox"]
        self.waypoints = data["waypoints"]
        self.cell_size_m = CONFIG["drone_simulator"]["cell_size_m"]
        self.speed_mps = CONFIG["drone_simulator"]["speed_mps"]
        self.interval_ms = CONFIG["drone_simulator"]["interval_ms"]
        self.gps_noise_std = CONFIG["drone_simulator"]["gps_noise_std"]
        self.geod = data.get("geod") or Geod(ellps="WGS84")

        self.origin_lat = CONFIG["drone_simulator"]["origin_lat"]
        self.origin_lon = CONFIG["drone_simulator"]["origin_lon"]
        self.elevation = data["elevation"]
        self.transform = data["transform"]
        self.start_lat = self.bbox["min_lat"] + 0.5 * (self.bbox["max_lat"] - self.bbox["min_lat"])
        self.start_lon = self.bbox["min_lon"] + 0.5 * (self.bbox["max_lon"] - self.bbox["min_lon"])
        self.ingest_url = ingest_url or sim_cfg.get("ingest_url", "http://localhost:8001")
        self.drone_id = drone_id or sim_cfg.get("drone_id", f"drone_{np.random.randint(1000, 9999)}")
        
        def safe_dem_func(lat, lon):
            try:
                row, col = rowcol(self.transform, lon, lat)
                return float(self.elevation[row, col])
            except (IndexError, ValueError):
                return 0.0
        self.dem_func = safe_dem_func

        self.grid = np.zeros(self.elevation.shape)
        self.planner = PathPlannerWrapper(
            planner_type="astar",         # or "rrt", "rrt*"
            grid=self.grid,
            elevation=self.elevation,
            elevation_penalty=0.001,
            step_size=1.5,
            max_iter=1500,
            debug=True
        )
        self.generated_trace = self.run_simulation()

        self.full_path = []
        self.waypoints_rc = []  # Will hold row, col indices of waypoints

    def is_slam_mode(self):
        return self.control_mode == "slam_autostart"

    def sigmoid(self, x):
        return 1 / (1 + np.exp(-x))

    def compute_heading(self, lat1, lon1, lat2, lon2):
        azimuth, _, _ = self.geod.inv(lon1, lat1, lon2, lat2)
        return (azimuth + 360) % 360

    def grid_to_latlon(self, row, col):
        x, y = self.transform * (col, row)  # Note col before row
        return y, x  # Return as lat, lon

    def interpolate_segment(self, p1, p2):
        lat1, lon1, alt1 = p1
        lat2, lon2, alt2 = p2

        distance = geodesic((lat1, lon1), (lat2, lon2)).meters
        duration_s = distance / self.speed_mps
        steps = int(duration_s * 1000 // self.interval_ms)

        t = np.linspace(-6, 6, steps)
        eased = self.sigmoid(t)

        lats = lat1 + (lat2 - lat1) * eased
        lons = lon1 + (lon2 - lon1) * eased
        alts = alt1 + (alt2 - alt1) * eased

        # GPS noise for realism
        lats += np.random.normal(0, self.gps_noise_std, size=steps)
        lons += np.random.normal(0, self.gps_noise_std, size=steps)

        if self.dem_func:
            alts = np.array([self.dem_func(lat, lon) for lat, lon in zip(lats, lons)])

        heading = self.compute_heading(lat1, lon1, lat2, lon2)

        segment_data = []
        for i in range(steps):
            segment_data.append({
                "timestamp_ms": i * self.interval_ms,
                "lat": lats[i],
                "lon": lons[i],
                "alt": alts[i],
                "heading": heading
            })
        return segment_data

    def _build_path(self):
        waypoints = self.waypoints
        print(f"[DEBUG] Building path with {len(waypoints)} waypoints")
        self.full_path = []

        waypoints_rc = []
        for idx, wp in enumerate(waypoints):
            colf, rowf = ~self.transform * (wp["lon"], wp["lat"])
            row = int(math.floor(rowf))
            col = int(math.floor(colf))

            # Clamp to grid bounds
            row = min(max(row, 0), self.elevation.shape[0] - 1)
            col = min(max(col, 0), self.elevation.shape[1] - 1)

            rc = (row, col)
            waypoints_rc.append(rc)
        self.waypoints_rc = waypoints_rc
        return waypoints_rc

    def step_towards(self, state, target, speed_mps=None):
        lat1, lon1 = state["lat"], state["lon"]
        lat2, lon2 = target[0], target[1]

        azimuth, _, dist = self.geod.inv(lon1, lat1, lon2, lat2)
        azimuth_rad = np.deg2rad(azimuth)

        distance_to_move = (speed_mps or self.speed_mps) * (self.interval_ms / 1000.0)
        moved = self.geod.fwd(lon1, lat1, azimuth, distance_to_move)

        new_lon, new_lat = moved[0], moved[1]
        return {
            "lat": new_lat,
            "lon": new_lon,
            "alt": self.dem_func(new_lat, new_lon),
            "heading": azimuth,
        }

    def has_arrived(self, state, target, threshold_m=2.0):
        d = geodesic((state["lat"], state["lon"]), (target[0], target[1])).meters
        return d <= threshold_m

    def run_simulation(self) -> dict:
        print("[SIM-RECORD] Running full simulation and accumulating trace...")

        waypoints_rc = self._build_path()
        if not waypoints_rc or len(waypoints_rc) < 2:
            raise ValueError("[SIM-RECORD] Not enough waypoints to simulate path.")

        state = self.get_start_location()
        all_points = []

        for i in range(len(waypoints_rc) - 1):
            start_rc = waypoints_rc[i]
            goal_rc = waypoints_rc[i + 1]

            print(f"[SIM-RECORD] Planning segment {i}: {start_rc} -> {goal_rc}")
            segment_rc = self.planner.find_segment_path(start_rc, goal_rc)
            if not segment_rc:
                print(f"[SIM-RECORD WARNING] Skipping unreachable segment {start_rc} -> {goal_rc}")
                continue

            segment_latlon = [self.grid_to_latlon(r, c) for r, c in segment_rc]

            for j, target in enumerate(segment_latlon):
                while not self.has_arrived(state, target):
                    state = self.step_towards(state, target)
                    gps_point = GPSPoint(
                        ts=datetime.utcnow(),
                        lat=state["lat"],
                        lon=state["lon"],
                        alt=state["alt"],
                        agl=None,
                        heading=state.get("heading")
                    )
                    all_points.append(gps_point)

        print(f"[SIM-RECORD] Accumulated {len(all_points)} GPS points.")
        self.generated_trace = {
            "drone_id": self.drone_id,
            "data": all_points
        }
        return self.generated_trace

    # === Accessors ===
    def get_start_location(self):
        return {
            "lat": self.start_lat,
            "lon": self.start_lon,
            "alt": self.dem_func(self.start_lat, self.start_lon),
            "heading": 0.0  
        }

    def get_full_path(self):
        return self.full_path

    def get_waypoints(self):
        return self.waypoints 

    def get_bbox(self):
        return self.bbox

    def reset(self):
        self.__init__(self.ingest_url)