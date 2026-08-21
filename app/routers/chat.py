from fastapi import APIRouter, HTTPException, Request

from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


def _kb(request: Request):
    return request.app.state.kb


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request):
    try:
        return await _kb(request).chat(body.question, body.conversation_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
