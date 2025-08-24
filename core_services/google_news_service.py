"""
Google News RSS Service - Pure business logic for Google News RSS API

This service provides Google News RSS functionality without Langflow dependencies.
Can be used by both Langflow components and MCP servers.
"""

from urllib.parse import quote_plus
from typing import List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup


class GoogleNewsService:
    """Google News RSS service for news search by keyword, topic, or location."""
    
    @staticmethod
    def _build_rss_url(
        query: Optional[str] = None,
        topic: Optional[str] = None,
        location: Optional[str] = None,
        hl: str = "en-US",
        gl: str = "US",
        ceid: Optional[str] = None
    ) -> str:
        """Build Google News RSS URL based on search parameters."""
        if not ceid:
            ceid = f"{gl}:{hl.split('-')[0]}"
        
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

    @staticmethod
    def _clean_html(html_string: str) -> str:
        """HTML 태그 제거 및 텍스트 정리"""
        if not html_string:
            return ""
        return BeautifulSoup(html_string, "html.parser").get_text(separator=" ", strip=True)

    @staticmethod
    def _parse_rss_items(items: list, max_results: int = 20) -> List[dict]:
        """RSS 아이템들을 파싱하여 딕셔너리 리스트로 변환"""
        articles = []
        max_results = min(max_results, len(items))
        
        for item in items[:max_results]:
            try:
                title = GoogleNewsService._clean_html(item.title.text if item.title else "")
                link = item.link.text if item.link else ""
                published = item.pubDate.text if item.pubDate else ""
                summary = GoogleNewsService._clean_html(item.description.text if item.description else "")
                
                # 빈 제목은 스킵
                if not title.strip():
                    continue
                    
                articles.append({
                    "title": title,
                    "link": link,
                    "published": published,
                    "summary": summary,
                })
            except Exception:
                # 개별 아이템 파싱 실패는 건너뛰기
                continue
                
        return articles

    @staticmethod
    def search_news(
        query: Optional[str] = None,
        topic: Optional[str] = None,
        location: Optional[str] = None,
        hl: str = "ko",
        gl: str = "KR", 
        ceid: str = "KR:ko",
        max_results: int = 5,
        timeout: int = 10
    ) -> pd.DataFrame:
        """
        Search Google News via RSS feed.
        
        Args:
            query: Search query string
            topic: Topic category (WORLD, NATION, BUSINESS, TECHNOLOGY, etc.)
            location: Geographic location for news
            hl: Language code (e.g., en-US, ko-KR)
            gl: Country code (e.g., US, KR)
            ceid: Country:Language combination (e.g., US:en, KR:ko)
            max_results: Maximum number of articles to return
            timeout: Request timeout in seconds
            
        Returns:
            DataFrame with news articles
        """
        try:
            rss_url = GoogleNewsService._build_rss_url(query, topic, location, hl, gl, ceid)
        except ValueError as e:
            return pd.DataFrame([{
                "title": "Error",
                "link": "",
                "published": "",
                "summary": str(e),
            }])

        try:
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
            return pd.DataFrame([{
                "title": "Error", 
                "link": "", 
                "published": "", 
                "summary": error_msg
            }])
        except Exception as e:
            error_msg = f"RSS 파싱 실패: {e}"
            return pd.DataFrame([{
                "title": "Error", 
                "link": "", 
                "published": "", 
                "summary": error_msg
            }])

        if not items:
            return pd.DataFrame([{
                "title": "No articles found", 
                "link": "", 
                "published": "", 
                "summary": "검색 결과가 없습니다."
            }])

        # 아이템들을 파싱
        articles = GoogleNewsService._parse_rss_items(items, max_results)
        
        if not articles:
            return pd.DataFrame([{
                "title": "No valid articles", 
                "link": "", 
                "published": "", 
                "summary": "유효한 기사를 찾을 수 없습니다."
            }])

        return pd.DataFrame(articles)
