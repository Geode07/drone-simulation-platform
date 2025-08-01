# world_data_builder.py
from .utils import (
    get_bbox_from_center,
    download_dem,
    compute_terrain_complexity,
    query_overpass_buildings,
    rank_buildings_by_complexity,
    generate_flight_waypoints_from_polygons,
)

from .tsp_utils import compute_cost_matrix, solve_tsp_christofides

import rasterio
from rasterio.transform import Affine
from rasterio.enums import Resampling
import os
import json
import numpy as np
import math
from pathlib import Path

class WorldDataBuilder:
    def __init__(self, config, lat=None, lon=None):
        self.config = config
        self.lat = lat or config["location"]["lat"]
        self.lon = lon or config["location"]["lon"]
        self.api_key = config["dem"]["api_key"]

        # Path setup
        self.output_dir = Path(config["paths"]["input_dir"])
        self.output_dir.mkdir(exist_ok=True)
        self.dem_file = Path(config["dem"].get("output_file", self.output_dir / "dem.tif"))

        self.target_dim = tuple(config["dem"].get("resolution", [256, 256]))
        self.bbox = None

    def generate_dem(self, buffer_km=None):
        buffer_km = buffer_km or self.config["dem"].get("km", 2.0)
        demtype = self.config["dem"].get("type", "SRTMGL1")

        self.bbox = get_bbox_from_center(self.lat, self.lon, buffer_km=buffer_km)
        temp_dem = download_dem(self.api_key, self.bbox, config=self.config)

        if not temp_dem:
            raise RuntimeError("DEM download failed.")
        if Path(temp_dem) != self.dem_file:
            os.rename(temp_dem, self.dem_file)

        # Add resampling step
        if self.target_dim:
            with rasterio.open(self.dem_file) as src:
                data = src.read(
                    1,
                    out_shape=(self.target_dim[0], self.target_dim[1]),
                    resampling=Resampling.bilinear
                )
                scale_x = src.width / self.target_dim[1]
                scale_y = src.height / self.target_dim[0]
                transform = src.transform * Affine.scale(scale_x, scale_y)

                # Alignment sanity check
                origin_lat = self.lat
                origin_lon = self.lon
                colf, rowf = ~transform * (origin_lon, origin_lat)
                row = int(rowf)
                col = int(colf)

                if 0 <= row < data.shape[0] and 0 <= col < data.shape[1]:
                    print("Origin is inside DEM bounds.")
                else:
                    print("[ERROR] Origin is outside DEM bounds — misalignment risk.")

                top_left_lon, top_left_lat = transform * (0, 0)
                bottom_right_lon, bottom_right_lat = transform * (data.shape[1], data.shape[0])
                print("[INFO] DEM bounding box:")
                print(f"  NW corner: ({top_left_lat:.6f}, {top_left_lon:.6f})")
                print(f"  SE corner: ({bottom_right_lat:.6f}, {bottom_right_lon:.6f})")

                profile = src.profile
                profile.update({
                    "height": self.target_dim[0],
                    "width": self.target_dim[1],
                    "transform": transform
                })
            with rasterio.open(self.dem_file, "w", **profile) as dst:
                dst.write(data, 1)
        return self.dem_file

    def generate_waypoints(self, output_json=None, force=True):
        if not self.bbox or not self.dem_file.exists():
            raise RuntimeError("DEM not ready. Run generate_dem first.")

        with rasterio.open(self.dem_file) as src:
            dem = src.read(1)
            transform = src.transform

        terrain = compute_terrain_complexity(dem)
        buildings = query_overpass_buildings(**self.bbox)
        ranked = rank_buildings_by_complexity(buildings, terrain, transform)

        seen_rc = set()
        deduped_polygons = []
        for poly in ranked:
            centroid = poly.centroid
            try:
                # Convert centroid lat/lon to row/col on DEM grid
                rowf, colf = ~transform * (centroid.x, centroid.y)
                row = int(math.floor(rowf))
                col = int(math.floor(colf))

                # Clamp to DEM shape
                row = min(max(row, 0), dem.shape[0] - 1)
                col = min(max(col, 0), dem.shape[1] - 1)

                key = (row, col)
                if key not in seen_rc:
                    seen_rc.add(key)
                    deduped_polygons.append(poly)
            except Exception as e:
                print(f"[WARN] Skipping building due to transform error: {e}")

        clearance = self.config["waypoints"].get("clearance", 30)
        waypoints = generate_flight_waypoints_from_polygons(deduped_polygons[:80], config=self.config)
        print(f"[INFO] Generated {len(waypoints)} waypoints from {len(deduped_polygons)} buildings.")
        output_json = output_json or self.config["paths"].get("flight_plan", self.output_dir / "flight_plan.json")
        with open(output_json, "w") as f:
            json.dump(waypoints, f)
        return waypoints, dem, transform, buildings

    def generate_ordered_waypoints(self, output_json=None, metric="euclidean", force=True):
        """
        Generates DEM-aligned waypoints and returns them in TSP-optimal visiting order.
        """
        waypoints, dem, transform, buildings = self.generate_waypoints(output_json=output_json, force=force)

        # Extract just (lat, lon) tuples for TSP cost computation
        coords_for_tsp = [(wp["lat"], wp["lon"]) for wp in waypoints]

        # Compute the TSP cost matrix from coordinate tuples
        cost_matrix = compute_cost_matrix(coords_for_tsp, metric=metric)

        # Solve TSP and get reordered waypoint indices
        tsp_order, _ = solve_tsp_christofides(cost_matrix)

        # Reorder the original waypoint dicts
        ordered_waypoints = [waypoints[i] for i in tsp_order]

        print(f"[INFO] TSP-ordered {len(ordered_waypoints)} waypoints.")
        return ordered_waypoints, dem, transform, buildings