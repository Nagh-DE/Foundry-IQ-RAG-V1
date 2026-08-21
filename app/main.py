from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers.chat import router as chat_router
from app.services.kb import KBService


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.kb = KBService(get_settings())
    yield
    # no cleanup needed for stateless Azure SDK clients


app = FastAPI(
    title="Health & Banking RAG API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)


@app.get("/health", tags=["ops"])
async def health():
    settings = get_settings()
    return {"status": "ok", "kb": settings.kb_name, "model": settings.llm_model_name}
