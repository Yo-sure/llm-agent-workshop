"""
Content Extractor Service - Pure business logic for news content extraction

This service provides news content extraction functionality without Langflow dependencies.
Can be used by both Langflow components and MCP servers.
"""

import re
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup


class ContentExtractorService:
    """Service for extracting clean article content from news websites."""
    
    @staticmethod
    def _extract_clean_news_content(
        html_content: str, 
        url: str = "",
        max_content_length: int = 5000,
        include_metadata: bool = True,
        remove_short_paragraphs: bool = True
    ) -> Dict[str, Any]:
        """Extract clean article content from HTML"""
        
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Extract metadata first
        title = ""
        description = ""
        
        if include_metadata:
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
        
        if remove_short_paragraphs:
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
        
        if len(clean_content) > max_content_length:
            clean_content = clean_content[:max_content_length] + '...'
        
        return {
            'url': url,
            'title': title,
            'description': description,
            'content': clean_content,
            'content_length': len(clean_content),
            'paragraphs_count': len(paragraphs),
        }

    @staticmethod
    def _fetch_url_content(
        url: str, 
        timeout: int = 15,
        max_content_length: int = 5000,
        include_metadata: bool = True,
        remove_short_paragraphs: bool = True
    ) -> Dict[str, Any]:
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
            
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            
            # Extract content
            result = ContentExtractorService._extract_clean_news_content(
                response.content, 
                url, 
                max_content_length,
                include_metadata,
                remove_short_paragraphs
            )
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

    @staticmethod
    def extract_content(
        urls: List[str],
        max_content_length: int = 5000,
        timeout: int = 15,
        include_metadata: bool = True,
        remove_short_paragraphs: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Extract content from multiple URLs.
        
        Args:
            urls: List of URLs to extract content from
            max_content_length: Maximum length of extracted content per article
            timeout: Request timeout in seconds
            include_metadata: Whether to include page title and metadata
            remove_short_paragraphs: Whether to filter out short paragraphs
            
        Returns:
            List of dictionaries with extracted content and metadata
        """
        # Validate URLs
        if not urls:
            return [{
                'url': '',
                'title': 'Error',
                'description': '',
                'content': 'No valid URLs provided',
                'content_length': 0,
                'paragraphs_count': 0,
                'success': False,
                'error': 'No URLs provided'
            }]
        
        # Filter out RSS URLs (not supported)
        rss_patterns = ("/rss", "rss.", ".rss")
        rss_urls = [u for u in urls if any(p.lower() in u.lower() for p in rss_patterns)]
        if rss_urls:
            return [{
                'url': rss_urls[0],
                'title': 'Error',
                'description': '',
                'content': f"RSS/Feed 링크는 지원하지 않습니다: {rss_urls[0]}",
                'content_length': 0,
                'paragraphs_count': 0,
                'success': False,
                'error': 'RSS URLs are not supported'
            }]
        
        # Process each URL
        results = []
        for url in urls:
            result = ContentExtractorService._fetch_url_content(
                url, timeout, max_content_length, include_metadata, remove_short_paragraphs
            )
            results.append(result)
        
        return results
