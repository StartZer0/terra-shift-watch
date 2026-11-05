"""User-drawn boundaries, normalized into the bounded local equal-area grid."""
import math
from pyproj import CRS, Transformer
from shapely.geometry import Polygon


def normalize_polygon(points, resolution):
    if not 3 <= len(points) <= 65:
        raise ValueError('Draw a boundary with 3–64 corners.')
    ring = [list(p) for p in points]
    if ring[0] == ring[-1]:
        ring.pop()
    if not 3 <= len(ring) <= 64:
        raise ValueError('A boundary needs at least three distinct corners.')
    for point in ring:
        if len(point) != 2 or not all(math.isfinite(v) for v in point):
            raise ValueError('Boundary coordinates must be longitude, latitude pairs.')
        if not -180 <= point[0] <= 180 or not -89 <= point[1] <= 89:
            raise ValueError('Boundary coordinates lie outside the supported globe range.')
    # Circular mean keeps a small boundary crossing the date line local.
    lon = math.degrees(math.atan2(sum(math.sin(math.radians(p[0])) for p in ring),
                                 sum(math.cos(math.radians(p[0])) for p in ring)))
    lat = sum(p[1] for p in ring) / len(ring)
    crs = CRS.from_proj4(f'+proj=laea +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs')
    forward = Transformer.from_crs('EPSG:4326', crs, always_xy=True)
    projected = [forward.transform(*point) for point in ring]
    geometry = Polygon(projected)
    if not geometry.is_valid or geometry.is_empty:
        raise ValueError('Boundary lines cross or form an invalid polygon. Redraw the corners in order.')
    if geometry.area < 4 * resolution ** 2:
        raise ValueError('Draw an area covering at least four analysis cells, or choose smaller cells.')
    reach = max(abs(v) for point in projected for v in point)
    side_km = max(1., (2 * reach + 2 * resolution) / 1000)
    if not math.isfinite(side_km) or side_km > 500:
        raise ValueError('The drawn boundary exceeds the local 500 km analysis extent.')
    return ring + [ring[0]], lon, lat, side_km, geometry.area / 1e6
