from typing import Any, Dict, List, Optional

import pandas as pd

from langflow.custom import Component
from core_services.gdelt_service import GDELTService
from langflow.io import (
    MessageTextInput,
    IntInput,
    BoolInput,
    DropdownInput,
    Output,
)
from langflow.schema import DataFrame


# Constants moved to GDELTService


class GDELTDocSearchComponent(Component):
    display_name = "GDELT Doc Search"
    description = "Searches global news via GDELT DOC 2.0. Supports ArtList & Timeline* modes."
    documentation: str = "https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/"
    icon = "globe"
    name = "GDELTDocSearch"

    inputs = [
        MessageTextInput(
            name="query",
            display_name="Query",
            info='예) ("NVDA" OR "NVIDIA"), (A OR B) AND C. 복잡한 쿼리는 직접 괄호 사용',
            tool_mode=True,
            required=True,
        ),
        MessageTextInput(
            name="domains",
            display_name="Domains",
            info="도메인 필터. 예: reuters.com, bloomberg.com",
            is_list=True,
            advanced=True,
        ),
        MessageTextInput(
            name="languages",
            display_name="Languages",
            info="언어 필터. 예: English, Korean",
            is_list=True,
            advanced=True,
        ),
        MessageTextInput(
            name="countries",
            display_name="Source Countries",
            info="발행국가(FIPS 2-letter). 예: US, KR",
            is_list=True,
            advanced=True,
        ),
        DropdownInput(
            name="mode",
            display_name="Mode",
            options=["ArtList", "timelinevol", "timelinevolraw", "timelinetone", "timelinelang", "timelinesourcecountry"],
            value="ArtList",
            tool_mode=True,
            required=True,
        ),
        MessageTextInput(
            name="timespan",
            display_name="TIMESPAN",
            info="예: 24hours, 7days, 14days (start/end 대신 사용)",
            advanced=True,
        ),
        MessageTextInput(
            name="start_datetime",
            display_name="STARTDATETIME",
            info="YYYYMMDDHHMMSS (timespan 대신 사용)",
            advanced=True,
        ),
        MessageTextInput(
            name="end_datetime",
            display_name="ENDDATETIME",
            info="YYYYMMDDHHMMSS (timespan 대신 사용)",
            advanced=True,
        ),
        IntInput(
            name="maxrecords",
            display_name="Max Records",
            info="1~250 (LLM Tool 사용시 5~20 권장)",
            value=5,
            advanced=False,
        ),
        DropdownInput(
            name="sort",
            display_name="Sort (ArtList)",
            options=["DateDesc", "DateAsc"],
            value="DateDesc",
            advanced=True,
        ),
        IntInput(
            name="timeline_smooth",
            display_name="Timeline Smooth",
            info="Timeline 전용. 0=off",
            value=0,
            advanced=True,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (sec)",
            value=25,
            advanced=True,
        ),
        BoolInput(
            name="use_cache",
            display_name="Use Cache",
            value=True,
            advanced=True,
        ),
        IntInput(
            name="cache_ttl",
            display_name="Cache TTL (sec)",
            value=300,
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="articles", display_name="Results", method="search_gdelt"),
    ]

    # ------------- Helper methods moved to GDELTService -------------

    # ------------- public method -------------
    def search_gdelt(self) -> DataFrame:
        """Search GDELT using the GDELTService."""
        try:
            # Call GDELTService with parameters from component
            df = GDELTService.search_news(
                query=getattr(self, "query", ""),
                mode=getattr(self, "mode", "ArtList"),
                maxrecords=getattr(self, "maxrecords", 5),
                domains=getattr(self, "domains", None),
                languages=getattr(self, "languages", None),
                countries=getattr(self, "countries", None),
                sort=getattr(self, "sort", "DateDesc"),
                start_datetime=getattr(self, "start_datetime", None),
                end_datetime=getattr(self, "end_datetime", None),
                timespan=getattr(self, "timespan", None),
                timeline_smooth=getattr(self, "timeline_smooth", 0),
                use_cache=getattr(self, "use_cache", True),
                cache_ttl=getattr(self, "cache_ttl", 300),
                timeout=getattr(self, "timeout", 25)
            )
            
            # Log the results
            if not df.empty and "title" in df.columns:
                if df.iloc[0]["title"] == "Error":
                    self.log(f"GDELT request failed: {df.iloc[0].get('summary', 'Unknown error')}")
                else:
                    self.log(f"GDELT returned {len(df)} results")
            
            return DataFrame(df)
            
        except Exception as e:
            self.log(f"GDELT service error: {e}")
            return DataFrame(pd.DataFrame([{"title": "Error", "url": "", "seendate": "", "domain": "", "summary": str(e)}]))
