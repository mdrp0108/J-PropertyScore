import os, sys, json, time
import requests
from typing import Tuple, Dict, Any, List, Optional
from utils_geo import latlon_to_tile, haversine_m, point_in_polygons, in_japan_bbox
from utils_http import get_json_with_retries

API_KEY = os.environ.get("REINFOLIB_API_KEY","").strip()
HEADERS = {"Ocp-Apim-Subscription-Key": API_KEY} if API_KEY else {}
BASE = "https://www.reinfolib.mlit.go.jp/ex-api/external"

def _nearest_point(lat: float, lon: float, features: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str,Any]], float]:
    best, best_d = None, 1e18
    for f in features or []:
        g = f.get("geometry") or {}
        coords = g.get("coordinates")
        if not coords: 
            continue
        flon, flat = coords[0], coords[1]
        d = haversine_m(lat, lon, flat, flon)
        if d < best_d:
            best, best_d = f, d
    return best, best_d

def query_landprice(lat: float, lon: float, year: int, session: requests.Session) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """当年→前年→… 5年までフォールバック。"""
    for k in range(0, 5):
        y = year - k
        z, x, ytile = latlon_to_tile(lat, lon, 15)
        url = f"{BASE}/XPT002?response_format=geojson&z={z}&x={x}&y={ytile}&year={y}"
        gj, meta = get_json_with_retries(url, headers=HEADERS, session=session)
        if not gj:
            # 続行（次の年にフォールバック） or 最後なら失敗を返す
            if k < 4: 
                continue
            return {"available": False, "year": year, "error": meta}, meta
        feat, dist = _nearest_point(lat, lon, gj.get("features"))
        if feat:
            p = feat.get("properties", {})
            return ({
                "available": True,
                "distance_m": round(dist,1),
                "point_id": p.get("point_id"),
                "year": p.get("target_year_name_ja"),
                "price_yen_per_m2": p.get("u_current_years_price_ja"),
                "yoy_rate": p.get("year_on_year_change_rate"),
                "use": p.get("use_category_name_ja"),
                "raw": p
            }, meta)
    # 到達しない想定
    return {"available": False, "year": year}, {"status":"unknown"}

def query_zoning(lat: float, lon: float, session: requests.Session) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    z, x, y = latlon_to_tile(lat, lon, 15)
    url = f"{BASE}/XKT002?response_format=geojson&z={z}&x={x}&y={y}"
    gj, meta = get_json_with_retries(url, headers=HEADERS, session=session)
    if not gj:
        return {"available": False, "error": meta}, meta
    feat = point_in_polygons(lat, lon, gj.get("features"))
    if not feat:
        return {"available": False}, meta
    p = feat.get("properties", {})
    return {"available": True, "zone": p.get("kubun_id") or p.get("area_classification_ja"), "raw": p}, meta

def query_station(lat: float, lon: float, session: requests.Session) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    z, x, y = latlon_to_tile(lat, lon, 15)
    url = f"{BASE}/XKT015?response_format=geojson&z={z}&x={x}&y={y}"
    gj, meta = get_json_with_retries(url, headers=HEADERS, session=session)
    if not gj:
        return {"available": False, "error": meta}, meta
    feat, dist = _nearest_point(lat, lon, gj.get("features"))
    if not feat:
        return {"available": False}, meta
    p = feat.get("properties", {})
    return ({
        "available": True,
        "name": p.get("S12_001_ja"),
        "operator": p.get("S12_002_ja"),
        "line": p.get("S12_003_ja"),
        "distance_m": round(dist,1),
        "walk_min": int(round(dist/80.0)),
        "raw": p
    }, meta)

def dynamic_score(land: Dict[str, Any], st: Dict[str, Any], zone: Dict[str, Any]) -> Dict[str, Any]:
    """利用可能な要素だけで重みを再正規化してスコアする（0–100）。"""
    import math
    parts = []
    # 地価（対数スケール）
    if land.get("available") and land.get("price_yen_per_m2"):
        try:
            v = float(str(land["price_yen_per_m2"]).replace(",", ""))
            s_price = min(1.0, (math.log1p(v) - math.log(1e3)) / (math.log(2e6) - math.log(1e3)))
            parts.append(("price", s_price, 0.5))
        except Exception:
            pass
    # 駅距離（2kmで0点）
    if st.get("available") and st.get("distance_m") is not None:
        d = max(1.0, float(st["distance_m"]))
        s_walk = max(0.0, 1.0 - d/2000.0)
        parts.append(("walk", s_walk, 0.35))
    # 用途（簡易ウェイト）
    if zone.get("available"):
        zkey = (zone.get("zone") or "").strip()
        s_zone = {"05":1.0, "00":0.8, "07":0.7, "09":0.6}.get(zkey, 0.7)
        parts.append(("zone", s_zone, 0.15))

    if not parts:
        return {"score": None, "breakdown": {}, "note":"no_signals"}

    # 利用可能な要素の重みを再正規化
    w_sum = sum(w for _,_,w in parts)
    score01 = sum(s * (w/w_sum) for _, s, w in parts)
    return {"score": round(score01*100,1), "breakdown": {k: s for k,s,_ in parts}}

def run(lat: float, lon: float, year: int):
    t0 = time.time()
    if not in_japan_bbox(lat, lon):
        return {
            "ok": False,
            "error": "out_of_range",
            "message": "lat/lng is outside Japan rough bbox (E122–154, N20–46)."
        }

    if not API_KEY:
        return {"ok": False, "error": "missing_api_key", "message": "REINFOLIB_API_KEY is not set."}

    s = requests.Session()
    land, m1 = query_landprice(lat, lon, year, s)
    st, m2 = query_station(lat, lon, s)
    zone, m3 = query_zoning(lat, lon, s)
    sc = dynamic_score(land, st, zone)

    warnings = []
    sources = {
        "landprice": m1, "station": m2, "zoning": m3
    }
    for name, meta in sources.items():
        if meta.get("status") not in (None, "ok"):
            warnings.append(f"{name}:{meta.get('status')} ({meta.get('http_status')})")

    return {
        "ok": True,
        "input": {"lat": lat, "lon": lon, "year": year},
        "asset_score": sc,
        "landprice": land,
        "station": st,
        "zoning": zone,
        "sources": sources,
        "warnings": warnings,
        "elapsed_ms": int((time.time()-t0)*1000)
    }

if __name__ == "__main__":
    # 使い方: python -m src.score_pipeline_stable 35.68 139.76 2024
    lat = float(sys.argv[1]); lon = float(sys.argv[2])
    year = int(sys.argv[3]) if len(sys.argv) > 3 else 2024
    out = run(lat, lon, year)
    print(json.dumps(out, ensure_ascii=False, indent=2))
