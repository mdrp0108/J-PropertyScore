import time, random, requests
from typing import Tuple, Optional, Dict, Any

def get_json_with_retries(
    url: str, headers: Optional[Dict[str,str]] = None, timeout: float = 10.0,
    retries: int = 3, backoff: float = 0.6, session: Optional[requests.Session] = None
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """HTTP GET → JSON。指数バックオフ＋ジッタでリトライ。メタ情報を返す。"""
    s = session or requests.Session()
    attempt = 0
    last_exc = None
    meta = {"attempts": 0, "http_status": None, "status": "ok", "error": None, "url": url}
    while attempt < retries:
        try:
            r = s.get(url, headers=headers, timeout=timeout)
            meta["http_status"] = r.status_code
            if r.status_code == 200:
                meta["attempts"] = attempt + 1
                return r.json(), meta
            if r.status_code in (429, 500, 502, 503, 504):
                # 再試行対象
                sleep_s = backoff * (2**attempt) + random.random() * 0.3
                time.sleep(sleep_s)
                attempt += 1
                continue
            # 非再試行（404等）
            meta.update({"status":"http_error", "attempts":attempt+1, "error":f"HTTP {r.status_code}"})
            return None, meta
        except requests.RequestException as e:
            last_exc = e
            sleep_s = backoff * (2**attempt) + random.random() * 0.3
            time.sleep(sleep_s)
            attempt += 1
    meta.update({"status":"network_error", "error":str(last_exc), "attempts":attempt})
    return None, meta
