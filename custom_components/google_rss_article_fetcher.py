# Google RSS Article Fetcher Component (Playwright Required)
# Note: This component requires Playwright to handle Google News redirects

# import asyncio
# from typing import Dict, Any, List, Optional

# import requests
# from bs4 import BeautifulSoup
# from loguru import logger
# from playwright.async_api import async_playwright

# from langflow.custom.custom_component.component import Component
# from langflow.helpers.data import safe_convert
# from langflow.io import MessageTextInput, IntInput, BoolInput, Output
# from langflow.schema.dataframe import DataFrame
# from langflow.schema.message import Message


# class GoogleRSSArticleFetcher(Component):
#     """A component that converts Google News RSS URLs to actual article content.
    
#     This component:
#     - Resolves Google News RSS redirects using Playwright
#     - Extracts article content from real news websites  
#     - Handles JavaScript redirects and bot detection
#     - Returns structured article data with metadata
#     """
    
#     display_name = "Google RSS Article Fetcher"
#     description = "Convert Google News RSS URLs to actual article content with metadata extraction."
#     documentation: str = "https://docs.langflow.org/components-custom-components"
#     icon = "newspaper"
#     name = "GoogleRSSArticleFetcher"
    
#     inputs = [
#         MessageTextInput(
#             name="urls",
#             display_name="URLs",
#             info="Enter one or more Google News RSS URLs, by clicking the '+' button.",
#             is_list=True,
#             tool_mode=True,
#             placeholder="Enter a Google News RSS URL...",
#             list_add_label="Add URL",
#         ),
#         IntInput(
#             name="timeout",
#             display_name="Timeout",
#             info="Page loading timeout in seconds.",
#             value=15,
#             advanced=True,
#         ),
#         BoolInput(
#             name="extract_content",
#             display_name="Extract Content",
#             info="If enabled, extracts full article content from the resolved URLs.",
#             value=True,
#             advanced=True,
#         ),
#         IntInput(
#             name="max_content_length",
#             display_name="Max Content Length",
#             info="Maximum length of extracted content in characters.",
#             value=2000,
#             advanced=True,
#         ),
#         BoolInput(
#             name="headless",
#             display_name="Headless Mode",
#             info="If enabled, runs browser in background mode.",
#             value=True,
#             advanced=True,
#         ),
#         IntInput(
#             name="max_concurrent",
#             display_name="Max Concurrent",
#             info="Maximum number of URLs to process concurrently.",
#             value=3,
#             advanced=True,
#         )
#     ]
    
#     outputs = [
#         Output(display_name="Articles", name="articles", method="fetch_articles"),
#         Output(display_name="Raw Content", name="raw_content", method="fetch_articles_as_message"),
#     ]

#     async def _resolve_google_news_url(self, url: str) -> Dict[str, Any]:
#         """
#         Google News RSS URL을 실제 기사 URL로 해결
        
#         Configuration:
#         - Uses domcontentloaded wait condition for better reliability
#         - Optimized timeout settings
#         """
#         result = {
#             'original_url': url,
#             'final_url': None,
#             'title': None,
#             'content': None,
#             'success': False,
#             'error': None,
#             'processing_time': 0
#         }
        
#         import time
#         start_time = time.time()
        
#         try:
#             async with async_playwright() as p:
#                 browser = await p.chromium.launch(headless=self.headless)
#                 context = await browser.new_context(
#                     user_agent=(
#                         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#                         "AppleWebKit/537.36 (KHTML, like Gecko) "
#                         "Chrome/120.0.0.0 Safari/537.36"
#                     ),
#                     extra_http_headers={
#                         "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
#                         "Referer": "https://news.google.com/",
#                         "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
#                         "DNT": "1",
#                         "Connection": "keep-alive",
#                         "Upgrade-Insecure-Requests": "1",
#                     },
#                     locale='ko-KR',
#                     timezone_id='Asia/Seoul',
#                 )
#                 page = await context.new_page()
                
#                 try:
#                     logger.info(f"🌐 Starting page load: {url}")
                    
#                     # Navigate to URL with optimized settings
#                     response = await page.goto(
#                         url, 
#                         wait_until='domcontentloaded',  # Better reliability than networkidle
#                         timeout=30000  # 30 second timeout
#                     )
                    
#                     # Wait for JavaScript redirects to complete
#                     await asyncio.sleep(3)
                    
#                     final_url = page.url
#                     logger.info(f"🔗 Final URL: {final_url}")
                    
#                     if 'news.google.com' not in final_url:
#                         # Successfully redirected to actual news site
#                         logger.info("🎉 SUCCESS! Redirected to actual news site")
                        
#                         title = await page.title()
#                         result.update({
#                             'final_url': final_url,
#                             'title': title,
#                             'success': True
#                         })
                        
#                         # Extract article content if requested
#                         if self.extract_content:
#                             content = await self._extract_content(final_url, title)
#                             result['content'] = content
                            
#                     else:
#                         # Redirect failed - still on Google News domain
#                         logger.warning("❌ Redirect failed - still on Google News domain")
#                         result.update({
#                             'final_url': final_url,
#                             'title': await page.title(),
#                             'error': 'No redirect detected - still on Google News domain'
#                         })
                        
#                 except Exception as e:
#                     logger.error(f"❌ Error during page processing: {e}")
#                     result['error'] = str(e)
                    
#                 finally:
#                     await browser.close()
                    
#         except Exception as e:
#             logger.error(f"❌ Playwright error: {e}")
#             result['error'] = str(e)
            
#         result['processing_time'] = time.time() - start_time
#         logger.info(f"⏱️ Processing time: {result['processing_time']:.2f}s")
        
#         return result

#     async def _extract_content(self, url: str, title: str) -> Optional[str]:
#         """
#         Extract article content from actual news URL
#         Uses requests + BeautifulSoup (faster than Playwright)
#         """
#         try:
#             logger.info(f"📝 Starting content extraction: {url}")
            
#             headers = {
#                 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
#             }
            
#             response = requests.get(url, headers=headers, timeout=10)
#             response.raise_for_status()
            
#             soup = BeautifulSoup(response.text, 'lxml')
            
#             # Domain-specific selectors for better extraction
#             domain = url.split('/')[2].lower()
            
#             domain_selectors = {
#                 'etnews.com': ['.article_body', '.news_body', '.view_content'],
#                 'yna.co.kr': ['.article-content', '.view-content', 'article p'],
#                 'mk.co.kr': ['.news_content', '.art_txt', 'article .content'],
#                 'hankyung.com': ['.article-body', '.news-content', '.view-content'],
#                 'chosun.com': ['.par', '.article-body'],
#                 'joongang.co.kr': ['.article_body', '.article-content'],
#                 'ddaily.co.kr': ['div[class*="content"]', '.article-content'],
#             }
            
#             # General selectors for common news sites
#             general_selectors = [
#                 '[itemprop="articleBody"]',
#                 '.article-body',
#                 '.article-content', 
#                 '.news-content',
#                 '.entry-content',
#                 'article .content',
#                 'div[class*="content"]',
#                 'div[class*="article"]',
#                 '.view-content'
#             ]
            
#             # Try domain-specific selectors first
#             selectors_to_try = []
#             for site in domain_selectors:
#                 if site in domain:
#                     selectors_to_try.extend(domain_selectors[site])
#                     break
            
#             # Add general selectors as fallback
#             selectors_to_try.extend(general_selectors)
            
#             # Attempt to extract main content
#             for selector in selectors_to_try:
#                 try:
#                     content_elem = soup.select_one(selector)
#                     if content_elem:
#                         # Extract content from paragraph tags
#                         paragraphs = content_elem.find_all('p')
#                         if paragraphs:
#                             article_paragraphs = []
#                             for p in paragraphs:
#                                 text = p.get_text().strip()
#                                 # Filter for meaningful content (length + article characteristics)
#                                 if (len(text) > 30 and 
#                                     not text.startswith(('Copyright', '저작권', '무단', '▲', '※')) and
#                                     ('기자' in text or len(text) > 50)):
#                                     article_paragraphs.append(text)
                            
#                             if article_paragraphs:
#                                 article_content = '\n\n'.join(article_paragraphs)
                                
#                                 # Apply content length limit
#                                 if len(article_content) > self.max_content_length:
#                                     article_content = article_content[:self.max_content_length] + '...'
                                
#                                 logger.info(f"✅ Content extracted successfully with selector '{selector}' ({len(article_content)} chars)")
#                                 return article_content
                                
#                 except Exception as e:
#                     logger.debug(f"Selector '{selector}' failed: {e}")
#                     continue
            
#             logger.warning("❌ Content extraction failed - no suitable selector found")
#             return None
            
#         except Exception as e:
#             logger.error(f"❌ Error during content extraction: {e}")
#             return None

#     async def _process_urls_async(self, urls: List[str]) -> List[Dict[str, Any]]:
#         """Process multiple URLs concurrently with rate limiting."""
#         logger.info(f"🚀 Processing {len(urls)} URLs")
        
#         # Use configured concurrent limit
#         semaphore = asyncio.Semaphore(self.max_concurrent)
        
#         async def process_single_url(url: str):
#             async with semaphore:
#                 return await self._resolve_google_news_url(url.strip())
        
#         tasks = [process_single_url(url) for url in urls if url.strip()]
#         results = await asyncio.gather(*tasks, return_exceptions=True)
        
#         # Handle exceptions
#         processed_results = []
#         for i, result in enumerate(results):
#             if isinstance(result, Exception):
#                 logger.error(f"Error processing URL {i+1}: {result}")
#                 processed_results.append({
#                     'original_url': urls[i] if i < len(urls) else 'unknown',
#                     'final_url': None,
#                     'title': None,
#                     'content': None,
#                     'success': False,
#                     'error': str(result),
#                     'processing_time': 0
#                 })
#             else:
#                 processed_results.append(result)
        
#         success_count = sum(1 for r in processed_results if r['success'])
#         logger.info(f"📊 Processing complete: {success_count}/{len(processed_results)} successful")
        
#         return processed_results

#     def fetch_article_contents(self) -> List[Dict[str, Any]]:
#         """Fetch and process articles from the configured URLs.
        
#         Returns:
#             List[Dict]: List of article data dictionaries
            
#         Raises:
#             ValueError: If no valid URLs are provided or processing fails
#         """
#         try:
#             # Handle both list and string inputs
#             if isinstance(self.urls, list):
#                 urls = [url.strip() for url in self.urls if url.strip()]
#             elif isinstance(self.urls, str):
#                 urls = [url.strip() for url in self.urls.split('\n') if url.strip()]
#             else:
#                 urls = []
            
#             if not urls:
#                 msg = "No valid URLs provided."
#                 raise ValueError(msg)
            
#             logger.debug(f"URLs: {urls}")
            
#             # Run async processing
#             loop = asyncio.new_event_loop()
#             asyncio.set_event_loop(loop)
            
#             try:
#                 results = loop.run_until_complete(self._process_urls_async(urls))
#             finally:
#                 loop.close()
            
#             if not results:
#                 msg = "No articles were successfully processed"
#                 raise ValueError(msg)
            
#             # Convert to standardized format
#             articles = []
#             for result in results:
#                 article_data = {
#                     "text": safe_convert(result.get('content', ''), clean_data=True),
#                     "url": result.get('final_url', result.get('original_url', '')),
#                     "title": result.get('title', ''),
#                     "original_url": result.get('original_url', ''),
#                     "success": result.get('success', False),
#                     "error": result.get('error'),
#                     "processing_time": result.get('processing_time', 0)
#                 }
#                 articles.append(article_data)
            
#             return articles
            
#         except Exception as e:
#             error_msg = e.message if hasattr(e, "message") else str(e)
#             msg = f"Error processing articles: {error_msg}"
#             logger.exception(msg)
#             raise ValueError(msg) from e

#     def fetch_articles(self) -> DataFrame:
#         """Convert the articles to a DataFrame."""
#         articles = self.fetch_article_contents()
#         logger.info(f"📊 Articles DataFrame created: {len(articles)} articles")
#         return DataFrame(data=articles)

#     def fetch_articles_as_message(self) -> Message:
#         """Convert the articles to a Message with combined text content."""
#         articles = self.fetch_article_contents()
        
#         # Combine all successful article texts
#         successful_articles = [article for article in articles if article.get('success', False)]
        
#         if successful_articles:
#             # Create combined text content
#             combined_text = "\n\n".join([
#                 f"# {article.get('title', 'Untitled')}\n\n{article.get('text', '')}"
#                 for article in successful_articles
#                 if article.get('text')
#             ])
            
#             # Create summary for message
#             success_count = len(successful_articles)
#             total_count = len(articles)
            
#             summary_parts = []
#             for i, article in enumerate(successful_articles[:3], 1):  # Show top 3
#                 title = article.get('title', 'No title')[:80]
#                 url = article.get('url', 'No URL')
#                 content_preview = article.get('text', '')[:150] if article.get('text') else 'No content'
                
#                 summary_parts.append(f"{i}. 📰 {title}\n   🔗 {url}\n   📝 {content_preview}...")
            
#             if len(successful_articles) > 3:
#                 summary_parts.append(f"... and {len(successful_articles) - 3} more articles")
            
#             message_text = f"""🎉 Google News RSS Processing Complete!

# 📊 Results: {success_count}/{total_count} successful

# ✅ Successfully processed articles:
# {chr(10).join(summary_parts)}

# 📄 Full content available in data field."""
            
#             return Message(text=message_text, data={"articles": articles, "combined_text": combined_text})
#         else:
#             error_summary = f"""❌ Google News RSS Processing Failed

# 📊 Results: 0/{len(articles)} successful

# All URLs failed to redirect properly:
# - URLs may have expired
# - Google's bot detection may be blocking requests
# - Network connectivity issues"""
            
#             return Message(text=error_summary, data={"articles": articles})



# if __name__ == "__main__":
#     # 테스트용 코드
#     fetcher = GoogleRSSArticleFetcher()
#     fetcher.urls = ["https://news.google.com/rss/articles/CBMiTkFVX3lxTE1mb21TZncyTGtyd0NuMnFCMFFVckJnT092cXNtd0ZfUExXZVBKNm5oWTV0NTZhN0xwaXl1Uk5uZElHLU1ZbTlLakNYa3FwZw?oc=5"]
#     fetcher.timeout = 15
#     fetcher.extract_content = True
#     fetcher.max_content_length = 2000
#     fetcher.headless = True
#     fetcher.max_concurrent = 3
    
#     try:
#         # DataFrame만 간단히 테스트
#         print("=== DataFrame Test ===")
#         df = fetcher.fetch_articles()
#         print(f"DataFrame type: {type(df)}")
        
#         # 직접 articles 데이터 확인
#         articles = fetcher.fetch_article_contents()
#         print(f"Articles count: {len(articles)}")
#         if articles:
#             print(f"First article title: {articles[0].get('title', 'No title')}")
#             print(f"Success: {articles[0].get('success', False)}")
            
#     except Exception as e:
#         print(f"Test failed: {e}")
#         import traceback
#         traceback.print_exc()
