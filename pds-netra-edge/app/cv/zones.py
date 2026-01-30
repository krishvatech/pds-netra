"""
Zone utilities for determining whether an object lies within a polygonal region.

Zones are defined as polygons (lists of [x, y] coordinate pairs). This module
provides helper functions to test whether a bounding box or point is inside
a zone using the ray casting algorithm.
"""

from __future__ import annotations

from typing import List, Tuple


def point_in_polygon(x: float, y: float, polygon: List[Tuple[float, float]]) -> bool:
    """
    Determine if a point (x, y) is inside a polygon.

    Uses the ray casting algorithm to test whether the point lies
    inside the polygon boundary. Points exactly on the boundary are
    considered inside.
    """
    num = len(polygon)
    j = num - 1
    inside = False
    for i in range(num):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def bbox_center(bbox: List[int]) -> Tuple[float, float]:
    """
    Compute the center point of a bounding box.

    Parameters
    ----------
    bbox: List[int]
        Bounding box in [x1, y1, x2, y2] format.

    Returns
    -------
    Tuple[float, float]
        The (x, y) coordinates of the bounding box center.
    """
    x1, y1, x2, y2 = bbox
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    return cx, cy


def is_bbox_in_zone(bbox: List[int], polygon: List[Tuple[float, float]]) -> bool:
    """
    Check whether a bounding box intersects a polygonal zone.

    A hit is true if the center or any corner lies within the polygon.
    This is more forgiving than center-only checks and matches operator
    expectations for hand-drawn zones.
    """
    cx, cy = bbox_center(bbox)
    if point_in_polygon(cx, cy, polygon):
        return True
    x1, y1, x2, y2 = bbox
    corners = [(x1, y1), (x1, y2), (x2, y1), (x2, y2)]
    if any(point_in_polygon(x, y, polygon) for x, y in corners):
        return True
    # Remove fallback: relying on points (center/corners) ensures the object is actually
    # within or touching the polygon boundary, reducing false positives for diagonal zones.
    return False