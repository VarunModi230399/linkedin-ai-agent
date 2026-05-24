# TODO: implement src/agent/schemas/idea.py
# src/agent/schemas/idea.py
from pydantic import BaseModel


class IdeaCreate(BaseModel):
    """Schema for a generated post idea."""

    pillar: str
    title: str
    brief: str = ""


class IdeaResponse(BaseModel):
    """Schema for returning idea data."""

    id: str
    pillar: str
    title: str
    status: str
