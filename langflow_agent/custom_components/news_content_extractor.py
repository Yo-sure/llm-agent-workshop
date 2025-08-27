#!/usr/bin/env python3
"""
News Content Extractor Component for LangFlow

A specialized component that extracts clean article content from news websites,
removing navigation, ads, and other unwanted elements.
"""

from langflow.custom import Component
from langflow.core_services.content_extractor_service import ContentExtractorService
from langflow.io import (
    MessageTextInput,
    IntInput,
    BoolInput,
    Output,
)
from langflow.schema import DataFrame


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

    def extract_content(self) -> DataFrame:
        """Extract content from all configured URLs using ContentExtractorService."""
        try:
            # Handle both list and string inputs
            if isinstance(self.urls, list):
                urls = [url.strip() for url in self.urls if url.strip()]
            elif isinstance(self.urls, str):
                urls = [url.strip() for url in self.urls.split('\n') if url.strip()]
            else:
                urls = []
            
            # Call ContentExtractorService with parameters from component
            results = ContentExtractorService.extract_content(
                urls=urls,
                max_content_length=getattr(self, "max_content_length", 5000),
                timeout=getattr(self, "timeout", 15),
                include_metadata=getattr(self, "include_metadata", True),
                remove_short_paragraphs=getattr(self, "remove_short_paragraphs", True)
            )
            
            # Log summary
            successful = sum(1 for r in results if r.get('success', False))
            self.log(f"Processed {len(results)} URLs, {successful} successful")
            
            # Log individual URLs
            for result in results:
                if result.get('success'):
                    self.log(f"Successfully extracted: {result.get('url', 'Unknown URL')}")
                else:
                    self.log(f"Failed to extract: {result.get('url', 'Unknown URL')} - {result.get('error', 'Unknown error')}")
            
            return DataFrame(results)
            
        except Exception as e:
            self.log(f"Content extraction service error: {e}")
            return DataFrame([{
                'url': '',
                'title': 'Error',
                'description': '',
                'content': f'Content extraction failed: {str(e)}',
                'content_length': 0,
                'paragraphs_count': 0,
                'success': False,
                'error': str(e)
            }])


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