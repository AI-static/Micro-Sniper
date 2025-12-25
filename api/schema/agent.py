from pydantic import BaseModel, Field, field_serializer
from typing import Optional
from datetime import datetime
from enum import Enum


class AnalyzeTrendsRequest(BaseModel):
    keywords: list[str] = Field(default=["Agent"], description="要分析的关键词列表，为空则使用默认关键词")
