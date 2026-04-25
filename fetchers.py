import json
import urllib.request
import urllib.parse
from typing import List, Dict
from constants import SERPAPI_KEY
from utils import parse_hours_for_display

GPLAY_AVAILABLE = False
try:
    from google_play_scraper import search as gplay_search, reviews as gplay_reviews
    GPLAY_AVAILABLE = True
except Exception:
    pass

SERPAPI_PKG_AVAILABLE = False
try:
    from serpapi import GoogleSearch
    SERPAPI_PKG_AVAILABLE = True
except Exception:
    pass


class MapsDataFetcher:

    @staticmethod
    def fetch_places(product: str, location: str = "Ahmedabad") -> List[Dict]:
        query = f"{product} shop near {location}"
        params = urllib.parse.urlencode({
            "engine": "google_maps",
            "q": query,
            "type": "search",
            "api_key": SERPAPI_KEY,
            "hl": "en",
        })
        try:
            with urllib.request.urlopen(f"https://serpapi.com/search?{params}", timeout=25) as r:
                data = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            try:
                msg = json.loads(body).get("error", body)
            except Exception:
                msg = body
            raise RuntimeError(f"SerpApi HTTP {e.code}: {msg}")
        except Exception as e:
            raise RuntimeError(f"Network error: {e}")

        out = []
        for place in data.get("local_results", [])[:15]:
            lat = place.get("gps_coordinates", {}).get("latitude", "")
            lng = place.get("gps_coordinates", {}).get("longitude", "")
            open_now = place.get("open_now", None)
            bstatus = "OPERATIONAL" if open_now is True else "CLOSED" if open_now is False else "UNKNOWN"
            raw_type = place.get("type", [])
            shop_type = ", ".join(raw_type if isinstance(raw_type, list) else [raw_type or "Store"])[:50] or "Store"
            maps_link = place.get("link", "") or (
                "https://www.google.com/maps/search/" +
                urllib.parse.quote(place.get("title", "") + " " + location)
            )
            hours_raw = place.get("hours", [])
            hours_display = parse_hours_for_display(hours_raw)
            out.append({
                "name": place.get("title", "Unknown"),
                "type": shop_type,
                "rating": float(place.get("rating") or 0),
                "review_count": int(place.get("reviews") or 0),
                "price_label": place.get("price", "") or "N/A",
                "location": place.get("address", location),
                "lat": lat,
                "lng": lng,
                "maps_link": maps_link,
                "phone": place.get("phone", ""),
                "website": place.get("website", ""),
                "hours": hours_raw,
                "hours_display": hours_display,
                "open_now": open_now,
                "business_status": bstatus,
                "place_id": str(place.get("place_id", place.get("data_id", ""))),
                "market_share": 0,
                "reviews": [],
            })
        return out

    @staticmethod
    def fetch_reviews(place_id: str) -> List[Dict]:
        if not place_id:
            return []
        params = urllib.parse.urlencode({
            "engine": "google_maps_reviews",
            "place_id": place_id,
            "api_key": SERPAPI_KEY,
            "hl": "en",
            "sort_by": "ratingHigh",
        })
        try:
            with urllib.request.urlopen(f"https://serpapi.com/search?{params}", timeout=20) as r:
                return json.loads(r.read().decode()).get("reviews", [])
        except Exception:
            return []


class PlayStoreFetcher:

    @staticmethod
    def fetch(query: str, n_hits: int = 10, review_count: int = 15) -> List[Dict]:
        if not GPLAY_AVAILABLE:
            raise RuntimeError(
                "google_play_scraper is not installed.\n"
                "Run:  pip install google-play-scraper"
            )

        results = []
        seen_ids = set()
        for attempt in [query, f"{query} app", f"best {query}"]:
            try:
                hits = gplay_search(query=attempt, lang="en", country="in", n_hits=n_hits)
                for h in hits:
                    if h.get("appId") and h["appId"] not in seen_ids:
                        seen_ids.add(h["appId"])
                        results.append(h)
                if len(results) >= n_hits:
                    break
            except Exception:
                continue

        apps = []
        for i, r in enumerate(results[:n_hits]):
            try:
                revs_raw, _ = gplay_reviews(
                    app_id=r["appId"], lang="en", country="in", count=review_count
                )
                revs = [{"score": rv["score"], "content": rv["content"] or "",
                         "thumbsUpCount": rv.get("thumbsUpCount", 0)} for rv in revs_raw]
            except Exception:
                revs = []

            apps.append({
                "rank": i,
                "appTitle": r.get("title", "—"),
                "rating": float(r.get("score") or 0),
                "isFree": r.get("free", True),
                "price": r.get("price", 0),
                "genre": r.get("genre", "—"),
                "installs": r.get("installs", "—"),
                "appId": r["appId"],
                "reviews": revs,
            })
        return apps


class AmazonFetcher:

    @staticmethod
    def fetch(keyword: str) -> List[Dict]:
        if not SERPAPI_PKG_AVAILABLE:
            raise RuntimeError(
                "serpapi package not installed.\nRun:  pip install google-search-results"
            )
        results = GoogleSearch({
            "engine": "amazon",
            "amazon_domain": "amazon.in",
            "k": keyword,
            "api_key": SERPAPI_KEY,
        }).get_dict()
        products = []
        for p in results.get("organic_results", [])[:10]:
            price_raw = p.get("price", "")
            price_num = None
            if price_raw:
                try:
                    price_num = float(str(price_raw).replace("₹", "").replace(",", "").strip())
                except Exception:
                    pass
            products.append({
                "title": p.get("title", "—"),
                "price": price_raw or "N/A",
                "price_num": price_num,
                "rating": p.get("rating", "N/A"),
                "reviews": p.get("reviews", 0),
                "link": p.get("link", ""),
                "position": p.get("position", 0),
                "asin": p.get("asin", ""),
            })
        return products
