import math
from shapely.geometry import shape, Point

EARTH_R = 6371000.0  # meters

def latlon_to_tile(lat: float, lon: float, z: int):
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    return z, x, y

def haversine_m(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return 2 * EARTH_R * math.asin(math.sqrt(a))

def point_in_polygons(lat, lon, features):
    p = Point(lon, lat)
    for f in features or []:
        g = f.get("geometry")
        if not g: 
            continue
        geom = shape(g)
        if not geom.is_empty and geom.geom_type in ("Polygon", "MultiPolygon") and geom.contains(p):
            return f
    return None

def in_japan_bbox(lat: float, lon: float) -> bool:
    # ざっくり：東経122–154／北緯20–46（離島簡略）
    return 20.0 <= lat <= 46.0 and 122.0 <= lon <= 154.0
