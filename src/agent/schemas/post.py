# TODO: implement src/agent/schemas/post.py
# src/agent/schemas/post.py
from pydantic import BaseModel
from datetime import datetime


class PostCreate(BaseModel):
    """Schema for creating a new post."""

    content: str
    pillar: str
    selected_idea: str


class PostResponse(BaseModel):
    """Schema for returning post data from API."""

    id: str
    content: str
    status: str
    critique_score: float
    created_at: datetime


class CritiqueScore(BaseModel):
    """Schema for critique scores from critique node."""

    hook: int
    value: int
    voice: int
    cta: int
    length: int
    feedback: str

    @property
    def average(self) -> float:
        scores = [self.hook, self.value, self.voice, self.cta, self.length]
        return round(sum(scores) / len(scores), 2)
