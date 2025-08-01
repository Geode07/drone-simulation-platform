# utils.py
import argparse
import requests
import rasterio
import rasterio.features
import numpy as np
import os
from skimage.transform import resize
from math import cos, radians
import requests
from shapely.geometry import Polygon
import json
import geopandas as gpd
import pyvista as pv
import osmnx as ox
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point, box
import geopandas as gpd
import matplotlib.pyplot as plt

def get_bbox_from_center(lat, lon, buffer_km=2.0, config=None):
    km = buffer_km
    if config and "simulation" in config:
        km = config["simulation"].get("dem_km", buffer_km)

    delta_deg = km / 111.0
    return {
        "min_lat": lat - delta_deg / 2,
        "max_lat": lat + delta_deg / 2,
        "min_lon": lon - delta_deg / 2,
        "max_lon": lon + delta_deg / 2,
    }

def download_dem(api_key, bbox, config=None):
    demtype = config["simulation"].get("dem_type", "SRTMGL1") if config else "SRTMGL1"
    out_file = config["simulation"].get("dem_output", "input_files/dem.tif") if config else "input_files/dem.tif"
    
    params = {
        "demtype": demtype,
        "south": bbox["min_lat"],
        "north": bbox["max_lat"],
        "west": bbox["min_lon"],
        "east": bbox["max_lon"],
        "outputFormat": "GTiff",
        "API_Key": api_key,
    }

    print(f"Requesting DEM ({demtype}) for bbox:", bbox)
    response = requests.get("https://portal.opentopography.org/API/globaldem", params=params)

    if response.ok:
        with open(out_file, "wb") as f:
            f.write(response.content)
        print(f"DEM downloaded: {out_file}")
        return out_file
    else:
        print("DEM download failed:", response.text)
        return None

def compute_terrain_complexity(dem_array):
    # Use gradient magnitude as terrain roughness
    gy, gx = np.gradient(dem_array)
    return np.sqrt(gx**2 + gy**2)

def rank_buildings_by_complexity(buildings_gdf, dem, transform, top_n=80):
    scores = []
    for poly in buildings_gdf.geometry:
        centroid = poly.centroid
        row, col = ~transform * (centroid.x, centroid.y)
        try:
            complexity = dem[int(row), int(col)]
            scores.append((complexity, poly))
        except:
            continue
    scores.sort(key=lambda x: x[0], reverse=True)
    return [b for _, b in scores[:top_n]]

def generate_flight_waypoints_from_polygons(polygons, config=None):
    clearance = config["simulation"].get("altitude_clearance", 20) if config else 20
    waypoints = []
    for poly in polygons:
        lon, lat = poly.centroid.x, poly.centroid.y
        waypoints.append({
            "lat": lat,
            "lon": lon,
            "alt": clearance
        })
    return waypoints

def query_overpass_buildings(min_lat, min_lon, max_lat, max_lon, config=None):
    api_url = config["overpass"].get("api_url", "https://overpass-api.de/api/interpreter") if config else "https://overpass-api.de/api/interpreter"
    
    query = f"""
    [out:json];
    (
      way["building"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out body;
    >;
    out skel qt;
    """
    print("Querying Overpass API...")
    response = requests.get(api_url, params={"data": query})

    if not response.ok:
        raise RuntimeError("Overpass API request failed:\n" + response.text)

    data = response.json()
    return parse_overpass_to_polygons(data, config=config)

def parse_overpass_to_polygons(data, config=None):
    default_height = config["overpass"].get("default_building_height", 10.0) if config else 10.0
    level_height = config["overpass"].get("building_levels_height", 3) if config else 3

    nodes = {el["id"]: (el["lon"], el["lat"]) for el in data["elements"] if el["type"] == "node"}
    ways = [el for el in data["elements"] if el["type"] == "way"]

    geometries, heights = [], []

    for way in ways:
        try:
            coords = [nodes[nid] for nid in way["nodes"]]
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            poly = Polygon(coords)
            if not poly.is_valid:
                continue

            tags = way.get("tags", {})
            height = None

            if "height" in tags:
                try:
                    height = float(tags["height"].replace("m", "").strip())
                except:
                    height = None
            elif "building:levels" in tags:
                try:
                    height = float(tags["building:levels"]) * level_height
                except:
                    height = None

            height = height if height is not None else default_height
            geometries.append(poly)
            heights.append(height)
        except KeyError:
            continue

    print(f"{len(geometries)} building polygons found.")
    return gpd.GeoDataFrame({"height": heights}, geometry=geometries, crs="EPSG:4326")

def rasterize_buildings(buildings_gdf, dem_shape, dem_transform):
    shapes = ((geom, height) for geom, height in zip(buildings_gdf.geometry, buildings_gdf.height))
    raster = rasterize(
        shapes=shapes,
        out_shape=dem_shape,
        transform=dem_transform,
        fill=0,
        dtype='float32',
    )
    return raster
