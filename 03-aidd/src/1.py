import os
import pydantic
from typing import Optional
from datetime import datetime, date, time
from enum import Enum
from pydantic import ValidationError
from pydantic import BaseModel, Field

class CalorieType(str, Enum):
    EAT = "Потребленные"
    BURN = "Потраченные"


class CalorieExtractionResult(BaseModel):
    date: date 
    time: time 
    calorie_type: CalorieType
    kkal: int  
    category: str

class CalorieResponse(BaseModel):
    calories: list[CalorieExtractionResult]  
    answer: str  


try:
    invalid_event = CalorieExtractionResult(
        date="2025-11-10", 
        time="14:30:00", 
        calorie_type="Потребленные",
        kkal=440,  
        category="другое" 
    )
except ValidationError as e:
    print(e.json())