#path_planner_wrapper.py
from .astar_planner import AStarPlanner
from .rrt_planner import RRT, GeoAwareRRT
from .rrt_star_planner import RRTStar, GeoAwareRRTStar
import numpy as np

class PathPlannerWrapper:
    PLANNER_MAP = {
        "astar": AStarPlanner,
        "rrt": RRT,
        "rrt*": RRTStar,
        "geo_rrt": GeoAwareRRT,
        "geo_rrt*": GeoAwareRRTStar,
    }

    def __init__(self, planner_type="astar", grid=None, elevation=None, elevation_penalty=1.0,
                 step_size=1.0, max_iter=1000, debug=False):
        self.planner_type = planner_type.lower()
        self.grid = grid
        self.elevation = elevation
        self.elevation_penalty = elevation_penalty
        self.step_size = step_size
        self.max_iter = max_iter
        self.debug = debug

        if self.planner_type == "astar":
            self.planner_core = self.PLANNER_MAP[self.planner_type](
                grid=self.grid,
                elevation=self.elevation,
                elevation_penalty=self.elevation_penalty,
                debug=self.debug
            )
        elif self.planner_type in self.PLANNER_MAP:
            self.planner_core = self.PLANNER_MAP[self.planner_type]  # class only
        else:
            raise ValueError(f"Unsupported planner type: {self.planner_type}")

    def find_segment_path(self, start, goal):
        if self.planner_type == "astar":
            return self.planner_core.find_path(start, goal)

        elif self.planner_type in ["rrt", "rrt*", "geo_rrt", "geo_rrt*"]:
            planner = self.planner_core(
                start=start,
                goal=goal,
                occupancy_grid=self.grid,
                step_size=self.step_size,
                max_iter=self.max_iter
            )
            return planner.plan()

        else:
            raise ValueError(f"Unsupported planner type: {self.planner_type}")