from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import pandas as pd
import requests
import requests_cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from langflow.custom import Component
from langflow.io import (
    MessageTextInput,
    IntInput,
    BoolInput,
    DropdownInput,
    Output,
)
from langflow.schema import DataFrame


GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
TIMELINE_MODES = {"timelinevol", "timelinevolraw", "timelinetone", "timelinelang", "timelinesourcecountry"}


class GDELTDocSearchComponent(Component):
    display_name = "GDELT Doc Search"
    description = "Searches global news via GDELT DOC 2.0. Supports ArtList & Timeline* modes."
    documentation: str = "https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/"
    icon = "globe"
    name = "GDELTDocSearch"

    inputs = [
        MessageTextInput(
            name="query",
            display_name="Query",
            info='예) ("NVDA" OR "NVIDIA"), (A OR B) AND C. 복잡한 쿼리는 직접 괄호 사용',
            tool_mode=True,
            required=True,
        ),
        MessageTextInput(
            name="domains",
            display_name="Domains",
            info="도메인 필터. 예: reuters.com, bloomberg.com",
            is_list=True,
            advanced=True,
        ),
        MessageTextInput(
            name="languages",
            display_name="Languages",
            info="언어 필터. 예: English, Korean",
            is_list=True,
            advanced=True,
        ),
        MessageTextInput(
            name="countries",
            display_name="Source Countries",
            info="발행국가(FIPS 2-letter). 예: US, KR",
            is_list=True,
            advanced=True,
        ),
        DropdownInput(
            name="mode",
            display_name="Mode",
            options=["ArtList", "timelinevol", "timelinevolraw", "timelinetone", "timelinelang", "timelinesourcecountry"],
            value="ArtList",
            tool_mode=True,
            required=True,
        ),
        MessageTextInput(
            name="timespan",
            display_name="TIMESPAN",
            info="예: 24hours, 7days, 14days (start/end 대신 사용)",
            advanced=True,
        ),
        MessageTextInput(
            name="start_datetime",
            display_name="STARTDATETIME",
            info="YYYYMMDDHHMMSS (timespan 대신 사용)",
            advanced=True,
        ),
        MessageTextInput(
            name="end_datetime",
            display_name="ENDDATETIME",
            info="YYYYMMDDHHMMSS (timespan 대신 사용)",
            advanced=True,
        ),
        IntInput(
            name="maxrecords",
            display_name="Max Records",
            info="1~250 (LLM Tool 사용시 5~20 권장)",
            value=5,
            advanced=False,
        ),
        DropdownInput(
            name="sort",
            display_name="Sort (ArtList)",
            options=["DateDesc", "DateAsc"],
            value="DateDesc",
            advanced=True,
        ),
        IntInput(
            name="timeline_smooth",
            display_name="Timeline Smooth",
            info="Timeline 전용. 0=off",
            value=0,
            advanced=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (sec)",
            value=25,
            advanced=True,
        ),
        BoolInput(
            name="use_cache",
            display_name="Use Cache",
            value=True,
            advanced=True,
        ),
        IntInput(
            name="cache_ttl",
            display_name="Cache TTL (sec)",
            value=300,
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="articles", display_name="Results", method="search_gdelt"),
    ]

    # ------------- internal helpers -------------
    def _make_session(self) -> requests.Session:
        expire = getattr(self, "cache_ttl", 300) if getattr(self, "use_cache", True) else 0
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

    def _or_join(self, prefix: str, values: Optional[List[str]]) -> str:
        if not values:
            return ""
        parts = [f"{prefix}{v.strip()}" for v in values if v and v.strip()]
        if not parts:
            return ""
        return parts[0] if len(parts) == 1 else "(" + " OR ".join(parts) + ")"

    def _build_query(self) -> str:
        base = (getattr(self, "query", "") or "").strip()
        q_parts = [base] if base else []
        q_parts += [self._or_join("domain:", getattr(self, "domains", None))]
        q_parts += [self._or_join("sourcelang:", getattr(self, "languages", None))]
        q_parts += [self._or_join("sourcecountry:", getattr(self, "countries", None))]
        return " ".join([p for p in q_parts if p])

    def _normalize_artlist(self, payload: Dict[str, Any]) -> pd.DataFrame:
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

    def _normalize_timeline(self, payload: Dict[str, Any]) -> pd.DataFrame:
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

    # ------------- public method -------------
    def search_gdelt(self) -> DataFrame:
        mode = getattr(self, "mode", "ArtList")
        maxrecords = min(max(1, int(getattr(self, "maxrecords", 5) or 5)), 250)

        params: Dict[str, Any] = {
            "mode": mode,
            "format": "json",
            "query": self._build_query(),
        }

        if mode == "ArtList":
            params["maxrecords"] = maxrecords
            params["sort"] = getattr(self, "sort", "DateDesc")
        elif mode in TIMELINE_MODES:
            smooth = int(getattr(self, "timeline_smooth", 0) or 0)
            if smooth > 0:
                params["timelinesmooth"] = smooth

        start_dt = getattr(self, "start_datetime", None)
        end_dt = getattr(self, "end_datetime", None)
        timespan = getattr(self, "timespan", None)
        if start_dt and end_dt:
            params["STARTDATETIME"] = str(start_dt).strip()
            params["ENDDATETIME"] = str(end_dt).strip()
        elif timespan:
            params["TIMESPAN"] = str(timespan).strip()

        try:
            sess = self._make_session()
            resp = sess.get(
                GDELT_ENDPOINT,
                params={k: v for k, v in params.items() if v not in (None, "", [])},
                timeout=getattr(self, "timeout", 25),
            )
            if not resp.ok:
                raise requests.RequestException(f"HTTP {resp.status_code}: {resp.text[:200]}")
            try:
                payload = resp.json()
            except ValueError:
                ctype = resp.headers.get("content-type", "unknown")
                raise requests.RequestException(f"Non-JSON response (Content-Type: {ctype})")
        except requests.RequestException as e:
            self.log(f"GDELT request failed: {e}")
            return DataFrame(pd.DataFrame([{"title": "Error", "url": "", "seendate": "", "domain": "", "summary": str(e)}]))

        try:
            if mode == "ArtList":
                df = self._normalize_artlist(payload)
            elif mode in TIMELINE_MODES:
                df = self._normalize_timeline(payload)
            else:
                df = pd.DataFrame([{"raw": payload}])

            if df is None or df.empty:
                return DataFrame(pd.DataFrame([{"message": "No results", "mode": mode}]))

            df = df.head(maxrecords)

            return DataFrame(df)
        except Exception as e:
            self.log(f"GDELT parse failed: {e}")
            return DataFrame(pd.DataFrame([{"title": "Error", "url": "", "seendate": "", "domain": "", "summary": str(e)}]))
