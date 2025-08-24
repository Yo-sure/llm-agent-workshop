from typing import Optional

import pandas as pd

from langflow.custom import Component
from core_services.google_news_service import GoogleNewsService
from langflow.io import IntInput, MessageTextInput, Output
from langflow.schema import DataFrame


class GoogleNewsRSSComponent(Component):
    display_name = "Google News RSS"
    description = "Google News RSS를 통한 뉴스 검색. 키워드/토픽/지역별 최신 뉴스를 DataFrame으로 반환."
    documentation: str = "https://developers.google.com/news"
    icon = "newspaper"
    name = "GoogleNewsRSS"

    inputs = [
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="뉴스 검색 키워드. 예: 'AI technology', 'climate change'",
            tool_mode=True,
            required=True,
        ),
        MessageTextInput(
            name="hl",
            display_name="Language (hl)",
            info="언어 코드. 예: en-US, ko-KR, ja-JP. 기본값: en-US",
            value="ko",
            required=False,
            advanced=True,
        ),
        MessageTextInput(
            name="gl",
            display_name="Country (gl)",
            info="국가 코드. 예: US, KR, JP. 기본값: US",
            value="KR",
            required=False,
            advanced=True,
        ),
        MessageTextInput(
            name="ceid",
            display_name="Country:Language (ceid)",
            info="국가:언어 조합. 예: US:en, KR:ko, JP:ja. 기본값: US:en",
            value="KR:ko",
            required=False,
            advanced=True,
        ),
        MessageTextInput(
            name="topic",
            display_name="Topic",
            info="토픽 카테고리: WORLD, NATION, BUSINESS, TECHNOLOGY, ENTERTAINMENT, SCIENCE, SPORTS, HEALTH",
            required=False,
            advanced=True,
        ),
        MessageTextInput(
            name="location",
            display_name="Location (Geo)",
            info="지역 기반 뉴스. 도시, 주, 국가명. 키워드 검색 대신 사용 시 입력",
            required=False,
            advanced=True,
        ),
        IntInput(
            name="max_results",
            display_name="Max Results",
            info="반환할 기사 수 제한 (1-100 권장)",
            value=5,
            required=False,
            advanced=False,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (sec)",
            info="요청 타임아웃 (초)",
            value=10,
            required=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="articles", display_name="News Articles", method="search_news")
    ]

    # Helper methods moved to GoogleNewsService

    def search_news(self) -> DataFrame:
        """Google News RSS 검색 실행"""
        try:
            # Call GoogleNewsService with parameters from component
            df = GoogleNewsService.search_news(
                query=getattr(self, "query", None),
                topic=getattr(self, "topic", None),
                location=getattr(self, "location", None),
                hl=getattr(self, "hl", "ko"),
                gl=getattr(self, "gl", "KR"),
                ceid=getattr(self, "ceid", "KR:ko"),
                max_results=getattr(self, "max_results", 5),
                timeout=getattr(self, "timeout", 10)
            )
            
            # Log the results
            if not df.empty and "title" in df.columns:
                if df.iloc[0]["title"] == "Error":
                    self.log(f"Google News request failed: {df.iloc[0].get('summary', 'Unknown error')}")
                else:
                    self.log(f"총 {len(df)}개 기사 반환 (max_results={getattr(self, 'max_results', 5)})")
            
            return DataFrame(df)
            
        except Exception as e:
            self.log(f"Google News service error: {e}")
            return DataFrame(pd.DataFrame([{
                "title": "Error", 
                "link": "", 
                "published": "", 
                "summary": str(e)
            }]))
