import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

class RRTStar:
    def __init__(self, start, goal, map_path=None, occupancy_grid=None, target_radius=1.0, delta=3.0, exploration_bias=0.8, max_nodes=100):
        """Initializes RRT* with either a map path or an in-memory occupancy grid."""
        if occupancy_grid is not None:
            self.map = occupancy_grid
        elif map_path:
            self.map = self.load_map(map_path)
        else:
            raise ValueError("Either map_path or occupancy_grid is required")

        self.map_size = self.map.shape[::-1]  # (width, height)

        # Define World Bounds (meters)
        self.world_x_min, self.world_x_max = -2.16, 2.42  
        self.world_y_min, self.world_y_max = -4.07, 1.78

        self.start = start
        self.goal = goal

        self.start_map = self.world2map(*start)
        self.goal_map = self.world2map(*goal)

        self.target_radius = target_radius
        self.exploration_bias = exploration_bias
        self.delta = delta
        self.max_nodes = max_nodes
        self.nodes = [self.start]  # Stored in world coords
        self.edges = []
        self.path = None

    def load_map(self, path):
        """Loads a binary map from a .npy file and rotates it 90 degrees."""
        map_data = np.load(path)  # Load .npy file
        binary_map = (map_data < 0.5).astype(int)  # Convert to binary (0 = obstacle, 1 = free)
        return np.rot90(binary_map, k=1)  # Rotate 90 degrees clockwise

    def world2map(self, xw, yw):
        # map.shape[0] is height and map.shape[1] is width
        # Normalize x, y correctly based on min/max
        px = int((xw - self.world_x_min) / (self.world_x_max - self.world_x_min) * (self.map.shape[1] - 1))
        py = int((self.world_y_max - yw) / (self.world_y_max - self.world_y_min) * (self.map.shape[0] - 1))
        
        # Ensure values stay in bounds
        px = min(max(px, 0), self.map.shape[1] - 1)
        py = min(max(py, 0), self.map.shape[0] - 1)
        return (px, py)

    def map2world(self, px, py):
        """Converts map coordinates (pixels) to world coordinates (meters)."""
        xw = self.world_x_min + (px / (self.map.shape[1] - 1)) * (self.world_x_max - self.world_x_min)
        yw = self.world_y_max - (py / (self.map.shape[0] - 1)) * (self.world_y_max - self.world_y_min)
        return (xw, yw)

    def distance(self, p1, p2):
        """Returns Euclidean distance between two points."""
        return np.linalg.norm(np.array(p1) - np.array(p2))

    def is_valid_point(self, point, parent=None):
        """Ensures a point is within bounds, not an obstacle, and path from parent is collision-free."""
        xw, yw = point  # Extract world coordinates
        px, py = self.world2map(xw, yw)  # Convert to map coordinates
        print(f"[DEBUG]: Converted to map coordinates: ({px}, {py})")
        px = int(px)
        py = int(py)

        # Ensure within map bounds
        if not (0 <= px < self.map.shape[1] and 0 <= py < self.map.shape[0]):
            return False

        # Ensure the point is in free space
        if self.map[py, px] == 0:  # 0 = obstacle
            return False
        return True  # Valid point

        # Check collision-free path from parent
        if parent is not None:
            num_samples = max(int(self.distance(parent, point) * 2), 1)
            pixels = np.column_stack((
                np.linspace(parent[0], point[0], num=num_samples),
                np.linspace(parent[1], point[1], num=num_samples)
            )).astype(int)

            for px, py in pixels:
                if not (0 <= px < self.map.shape[1] and 0 <= py < self.map.shape[0]) or self.map[py, px] == 0:
                    return False  # Path collides or out of bounds
        return True  # Point is valid and path is collision-free

    def sample_point(self):
        """Samples a valid random point with dynamic bias toward the goal."""
        goal_distance = min(self.distance(node, self.goal) for node in self.nodes)
        dynamic_bias = min(0.95, max(0.4, 1.0 - goal_distance / (self.world_x_max - self.world_x_min)))  # Closer = Higher bias

        if np.random.rand() < dynamic_bias:
            return self.goal  # Bias sampling toward goal

        max_attempts = 10
        for _ in range(max_attempts):
            rand_x = np.random.uniform(self.world_x_min, self.world_x_max)
            rand_y = np.random.uniform(self.world_y_min, self.world_y_max)
            rand_point = (rand_x, rand_y)

            print(f"[DEBUG]: Sampled raw point (world): {rand_point}") 

            if self.is_valid_point(rand_point):
                return rand_point
        return self.start  # Fallback

    def find_nearest(self, point):
        """Finds the nearest node in the tree to the given point."""
        return min(self.nodes, key=lambda n: self.distance(n, point))

    def generate_new_point(self, nearest, random_point):
        """Moves from nearest node towards random point with an adaptive step size."""
        direction = np.array(random_point) - np.array(nearest)
        length = np.linalg.norm(direction)

        if length == 0:
            return nearest

        step_size = min(self.delta, length * 0.7)  # Reduce step size dynamically
        new_point_world = tuple(np.array(nearest) + (direction / length) * step_size)

        # Ensure step_size is computed before use
        new_point_map = self.world2map(*new_point_world)  # New point in map coordinates
        return new_point_world if self.is_valid_point(new_point_map, parent=nearest) else nearest

    def step(self):
        """Performs one iteration of the RRT* expansion."""
        if len(self.nodes) >= self.max_nodes:
            return False  # Stop if max nodes reached

        random_point = self.sample_point()

        nearest = self.find_nearest(random_point)

        new_point = self.generate_new_point(nearest, random_point)
        if not self.is_valid_point(new_point, parent=nearest):")
            return True  # Continue searching

        self.nodes.append(new_point)

        if self.distance(new_point, self.goal) <= self.target_radius:
            print("[INFO]: Goal Reached!")
            self.path = self.get_final_path()
            return False  # Stop animation
        return True  # Continue searching

    def get_final_path(self):
        """Retrieves the final path from goal to start, ensuring the goal is at the end."""
        path = []
        node = self.nodes[-1]  # Last node added (should be near goal)

        while node != self.start:
            path.append(node)
            node = next((p[0] for p in self.edges if p[1] == node), None)  # Find parent

            if node is None:
                print("[ERROR]: Path tracing failed.")
                return None

        path.append(self.start)  # Ensure start is included

        # Reverse path so it starts at 'start' and ends at 'goal'
        path = path[::-1]

        # If goal is found at the beginning, move it to the end
        if path[0] == self.goal:
            path.pop(0)  # Remove goal from start
            path.append(self.goal)  # Add goal to the end

        # Ensure goal is included exactly once at the end
        if path[-1] != self.goal:
            path.append(self.goal)
        return path

    def save_path(self, filename="rrt_star_path.npy"):
        """Saves the path to a .npy file, ensuring the goal is not duplicated."""
        if self.path and len(self.path) > 1:  # Ensure the path is valid before saving
            path_array = np.array(self.path)  # Convert to NumPy array for saving

            np.save(filename, path_array)
            print(f"[INFO]: Path saved to {filename}")
            print(f"[DEBUG]: Saved waypoints:\n{path_array}")
        else:
            print("[ERROR]: No valid path found to save.")

    def is_valid_path(self, p1, p2):
        """Checks if the path between two points crosses an obstacle."""
        num_samples = int(self.distance(p1, p2) * 2)  # More samples for long edges
        pixels = np.column_stack((
            np.linspace(p1[0], p2[0], num=num_samples),
            np.linspace(p1[1], p2[1], num=num_samples)
        )).astype(int)

        for xw, yw in pixels:
            px, py = self.world2map(xw, yw)
            if self.map[py, px] == 0:  # Obstacle detected
                return False  
        return True  # Path is free

class GeoAwareRRTStar:
    def __init__(self, occupancy_grid, transform_func, dem_func=None):
        self.grid = occupancy_grid
        self.transform_func = transform_func
        self.dem_func = dem_func or (lambda lat, lon: 0)

    def find_path(self, start_latlon, goal_latlon):
        # Convert lat/lon to grid row/col
        start_rc = self.transform_func.latlon_to_rc(*start_latlon)
        goal_rc = self.transform_func.latlon_to_rc(*goal_latlon)

        # Convert to world coords (meters, if needed) for RRT*
        start_xy = self.transform_func.rc_to_world(*start_rc)
        goal_xy = self.transform_func.rc_to_world(*goal_rc)

        # Plan path using your RRT_starAlgorithm
        planner = RRTStar(
            map_path=None,  
            start=start_xy,
            goal=goal_xy,
            max_nodes=300,
            delta=2.0
        )
        planner.map = self.grid  # override load_map()
        planner.run()  

        if planner.path is None:
            return []

        # Convert back to lat/lon
        latlon_path = []
        for x, y in planner.path:
            px, py = planner.world2map(x, y)
            lat, lon = self.transform_func.rc_to_latlon(py, px)
            alt = self.dem_func(lat, lon)
            latlon_path.append((lat, lon, alt))

        return latlon_path
