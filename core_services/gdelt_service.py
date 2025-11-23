"""
GDELT Service - Pure business logic for GDELT DOC 2.0 API

This service provides GDELT news search functionality without Langflow dependencies.
Can be used by both Langflow components and MCP servers.
"""

from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import pandas as pd
import requests
import requests_cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
TIMELINE_MODES = {"timelinevol", "timelinevolraw", "timelinetone", "timelinelang", "timelinesourcecountry"}


class GDELTService:
    """GDELT DOC 2.0 API service for news search and timeline analysis."""
    
    @staticmethod
    def _make_session(use_cache: bool = True, cache_ttl: int = 300) -> requests.Session:
        """Create configured requests session with caching and retry logic."""
        expire = cache_ttl if use_cache else 0
        sess: requests.Session = requests_cache.CachedSession("gdelt_cache", expire_after=expire)
        retry = Retry(
            total=3,
            backoff_factor=1.2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD", "OPTIONS"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        sess.mount("https://", adapter)
        sess.mount("http://", adapter)
        sess.headers.update({"User-Agent": "Mozilla/5.0 (compatible; LangFlow-GDELT/1.0)"})
        return sess

    @staticmethod
    def _or_join(prefix: str, values: Optional[List[str]]) -> str:
        """Join list values with OR operator for GDELT query."""
        if not values:
            return ""
        parts = []
        for v in values:
            if v and v.strip():
                clean_v = v.strip()
                if " " in clean_v:
                    clean_v = clean_v.replace(" ", "")
                parts.append(f"{prefix}{clean_v}")
        if not parts:
            return ""
        return parts[0] if len(parts) == 1 else "(" + " OR ".join(parts) + ")"

    @staticmethod
    def _build_query(
        query: str,
        domains: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        countries: Optional[List[str]] = None
    ) -> str:
        """Build GDELT query string with filters."""
        base = (query or "").strip()
        q_parts = [base] if base else []
        q_parts += [GDELTService._or_join("domain:", domains)]
        q_parts += [GDELTService._or_join("sourcelang:", languages)]
        q_parts += [GDELTService._or_join("sourcecountry:", countries)]
        return " ".join([p for p in q_parts if p])

    @staticmethod
    def _normalize_artlist(payload: Dict[str, Any]) -> pd.DataFrame:
        """Normalize ArtList response to DataFrame."""
        arts = payload.get("articles", [])
        if not isinstance(arts, list):
            return pd.DataFrame([])
        rows = []
        for a in arts:
            if not isinstance(a, dict):
                continue
            rows.append(
                {
                    "title": a.get("title"),
                    "url": a.get("url"),
                    "seendate": a.get("seendate"),
                    "domain": a.get("domain"),
                    "language": a.get("language") or a.get("sourcelang"),
                    "sourcecountry": a.get("sourcecountry"),
                    # url_mobile, socialimage 제거 - 토큰 절약
                }
            )
        return pd.DataFrame(rows)

    @staticmethod
    def _normalize_timeline(payload: Dict[str, Any]) -> pd.DataFrame:
        """Normalize Timeline response to DataFrame."""
        tl = payload.get("timeline", [])
        if not isinstance(tl, list):
            return pd.DataFrame([])
        rows: List[Dict[str, Any]] = []
        for series_item in tl:
            if not isinstance(series_item, dict):
                continue
            series_name = series_item.get("series", "series")
            data_points = series_item.get("data", [])
            if isinstance(data_points, list):
                for dp in data_points:
                    if not isinstance(dp, dict):
                        continue
                    row = {"series": series_name, "date": dp.get("date"), "value": dp.get("value")}
                    for k, v in dp.items():
                        if k not in ("date", "value"):
                            row[k] = v
                    rows.append(row)
            else:
                row = {"series": series_name, "date": series_item.get("date")}
                for k in ("value", "volume", "count", "v"):
                    if k in series_item:
                        row["value"] = series_item[k]
                        break
                for k in ("language", "languages", "lang", "country", "countries", "sourcecountry", "counts"):
                    v = series_item.get(k)
                    if isinstance(v, dict):
                        for kk, vv in v.items():
                            row[str(kk)] = vv
                rows.append(row)
        return pd.DataFrame(rows)

    @staticmethod
    def search_news(
        query: str,
        mode: str = "ArtList", 
        maxrecords: int = 5,
        domains: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        countries: Optional[List[str]] = None,
        sort: str = "DateDesc",
        start_datetime: Optional[str] = None,
        end_datetime: Optional[str] = None,
        timespan: Optional[str] = None,
        timeline_smooth: int = 0,
        use_cache: bool = True,
        cache_ttl: int = 300,
        timeout: int = 25
    ) -> pd.DataFrame:
        """
        Search GDELT database for news articles or timeline data.
        
        Args:
            query: Search query string
            mode: Search mode (ArtList or timeline modes)
            maxrecords: Maximum number of records to return (1-250)
            domains: List of domain filters
            languages: List of language filters  
            countries: List of country filters
            sort: Sort order for ArtList mode
            start_datetime: Start datetime for search
            end_datetime: End datetime for search
            timespan: Timespan for search (alternative to datetime range)
            timeline_smooth: Smoothing parameter for timeline modes
            use_cache: Whether to use request caching
            cache_ttl: Cache TTL in seconds
            timeout: Request timeout in seconds
            
        Returns:
            DataFrame with search results
        """
        # Validate and normalize parameters
        maxrecords = min(max(1, int(maxrecords or 5)), 250)
        
        # Build query parameters
        params: Dict[str, Any] = {
            "mode": mode,
            "format": "json", 
            "query": GDELTService._build_query(query, domains, languages, countries),
        }

        if mode == "ArtList":
            params["maxrecords"] = maxrecords
            params["sort"] = sort
        elif mode in TIMELINE_MODES:
            smooth = int(timeline_smooth or 0)
            if smooth > 0:
                params["timelinesmooth"] = smooth

        # Add datetime parameters
        if start_datetime and end_datetime:
            params["STARTDATETIME"] = str(start_datetime).strip()
            params["ENDDATETIME"] = str(end_datetime).strip()
        elif timespan:
            params["TIMESPAN"] = str(timespan).strip()

        try:
            # Make API request
            sess = GDELTService._make_session(use_cache, cache_ttl)
            resp = sess.get(
                GDELT_ENDPOINT,
                params={k: v for k, v in params.items() if v not in (None, "", [])},
                timeout=timeout,
            )
            if not resp.ok:
                raise requests.RequestException(f"HTTP {resp.status_code}: {resp.text[:200]}")
            try:
                payload = resp.json()
            except ValueError:
                ctype = resp.headers.get("content-type", "unknown")
                raise requests.RequestException(f"Non-JSON response (Content-Type: {ctype})")
        except requests.RequestException as e:
            # Return error as DataFrame
            return pd.DataFrame([{"title": "Error", "url": "", "seendate": "", "domain": "", "summary": str(e)}])

        try:
            # Parse response based on mode
            if mode == "ArtList":
                df = GDELTService._normalize_artlist(payload)
            elif mode in TIMELINE_MODES:
                df = GDELTService._normalize_timeline(payload)
            else:
                df = pd.DataFrame([{"raw": payload}])

            if df is None or df.empty:
                return pd.DataFrame([{"message": "No results", "mode": mode}])

            df = df.head(maxrecords)
            return df
            
        except Exception as e:
            # Return error as DataFrame
            return pd.DataFrame([{"title": "Error", "url": "", "seendate": "", "domain": "", "summary": str(e)}])
