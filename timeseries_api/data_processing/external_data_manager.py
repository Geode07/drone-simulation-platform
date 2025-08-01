# data_processing/external_data_manager.py
from config.load_config import load_simulation_config
CONFIG = load_simulation_config()

from pathlib import Path
import osmnx as ox
from shapely.geometry import box
import geopandas as gpd

from .world_data_builder import WorldDataBuilder

class ExternalDataManager:
    def __init__(self, config=None):
        self.lat = CONFIG["location"]["lat"]
        self.lon = CONFIG["location"]["lon"]
        self.output_dir = Path(CONFIG["paths"]["input_dir"])
        self.output_dir.mkdir(exist_ok=True)

        self.api_key = CONFIG["dem"]["api_key"]
        if not self.api_key:
            print("[WARN] DEM API key is not set. DEM generation may fail.")

        # Internal storage
        self.waypoints = None
        self.transform = None
        self.elevation = None

    def prepare_data(self, lat=None, lon=None):
        builder = WorldDataBuilder(CONFIG, lat=self.lat, lon=self.lon)

        dem_path = builder.generate_dem()
        waypoints, dem_array, transform, buildings_gdf = builder.generate_ordered_waypoints()

        self.waypoints = waypoints
        self.transform = transform
        self.elevation = dem_array
        self.bbox = builder.bbox

        self.export_osm_features(self.bbox)

        if buildings_gdf is not None and not buildings_gdf.empty:
            buildings_path = self.output_dir / "buildings.geojson"
            buildings_gdf.to_file(buildings_path, driver="GeoJSON")

        return {
            "bbox": self.bbox,
            "waypoints": self.waypoints,
            "transform": self.transform,
            "elevation": self.elevation,
            "dem_path": dem_path,
            "buildings": buildings_gdf,
        }

    def export_osm_features(self, bbox):
        overpass_cfg = CONFIG.get("overpass", {})
        api_url = overpass_cfg.get("api_url", "https://overpass-api.de/api/interpreter")

        north = bbox["max_lat"]
        south = bbox["min_lat"]
        east = bbox["max_lon"]
        west = bbox["min_lon"]

        tags = {
            "building": True,
            "highway": True,
            "natural": True,
            "landuse": True
        }

        print("[INFO] Querying OSM features from Overpass API...")
        try:
            bbox_polygon = box(west, south, east, north)
            gdf = ox.features_from_polygon(polygon=bbox_polygon, tags=tags)

            output_path = Path(self.output_dir) / "osm_features.geojson"
            gdf.to_file(output_path, driver="GeoJSON")
            print(f"Exported OSM features to {output_path}")
        except Exception as e:
            print(f"[ERROR] Failed to fetch or export OSM features: {e}")


