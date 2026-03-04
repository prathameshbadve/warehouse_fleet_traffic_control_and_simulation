"""
Hungarian Solver for Bipartite assignment
"""

from typing import List


def hungarian_solver(cost: List[List[float]]) -> List[int]:
    """
    Hungarian algorithm for rectangular assignment reduced to square matrix.
    Expects cost is square: n x n.
    Returns assignment p where p[i] = j means row i assigned to col j.

    Implementation uses potentials (u, v) with 1-indexed arrays (classic).
    """

    n = len(cost)

    # 1 indexed
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    p = [0] * (n + 1)  # p[j] = i matched to column j
    way = [0] * (n + 1)

    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [float("inf")] * (n + 1)
        used = [False] * (n + 1)

        while True:
            used[j0] = True
            i0 = p[j0]
            delta = float("inf")
            j1 = 0

            for j in range(1, n + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j

            for j in range(0, n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta

            j0 = j1
            if p[j0] == 0:
                break

        # augmenting
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break

    # build row-col assignment
    assignment = [-1] * n
    for j in range(1, n + 1):
        i = p[j]
        assignment[i - 1] = j - 1

    return assignment
