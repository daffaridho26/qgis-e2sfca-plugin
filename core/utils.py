"""
utils.py
---------
Input validation and conversion of geometries to points.
"""

# Representative point methods for polygons
POINT_ON_SURFACE = "pointOnSurface"   # default: always inside the polygon
CENTROID = "centroid"                 # geometric center, may fall outside the polygon


class InputError(Exception):
    """Input data error that must be fixed by the user."""