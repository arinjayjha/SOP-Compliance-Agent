from pydantic import BaseModel, Field, field_validator
from typing import List, Literal

Verdict = Literal["YES", "NO", "CONDITIONAL"]

class Decision(BaseModel):
    verdict: Verdict = Field(..., description="YES/NO/CONDITIONAL")
    rationale: str = Field(..., description="Short explanation grounded in SOP text.")
    citations: List[str] = Field(..., description="SOP section IDs, e.g., AC-2.2")

    @field_validator("citations")
    @classmethod
    def validate_citations(cls, v: List[str]) -> List[str]:
        return [c.strip() for c in v if isinstance(c, str) and c.strip()]
