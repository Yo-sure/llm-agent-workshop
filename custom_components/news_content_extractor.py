#!/usr/bin/env python3
"""
News Content Extractor Component for LangFlow

뉴스 웹사이트에서 깨끗한 기사 본문을 추출하는 전문 컴포넌트.
네비게이션, 광고, 기타 불필요한 요소들을 제거합니다.
"""

import re
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup

from langflow.custom import Component
from langflow.io import (
    MessageTextInput,
    IntInput,
    BoolInput,
    Output,
)
from langflow.schema import DataFrame


class NewsContentExtractorComponent(Component):
    """뉴스 본문 추출 컴포넌트"""
    
    display_name = "News Content Extractor"
    description = "Extract clean article content from news websites, removing navigation, ads, and unwanted elements."
    documentation: str = "https://docs.langflow.org/components-custom"
    icon = "newspaper"
    name = "NewsContentExtractor"

    # ==================== 클래스 상수 ====================
    
    # 제거할 요소 선택자들
    UNWANTED_SELECTORS = [
        'nav', 'header', 'footer',  # 페이지 구조 요소
        '.nav', '.navigation', '.menu',  # 네비게이션 클래스
        '.ad', '.advertisement', '.ads',  # 광고
        '.social', '.share', '.sharing',  # 소셜 공유
        '.sidebar', '.related', '.recommended',  # 사이드바, 관련 기사
        '.comments', '.comment',  # 댓글
        'script', 'style', 'noscript',  # 스크립트, 스타일
        '.subscribe', '.newsletter',  # 구독 관련
        '.breadcrumb', '.breadcrumbs',  # 브레드크럼
        '.cookie', '.privacy',  # 쿠키/개인정보 고지
        '.popup', '.modal',  # 팝업, 모달
    ]
    
    # 본문 영역 선택자들 (우선순위순)
    CONTENT_SELECTORS = [
        'article',  # HTML5 article 태그
        '.article-body', '.article-content',  # 일반적인 기사 본문 클래스
        '.story-body', '.story-content',  # 스토리 본문
        '.post-content', '.post-body',  # 포스트 컨텐츠
        '.content', '.main-content',  # 메인 컨텐츠
        '[data-module="ArticleBody"]',  # CNBC 전용
        '.ArticleBody-articleBody',  # CNBC 전용
        '[itemprop="articleBody"]',  # Schema.org 마크업
        '.entry-content',  # WordPress 기본
        '.news-content', '.news-body',  # 뉴스 전용
    ]
    
    # 제거할 텍스트 패턴들
    UNWANTED_TEXT_PATTERNS = [
        r'Skip Navigation.*?(?=\w)',  # Skip Navigation
        r'Subscribe.*?(?=\w)',  # Subscribe 관련
        r'Share.*?(?=\w)',  # Share 버튼
        r'Follow.*?(?=\w)',  # Follow 버튼
        r'Sign up.*?(?=\w)',  # Sign up
        r'Cookie.*?(?=\w)',  # Cookie 고지
        r'Privacy.*?(?=\w)',  # Privacy 고지
    ]
    
    # RSS URL 패턴
    RSS_PATTERNS = ("/rss", "rss.", ".rss")

    # ==================== Langflow 설정 ====================
    
    inputs = [
        MessageTextInput(
            name="urls",
            display_name="URLs",
            info="Enter one or more news article URLs to extract content from.",
            is_list=True,
            tool_mode=True,
            placeholder="Enter a news URL...",
            list_add_label="Add URL",
            required=True,
        ),
        IntInput(
            name="max_content_length",
            display_name="Max Content Length",
            info="Maximum length of extracted content per article (characters).",
            value=5000,
            advanced=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (sec)",
            info="Request timeout in seconds.",
            value=15,
            advanced=True,
        ),
        BoolInput(
            name="include_metadata",
            display_name="Include Metadata",
            info="If enabled, includes page title and other metadata.",
            value=True,
            advanced=True,
        ),
        BoolInput(
            name="remove_short_paragraphs",
            display_name="Remove Short Paragraphs",
            info="If enabled, filters out paragraphs shorter than 50 characters.",
            value=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="extracted_content", display_name="Extracted Content", method="extract_content"),
    ]

    # ==================== Private 헬퍼 메서드들 ====================
    
    @staticmethod
    def _is_rss_url(url: str) -> bool:
        """RSS/Feed URL인지 확인"""
        return any(pattern.lower() in url.lower() for pattern in NewsContentExtractorComponent.RSS_PATTERNS)
    
    @staticmethod
    def _normalize_urls(urls: Any) -> List[str]:
        """다양한 입력 형식의 URL을 리스트로 정규화"""
        if isinstance(urls, list):
            return [url.strip() for url in urls if url.strip()]
        elif isinstance(urls, str):
            return [url.strip() for url in urls.split('\n') if url.strip()]
        return []
    
    @staticmethod
    def _create_error_response(url: str, error_msg: str) -> Dict[str, Any]:
        """표준 에러 응답 생성"""
        return {
            'url': url,
            'title': 'Error' if url else '',
            'description': '',
            'content': error_msg,
            'content_length': 0,
            'paragraphs_count': 0,
            'success': False,
            'error': error_msg
        }

    def _extract_metadata(self, soup: BeautifulSoup) -> Dict[str, str]:
        """페이지 메타데이터 추출 (제목, 설명)"""
        if not self.include_metadata:
            return {'title': '', 'description': ''}
        
        title = ''
        description = ''
        
        # 페이지 제목 추출
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text().strip()
        
        # 메타 설명 추출
        desc_tag = soup.find('meta', attrs={'name': 'description'}) or \
                   soup.find('meta', attrs={'property': 'og:description'})
        if desc_tag:
            description = desc_tag.get('content', '').strip()
        
        return {'title': title, 'description': description}

    def _remove_unwanted_elements(self, soup: BeautifulSoup) -> None:
        """불필요한 HTML 요소 제거 (in-place)"""
        for selector in self.UNWANTED_SELECTORS:
            for element in soup.select(selector):
                element.decompose()

    def _find_main_content(self, soup: BeautifulSoup) -> BeautifulSoup:
        """본문 영역 찾기 (우선순위 기반)"""
        # 본문 영역 선택자로 순차 탐색
        for selector in self.CONTENT_SELECTORS:
            elements = soup.select(selector)
            if elements:
                return elements[0]
        
        # Fallback: body 또는 전체
        return soup.find('body') or soup

    def _clean_text(self, text: str) -> str:
        """텍스트 정리 (공백, 불필요한 패턴 제거)"""
        # 연속 공백 제거
        text = re.sub(r'\s+', ' ', text)
        
        # 불필요한 텍스트 패턴 제거
        for pattern in self.UNWANTED_TEXT_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        return text.strip()

    def _filter_paragraphs(self, paragraphs: List[str]) -> List[str]:
        """짧거나 의미 없는 문단 필터링"""
        if not self.remove_short_paragraphs:
            return paragraphs
        
        filtered = []
        for p in paragraphs:
            # 길이 체크 및 일반적인 비본문 제외
            if (len(p) > 50 and 
                not p.startswith(('Copyright', '©', 'Terms', 'Privacy', 'Contact')) and
                not p.lower().startswith(('click', 'tap', 'swipe', 'scroll'))):
                filtered.append(p)
        
        return filtered

    def _apply_length_limit(self, content: str) -> str:
        """최대 길이 제한 적용"""
        if len(content) > self.max_content_length:
            return content[:self.max_content_length] + '...'
        return content

    def _extract_clean_news_content(self, html_content: str, url: str = "") -> Dict[str, Any]:
        """HTML에서 깨끗한 기사 본문 추출 (메인 로직)"""
        soup = BeautifulSoup(html_content, 'lxml')
        
        # 1. 메타데이터 추출
        metadata = self._extract_metadata(soup)
        
        # 2. 불필요한 요소 제거
        self._remove_unwanted_elements(soup)
        
        # 3. 본문 영역 찾기
        main_content = self._find_main_content(soup)
        
        # 4. 텍스트 추출 및 정리
        raw_text = main_content.get_text(separator=' ', strip=True)
        clean_text = self._clean_text(raw_text)
        
        # 5. 문단 분리 및 필터링
        paragraphs = [p.strip() for p in clean_text.split('\n') if p.strip()]
        filtered_paragraphs = self._filter_paragraphs(paragraphs)
        
        # 6. 문단 합치기 및 길이 제한
        content = '\n\n'.join(filtered_paragraphs)
        content = self._apply_length_limit(content)
        
        return {
            'url': url,
            'title': metadata['title'],
            'description': metadata['description'],
            'content': content,
            'content_length': len(content),
            'paragraphs_count': len(filtered_paragraphs),
        }

    def _fetch_url_content(self, url: str) -> Dict[str, Any]:
        """단일 URL에서 컨텐츠 가져오기"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; NewsContentExtractor/1.0)',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            # 본문 추출
            result = self._extract_clean_news_content(response.content, url)
            result['success'] = True
            result['error'] = None
            
            return result
            
        except requests.RequestException as e:
            return self._create_error_response(url, str(e))
        except Exception as e:
            return self._create_error_response(url, f"Extraction error: {str(e)}")

    # ==================== Public API ====================
    
    def extract_content(self) -> DataFrame:
        """설정된 모든 URL에서 컨텐츠 추출 (메인 진입점)"""
        
        # URL 입력 정규화
        urls = self._normalize_urls(self.urls)
        
        # RSS URL 체크
        rss_urls = [u for u in urls if self._is_rss_url(u)]
        if rss_urls:
            return DataFrame([self._create_error_response(
                rss_urls[0], 
                f"RSS/Feed 링크는 지원하지 않습니다: {rss_urls[0]}"
            )])
        
        # 빈 URL 체크
        if not urls:
            return DataFrame([self._create_error_response('', 'No valid URLs provided')])
        
        # 각 URL 처리
        results = []
        for url in urls:
            self.log(f"Processing: {url}")
            result = self._fetch_url_content(url)
            results.append(result)
        
        # 요약 로그
        successful = sum(1 for r in results if r['success'])
        self.log(f"Processed {len(results)} URLs, {successful} successful")
        
        return DataFrame(results)


# ==================== 독립 실행 테스트 ====================

if __name__ == "__main__":
    # 컴포넌트 테스트
    extractor = NewsContentExtractorComponent()
    extractor.urls = [
        "https://www.cnbc.com/2025/08/22/stocks-making-the-biggest-moves-premarket-nvda-intu-wday-rost.html"
    ]
    extractor.max_content_length = 2000
    extractor.timeout = 15
    extractor.include_metadata = True
    extractor.remove_short_paragraphs = True
    
    try:
        result = extractor.extract_content()
        print("=== 뉴스 본문 추출 테스트 ===")
        
        # DataFrame 데이터 접근
        if hasattr(result, 'data'):
            data = result.data
        else:
            data = result.to_dict('records') if hasattr(result, 'to_dict') else []
        
        print(f"결과: {len(data)}개 기사")
        
        if data:
            first_result = data[0]
            print(f"제목: {first_result.get('title', 'No title')}")
            print(f"성공: {first_result.get('success', False)}")
            print(f"본문 길이: {first_result.get('content_length', 0)}자")
            print(f"본문 미리보기: {first_result.get('content', '')[:200]}...")
            
    except Exception as e:
        print(f"테스트 실패: {e}")
        import traceback
        traceback.print_exc()
