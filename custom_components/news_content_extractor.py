#!/usr/bin/env python3
"""
News Content Extractor Component for LangFlow

A specialized component that extracts clean article content from news websites,
removing navigation, ads, and other unwanted elements.
"""

import re
from typing import Any, Dict, List, Optional

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
from langflow.helpers.data import safe_convert


class NewsContentExtractorComponent(Component):
    display_name = "News Content Extractor"
    description = "Extract clean article content from news websites, removing navigation, ads, and unwanted elements."
    documentation: str = "https://docs.langflow.org/components-custom"
    icon = "newspaper"
    name = "NewsContentExtractor"

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

    def _extract_clean_news_content(self, html_content: str, url: str = "") -> Dict[str, Any]:
        """Extract clean article content from HTML"""
        
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Extract metadata first
        title = ""
        description = ""
        
        if self.include_metadata:
            # Try to get page title
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text().strip()
            
            # Try to get meta description
            desc_tag = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
            if desc_tag:
                description = desc_tag.get('content', '').strip()
        
        # 1. Remove unwanted elements
        unwanted_selectors = [
            'nav', 'header', 'footer',  # Page structure elements
            '.nav', '.navigation', '.menu',  # Navigation classes
            '.ad', '.advertisement', '.ads',  # Ads
            '.social', '.share', '.sharing',  # Social sharing
            '.sidebar', '.related', '.recommended',  # Sidebar, related articles
            '.comments', '.comment',  # Comments
            'script', 'style', 'noscript',  # Scripts, styles
            '.subscribe', '.newsletter',  # Subscription related
            '.breadcrumb', '.breadcrumbs',  # Breadcrumbs
            '.cookie', '.privacy',  # Cookie/privacy notices
            '.popup', '.modal',  # Popups and modals
        ]
        
        for selector in unwanted_selectors:
            for element in soup.select(selector):
                element.decompose()
        
        # 2. Find main content area (news site patterns)
        content_selectors = [
            'article',  # HTML5 article tag
            '.article-body', '.article-content',  # Common article body classes
            '.story-body', '.story-content',  # Story body
            '.post-content', '.post-body',  # Post content
            '.content', '.main-content',  # Main content
            '[data-module="ArticleBody"]',  # CNBC specific
            '.ArticleBody-articleBody',  # CNBC specific
            '[itemprop="articleBody"]',  # Schema.org markup
            '.entry-content',  # WordPress default
            '.news-content', '.news-body',  # News specific
        ]
        
        main_content = None
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                main_content = elements[0]
                break
        
        # 3. Fallback to body if no main content found
        if not main_content:
            main_content = soup.find('body') or soup
        
        # 4. Extract and clean text
        text = main_content.get_text(separator=' ', strip=True)
        
        # 5. Text post-processing
        # Remove consecutive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove unwanted patterns
        unwanted_patterns = [
            r'Skip Navigation.*?(?=\w)',  # Skip Navigation
            r'Subscribe.*?(?=\w)',  # Subscribe related
            r'Share.*?(?=\w)',  # Share buttons
            r'Follow.*?(?=\w)',  # Follow buttons
            r'Sign up.*?(?=\w)',  # Sign up
            r'Cookie.*?(?=\w)',  # Cookie notices
            r'Privacy.*?(?=\w)',  # Privacy notices
        ]
        
        for pattern in unwanted_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # 6. Split into paragraphs and filter
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        
        if self.remove_short_paragraphs:
            # Filter out very short paragraphs and common non-content
            filtered_paragraphs = []
            for p in paragraphs:
                if (len(p) > 50 and 
                    not p.startswith(('Copyright', '©', 'Terms', 'Privacy', 'Contact')) and
                    not p.lower().startswith(('click', 'tap', 'swipe', 'scroll'))):
                    filtered_paragraphs.append(p)
            paragraphs = filtered_paragraphs
        
        # 7. Join paragraphs and apply length limit
        clean_content = '\n\n'.join(paragraphs)
        
        if len(clean_content) > self.max_content_length:
            clean_content = clean_content[:self.max_content_length] + '...'
        
        return {
            'url': url,
            'title': title,
            'description': description,
            'content': clean_content,
            'content_length': len(clean_content),
            'paragraphs_count': len(paragraphs),
        }

    def _fetch_url_content(self, url: str) -> Dict[str, Any]:
        """Fetch content from a single URL"""
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
            
            # Extract content
            result = self._extract_clean_news_content(response.content, url)
            result['success'] = True
            result['error'] = None
            
            return result
            
        except requests.RequestException as e:
            return {
                'url': url,
                'title': '',
                'description': '',
                'content': '',
                'content_length': 0,
                'paragraphs_count': 0,
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            return {
                'url': url,
                'title': '',
                'description': '',
                'content': '',
                'content_length': 0,
                'paragraphs_count': 0,
                'success': False,
                'error': f"Extraction error: {str(e)}"
            }

    def extract_content(self) -> DataFrame:
        """Extract content from all configured URLs"""
        
        # Handle both list and string inputs
        if isinstance(self.urls, list):
            urls = [url.strip() for url in self.urls if url.strip()]
        elif isinstance(self.urls, str):
            urls = [url.strip() for url in self.urls.split('\n') if url.strip()]
        else:
            urls = []
        
        rss_patterns = ("/rss", "rss.", ".rss")
        rss_urls = [u for u in urls if any(p.lower() in u.lower() for p in rss_patterns)]
        if rss_urls:
            return DataFrame([{
                'url': rss_urls[0],
                'title': 'Error',
                'description': '',
                'content': f"RSS/Feed 링크는 지원하지 않습니다: {rss_urls[0]}",
                'content_length': 0,
                'paragraphs_count': 0,
                'success': False,
                'error': 'RSS URLs are not supported'
            }])
        # ----------------------------------

        if not urls:
            return DataFrame([{
                'url': '',
                'title': 'Error',
                'description': '',
                'content': 'No valid URLs provided',
                'content_length': 0,
                'paragraphs_count': 0,
                'success': False,
                'error': 'No URLs provided'
            }])
        
        # Process each URL
        results = []
        for url in urls:
            self.log(f"Processing: {url}")
            result = self._fetch_url_content(url)
            results.append(result)
        
        # Log summary
        successful = sum(1 for r in results if r['success'])
        self.log(f"Processed {len(results)} URLs, {successful} successful")
        
        return DataFrame(results)


# For standalone testing
if __name__ == "__main__":
    # Test the component
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
        print("=== News Content Extraction Test ===")
        
        # DataFrame의 실제 데이터에 접근
        if hasattr(result, 'data'):
            data = result.data
        else:
            data = result.to_dict('records') if hasattr(result, 'to_dict') else []
        
        print(f"Results: {len(data)} articles")
        
        if data:
            first_result = data[0]
            print(f"Title: {first_result.get('title', 'No title')}")
            print(f"Success: {first_result.get('success', False)}")
            print(f"Content length: {first_result.get('content_length', 0)}")
            print(f"Content preview: {first_result.get('content', '')[:200]}...")
            
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
