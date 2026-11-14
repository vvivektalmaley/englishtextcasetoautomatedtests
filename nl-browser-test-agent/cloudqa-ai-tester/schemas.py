
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    CLICK = "CLICK"
    TYPE = "TYPE"
    SELECT = "SELECT"
    ASSERT_TEXT = "ASSERT_TEXT"
    ASSERT_URL = "ASSERT_URL"
    WAIT = "WAIT"
    PRESS_ENTER = "PRESS_ENTER"


class TestStep(BaseModel):
    action: ActionType
    element_description: Optional[str] = None
    value: Optional[str] = None
    expected_text: Optional[str] = None
    expected_url: Optional[str] = None
    timeout_seconds: int = 10
    description: str = ""


class TestPlan(BaseModel):
    test_name: str
    description: str = ""
    steps: List[TestStep] = Field(default_factory=list)


class StepResult(BaseModel):
    step_number: int
    action: str
    description: str
    status: str
    message: str = ""
    duration_seconds: float = 0.0
    screenshot: Optional[str] = None


class TestReport(BaseModel):
    test_name: str
    url: str
    status: str
    total_steps: int
    passed_steps: int
    failed_steps: int
    skipped_steps: int
    results: List[StepResult] = Field(default_factory=list)
