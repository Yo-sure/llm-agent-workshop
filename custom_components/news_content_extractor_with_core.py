#!/usr/bin/env python3
"""
News Content Extractor Component (with Core Service) for LangFlow

뉴스 웹사이트에서 깨끗한 기사 본문을 추출하는 전문 컴포넌트.
core_services.content_extractor_service를 활용한 버전.
네비게이션, 광고, 기타 불필요한 요소들을 제거합니다.
"""

from typing import List

from langflow.custom import Component
from langflow.io import (
    MessageTextInput,
    IntInput,
    BoolInput,
    Output,
)
from langflow.schema import DataFrame

# Import core service
from core_services.content_extractor_service import ContentExtractorService


class NewsContentExtractorComponentWithCore(Component):
    """
    뉴스 본문 추출 컴포넌트 (Core Service 사용)
    
    core_services.ContentExtractorService에 로직을 위임합니다.
    """
    
    display_name = "News Content Extractor (with Core)"
    description = "Extract clean article content from news websites (using core_services), removing navigation, ads, and unwanted elements."
    documentation: str = "https://docs.langflow.org/components-custom"
    icon = "newspaper"
    name = "NewsContentExtractorWithCore"

    # ==================== Langflow 설정 ====================
    
    inputs = [
        MessageTextInput(
            name="urls",
            display_name="URLs",
            info="뉴스 기사 URL 리스트. GDELT 검색 후 상위 2-3개 URL 전달 권장",
            is_list=True,
            tool_mode=True,
            required=True,
        ),
        IntInput(
            name="max_content_length",
            display_name="Max Content Length",
            info="추출할 본문 최대 길이 (문자 수)",
            value=5000,
            advanced=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (sec)",
            info="각 URL당 타임아웃",
            value=15,
            advanced=True,
        ),
        BoolInput(
            name="include_metadata",
            display_name="Include Metadata",
            info="페이지 제목 및 설명 포함 여부",
            value=True,
            advanced=True,
        ),
        BoolInput(
            name="remove_short_paragraphs",
            display_name="Remove Short Paragraphs",
            info="짧은 문단 자동 제거 (50자 미만)",
            value=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="extracted_content", display_name="Extracted Content", method="extract_content"),
    ]

    # ==================== Public Methods ====================
    
    def extract_content(self) -> DataFrame:
        """
        뉴스 기사 본문 추출 실행 (core_services.ContentExtractorService 위임)
        
        Returns:
            DataFrame: 추출된 본문 및 메타데이터
        """
        try:
            # Validate URLs
            if not self.urls:
                return DataFrame([{
                    'url': '',
                    'title': 'Error',
                    'description': '',
                    'content': 'No URLs provided',
                    'content_length': 0,
                    'paragraphs_count': 0,
                    'success': False,
                    'error': 'No URLs provided'
                }])
            
            # Call core service
            results = ContentExtractorService.extract_content(
                urls=self.urls,
                max_content_length=self.max_content_length,
                timeout=self.timeout,
                include_metadata=self.include_metadata,
                remove_short_paragraphs=self.remove_short_paragraphs
            )
            
            return DataFrame(results)
            
        except Exception as e:
            # Return error as DataFrame
            return DataFrame([{
                'url': '',
                'title': 'Component Error',
                'description': '',
                'content': str(e),
                'content_length': 0,
                'paragraphs_count': 0,
                'success': False,
                'error': str(e)
            }])

