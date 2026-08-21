from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str
    conversation_id: str | None = None


class Source(BaseModel):
    type: str
    id: str
    reranker_score: float | None = None
    blob_url: str | None = None


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    sources: list[Source]
