# TODO: implement src/agent/schemas/critique.py
# src/agent/schemas/critique.py
from pydantic import BaseModel


class CritiqueResult(BaseModel):
    """
    Output of the critique node.
    Scores each dimension 0-10.
    Average determines routing: >= 7 → approval, < 7 → refine.
    """

    hook: int
    value: int
    voice: int
    cta: int
    length: int
    feedback: str
    average_score: float
    routes_to: str  # "human_approval" or "refine"
