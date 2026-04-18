from tracelens.types import AnalysisResult


def render_analysis(result: AnalysisResult) -> str:
    sections = [result.conclusion]
    for item in result.key_evidence:
        sections.append(item.title)
        sections.append(item.summary)
    sections.extend(result.analysis_chain)
    sections.extend(result.optimization_directions)
    return "\n".join(sections)
