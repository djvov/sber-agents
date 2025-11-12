"""Pydantic models for structured calorie extraction output."""
from typing import Optional
from datetime import datetime, date, time
from enum import Enum

from pydantic import BaseModel, Field


class CalorieType(str, Enum):
    EAT = "EAT"
    BURN = "BURN"


class CalorieExtractionResult(BaseModel):
    date: date 
    time: time 
    calorie_type: CalorieType
    kkal: int  
    category: str

class CalorieResponse(BaseModel):
    calories: list[CalorieExtractionResult]  
    answer: str  
