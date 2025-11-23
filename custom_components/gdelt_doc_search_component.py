#!/usr/bin/env python3
"""
GDELT Doc Search Component for Langflow

GDELT DOC 2.0 API를 통해 전 세계 뉴스를 실시간 검색하는 커스텀 컴포넌트.

주요 기능:
- Articles 모드: 뉴스 기사 목록 검색 (title, url, domain, tone 등)
- Timeline 모드: 시계열 트렌드 분석 (기사량, 감성, 언어/국가 분포)
- 금융 미디어 프리셋: Reuters, Bloomberg 등 10개 금융 매체
- 감성 필터링: Positive/Negative/Neutral 톤 기반 필터
- 다국어 지원: 65개 언어 검색 (ISO 639-3 코드)

권장 사항:
- 영문 키워드 사용 (예: "Samsung SDS", "NVIDIA")
- 한글 키워드는 검색 결과가 거의 없음 (글로벌 뉴스 중심)
"""

from typing import Any, Dict, List, Optional

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


class GDELTDocSearchComponent(Component):
    """
    GDELT DOC 2.0 API 검색 컴포넌트
    
    전 세계 뉴스를 실시간 검색하고 감성 분석을 수행하는 Langflow 커스텀 컴포넌트입니다.
    """
    
    display_name = "GDELT Doc Search"
    description = """Search global news via GDELT DOC 2.0 API.

IMPORTANT: Use ENGLISH keywords for best results!
   Korean/non-English keywords rarely return results (global news focus).

Basic Usage:
   • query: English keywords ("Samsung SDS", "NVIDIA", "Tesla")
   • mode: "Articles" (news list) or "Timeline" (trend analysis)
   • maxrecords: 5-20 recommended for LLM agents

Financial Analysis:
   • financial_media_only=True → Reuters, Bloomberg, WSJ, etc. (10 sources)
   • tone_filter=Positive → bullish news only
   • tone_filter=Negative → risk monitoring

Advanced Filters:
   • languages: ISO 639-3 codes (eng, kor, jpn, zho)
   • countries: FIPS codes (US, KS=Korea, JA=Japan, CH=China)

Examples:
   1. Basic: "Samsung SDS" → finds all articles (incl. Korean articles!)
   2. Bullish: "NVIDIA" + financial_media_only + tone_filter=Positive
   3. Risk: "Tesla recall" + tone_filter=Negative + timespan=7days

📊 Returns: DataFrame with title, url, domain, language, country, tone"""
    documentation: str = "https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/"
    icon = "globe"
    name = "GDELTDocSearch"

    # ==================== 클래스 상수 ====================
    
    # GDELT API 엔드포인트
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
    
    # 에러 응답 컬럼 (내부 API 모드 기준)
    ERROR_COLUMNS = {
        "ArtList": ["title", "url", "seendate", "domain", "summary"],
        "timeline": ["message", "mode"],
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
    
    # 알려진 기업명 정규화 맵 (붙여쓰기 → 띄어쓰기)
    COMPANY_NAME_NORMALIZATION = {
        "samsungsds": "Samsung SDS",
        "skhynix": "SK Hynix",
        "sktelekom": "SK Telecom",
        "lgelectronics": "LG Electronics",
        "lgenergy": "LG Energy",
        "navercloud": "Naver Cloud",
        "kakaocorp": "Kakao Corp",
    }

    # ==================== Langflow 설정 ====================
    
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
        BoolInput(
            name="financial_media_only",
            display_name="Financial Media Only",
            info="금융 미디어만 검색 (Reuters, Bloomberg, WSJ 등)",
            value=False,
            advanced=True,
        ),
        MessageTextInput(
            name="languages",
            display_name="Languages",
            info="언어 필터 (ISO 639-3, 3자리). 예: eng, kor, jpn, zho",
            is_list=True,
            advanced=True,
        ),
        MessageTextInput(
            name="countries",
            display_name="Source Countries",
            info="발행국가 (FIPS 2자리). 예: US, KS, JA, CH",
            is_list=True,
            advanced=True,
        ),
        DropdownInput(
            name="mode",
            display_name="Mode",
            options=[
                "Articles (기사 목록)",
                "Timeline - Volume (시간별 기사량)",
                "Timeline - Sentiment (시간별 감성 변화)",
                "Timeline - Language (언어별 분포)",
                "Timeline - Country (국가별 분포)"
            ],
            value="Articles (기사 목록)",
            info="검색 모드: 기사 목록을 받을지, 시계열 트렌드 데이터를 받을지 선택",
            tool_mode=True,
            required=True,
        ),
        MessageTextInput(
            name="timespan",
            display_name="TIMESPAN",
            info="예: 24hours, 7days, 14days, 30days (미지정 시: 7days)",
            value="7days",
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
        DropdownInput(
            name="tone_filter",
            display_name="Sentiment Filter",
            options=["All", "Positive", "Negative", "Neutral"],
            value="All",
            info="감성 톤으로 필터링 (Positive: >5, Negative: <-5, Neutral: -5~5)",
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="articles", display_name="Results", method="search_gdelt"),
    ]

    # ==================== Private Methods ====================
    
    def _make_session(self) -> requests.Session:
        """
        캐싱 및 Retry 정책이 적용된 HTTP 세션 생성
        
        Returns:
            requests.Session: 설정이 적용된 HTTP 세션
        """
        expire = self.cache_ttl if self.use_cache else 0
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

    def _or_join(self, prefix: str, values: Optional[List[str]]) -> str:
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

    def _normalize_company_name(self, query: str) -> str:
        """
        알려진 기업명을 GDELT 친화적 형식으로 정규화
        
        Args:
            query: 원본 검색어
            
        Returns:
            str: 정규화된 검색어
            
        Examples:
            "SamsungSDS" → "Samsung SDS"
            "skhynix" → "SK Hynix"
            "NVIDIA" → "NVIDIA" (변경 없음)
        """
        query_lower = query.lower().strip()
        
        # 정규화 맵에서 찾기
        if query_lower in self.COMPANY_NAME_NORMALIZATION:
            return self.COMPANY_NAME_NORMALIZATION[query_lower]
        
        return query
    
    def _build_query(self) -> str:
        """
        최종 검색 쿼리 문자열 생성 (도메인, 언어, 국가 필터 포함)
        
        Returns:
            str: GDELT API 호환 쿼리 문자열
            
        Examples:
            "NVIDIA" → "NVIDIA"
            "SamsungSDS" → "Samsung SDS" (정규화)
            "NVIDIA" + financial_media_only → "NVIDIA (domain:reuters.com OR ...)"
            "Samsung" + languages=["kor"] → "Samsung sourcelang:kor"
        """
        # 기업명 정규화
        normalized_query = self._normalize_company_name(self.query or "")
        base = normalized_query.strip()
        q_parts = [base] if base else []
        
        # 금융 미디어 프리셋 적용
        domains_to_use = self.domains
        if self.financial_media_only:
            if domains_to_use:
                # 기존 domains와 프리셋 병합 (중복 제거)
                domains_to_use = list(set(domains_to_use + self.FINANCIAL_DOMAINS))
            else:
                domains_to_use = self.FINANCIAL_DOMAINS
        
        # 필터 추가 (공백으로 연결)
        q_parts.append(self._or_join("domain:", domains_to_use))
        q_parts.append(self._or_join("sourcelang:", self.languages))
        q_parts.append(self._or_join("sourcecountry:", self.countries))
        
        return " ".join([p for p in q_parts if p])
    
    def _get_api_mode(self) -> str:
        """
        사용자 친화적 모드명을 GDELT API 모드로 변환
        
        Returns:
            str: GDELT API 모드 ("ArtList", "timelinevol", etc.)
        """
        return self.MODE_MAPPING.get(self.mode, "ArtList")

    def _build_api_params(self) -> Dict[str, Any]:
        """
        GDELT API 호출 파라미터 구성
        
        Returns:
            Dict[str, Any]: API 호출용 파라미터 딕셔너리
        """
        api_mode = self._get_api_mode()
        maxrecords = min(max(1, int(self.maxrecords or 5)), 250)
        
        params: Dict[str, Any] = {
            "mode": api_mode,
            "format": "json",
            "query": self._build_query(),
        }

        # Articles 모드 전용 파라미터
        if api_mode == "ArtList":
            params["maxrecords"] = maxrecords
            params["sort"] = self.sort
        
        # Timeline 모드 전용 파라미터
        elif api_mode in self.TIMELINE_MODES:
            smooth = int(self.timeline_smooth or 0)
            if smooth > 0:
                params["timelinesmooth"] = smooth

        # 시간 범위 설정 (우선순위: 절대 시간 > 상대 시간)
        if self.start_datetime and self.end_datetime:
            params["STARTDATETIME"] = str(self.start_datetime).strip()
            params["ENDDATETIME"] = str(self.end_datetime).strip()
        elif self.timespan:
            params["TIMESPAN"] = str(self.timespan).strip()

        # 빈 값 제거
        return {k: v for k, v in params.items() if v not in (None, "", [])}

    def _fetch_gdelt_api(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        GDELT API 호출 및 JSON 응답 반환
        
        Args:
            params: API 호출 파라미터
            
        Returns:
            Dict[str, Any]: JSON 응답 데이터
            
        Raises:
            requests.RequestException: API 오류 (HTTP 에러, HTML 응답 등)
        """
        sess = self._make_session()
        
        resp = sess.get(
            self.GDELT_ENDPOINT,
            params=params,
            timeout=self.timeout,
        )
        
        if not resp.ok:
            raise requests.RequestException(
                f"HTTP {resp.status_code}: {resp.text[:200]}"
            )
        
        try:
            payload = resp.json()
            
            # 빈 JSON {} 체크 (검색 결과 없음)
            if not payload or (isinstance(payload, dict) and not payload):
                self.log("GDELT API returned empty JSON - no results found")
            
            return payload
            
        except ValueError as e:
            ctype = resp.headers.get("content-type", "unknown")
            
            # HTML 응답 = GDELT 에러 메시지
            if "text/html" in ctype:
                error_msg = resp.text.strip()
                
                # 짧은 키워드 에러 (2글자 이하)
                if "too short" in error_msg.lower():
                    raise requests.RequestException(
                        'GDELT 오류: 검색어가 너무 짧습니다. '
                        '2글자 키워드는 따옴표로 묶으세요 (예: "SK Hynix")'
                    ) from e
                
                # 괄호 사용 오류
                elif "parentheses" in error_msg.lower():
                    raise requests.RequestException(
                        'GDELT 오류: 괄호는 OR 조합에만 사용 가능합니다.'
                    ) from e
                
                # 기타 GDELT 에러
                else:
                    raise requests.RequestException(
                        f"GDELT 오류: {error_msg[:100]}. "
                        "한글 키워드는 영문으로 변환하세요 (예: '삼성SDS' → 'Samsung SDS')"
                    ) from e
            else:
                raise requests.RequestException(
                    f"Non-JSON response (Content-Type: {ctype})"
                ) from e

    def _normalize_artlist(self, payload: Dict[str, Any]) -> pd.DataFrame:
        """
        Articles 모드 응답을 DataFrame으로 변환
        
        Args:
            payload: GDELT API JSON 응답
            
        Returns:
            pd.DataFrame: 기사 목록 (title, url, domain, language, tone 등)
        """
        # 빈 payload 체크
        if not payload:
            return pd.DataFrame([])
        
        arts = payload.get("articles", [])
        if not isinstance(arts, list):
            return pd.DataFrame([])
        
        rows = []
        for article in arts:
            if not isinstance(article, dict):
                continue
            
            # 기본 정보
            row = {
                "title": article.get("title"),
                "url": article.get("url"),
                "seendate": article.get("seendate"),
                "domain": article.get("domain"),
                "language": article.get("language") or article.get("sourcelang"),
                "sourcecountry": article.get("sourcecountry"),
            }
            
            # 감성 톤 추가 (GDELT 2.0 GKG에서 제공)
            if "tone" in article:
                row["tone"] = article.get("tone")
            
            rows.append(row)
        
        return pd.DataFrame(rows)

    def _normalize_timeline(self, payload: Dict[str, Any]) -> pd.DataFrame:
        """
        Timeline 모드 응답을 DataFrame으로 변환
        
        Args:
            payload: GDELT API JSON 응답
            
        Returns:
            pd.DataFrame: 시계열 데이터 (series, date, value 등)
        """
        timeline = payload.get("timeline", [])
        if not isinstance(timeline, list):
            return pd.DataFrame([])
        
        rows: List[Dict[str, Any]] = []
        
        for series_item in timeline:
            if not isinstance(series_item, dict):
                continue
            
            series_name = series_item.get("series", "series")
            data_points = series_item.get("data", [])
            
            # 데이터 포인트가 리스트인 경우
            if isinstance(data_points, list):
                for dp in data_points:
                    if not isinstance(dp, dict):
                        continue
                    
                    row = {
                        "series": series_name,
                        "date": dp.get("date"),
                        "value": dp.get("value")
                    }
                    
                    # 추가 필드 복사
                    for k, v in dp.items():
                        if k not in ("date", "value"):
                            row[k] = v
                    
                    rows.append(row)
            
            # 단일 데이터 포인트인 경우
            else:
                row = {
                    "series": series_name,
                    "date": series_item.get("date")
                }
                
                # value 필드 찾기
                for key in ("value", "volume", "count", "v"):
                    if key in series_item:
                        row["value"] = series_item[key]
                        break
                
                # 중첩된 딕셔너리 필드 펼치기
                for key in ("language", "languages", "lang", "country", 
                           "countries", "sourcecountry", "counts"):
                    value = series_item.get(key)
                    if isinstance(value, dict):
                        for k, v in value.items():
                            row[str(k)] = v
                
                rows.append(row)
        
        return pd.DataFrame(rows)

    def _filter_by_tone(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        감성 톤 기반 필터링 (Positive/Negative/Neutral)
        
        Args:
            df: 원본 DataFrame (tone 컬럼 포함)
            
        Returns:
            pd.DataFrame: 필터링된 DataFrame
            
        Filter Rules:
            - Positive: tone > 5
            - Negative: tone < -5
            - Neutral: -5 <= tone <= 5
            - All: 필터링 안 함
        """
        if self.tone_filter == "All" or "tone" not in df.columns:
            return df
        
        # 톤 값을 숫자로 변환 (실패 시 0)
        df["tone_numeric"] = pd.to_numeric(df["tone"], errors="coerce").fillna(0)
        
        if self.tone_filter == "Positive":
            df = df[df["tone_numeric"] > 5]
        elif self.tone_filter == "Negative":
            df = df[df["tone_numeric"] < -5]
        elif self.tone_filter == "Neutral":
            df = df[(df["tone_numeric"] >= -5) & (df["tone_numeric"] <= 5)]
        
        # tone_numeric 컬럼 제거 (임시 컬럼)
        if "tone_numeric" in df.columns:
            df = df.drop(columns=["tone_numeric"])
        
        return df
    
    def _parse_response(self, payload: Dict[str, Any]) -> pd.DataFrame:
        """
        모드에 따라 API 응답 파싱
        
        Args:
            payload: GDELT API JSON 응답
            
        Returns:
            pd.DataFrame: 파싱된 데이터
        """
        api_mode = self._get_api_mode()
        
        if api_mode == "ArtList":
            df = self._normalize_artlist(payload)
            # 감성 필터 적용
            df = self._filter_by_tone(df)
            return df
        elif api_mode in self.TIMELINE_MODES:
            return self._normalize_timeline(payload)
        else:
            # 알 수 없는 모드는 원본 반환
            return pd.DataFrame([{"raw": payload}])

    @staticmethod
    def _create_error_response(error_msg: str, mode: str = "ArtList") -> DataFrame:
        """
        에러 발생 시 표준 에러 응답 DataFrame 생성
        
        Args:
            error_msg: 에러 메시지
            mode: GDELT API 모드
            
        Returns:
            DataFrame: 에러 정보가 포함된 DataFrame
        """
        if mode == "ArtList":
            return DataFrame(pd.DataFrame([{
                "title": "Error",
                "url": "",
                "seendate": "",
                "domain": "",
                "summary": error_msg
            }]))
        else:
            return DataFrame(pd.DataFrame([{
                "message": error_msg,
                "mode": mode
            }]))

    # ==================== Public API ====================
    
    def search_gdelt(self) -> DataFrame:
        """
        GDELT 검색 실행 (메인 진입점)
        
        이 메서드는 Langflow에서 자동으로 호출됩니다.
        
        Returns:
            DataFrame: 검색 결과 또는 에러 정보
            
        Process:
            1. API 파라미터 구성 (_build_api_params)
            2. GDELT API 호출 (_fetch_gdelt_api)
            3. 응답 파싱 (_parse_response)
            4. 감성 필터링 적용 (Articles 모드)
            5. 결과 수 제한 (maxrecords)
        """
        api_mode = self._get_api_mode()
        maxrecords = min(max(1, int(self.maxrecords or 5)), 250)
        
        try:
            # 1. API 파라미터 구성
            params = self._build_api_params()
            
            # 2. API 호출
            payload = self._fetch_gdelt_api(params)
            
            # 3. 응답 파싱
            df = self._parse_response(payload)
            
            # 4. 빈 결과 체크
            if df is None or df.empty:
                return self._create_error_response("No results", api_mode)
            
            # 5. 레코드 수 제한
            df = df.head(maxrecords)
            
            return DataFrame(df)
            
        except requests.RequestException as e:
            self.log(f"GDELT API 요청 실패: {e}")
            return self._create_error_response(str(e), api_mode)
        
        except Exception as e:
            self.log(f"GDELT 응답 파싱 실패: {e}")
            return self._create_error_response(f"Parsing error: {str(e)}", api_mode)


# ==================== 독립 실행 테스트 ====================

if __name__ == "__main__":
    """
    독립 실행 테스트
    
    Usage:
        python custom_components/gdelt_doc_search_component.py
    """
    print("="*70)
    print("GDELT Doc Search Component - 테스트")
    print("="*70)
    
    # 컴포넌트 초기화
    component = GDELTDocSearchComponent()
    
    # 테스트 설정: 금융 미디어에서 NVIDIA 긍정 뉴스 검색
    component.query = "NVIDIA"
    component.mode = "Articles (기사 목록)"
    component.maxrecords = 5
    component.timespan = "7days"
    component.financial_media_only = True
    component.tone_filter = "Positive"
    component.use_cache = False
    component.timeout = 25
    
    print(f"\n검색 조건:")
    print(f"  - Query: {component.query}")
    print(f"  - Mode: {component.mode}")
    print(f"  - Financial Media Only: {component.financial_media_only}")
    print(f"  - Tone Filter: {component.tone_filter}")
    print(f"  - Max Records: {component.maxrecords}")
    print(f"  - Timespan: {component.timespan}")
    
    try:
        print(f"\n🔍 검색 중...")
        result = component.search_gdelt()
        
        # DataFrame 데이터 접근
        if hasattr(result, 'data'):
            data = result.data
        else:
            data = result.to_dict('records') if hasattr(result, 'to_dict') else []
        
        print(f"\n✅ 검색 완료: {len(data)}개 기사")
        
        if data:
            print(f"\n📰 첫 번째 기사:")
            first = data[0]
            print(f"  제목: {first.get('title', 'No title')[:80]}")
            print(f"  URL: {first.get('url', 'No URL')}")
            print(f"  도메인: {first.get('domain', 'No domain')}")
            if 'tone' in first:
                print(f"  감성 톤: {first.get('tone')} (긍정적)")
        else:
            print("\n⚠️ 검색 결과 없음")
            
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*70)
