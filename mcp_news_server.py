#!/usr/bin/env python3
"""
MCP News Research Server

A Model Context Protocol server that provides news research tools using:
- GDELT DOC 2.0 API for global news search
- Content extraction from news URLs

This server exposes the same functionality as the Langflow components
but through MCP tools that can be used by Claude and other AI models.
"""

import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # stderr로 출력
    ]
)
logger = logging.getLogger("mcp-news-server")

# Import our core services
from core_services.gdelt_service import GDELTService
from core_services.content_extractor_service import ContentExtractorService

# Initialize FastMCP server
mcp = FastMCP(
    name="news-research",
    host="127.0.0.1",
    port=8080
)


@mcp.tool()
async def search_gdelt_news(
    query: str,
    max_results: int = 10,
    mode: str = "ArtList",
    domains: Optional[str] = None,
    languages: Optional[str] = None,
    countries: Optional[str] = None,
    financial_media_only: bool = False,
    tone_filter: str = "All",
    timespan: str = "7days"
) -> str:
    """
    Search global news using GDELT DOC 2.0 API.
    
    GDELT monitors global news media and provides comprehensive coverage of events worldwide.
    
    IMPORTANT: Use SHORT ENGLISH keywords for best results!
       Korean/non-English keywords rarely return results (global news focus).
    
    Args:
        query: Search query in ENGLISH (supports Boolean operators like AND, OR, parentheses)
               Examples: "Samsung SDS", "NVIDIA", "(Tesla OR SpaceX)"
        max_results: Maximum number of articles to return (1-250, default: 10)
        mode: Search mode - "ArtList" for articles, or timeline modes for analysis
        domains: Comma-separated domain filters (e.g., "reuters.com,bloomberg.com")
        languages: Comma-separated language filters - ISO 639-3 codes (e.g., "eng,kor,jpn,zho")
        countries: Comma-separated country filters - FIPS codes (e.g., "US,KS,JA,CH")
                   Note: KS=South Korea, not KR
        financial_media_only: Filter to financial media only (Reuters, Bloomberg, WSJ, etc.)
        tone_filter: Sentiment filter - "All", "Positive" (>5), "Negative" (<-5), "Neutral" (-5~5)
        timespan: Time range (e.g., "7days", "24hours", "14days", "30days", default: "7days")
    
    Returns:
        Formatted string with article titles, URLs, dates, domains, language, country, and tone
    
    Examples:
        1. Basic search: search_gdelt_news("Samsung SDS", max_results=5)
        2. Financial bullish news: search_gdelt_news("NVIDIA", financial_media_only=True, tone_filter="Positive")
        3. Risk monitoring: search_gdelt_news("Tesla recall", tone_filter="Negative", timespan="7days")
    """
    try:
        # Parse comma-separated filters
        domain_list = [d.strip() for d in domains.split(",")] if domains else None
        language_list = [l.strip() for l in languages.split(",")] if languages else None
        country_list = [c.strip() for c in countries.split(",")] if countries else None
        
        df = GDELTService.search_news(
            query=query,
            mode=mode,
            maxrecords=min(max_results, 250),
            domains=domain_list,
            languages=language_list, 
            countries=country_list,
            financial_media_only=financial_media_only,
            tone_filter=tone_filter,
            timespan=timespan
        )
        
        if df.empty:
            return "No articles found for the given query."
        
        # Check for errors
        if "title" in df.columns and df.iloc[0]["title"] == "Error":
            return f"GDELT API Error: {df.iloc[0].get('summary', 'Unknown error')}"
        
        # Check for "No results" message
        if "title" in df.columns and df.iloc[0]["title"] == "No results":
            return f"No articles found: {df.iloc[0].get('summary', 'No matching articles')}"
        
        # Format results
        results = []
        for _, row in df.head(max_results).iterrows():
            if mode == "ArtList":
                result = f"""Title: {row.get('title', 'N/A')}
URL: {row.get('url', 'N/A')}
Date: {row.get('seendate', 'N/A')}
Domain: {row.get('domain', 'N/A')}
Language: {row.get('language', 'N/A')}
Country: {row.get('sourcecountry', 'N/A')}
Tone: {row.get('tone', 'N/A')}"""
            else:
                # Timeline mode formatting
                result = f"""Series: {row.get('series', 'N/A')}
Date: {row.get('date', 'N/A')}
Value: {row.get('value', 'N/A')}"""
            results.append(result)
        
        return f"Found {len(df)} articles from GDELT:\n\n" + "\n\n---\n\n".join(results)
        
    except Exception as e:
        logger.error(f"Error searching GDELT: {str(e)}")
        return f"Error searching GDELT: {str(e)}"


@mcp.tool()
async def extract_article_content(
    urls: str,
    max_length: int = 5000,
    include_metadata: bool = True
) -> str:
    """
    Extract clean article content from news website URLs.
    
    Removes navigation, ads, and other unwanted elements to get just the article text.
    
    USAGE: ALWAYS call this after search_gdelt_news to get full article text!
           GDELT only returns headlines - this tool extracts the complete content.
    
    Args:
        urls: Comma-separated list of news article URLs to extract content from
              Limit to 2-3 URLs for optimal performance
        max_length: Maximum length of extracted content per article (characters, default: 5000)
        include_metadata: Whether to include page title and description metadata (default: True)
    
    Returns:
        Formatted string with extracted content, titles, and metadata for each URL
    
    Example:
        After getting GDELT results, extract top 2 articles:
        extract_article_content("https://example.com/article1,https://example.com/article2")
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
        logger.error(f"Error extracting content: {str(e)}")
        return f"Error extracting content: {str(e)}"


if __name__ == "__main__":
    import sys
    
    mode = sys.argv[1] if len(sys.argv) > 1 else ""

    if mode == "--http":
        logger.info("🌐 Starting MCP News Server (Streamable HTTP)")
        logger.info("📡 Base URL: http://127.0.0.1:8080/mcp")
        mcp.run(transport="streamable-http")

    elif mode == "--sse":
        logger.info("🌐 Starting MCP News Server (SSE)")
        logger.info("📡 SSE URL: http://127.0.0.1:8080/sse")
        mcp.run(transport="sse")

    else:
        logger.info("🔌 Starting MCP News Server in STDIO mode")
        logger.info("🔗 Ready for Claude Desktop/Langflow connection")
        mcp.run()  # transport="stdio" (default)
