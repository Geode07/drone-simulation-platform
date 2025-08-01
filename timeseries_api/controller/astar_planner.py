# astar_planner.py
import numpy as np
import pandas as pd
from geopy.distance import geodesic
from pyproj import Geod
import random
from heapq import heappush, heappop, heapify
from collections import defaultdict

class AStarPlanner:
    def __init__(self, grid, elevation=None, elevation_penalty=1.0, debug=False):
        """
        grid: 2D array where 0 = free, 1 = obstacle
        elevation: 2D array of same shape, with elevation values (in meters)
        elevation_penalty: cost multiplier for elevation changes
        debug: whether to print debug information
        """
        self.grid = grid
        self.elevation = elevation
        self.elevation_penalty = elevation_penalty
        self.debug = debug

    def find_path(self, start, goal):
        if start == goal:
            if self.debug:
                print(f"[A*] Start and goal are the same: {start}. Returning single-point path.")
            return [start]

        def get_neighbors(pos):
            directions = [
                (0, 1),  (0, -1),   # right, left
                (1, 0),  (-1, 0),   # down, up
                (1, 1),  (1, -1),   # down-right, down-left
                (-1, 1), (-1, -1)   # up-right, up-left
            ]
            for dx, dy in directions:
                nx, ny = pos[0] + dx, pos[1] + dy
                if 0 <= nx < self.grid.shape[0] and 0 <= ny < self.grid.shape[1]:
                    if self.grid[nx, ny] == 0:
                        yield (nx, ny), np.linalg.norm([dx, dy])

        open_set = [(0, start)]
        heapify(open_set)
        came_from = {}
        g_score = defaultdict(lambda: float('inf'))
        g_score[start] = 0
        visited = set()

        while open_set:
            _, current = heappop(open_set)
            if current == goal:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start)
                path = path[::-1]
                if self.debug and len(path) == 1:
                    print(f"[A*] Trivial 1-point path detected: {path}")
                return path

            visited.add(current)

            for neighbor, base_cost in get_neighbors(current):
                if neighbor in visited:
                    continue

                elev_cost = 0
                if self.elevation is not None:
                    elev_current = self.elevation[current[0], current[1]]
                    elev_neighbor = self.elevation[neighbor[0], neighbor[1]]
                    elev_cost = self.elevation_penalty * abs(elev_neighbor - elev_current)

                cost = base_cost + elev_cost
                tentative_g = g_score[current] + cost

                if tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g

                    goal_np = np.asarray(goal).flatten()
                    neighbor_np = np.asarray(neighbor).flatten()
                    f_score = tentative_g + np.linalg.norm(goal_np - neighbor_np)

                    heappush(open_set, (f_score, neighbor))

        if self.debug:
            print(f"[A*] No path found from {start} to {goal}.")
        return None
