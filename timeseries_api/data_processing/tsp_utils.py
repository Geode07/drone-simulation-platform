import numpy as np
import networkx as nx
from scipy.spatial.distance import euclidean
from geopy.distance import geodesic


def compute_cost_matrix(waypoints, metric="euclidean"):
    """
    Compute the symmetric cost matrix between waypoints.
    - waypoints: list of (x, y) or (lat, lon) tuples
    - metric: 'euclidean' or 'geodesic'
    """
    n = len(waypoints)
    matrix = [[0.0] * n for _ in range(n)]

    for i in range(n):
        for j in range(i):
            if metric == "euclidean":
                dist = euclidean(waypoints[i], waypoints[j])
            elif metric == "geodesic":
                dist = geodesic(waypoints[i], waypoints[j]).meters
            else:
                raise ValueError("Unsupported metric")
            matrix[i][j] = matrix[j][i] = dist

    return matrix


def build_graph_from_matrix(cost_matrix):
    """
    Build a fully connected undirected graph from a cost matrix.
    """
    G = nx.Graph()
    n = len(cost_matrix)
    for i in range(n):
        for j in range(i):
            G.add_edge(i, j, weight=cost_matrix[i][j])
    return G


def solve_tsp_christofides(cost_matrix, debug=False):
    """
    Solve TSP using NetworkX's Christofides approximation.
    - Returns: tsp_tour (list of indices), total_cost (float)
    """
    if not hasattr(nx.algorithms.approximation, "christofides"):
        raise ImportError("Your networkx version does not include christofides. Upgrade to >=3.2.")

    G = build_graph_from_matrix(cost_matrix)
    tsp_tour = nx.algorithms.approximation.christofides(G)
    tour_cost = sum(
        cost_matrix[tsp_tour[i]][tsp_tour[i+1]] for i in range(len(tsp_tour) - 1)
    )
    tour_cost += cost_matrix[tsp_tour[-1]][tsp_tour[0]]  # complete cycle
    if debug:
        print(f"Found TSP tour: {tsp_tour}")
        print(f"Tour cost: {tour_cost:.2f}")
    return tsp_tour, tour_cost
