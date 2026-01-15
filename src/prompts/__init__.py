"""
AI prompt templates for DataReady.io

Contains structured prompts for:
- Question generation
- Follow-up decision making
- Response evaluation
- Report generation
"""

from src.prompts.interviewer import InterviewerPrompts
from src.prompts.evaluator import EvaluatorPrompts
from src.prompts.report import ReportPrompts

__all__ = [
    "InterviewerPrompts",
    "EvaluatorPrompts",
    "ReportPrompts",
]
