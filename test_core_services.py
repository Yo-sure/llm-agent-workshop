#!/usr/bin/env python3
"""
간단한 core_services 통합 테스트

이 스크립트는 core_services 모듈들이 제대로 작동하는지 확인합니다.
"""

import sys

def test_gdelt_service():
    """GDELT 서비스 테스트"""
    print("🧪 Testing GDELTService...")
    
    try:
        from core_services.gdelt_service import GDELTService
        
        # 간단한 검색 테스트
        df = GDELTService.search_news(
            query="NVIDIA",
            mode="ArtList",
            maxrecords=3,
            timespan="7days"
        )
        
        print(f"   ✅ GDELTService.search_news() - {len(df)} results")
        
        # 금융 미디어 프리셋 테스트
        df_financial = GDELTService.search_news(
            query="Tesla",
            mode="ArtList",
            maxrecords=3,
            financial_media_only=True,
            timespan="7days"
        )
        
        print(f"   ✅ GDELTService.search_news() with financial_media_only - {len(df_financial)} results")
        
        # 감성 필터 테스트
        df_positive = GDELTService.search_news(
            query="Samsung",
            mode="ArtList",
            maxrecords=3,
            tone_filter="Positive",
            timespan="7days"
        )
        
        print(f"   ✅ GDELTService.search_news() with tone_filter=Positive - {len(df_positive)} results")
        
        return True
        
    except Exception as e:
        print(f"   ❌ GDELTService test failed: {e}")
        return False


def test_content_extractor_service():
    """Content Extractor 서비스 테스트"""
    print("🧪 Testing ContentExtractorService...")
    
    try:
        from core_services.content_extractor_service import ContentExtractorService
        
        # 간단한 추출 테스트 (BBC 뉴스)
        test_url = "https://www.bbc.com/news"
        results = ContentExtractorService.extract_content(
            urls=[test_url],
            max_content_length=1000,
            timeout=10
        )
        
        if results and len(results) > 0:
            result = results[0]
            print(f"   ✅ ContentExtractorService.extract_content() - Success: {result.get('success', False)}")
            print(f"      Content length: {result.get('content_length', 0)} chars")
        else:
            print(f"   ⚠️  ContentExtractorService.extract_content() - No results")
        
        return True
        
    except Exception as e:
        print(f"   ❌ ContentExtractorService test failed: {e}")
        return False


def test_imports():
    """모듈 임포트 테스트"""
    print("🧪 Testing module imports...")
    
    try:
        from core_services import GDELTService, ContentExtractorService
        print("   ✅ core_services imports successful")
        return True
    except Exception as e:
        print(f"   ❌ Import test failed: {e}")
        return False


def main():
    """메인 테스트 실행"""
    print("=" * 60)
    print("Core Services Integration Test")
    print("=" * 60)
    print()
    
    results = []
    
    # 임포트 테스트
    results.append(("Imports", test_imports()))
    print()
    
    # GDELT 서비스 테스트
    results.append(("GDELT Service", test_gdelt_service()))
    print()
    
    # Content Extractor 서비스 테스트
    results.append(("Content Extractor Service", test_content_extractor_service()))
    print()
    
    # 결과 요약
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())

