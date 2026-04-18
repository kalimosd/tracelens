from dataclasses import dataclass

from tracelens.types import AnalysisResult


@dataclass(slots=True)
class AnalysisSession:
    session_id: str
    result: AnalysisResult
