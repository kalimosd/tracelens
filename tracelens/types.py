from pydantic import BaseModel


class EvidenceItem(BaseModel):
    title: str
    summary: str


class AnalysisResult(BaseModel):
    conclusion: str
    key_evidence: list[EvidenceItem]
    analysis_chain: list[str]
    optimization_directions: list[str]
    uncertainties: list[str]
