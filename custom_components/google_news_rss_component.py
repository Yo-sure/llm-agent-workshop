from urllib.parse import quote_plus
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

from langflow.custom import Component
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

    def _build_rss_url(self) -> str:
        """RSS URL 구성"""
        hl = getattr(self, "hl", None) or "en-US"
        gl = getattr(self, "gl", None) or "US"
        ceid = getattr(self, "ceid", None) or f"{gl}:{hl.split('-')[0]}"
        topic = getattr(self, "topic", None)
        location = getattr(self, "location", None)
        query = getattr(self, "query", None)

        # 우선순위: topic > location > query
        if topic:
            base_url = f"https://news.google.com/rss/headlines/section/topic/{quote_plus(topic.upper())}"
            params = f"?hl={hl}&gl={gl}&ceid={ceid}"
            return base_url + params
        elif location:
            base_url = f"https://news.google.com/rss/headlines/section/geo/{quote_plus(location)}"
            params = f"?hl={hl}&gl={gl}&ceid={ceid}"
            return base_url + params
        elif query:
            base_url = "https://news.google.com/rss/search?q="
            query_encoded = quote_plus(query)
            params = f"&hl={hl}&gl={gl}&ceid={ceid}"
            return f"{base_url}{query_encoded}{params}"
        else:
            raise ValueError("query, topic, 또는 location 중 하나는 필수입니다.")

    def _clean_html(self, html_string: str) -> str:
        """HTML 태그 제거 및 텍스트 정리"""
        if not html_string:
            return ""
        return BeautifulSoup(html_string, "html.parser").get_text(separator=" ", strip=True)

    def _parse_rss_items(self, items: list) -> list:
        """RSS 아이템들을 파싱하여 딕셔너리 리스트로 변환"""
        articles = []
        max_results = min(getattr(self, "max_results", 20), len(items))
        
        for item in items[:max_results]:
            try:
                title = self._clean_html(item.title.text if item.title else "")
                link = item.link.text if item.link else ""
                published = item.pubDate.text if item.pubDate else ""
                summary = self._clean_html(item.description.text if item.description else "")
                
                # 빈 제목은 스킵
                if not title.strip():
                    continue
                    
                articles.append({
                    "title": title,
                    "link": link,
                    "published": published,
                    "summary": summary,
                })
            except Exception as e:
                # 개별 아이템 파싱 실패는 로그만 남기고 계속 진행
                self.log(f"아이템 파싱 실패: {e}")
                continue
                
        return articles

    def search_news(self) -> DataFrame:
        """Google News RSS 검색 실행"""
        try:
            rss_url = self._build_rss_url()
        except ValueError as e:
            return DataFrame(pd.DataFrame([{
                "title": "Error",
                "link": "",
                "published": "",
                "summary": str(e),
            }]))

        try:
            timeout = getattr(self, "timeout", 10)
            response = requests.get(
                rss_url, 
                timeout=timeout,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; LangFlow-GoogleNews/1.0)'}
            )
            response.raise_for_status()
            
            # XML 파싱
            soup = BeautifulSoup(response.content, "xml")
            items = soup.find_all("item")
            
        except requests.RequestException as e:
            error_msg = f"RSS 요청 실패: {e}"
            self.log(error_msg)
            return DataFrame(pd.DataFrame([{
                "title": "Error", 
                "link": "", 
                "published": "", 
                "summary": error_msg
            }]))
        except Exception as e:
            error_msg = f"RSS 파싱 실패: {e}"
            self.log(error_msg)
            return DataFrame(pd.DataFrame([{
                "title": "Error", 
                "link": "", 
                "published": "", 
                "summary": error_msg
            }]))

        if not items:
            return DataFrame(pd.DataFrame([{
                "title": "No articles found", 
                "link": "", 
                "published": "", 
                "summary": "검색 결과가 없습니다."
            }]))

        # 아이템들을 파싱
        articles = self._parse_rss_items(items)
        
        if not articles:
            return DataFrame(pd.DataFrame([{
                "title": "No valid articles", 
                "link": "", 
                "published": "", 
                "summary": "유효한 기사를 찾을 수 없습니다."
            }]))

        df_articles = pd.DataFrame(articles)
        self.log(f"총 {len(df_articles)}개 기사 반환 (max_results={getattr(self, 'max_results', 20)})")
        
        return DataFrame(df_articles)
