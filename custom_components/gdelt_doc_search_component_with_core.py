#!/usr/bin/env python3
"""
GDELT Doc Search Component (with Core Service) for Langflow

GDELT DOC 2.0 API를 통해 전 세계 뉴스를 실시간 검색하는 커스텀 컴포넌트.
core_services.gdelt_service를 활용한 버전.

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

from typing import List, Optional

from langflow.custom import Component
from langflow.io import (
    MessageTextInput,
    IntInput,
    BoolInput,
    DropdownInput,
    Output,
)
from langflow.schema import DataFrame

# Import core service
from core_services.gdelt_service import GDELTService


class GDELTDocSearchComponentWithCore(Component):
    """
    GDELT DOC 2.0 API 검색 컴포넌트 (Core Service 사용)
    
    전 세계 뉴스를 실시간 검색하고 감성 분석을 수행하는 Langflow 커스텀 컴포넌트입니다.
    core_services.GDELTService에 로직을 위임합니다.
    """
    
    display_name = "GDELT Doc Search (with Core)"
    description = """Search global news via GDELT DOC 2.0 API (using core_services).

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
    name = "GDELTDocSearchWithCore"

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

    # ==================== Public Methods ====================
    
    def search_gdelt(self) -> DataFrame:
        """
        GDELT API 검색 실행 (core_services.GDELTService 위임)
        
        Returns:
            DataFrame: 검색 결과
        """
        try:
            # Call core service
            df = GDELTService.search_news(
                query=self.query,
                mode=self.mode,
                maxrecords=self.maxrecords,
                domains=self.domains,
                languages=self.languages,
                countries=self.countries,
                financial_media_only=self.financial_media_only,
                tone_filter=self.tone_filter,
                sort=self.sort,
                start_datetime=self.start_datetime,
                end_datetime=self.end_datetime,
                timespan=self.timespan,
                timeline_smooth=self.timeline_smooth,
                use_cache=self.use_cache,
                cache_ttl=self.cache_ttl,
                timeout=self.timeout
            )
            
            return DataFrame(df)
            
        except Exception as e:
            # Return error as DataFrame
            return DataFrame([{
                "title": "Component Error",
                "url": "",
                "seendate": "",
                "domain": "",
                "summary": str(e)
            }])

