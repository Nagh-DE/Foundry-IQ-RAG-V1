import asyncio
import uuid
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.search.documents.knowledgebases import KnowledgeBaseRetrievalClient
from azure.search.documents.knowledgebases.models import (
    KnowledgeBaseMessage,
    KnowledgeBaseMessageTextContent,
    KnowledgeBaseRetrievalRequest,
    KnowledgeRetrievalMinimalReasoningEffort,
    KnowledgeRetrievalSemanticIntent,
)

from app.config import Settings
from app.schemas import ChatResponse, Source

_SYSTEM_PROMPT = (
    "You are a financial and health economics research assistant. "
    "Answer ONLY using the provided documents. "
    "Cite the source table or document name when referencing data. "
    "If the answer is not in the documents, say: 'I don't know.'"
)


def _parse_sources(references: list[Any]) -> list[Source]:
    sources = []
    for ref in references or []:
        sources.append(
            Source(
                type=getattr(ref, "type", "unknown"),
                id=str(getattr(ref, "id", "")),
                reranker_score=getattr(ref, "reranker_score", None),
                blob_url=getattr(ref, "blob_url", None),
            )
        )
    return sources


class KBService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        credential = AzureKeyCredential(settings.search_service_api_key)
        self._retrieval_client = KnowledgeBaseRetrievalClient(
            endpoint=settings.search_service_url,
            credential=credential,
            knowledge_base_name=settings.kb_name,
        )
        project_client = AIProjectClient(
            endpoint=settings.foundry_project_endpoint,
            credential=DefaultAzureCredential(),
        )
        self._openai_client = project_client.get_openai_client()
        self._histories: dict[str, list[KnowledgeBaseMessage]] = {}

    def _retrieve(self, question: str, history: list[KnowledgeBaseMessage]):
        messages = list(history) + [
            KnowledgeBaseMessage(
                role="user",
                content=[KnowledgeBaseMessageTextContent(text=question)],
            )
        ]
        return self._retrieval_client.retrieve(
            KnowledgeBaseRetrievalRequest(
                intents=[KnowledgeRetrievalSemanticIntent(search=question)],
                retrieval_reasoning_effort=KnowledgeRetrievalMinimalReasoningEffort(),
                output_mode="extractiveData",
                max_output_documents=self._settings.max_output_documents,
            )
        )

    def _synthesize(self, question: str, context: str) -> str:
        response = self._openai_client.chat.completions.create(
            model=self._settings.llm_model_name,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Documents:\n\n{context}\n\nQuestion: {question}"},
            ],
        )
        return response.choices[0].message.content

    async def chat(self, question: str, conversation_id: str | None) -> ChatResponse:
        conv_id = conversation_id or str(uuid.uuid4())
        history = self._histories.setdefault(conv_id, [])

        retrieval_response = await asyncio.to_thread(self._retrieve, question, history)

        chunks = [
            block.text
            for msg in retrieval_response.response
            for block in msg.content
            if getattr(block, "text", None)
        ]
        context = "\n\n---\n\n".join(chunks) if chunks else "No relevant documents found."

        answer = await asyncio.to_thread(self._synthesize, question, context)

        history.append(
            KnowledgeBaseMessage(role="user", content=[KnowledgeBaseMessageTextContent(text=question)])
        )
        history.append(
            KnowledgeBaseMessage(role="assistant", content=[KnowledgeBaseMessageTextContent(text=answer)])
        )

        return ChatResponse(
            answer=answer,
            conversation_id=conv_id,
            sources=_parse_sources(retrieval_response.references),
        )

