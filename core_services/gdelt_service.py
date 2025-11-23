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


# ==================== 상수 ====================

GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"

# 모드 매핑: 사용자 친화적 이름 → GDELT API 파라미터
MODE_MAPPING = {
    "Articles (기사 목록)": "ArtList",
    "Timeline - Volume (시간별 기사량)": "timelinevol",
    "Timeline - Sentiment (시간별 감성 변화)": "timelinetone",
    "Timeline - Language (언어별 분포)": "timelinelang",
    "Timeline - Country (국가별 분포)": "timelinesourcecountry",
}

# Timeline 모드 집합 (내부 API 값)
TIMELINE_MODES = {
    "timelinevol",
    "timelinevolraw",
    "timelinetone",
    "timelinelang",
    "timelinesourcecountry"
}

# 금융 미디어 도메인 (프리셋)
FINANCIAL_DOMAINS = [
    "reuters.com",
    "bloomberg.com",
    "ft.com",            # Financial Times
    "wsj.com",           # Wall Street Journal
    "cnbc.com",
    "marketwatch.com",
    "barrons.com",
    "seekingalpha.com",
    "investopedia.com",
    "fool.com",          # Motley Fool
]


class GDELTService:
    """GDELT DOC 2.0 API service for news search and timeline analysis."""
    
    @staticmethod
    def _make_session(use_cache: bool = True, cache_ttl: int = 300) -> requests.Session:
        """
        캐싱 및 Retry 정책이 적용된 HTTP 세션 생성
        
        Args:
            use_cache: 캐싱 사용 여부
            cache_ttl: 캐시 TTL (초)
            
        Returns:
            requests.Session: 설정이 적용된 HTTP 세션
        """
        expire = cache_ttl if use_cache else 0
        sess: requests.Session = requests_cache.CachedSession(
            "gdelt_cache", 
            expire_after=expire
        )
        
        # Retry 정책: 3회 재시도, 지수 백오프
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
        sess.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; Langflow-GDELT/2.0)"
        })
        
        return sess

    @staticmethod
    def _or_join(prefix: str, values: Optional[List[str]]) -> str:
        """
        리스트를 OR 조건으로 결합
        
        Args:
            prefix: 필터 접두사 (예: "domain:", "sourcelang:")
            values: 값 리스트
            
        Returns:
            str: 조합된 쿼리 문자열
            - 단일 값: "prefix:value" (괄호 없음)
            - 복수 값: "(prefix:a OR prefix:b)" (괄호 + OR)
            
        Examples:
            ["kor"] → "sourcelang:kor"
            ["eng", "kor"] → "(sourcelang:eng OR sourcelang:kor)"
        """
        if not values:
            return ""
        
        parts = [f"{prefix}{v.strip()}" for v in values if v and v.strip()]
        if not parts:
            return ""
        
        # GDELT 규칙: 괄호는 OR 조합에서만 사용
        return parts[0] if len(parts) == 1 else "(" + " OR ".join(parts) + ")"

    @staticmethod
    def _build_query(
        query: str,
        domains: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        countries: Optional[List[str]] = None,
        financial_media_only: bool = False
    ) -> str:
        """
        최종 검색 쿼리 문자열 생성 (도메인, 언어, 국가 필터 포함)
        
        Args:
            query: 기본 검색 쿼리
            domains: 도메인 필터 리스트
            languages: 언어 필터 리스트 (ISO 639-3)
            countries: 국가 필터 리스트 (FIPS)
            financial_media_only: 금융 미디어 프리셋 적용 여부
            
        Returns:
            str: GDELT API 호환 쿼리 문자열
            
        Examples:
            "NVIDIA" → "NVIDIA"
            "NVIDIA" + financial_media_only → "NVIDIA (domain:reuters.com OR ...)"
            "Samsung" + languages=["kor"] → "Samsung sourcelang:kor"
        """
        base = (query or "").strip()
        q_parts = [base] if base else []
        
        # 금융 미디어 프리셋 적용
        domains_to_use = domains
        if financial_media_only:
            if domains_to_use:
                # 기존 domains와 프리셋 병합 (중복 제거)
                domains_to_use = list(set(domains_to_use + FINANCIAL_DOMAINS))
            else:
                domains_to_use = FINANCIAL_DOMAINS
        
        # 필터 추가 (공백으로 연결)
        q_parts.append(GDELTService._or_join("domain:", domains_to_use))
        q_parts.append(GDELTService._or_join("sourcelang:", languages))
        q_parts.append(GDELTService._or_join("sourcecountry:", countries))
        
        return " ".join([p for p in q_parts if p])

    @staticmethod
    def _normalize_artlist(payload: Dict[str, Any]) -> pd.DataFrame:
        """
        ArtList 응답을 DataFrame으로 정규화
        
        Args:
            payload: GDELT API JSON 응답
            
        Returns:
            pd.DataFrame: 정규화된 기사 데이터
        """
        arts = payload.get("articles", [])
        if not isinstance(arts, list):
            return pd.DataFrame([])
        
        rows = []
        for a in arts:
            if not isinstance(a, dict):
                continue
            rows.append({
                "title": a.get("title"),
                "url": a.get("url"),
                "seendate": a.get("seendate"),
                "domain": a.get("domain"),
                "language": a.get("language") or a.get("sourcelang"),
                "sourcecountry": a.get("sourcecountry"),
                "tone": a.get("tone"),  # 감성 톤 추가
            })
        
        return pd.DataFrame(rows)

    @staticmethod
    def _normalize_timeline(payload: Dict[str, Any]) -> pd.DataFrame:
        """
        Timeline 응답을 DataFrame으로 정규화
        
        Args:
            payload: GDELT API JSON 응답
            
        Returns:
            pd.DataFrame: 정규화된 타임라인 데이터
        """
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
                    row = {
                        "series": series_name,
                        "date": dp.get("date"),
                        "value": dp.get("value")
                    }
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
    def _filter_by_tone(df: pd.DataFrame, tone_filter: str) -> pd.DataFrame:
        """
        감성 톤 기반 필터링 (Positive/Negative/Neutral)
        
        Args:
            df: 원본 DataFrame (tone 컬럼 포함)
            tone_filter: 필터 타입 ("All", "Positive", "Negative", "Neutral")
            
        Returns:
            pd.DataFrame: 필터링된 DataFrame
            
        Filter Rules:
            - Positive: tone > 5
            - Negative: tone < -5
            - Neutral: -5 <= tone <= 5
            - All: 필터링 안 함
        """
        if tone_filter == "All" or "tone" not in df.columns:
            return df
        
        # 톤 값을 숫자로 변환 (실패 시 0)
        df["tone_numeric"] = pd.to_numeric(df["tone"], errors="coerce").fillna(0)
        
        if tone_filter == "Positive":
            df = df[df["tone_numeric"] > 5]
        elif tone_filter == "Negative":
            df = df[df["tone_numeric"] < -5]
        elif tone_filter == "Neutral":
            df = df[(df["tone_numeric"] >= -5) & (df["tone_numeric"] <= 5)]
        
        # tone_numeric 컬럼 제거 (임시 컬럼)
        if "tone_numeric" in df.columns:
            df = df.drop(columns=["tone_numeric"])
        
        return df

    @staticmethod
    def search_news(
        query: str,
        mode: str = "ArtList", 
        maxrecords: int = 5,
        domains: Optional[List[str]] = None,
        languages: Optional[List[str]] = None,
        countries: Optional[List[str]] = None,
        financial_media_only: bool = False,
        tone_filter: str = "All",
        sort: str = "DateDesc",
        start_datetime: Optional[str] = None,
        end_datetime: Optional[str] = None,
        timespan: str = "7days",
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
            languages: List of language filters (ISO 639-3)
            countries: List of country filters (FIPS)
            financial_media_only: Apply financial media preset
            tone_filter: Sentiment filter ("All", "Positive", "Negative", "Neutral")
            sort: Sort order for ArtList mode
            start_datetime: Start datetime for search (YYYYMMDDHHMMSS)
            end_datetime: End datetime for search (YYYYMMDDHHMMSS)
            timespan: Timespan for search (e.g., "7days", default: "7days")
            timeline_smooth: Smoothing parameter for timeline modes
            use_cache: Whether to use request caching
            cache_ttl: Cache TTL in seconds
            timeout: Request timeout in seconds
            
        Returns:
            DataFrame with search results
        """
        # Validate and normalize parameters
        maxrecords = min(max(1, int(maxrecords or 5)), 250)
        
        # Resolve mode mapping
        api_mode = MODE_MAPPING.get(mode, mode)
        
        # Build query parameters
        params: Dict[str, Any] = {
            "mode": api_mode,
            "format": "json", 
            "query": GDELTService._build_query(
                query, domains, languages, countries, financial_media_only
            ),
        }

        # Articles 모드 전용 파라미터
        if api_mode == "ArtList":
            params["maxrecords"] = maxrecords
            params["sort"] = sort
        
        # Timeline 모드 전용 파라미터
        elif api_mode in TIMELINE_MODES:
            smooth = int(timeline_smooth or 0)
            if smooth > 0:
                params["timelinesmooth"] = smooth

        # 시간 범위 설정 (우선순위: 절대 시간 > 상대 시간)
        if start_datetime and end_datetime:
            params["STARTDATETIME"] = str(start_datetime).strip()
            params["ENDDATETIME"] = str(end_datetime).strip()
        elif timespan:
            params["TIMESPAN"] = str(timespan).strip()

        # 빈 값 제거
        params = {k: v for k, v in params.items() if v not in (None, "", [])}

        try:
            # Make API request
            sess = GDELTService._make_session(use_cache, cache_ttl)
            resp = sess.get(
                GDELT_ENDPOINT,
                params=params,
                timeout=timeout,
            )
            
            if not resp.ok:
                raise requests.RequestException(
                    f"HTTP {resp.status_code}: {resp.text[:200]}"
                )
            
            try:
                payload = resp.json()
            except ValueError:
                ctype = resp.headers.get("content-type", "unknown")
                raise requests.RequestException(
                    f"Non-JSON response (Content-Type: {ctype})"
                )
                
        except requests.RequestException as e:
            # Return error as DataFrame
            if api_mode == "ArtList":
                return pd.DataFrame([{
                    "title": "Error",
                    "url": "",
                    "seendate": "",
                    "domain": "",
                    "summary": str(e)
                }])
            else:
                return pd.DataFrame([{"message": "Error", "mode": api_mode, "error": str(e)}])

        try:
            # Parse response based on mode
            if api_mode == "ArtList":
                df = GDELTService._normalize_artlist(payload)
                # 감성 필터 적용
                df = GDELTService._filter_by_tone(df, tone_filter)
            elif api_mode in TIMELINE_MODES:
                df = GDELTService._normalize_timeline(payload)
            else:
                df = pd.DataFrame([{"raw": payload}])

            if df is None or df.empty:
                if api_mode == "ArtList":
                    return pd.DataFrame([{
                        "title": "No results",
                        "url": "",
                        "seendate": "",
                        "domain": "",
                        "summary": "No articles found"
                    }])
                else:
                    return pd.DataFrame([{"message": "No results", "mode": api_mode}])

            df = df.head(maxrecords)
            return df
            
        except Exception as e:
            # Return error as DataFrame
            if api_mode == "ArtList":
                return pd.DataFrame([{
                    "title": "Error",
                    "url": "",
                    "seendate": "",
                    "domain": "",
                    "summary": str(e)
                }])
            else:
                return pd.DataFrame([{"message": "Error", "mode": api_mode, "error": str(e)}])
