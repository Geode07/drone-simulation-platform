from simulation_controller import SimulationController
from plotting_function import plot_waypoints_and_trace  # if you break plotting out
import matplotlib.pyplot as plt
import geopandas as gpd
from shapely.geometry import Point, LineString

controller = SimulationController(debug=True)

# Generate waypoints
waypoints_rc = controller._build_path()  # e.g. list of (r, c) tuples

# Convert to lat/lon
waypoints_latlon = [controller.grid_to_latlon(r, c) for r, c in waypoints_rc]

# Make GeoDataFrame for waypoints
gdf = gpd.GeoDataFrame(
    geometry=[Point(lon, lat) for lat, lon in waypoints_latlon],
    crs="EPSG:4326"
)

# Optional: connect the waypoints into a path
route = LineString([Point(lon, lat) for lat, lon in waypoints_latlon])
route_gdf = gpd.GeoDataFrame(geometry=[route], crs="EPSG:4326")

fig, ax = plt.subplots(figsize=(10, 8))
route_gdf.plot(ax=ax, color="red", linewidth=2, label="Route")
gdf.plot(ax=ax, marker="o", color="blue", markersize=40, label="Waypoints")
plt.title("Simulated Drone Path")
plt.legend()
plt.grid(True)
plt.show()
