from backend.ops.schemas import CamelModel


class AskAgentContext(CamelModel):
    recommendation_id: str | None = None


class AskAgentIn(CamelModel):
    question: str
    context: AskAgentContext | None = None


class AskAgentOut(CamelModel):
    answer: str
    evidence: list[str]
