#!/usr/bin/env python3
"""
MCP News Research Server

A Model Context Protocol server that provides news research tools using:
- GDELT DOC 2.0 API for global news search
- Google News RSS for current news
- Content extraction from news URLs

This server exposes the same functionality as the Langflow components
but through MCP tools that can be used by Claude and other AI models.
"""

import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # stderr로 출력
    ]
)
logger = logging.getLogger("mcp-news-server")

# Import our core services
from langflow.core_services import GDELTService
from langflow.core_services import GoogleNewsService
from langflow.core_services import ContentExtractorService

# Initialize FastMCP server
mcp = FastMCP(
    name="news-research",
    host="127.0.0.1",
    port=8080  # Back to original port
)


@mcp.tool()
async def search_gdelt_news(
    query: str,
    max_results: int = 10,
    mode: str = "ArtList",
    domains: Optional[str] = None,
    languages: Optional[str] = None,
    countries: Optional[str] = None,
    timespan: Optional[str] = None
) -> str:
    """
    Search global news using GDELT DOC 2.0 API.
    
    GDELT monitors global news media and provides comprehensive coverage of events worldwide.
    ⚠️  BEST FOR: English queries and international news. For Korean/local news, use search_google_news instead.
    
    Args:
        query: Search query in ENGLISH (supports Boolean operators like AND, OR, parentheses)
        max_results: Maximum number of articles to return (1-250)
        mode: Search mode - "ArtList" for articles, timeline modes for analysis
        domains: Comma-separated domain filters (e.g., "reuters.com,bloomberg.com")
        languages: Comma-separated language filters (e.g., "English,Korean")
        countries: Comma-separated country filters (e.g., "United States,South Korea")
        timespan: Time range (e.g., "7d" for last 7 days, "1m" for last month)
    
    Returns:
        Formatted string with article titles, URLs, dates, and domains
    """
    try:
        # Parse comma-separated filters
        domain_list = [d.strip() for d in domains.split(",")] if domains else None
        language_list = [l.strip() for l in languages.split(",")] if languages else None
        country_list = [c.strip() for c in countries.split(",")] if countries else None
        
        df = None
        filter_attempts = [
            {"domains": domain_list, "languages": language_list, "countries": country_list, "desc": "모든 필터"},
            {"domains": None, "languages": language_list, "countries": country_list, "desc": "도메인 필터 제거"},  
            {"domains": None, "languages": None, "countries": country_list, "desc": "언어 필터까지 제거"},
            {"domains": None, "languages": None, "countries": None, "desc": "모든 필터 제거"}
        ]
        
        for attempt in filter_attempts:
            df = GDELTService.search_news(
                query=query,
                mode=mode,
                maxrecords=min(max_results, 250),
                domains=attempt["domains"],
                languages=attempt["languages"], 
                countries=attempt["countries"],
                timespan=timespan
            )
            
            # 성공적인 결과가 있으면 중단
            if not df.empty and not ('message' in df.columns and 'No results' in str(df.iloc[0].get('message', ''))):
                logger.info(f"GDELT 검색 성공: {attempt['desc']} 적용")
                break
        
        if df.empty or ('message' in df.columns and 'No results' in str(df.iloc[0].get('message', ''))):
            return "No articles found for the given query, even with relaxed filters."
        
        # Check for errors
        if "title" in df.columns and df.iloc[0]["title"] == "Error":
            return f"GDELT API Error: {df.iloc[0].get('summary', 'Unknown error')}"
        
        # Format results
        results = []
        for _, row in df.head(max_results).iterrows():
            if mode == "ArtList":
                result = f"""Title: {row.get('title', 'N/A')}
URL: {row.get('url', 'N/A')}
Date: {row.get('seendate', 'N/A')}
Domain: {row.get('domain', 'N/A')}
Language: {row.get('language', 'N/A')}
Country: {row.get('sourcecountry', 'N/A')}"""
            else:
                # Timeline mode formatting
                result = f"""Series: {row.get('series', 'N/A')}
Date: {row.get('date', 'N/A')}
Value: {row.get('value', 'N/A')}"""
            results.append(result)
        
        return f"Found {len(df)} articles from GDELT:\n\n" + "\n\n---\n\n".join(results)
        
    except Exception as e:
        return f"Error searching GDELT: {str(e)}"


@mcp.tool()
async def search_google_news(
    query: Optional[str] = None,
    topic: Optional[str] = None,
    location: Optional[str] = None,
    max_results: int = 10,
    language: str = "ko",
    country: str = "KR"
) -> str:
    """
    Search current news using Google News RSS.
    
    Get the latest news articles from Google News by keyword, topic, or location.
    ✅ BEST FOR: Korean queries, local news, and recent breaking news with excellent language support.
    
    Args:
        query: Search keyword in ANY LANGUAGE (e.g., "삼성SDS", "artificial intelligence")
        topic: News topic category (WORLD, NATION, BUSINESS, TECHNOLOGY, ENTERTAINMENT, SCIENCE, SPORTS, HEALTH)
        location: Geographic location for news (e.g., "Seoul", "California", "Japan")
        max_results: Maximum number of articles to return (1-100)
        language: Language code (e.g., "ko" for Korean, "en" for English)
        country: Country code (e.g., "KR" for Korea, "US" for United States)
    
    Returns:
        Formatted string with article titles, links, publication dates, and summaries
    """
    try:
        # Build language parameters
        hl = f"{language}-{country}" if language == "en" else language
        ceid = f"{country}:{language}"
        
        # Call Google News service
        df = GoogleNewsService.search_news(
            query=query,
            topic=topic,
            location=location,
            hl=hl,
            gl=country,
            ceid=ceid,
            max_results=max_results
        )
        
        if df.empty:
            return "No articles found from Google News."
        
        # Check for errors
        if "title" in df.columns and df.iloc[0]["title"] == "Error":
            return f"Google News Error: {df.iloc[0].get('summary', 'Unknown error')}"
        
        # Format results
        results = []
        for _, row in df.head(max_results).iterrows():
            result = f"""Title: {row.get('title', 'N/A')}
Link: {row.get('link', 'N/A')}
Published: {row.get('published', 'N/A')}
Summary: {row.get('summary', 'N/A')}"""
            results.append(result)
        
        return f"Found {len(df)} articles from Google News:\n\n" + "\n\n---\n\n".join(results)
        
    except Exception as e:
        return f"Error searching Google News: {str(e)}"


@mcp.tool()
async def extract_article_content(
    urls: str,
    max_length: int = 5000,
    include_metadata: bool = True
) -> str:
    """
    Extract clean article content from news website URLs.
    
    Removes navigation, ads, and other unwanted elements to get just the article text.
    
    Args:
        urls: Comma-separated list of news article URLs to extract content from
        max_length: Maximum length of extracted content per article (characters)
        include_metadata: Whether to include page title and description metadata
    
    Returns:
        Formatted string with extracted content, titles, and metadata for each URL
    """
    try:
        # Parse URLs
        url_list = [url.strip() for url in urls.split(",") if url.strip()]
        
        if not url_list:
            return "No valid URLs provided."
        
        # Call content extraction service
        results = ContentExtractorService.extract_content(
            urls=url_list,
            max_content_length=max_length,
            include_metadata=include_metadata,
            timeout=15,
            remove_short_paragraphs=True
        )
        
        if not results:
            return "No content could be extracted."
        
        # Format results
        formatted_results = []
        for result in results:
            if not result.get('success', False):
                formatted_result = f"""URL: {result.get('url', 'N/A')}
Status: FAILED
Error: {result.get('error', 'Unknown error')}"""
            else:
                formatted_result = f"""URL: {result.get('url', 'N/A')}
Title: {result.get('title', 'N/A')}
Content Length: {result.get('content_length', 0)} characters
Paragraphs: {result.get('paragraphs_count', 0)}

Content:
{result.get('content', 'No content extracted')}"""
            
            formatted_results.append(formatted_result)
        
        successful = sum(1 for r in results if r.get('success', False))
        return f"Processed {len(results)} URLs, {successful} successful:\n\n" + "\n\n" + "="*50 + "\n\n".join(formatted_results)
        
    except Exception as e:
        return f"Error extracting content: {str(e)}"


if __name__ == "__main__":
    import sys
    
    mode = sys.argv[1] if len(sys.argv) > 1 else ""

    if mode == "--http":
        logger.info("🌐 Starting MCP News Server (Streamable HTTP)")
        logger.info("📡 Base URL: http://127.0.0.1:8080/mcp")
        # run()에는 host/port/path를 넘기지 않는다 (해당 버전 미지원)
        mcp.run(transport="streamable-http")

    elif mode == "--sse":
        logger.info("🌐 Starting MCP News Server (SSE)")
        logger.info("📡 SSE URL: http://127.0.0.1:8080/sse")
        # run()에는 host/port/path를 넘기지 않는다 (해당 버전 미지원)
        mcp.run(transport="sse")

    else:
        logger.info("🔌 Starting MCP News Server in STDIO mode")
        logger.info("🔗 Ready for Claude Desktop/Langflow connection")
        mcp.run()  # transport="stdio" (default)
