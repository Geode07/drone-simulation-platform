import numpy as np
import random
import numpy as np
from pyproj import Transformer
from affine import Affine

class RRT:
    def __init__(self, occupancy_grid, step_size=1.0, max_iter=1000, debug=False):
        self.map = occupancy_grid
        self.step_size = step_size
        self.max_iter = max_iter
        self.debug = debug

    def find_path(self, start, goal):
        self.start = tuple(start)
        self.goal = tuple(goal)
        self.tree = {self.start: None}
        return self.plan()

    def sample_point(self):
        """ Randomly sample a point, with a small bias toward the goal. """
        if random.random() > 0.9:  # 10% chance we sample the goal
            return self.goal
        # Adjust sample bounds
        return (random.uniform(0, self.map.shape[0]),
                random.uniform(0, self.map.shape[1]))

    def nearest_neighbor(self, point):
        """ Find the existing tree node closest to 'point'. """
        return min(self.tree.keys(), key=lambda n: np.linalg.norm(np.array(n) - np.array(point)))

    def steer(self, nearest, sampled):
        """
        Move from 'nearest' toward 'sampled' by 'step_size'.
        Returns the new node to be added to the tree.
        """
        direction = np.array(sampled) - np.array(nearest)
        dist = np.linalg.norm(direction)
        if dist <= self.step_size:
            return tuple(sampled)
        step = (direction / dist) * self.step_size
        new_node = np.array(nearest) + step
        return tuple(new_node)

    def is_collision_free(self, point):
        """ 
        Check if (x, y) is in free space (not an obstacle).
        This assumes self.map[x, y] = 0 => free, anything else => obstacle.
        Also checks bounds.
        """
        x, y = point
        # Must be within map bounds
        if (x < 0 or x >= self.map.shape[0] or
            y < 0 or y >= self.map.shape[1]):
            return False
        # Check occupancy
        return (self.map[int(x), int(y)] == 0)

    def plan(self):
        """
        Build an RRT tree from start to goal within max_iter attempts.
        Returns a list of (x, y) positions if successful, or None if failed.
        """
        for _ in range(self.max_iter):
            sampled = self.sample_point()
            nearest = self.nearest_neighbor(sampled)
            new_point = self.steer(nearest, sampled)

            if self.is_collision_free(new_point):
                self.tree[new_point] = nearest
                # Check if we're close enough to goal
                if np.linalg.norm(np.array(new_point) - np.array(self.goal)) < self.step_size:
                    return self._reconstruct_path(new_point)
        return None  # Path not found within max_iter

    def _reconstruct_path(self, end_point):
        """ Reconstruct path by walking up the tree parents. """
        path = [end_point]
        while end_point in self.tree and self.tree[end_point] is not None:
            end_point = self.tree[end_point]
            path.append(end_point)
        return list(reversed(path))

class GeoAwareRRT:
    def __init__(self, grid, transform, elevation=None, elevation_penalty=1.0,
                 step_size=1.0, max_iter=1000, debug=False):
        """
        grid: 2D numpy array (0 = free, 1 = obstacle)
        transform: Affine transform for lat/lon <-> pixel
        elevation: 2D numpy array same shape as grid (in meters)
        elevation_penalty: weight applied to elevation change
        """
        self.grid = grid
        self.transform = transform
        self.inv_transform = ~transform
        self.elevation = elevation
        self.elevation_penalty = elevation_penalty
        self.step_size = step_size
        self.max_iter = max_iter
        self.debug = debug

    def latlon_to_grid(self, lat, lon):
        x, y = self.inv_transform * (lon, lat)  # Affine expects (x, y) = (lon, lat)
        return (int(round(y)), int(round(x)))   # row = y, col = x

    def grid_to_latlon(self, row, col):
        lon, lat = self.transform * (col, row)
        return (lat, lon)

    def elevation_cost(self, pt1, pt2):
        """Add elevation cost between two grid cells"""
        if self.elevation is None:
            return 0.0
        r1, c1 = map(int, pt1)
        r2, c2 = map(int, pt2)
        try:
            elev1 = self.elevation[r1, c1]
            elev2 = self.elevation[r2, c2]
            return self.elevation_penalty * abs(elev2 - elev1)
        except IndexError:
            return float("inf")  # Penalize going off bounds

    def find_path(self, start_latlon, goal_latlon):
        start_rc = self.latlon_to_grid(*start_latlon)
        goal_rc = self.latlon_to_grid(*goal_latlon)

        base_rrt = RRT(start_rc, goal_rc, self.grid,
                       step_size=self.step_size, max_iter=self.max_iter)

        base_rrt.is_collision_free = lambda pt: self._is_valid_and_free(pt)

        path_rc = base_rrt.plan()
        if not path_rc:
            if self.debug:
                print("[GeoAwareRRT] Path not found.")
            return None

        return [self.grid_to_latlon(*pt) for pt in path_rc]

    def _is_valid_and_free(self, pt):
        """Wraps grid bounds check + obstacle check."""
        row, col = map(int, pt)
        if (row < 0 or row >= self.grid.shape[0] or
            col < 0 or col >= self.grid.shape[1]):
            return False
        if self.grid[row, col] != 0:
            return False
        return True